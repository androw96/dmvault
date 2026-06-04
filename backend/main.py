from __future__ import annotations

import base64
from datetime import datetime
from datetime import timedelta
import hmac
import hashlib
import json
import logging
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from .database import BASE_DIR, SessionLocal
from .image_service import ensure_card_image
from .models import AdminAuditLog, Card, ContactMessage, Deck, DeckItem, DeckLike, DeckRevision, EmailVerificationToken, Notification, PasswordResetToken, PlayMatch, Profile, ProfileFollow
from .pdf_service import build_deck_pdf
from .rules_engine import build_creature_coverage, build_rules_coverage, build_spell_coverage
from .schemas import (
    AdminBanIn,
    AdminEmailIn,
    AdminMonthDeckOut,
    AdminMonthDetailsOut,
    AdminMonthProfileOut,
    AdminNotificationIn,
    AdminOverviewOut,
    AdminTwoFactorVerifyIn,
    AdminVerifyIn,
    AuthLoginIn,
    AuthRegisterIn,
    AuthResponse,
    CardListResponse,
    ContactMessageIn,
    ContactMessageOut,
    CardOut,
    DeckCardOut,
    DeckCreateIn,
    DeckCreateOut,
    DeckHistoryEntryOut,
    DeckHistoryResponse,
    DeckListResponse,
    DeckLikeToggleIn,
    DeckOut,
    DeckSummaryOut,
    FollowToggleIn,
    GenericMessageOut,
    MetadataResponse,
    MonthlyStatOut,
    NotificationListResponse,
    NotificationOut,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    PlaymodeActionIn,
    PlaymodeCardViewOut,
    PlaymodeMatchCreateIn,
    PlaymodeMatchJoinIn,
    PlaymodeMatchListOut,
    PlaymodeMatchSummaryOut,
    PlaymodeMatchUpdateIn,
    PlaymodeMatchViewOut,
    PlaymodePlayerViewOut,
    PlaymodeSpectateInviteIn,
    PlaymodeZoneViewOut,
    ProfileCreateIn,
    ProfileDeleteIn,
    ProfileDetailOut,
    ProfileDecksResponse,
    ProfileListResponse,
    ProfileOut,
    ProfileUpdateIn,
    VerificationResendIn,
)
from .seed import seed_cards_if_needed
from .utils import canonical_card_name, format_image_path, format_illustration_path, generate_public_id, slugify

FRONTEND_DIR = BASE_DIR.parent
logger = logging.getLogger(__name__)
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "2587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").strip() != "0"
EMAIL_VERIFICATION_TTL_HOURS = int(os.getenv("EMAIL_VERIFICATION_TTL_HOURS", "24"))
EMAIL_RESEND_COOLDOWN_SECONDS = int(os.getenv("EMAIL_RESEND_COOLDOWN_SECONDS", "60"))
PASSWORD_RESET_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "30"))
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "konyaandras96@gmail.com").strip().lower()
DEFAULT_ADMIN_USERNAME = slugify(os.getenv("DEFAULT_ADMIN_USERNAME", "paladins-vault-admin"))
DEFAULT_ADMIN_PASSWORD_ENV = os.getenv("DEFAULT_ADMIN_PASSWORD")
DEFAULT_ADMIN_PASSWORD = DEFAULT_ADMIN_PASSWORD_ENV or secrets.token_urlsafe(32)
ALLOW_DEFAULT_ADMIN_BOOTSTRAP = os.getenv("ALLOW_DEFAULT_ADMIN_BOOTSTRAP", "").strip().lower() in {"1", "true", "yes"}
RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}
RATE_LIMIT_MAX_BUCKETS = int(os.getenv("RATE_LIMIT_MAX_BUCKETS", "5000"))
RATE_LIMIT_PRUNE_INTERVAL_SECONDS = int(os.getenv("RATE_LIMIT_PRUNE_INTERVAL_SECONDS", "60"))
RATE_LIMIT_LAST_PRUNE = 0.0
ASSET_VERSION = "20260603avatarsave"
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 14)))
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", os.getenv("SECRET_KEY", DEFAULT_ADMIN_PASSWORD)).encode("utf-8")
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "pv_session")
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "pv_csrf")
ADMIN_2FA_TTL_SECONDS = int(os.getenv("ADMIN_2FA_TTL_SECONDS", "600"))
ADMIN_2FA_ENABLED = os.getenv("ADMIN_2FA_ENABLED", "1").strip() != "0"
ADMIN_2FA_CHALLENGES: dict[str, dict[str, int | str]] = {}
PDF_GENERATION_SEMAPHORE = threading.Semaphore(int(os.getenv("PDF_MAX_CONCURRENCY", "1")))
LAST_EMAIL_ERROR: str | None = None
RATE_LIMIT_RULES = {
    "register": (5, 900),
    "login": (10, 900),
    "admin_2fa": (8, 900),
    "resend_verification": (6, 900),
    "password_reset": (5, 900),
    "follow": (60, 300),
    "like": (90, 300),
    "create_deck": (180, 300),
    "admin_notify": (20, 300),
    "admin_ban": (30, 300),
}

app = FastAPI(title="Paladin's Vault")
app.add_middleware(GZipMiddleware, minimum_size=1024)


class CachedStaticFiles(StaticFiles):
    def file_response(self, full_path, stat_result, scope, status_code=200):
        response = super().file_response(full_path, stat_result, scope, status_code)
        path = scope.get("path", "")
        if any(path.endswith(ext) for ext in (".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".woff2")):
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response


app.mount("/assets", CachedStaticFiles(directory=FRONTEND_DIR), name="assets")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), browsing-topics=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data: https: blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self' https:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if request.url.scheme == "https" or "https" in forwarded_proto:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.on_event("startup")
def startup() -> None:
    seed_cards_if_needed()
    ensure_default_admin_account()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def profile_to_out(profile: Profile | None, *, include_email: bool = False, viewer_profile_id: int | None = None) -> ProfileOut | None:
    if not profile:
        return None
    return ProfileOut(
        id=profile.id,
        username=profile.username,
        display_name=profile.username,
        email=profile.email if include_email else None,
        email_verified=bool(profile.email_verified_at),
        is_admin=bool(profile.is_admin),
        is_banned=bool(profile.banned_at),
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        follower_count=len(profile.follower_links),
        following_count=len(profile.following_links),
        followed_by_viewer=bool(viewer_profile_id and any(link.follower_id == viewer_profile_id for link in profile.follower_links)),
    )


def playmode_deadline_label(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.strftime("%Y-%m-%d %H:%M UTC")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "*"
    else:
        masked_local = f"{local[:2]}{'*' * min(len(local) - 2, 6)}"
    return f"{masked_local}@{domain}"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${derived.hex()}"


def password_fingerprint(profile: Profile) -> str:
    return hashlib.sha256((profile.password_hash or "").encode("utf-8")).hexdigest()[:24]


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, digest = stored_hash.split("$", 1)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return secrets.compare_digest(derived.hex(), digest)


def is_email_verified(profile: Profile) -> bool:
    return bool(profile.email_verified_at)


def ensure_default_admin_account() -> None:
    with SessionLocal() as db:
        existing = db.scalar(select(Profile).where(Profile.email == DEFAULT_ADMIN_EMAIL))
        if existing:
            updated = False
            if not existing.is_admin:
                existing.is_admin = 1
                updated = True
            if not existing.email_verified_at:
                existing.email_verified_at = datetime.utcnow()
                updated = True
            if updated:
                db.commit()
            return
        if not DEFAULT_ADMIN_PASSWORD_ENV and not ALLOW_DEFAULT_ADMIN_BOOTSTRAP:
            logger.warning(
                "Skipping default admin bootstrap because DEFAULT_ADMIN_PASSWORD is not configured."
            )
            return
        username = DEFAULT_ADMIN_USERNAME
        collision = db.scalar(select(Profile).where(Profile.username == username))
        if collision:
            username = slugify(f"{DEFAULT_ADMIN_USERNAME}-{secrets.token_hex(2)}")
        admin = Profile(
            email=DEFAULT_ADMIN_EMAIL,
            username=username,
            display_name=username,
            password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            email_verified_at=datetime.utcnow(),
            is_admin=1,
        )
        db.add(admin)
        db.commit()


def create_auth_token(profile: Profile) -> str:
    expires_at = int(time.time()) + AUTH_TOKEN_TTL_SECONDS
    nonce = secrets.token_urlsafe(12)
    payload = f"{profile.id}:{expires_at}:{nonce}:{password_fingerprint(profile)}"
    signature = hmac.new(AUTH_SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}:{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(token).decode("ascii")


def create_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def request_is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or "https" in forwarded_proto


def set_auth_cookies(response: Response, request: Request, auth_token: str, csrf_token: str) -> None:
    secure = request_is_https(request)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        auth_token,
        max_age=AUTH_TOKEN_TTL_SECONDS,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=AUTH_TOKEN_TTL_SECONDS,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response, request: Request) -> None:
    secure = request_is_https(request)
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", secure=secure, httponly=False, samesite="lax")


def profile_id_from_auth_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        profile_id, expires_at, nonce, fingerprint, signature = decoded.split(":", 4)
    except Exception:
        return None
    payload = f"{profile_id}:{expires_at}:{nonce}:{fingerprint}"
    expected = hmac.new(AUTH_SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    if int(expires_at) < int(time.time()):
        return None
    return int(profile_id) if profile_id.isdigit() else None


def auth_token_password_fingerprint(token: str | None) -> str | None:
    if not token:
        return None
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        _profile_id, _expires_at, _nonce, fingerprint, _signature = decoded.split(":", 4)
    except Exception:
        return None
    return fingerprint


def auth_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    if not cookie_token:
        return None
    if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        header_csrf = request.headers.get("x-csrf-token", "")
        cookie_csrf = request.cookies.get(CSRF_COOKIE_NAME, "")
        if not header_csrf or not cookie_csrf or not hmac.compare_digest(header_csrf, cookie_csrf):
            return None
    return cookie_token


def require_authenticated_profile(profile_id: int, request: Request, db: Session) -> Profile:
    token = auth_bearer_token(request)
    token_profile_id = profile_id_from_auth_token(token)
    if token_profile_id != profile_id:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    if profile.banned_at:
        raise HTTPException(status_code=403, detail="This account is banned.")
    token_fingerprint = auth_token_password_fingerprint(token)
    if not token_fingerprint or not hmac.compare_digest(token_fingerprint, password_fingerprint(profile)):
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    return profile


def optional_authenticated_profile(request: Request, db: Session) -> Profile | None:
    token = auth_bearer_token(request)
    token_profile_id = profile_id_from_auth_token(token)
    if not token_profile_id:
        return None
    profile = db.get(Profile, token_profile_id)
    if not profile or profile.banned_at:
        return None
    token_fingerprint = auth_token_password_fingerprint(token)
    if not token_fingerprint or not hmac.compare_digest(token_fingerprint, password_fingerprint(profile)):
        return None
    return profile


def authenticated_viewer_id(request: Request, db: Session) -> int | None:
    profile = optional_authenticated_profile(request, db)
    return profile.id if profile else None


def require_admin(profile_id: int, db: Session, request: Request | None = None) -> Profile:
    if request is not None:
        profile = require_authenticated_profile(profile_id, request, db)
    else:
        profile = db.get(Profile, profile_id)
    if not profile or not profile.is_admin:
        raise HTTPException(status_code=403, detail="Admin access is required.")
    if profile.banned_at:
        raise HTTPException(status_code=403, detail="This admin account is banned.")
    return profile


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def prune_rate_limit_buckets(now: float) -> None:
    global RATE_LIMIT_LAST_PRUNE
    if now - RATE_LIMIT_LAST_PRUNE < RATE_LIMIT_PRUNE_INTERVAL_SECONDS:
        return

    RATE_LIMIT_LAST_PRUNE = now
    oldest_window = max(window for _, window in RATE_LIMIT_RULES.values())
    cutoff = now - oldest_window
    empty_keys = []
    for key, bucket in RATE_LIMIT_BUCKETS.items():
        bucket[:] = [stamp for stamp in bucket if stamp >= cutoff]
        if not bucket:
            empty_keys.append(key)
    for key in empty_keys:
        RATE_LIMIT_BUCKETS.pop(key, None)

    if len(RATE_LIMIT_BUCKETS) <= RATE_LIMIT_MAX_BUCKETS:
        return
    oldest_keys = sorted(
        RATE_LIMIT_BUCKETS,
        key=lambda key: RATE_LIMIT_BUCKETS[key][-1] if RATE_LIMIT_BUCKETS[key] else 0,
    )
    for key in oldest_keys[:len(RATE_LIMIT_BUCKETS) - RATE_LIMIT_MAX_BUCKETS]:
        RATE_LIMIT_BUCKETS.pop(key, None)


def enforce_rate_limit(name: str, request: Request, *, extra_key: str = "") -> None:
    limit, window_seconds = RATE_LIMIT_RULES[name]
    key = f"{name}:{client_ip(request)}:{extra_key}"
    now = time.time()
    prune_rate_limit_buckets(now)
    bucket = RATE_LIMIT_BUCKETS.setdefault(key, [])
    cutoff = now - window_seconds
    bucket[:] = [stamp for stamp in bucket if stamp >= cutoff]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please wait and try again.")
    bucket.append(now)


def create_admin_audit(db: Session, admin_id: int, action: str, *, target_profile_id: int | None = None, detail: str | None = None) -> None:
    db.add(
        AdminAuditLog(
            admin_profile_id=admin_id,
            target_profile_id=target_profile_id,
            action=action,
            detail=detail,
            created_at=datetime.utcnow(),
        )
    )


def monthly_counts(values: list[datetime], months: int = 12) -> list[dict[str, int | str]]:
    buckets: list[dict[str, int | str]] = []
    now = datetime.utcnow()
    year = now.year
    month = now.month
    for _ in range(months):
        label = f"{year:04d}-{month:02d}"
        buckets.append({"label": label, "count": 0})
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    bucket_map = {item["label"]: item for item in buckets}
    for value in values:
        label = value.strftime("%Y-%m")
        if label in bucket_map:
            bucket_map[label]["count"] = int(bucket_map[label]["count"]) + 1
    return list(reversed(buckets))


def verification_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def resend_configured() -> bool:
    return bool(RESEND_API_KEY and SMTP_FROM_EMAIL)


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM_EMAIL and SMTP_PASSWORD)


def email_delivery_configured() -> bool:
    return resend_configured() or smtp_configured()


def local_verification_fallback_enabled() -> bool:
    return not email_delivery_configured()


def record_email_error(detail: str | None) -> None:
    global LAST_EMAIL_ERROR
    LAST_EMAIL_ERROR = detail.strip() if detail else None


def clear_email_error() -> None:
    global LAST_EMAIL_ERROR
    LAST_EMAIL_ERROR = None


def build_verification_link(raw_token: str) -> str:
    return f"{APP_BASE_URL}/api/auth/verify-email?token={raw_token}"


def build_password_reset_link(raw_token: str) -> str:
    return f"{APP_BASE_URL}/profile?reset_token={raw_token}"


def build_email_shell(*, eyebrow: str, title: str, intro: str, body_html: str, footer_html: str = "") -> str:
    return f"""
    <html>
      <body style="margin:0;padding:0;background:#070b14;color:#f5faff;font-family:Arial,sans-serif;">
        <div style="max-width:640px;margin:0 auto;padding:32px 18px;">
          <div style="background:linear-gradient(160deg,#0f1728 0%,#101a30 45%,#12233f 100%);border:1px solid rgba(118,227,255,0.18);border-radius:28px;padding:32px 28px;box-shadow:0 22px 60px rgba(6,12,30,0.45);">
            <div style="text-align:center;margin-bottom:22px;">
              <img src="{APP_BASE_URL}/assets/assets/crystal-vault-logo.png?v=20260505w" alt="Paladin's Vault" style="width:92px;height:auto;display:block;margin:0 auto 12px;">
              <div style="letter-spacing:0.22em;text-transform:uppercase;font-size:11px;color:#7eddf6;">{eyebrow}</div>
              <h1 style="margin:10px 0 8px;font-size:30px;line-height:1.15;color:#ffffff;font-family:'Georgia',serif;">{title}</h1>
              <p style="margin:0 auto;max-width:480px;font-size:15px;line-height:1.7;color:#c7d7f6;">{intro}</p>
            </div>
            <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(126,221,246,0.14);border-radius:20px;padding:22px 20px;">
              {body_html}
            </div>
            <div style="margin-top:18px;font-size:12px;line-height:1.7;color:#8ea3c7;">
              {footer_html}
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def build_verification_message(profile: Profile, raw_token: str) -> EmailMessage:
    verify_url = build_verification_link(raw_token)
    message = EmailMessage()
    message["Subject"] = "Verify your Paladin's Vault account"
    message["From"] = f"Paladin's Vault <{SMTP_FROM_EMAIL}>"
    message["To"] = profile.email
    message.set_content(
        f"""Hello {profile.username},

Welcome to Paladin's Vault.

Please verify your email address by opening the link below:
{verify_url}

This verification link expires in {EMAIL_VERIFICATION_TTL_HOURS} hours.

If you did not create this account, you can safely ignore this email.
"""
    )
    body_html = f"""
      <p style="margin:0 0 14px;font-size:15px;line-height:1.75;color:#d7e5ff;">Hello <strong>{profile.username}</strong>,</p>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.75;color:#d7e5ff;">Welcome to Paladin's Vault. Click the button below to verify your email and unlock secure login.</p>
      <div style="text-align:center;margin:24px 0 20px;">
        <a href="{verify_url}" style="display:inline-block;padding:14px 22px;border-radius:14px;background:linear-gradient(135deg,#7ce7ff,#9fcbff);color:#081018;text-decoration:none;font-weight:800;letter-spacing:0.04em;">Verify Email</a>
      </div>
      <p style="margin:0 0 12px;font-size:14px;line-height:1.7;color:#c7d7f6;word-break:break-all;">Or open this link directly:<br><a href="{verify_url}" style="color:#8fe7ff;">{verify_url}</a></p>
      <p style="margin:0;font-size:13px;line-height:1.7;color:#9fb2d5;">This verification link expires in <strong>{EMAIL_VERIFICATION_TTL_HOURS} hours</strong>.</p>
    """
    footer_html = "If you did not create this account, you can safely ignore this email."
    message.add_alternative(build_email_shell(eyebrow="Account Security", title="Verify your email", intro="Complete your Paladin's Vault registration with one secure click.", body_html=body_html, footer_html=footer_html), subtype="html")
    return message


def build_password_reset_message(profile: Profile, raw_token: str) -> EmailMessage:
    reset_url = build_password_reset_link(raw_token)
    message = EmailMessage()
    message["Subject"] = "Reset your Paladin's Vault password"
    message["From"] = f"Paladin's Vault <{SMTP_FROM_EMAIL}>"
    message["To"] = profile.email
    message.set_content(
        f"""Hello {profile.username},

We received a request to reset your Paladin's Vault password.

Reset your password:
{reset_url}

This link expires in {PASSWORD_RESET_TTL_MINUTES} minutes. If you did not request this, you can safely ignore this email.
"""
    )
    body_html = f"""
      <p style="margin:0 0 14px;font-size:15px;line-height:1.75;color:#d7e5ff;">Hello <strong>{profile.username}</strong>,</p>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.75;color:#d7e5ff;">We received a request to reset your Paladin's Vault password.</p>
      <div style="text-align:center;margin:24px 0 20px;">
        <a href="{reset_url}" style="display:inline-block;padding:14px 22px;border-radius:14px;background:linear-gradient(135deg,#7ce7ff,#9fcbff);color:#081018;text-decoration:none;font-weight:800;letter-spacing:0.04em;">Reset Password</a>
      </div>
      <p style="margin:0 0 12px;font-size:14px;line-height:1.7;color:#c7d7f6;word-break:break-all;">Or open this link directly:<br><a href="{reset_url}" style="color:#8fe7ff;">{reset_url}</a></p>
      <p style="margin:0;font-size:13px;line-height:1.7;color:#9fb2d5;">This link expires in <strong>{PASSWORD_RESET_TTL_MINUTES} minutes</strong>. Changing your password invalidates old sessions.</p>
    """
    footer_html = "If you did not request this password reset, you can safely ignore this email."
    message.add_alternative(
        build_email_shell(
            eyebrow="Account Security",
            title="Reset your password",
            intro="Use this secure link to choose a new password.",
            body_html=body_html,
            footer_html=footer_html,
        ),
        subtype="html",
    )
    return message


def build_deck_like_message(owner: Profile, liking_profile: Profile, deck: Deck) -> EmailMessage:
    deck_url = f"{APP_BASE_URL}/share/{deck.public_id}"
    message = EmailMessage()
    message["Subject"] = "Your deck was liked on Paladin's Vault"
    message["From"] = f"Paladin's Vault <{SMTP_FROM_EMAIL}>"
    message["To"] = owner.email
    message.set_content(
        f"""Hello {owner.username},

{liking_profile.username} liked your deck "{deck.title}" on Paladin's Vault.

Open the deck:
{deck_url}
"""
    )
    body_html = f"""
      <p style="margin:0 0 14px;font-size:15px;line-height:1.75;color:#d7e5ff;">Hello <strong>{owner.username}</strong>,</p>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.75;color:#d7e5ff;"><strong>{liking_profile.username}</strong> just crystal liked your deck <strong>{deck.title}</strong>.</p>
      <div style="text-align:center;margin:24px 0 20px;">
        <a href="{deck_url}" style="display:inline-block;padding:14px 22px;border-radius:14px;background:linear-gradient(135deg,#7ce7ff,#9fcbff);color:#081018;text-decoration:none;font-weight:800;letter-spacing:0.04em;">Open Deck</a>
      </div>
    """
    message.add_alternative(build_email_shell(eyebrow="Deck Activity", title="Your deck got a new like", intro="Your shared Duel Masters lists are getting noticed.", body_html=body_html, footer_html="You are receiving this because notifications for deck activity are enabled through your Paladin's Vault account."), subtype="html")
    return message


def build_admin_email_message(*, recipient_email: str, recipient_name: str, subject: str, body_message: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Paladin's Vault <{SMTP_FROM_EMAIL}>"
    message["To"] = recipient_email
    message.set_content(
        f"""Hello {recipient_name},

{body_message}

This message was sent from the Paladin's Vault admin dashboard.
"""
    )
    html_body = f"""\
<html>
  <body style="margin:0;padding:0;background:#07111b;color:#ecf8ff;font-family:Arial,sans-serif;">
    <div style="max-width:640px;margin:0 auto;padding:32px 20px;">
      <div style="padding:24px;border-radius:24px;background:linear-gradient(180deg,#0c1724,#09111d);border:1px solid rgba(167,220,255,.18);">
        <div style="text-align:center;margin:0 0 16px;">
          <img src="{APP_BASE_URL}/assets/assets/crystal-vault-logo.png?v=20260505w" alt="Paladin's Vault" style="width:84px;height:auto;display:block;margin:0 auto 10px;">
        </div>
        <p style="margin:0 0 12px;color:#86dfff;font-size:12px;letter-spacing:.14em;text-transform:uppercase;">Paladin's Vault Admin</p>
        <h1 style="margin:0 0 18px;font-size:28px;line-height:1.15;color:#f5fcff;">{subject}</h1>
        <p style="margin:0 0 18px;color:#d7ecff;line-height:1.75;">Hello {recipient_name},</p>
        <div style="margin:0 0 18px;color:#d7ecff;line-height:1.8;white-space:pre-line;">{body_message}</div>
        <p style="margin:24px 0 0;color:#9fc4df;font-size:14px;line-height:1.7;">This message was sent from the Paladin's Vault admin dashboard.</p>
      </div>
    </div>
  </body>
</html>
"""
    message.add_alternative(html_body, subtype="html")
    return message


def build_admin_2fa_message(profile: Profile, code: str) -> EmailMessage:
    subject = "Your Paladin's Vault admin security code"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Paladin's Vault <{SMTP_FROM_EMAIL}>"
    message["To"] = profile.email
    message.set_content(
        f"""Hello {profile.username},

Your Paladin's Vault admin login code is:

{code}

This code expires in {ADMIN_2FA_TTL_SECONDS // 60} minutes.
If this was not you, change your password immediately.
"""
    )
    body_html = f"""
      <p style="margin:0 0 14px;font-size:15px;line-height:1.75;color:#d7e5ff;">Hello <strong>{profile.username}</strong>,</p>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.75;color:#d7e5ff;">Use this one-time code to finish your admin login:</p>
      <div style="text-align:center;margin:24px 0;">
        <span style="display:inline-block;padding:16px 24px;border-radius:16px;background:#dff8ff;color:#07111b;font-size:30px;font-weight:900;letter-spacing:.22em;">{code}</span>
      </div>
      <p style="margin:0;font-size:13px;line-height:1.7;color:#9fb2d5;">This code expires in <strong>{ADMIN_2FA_TTL_SECONDS // 60} minutes</strong>. If this was not you, change your password immediately.</p>
    """
    message.add_alternative(
        build_email_shell(
            eyebrow="Admin Security",
            title="Confirm your admin login",
            intro="A second security check is required before opening the admin dashboard.",
            body_html=body_html,
            footer_html="This extra check protects Paladin's Vault admin tools and user data.",
        ),
        subtype="html",
    )
    return message


def prune_admin_2fa_challenges() -> None:
    now = int(time.time())
    expired = [challenge_id for challenge_id, challenge in ADMIN_2FA_CHALLENGES.items() if int(challenge.get("expires_at", 0)) < now]
    for challenge_id in expired:
        ADMIN_2FA_CHALLENGES.pop(challenge_id, None)


def issue_admin_2fa_challenge(profile: Profile, request: Request, db: Session) -> str:
    if not profile.email:
        raise HTTPException(status_code=400, detail="Admin account needs an email address for 2FA.")
    if not email_delivery_configured():
        raise HTTPException(status_code=503, detail="Admin 2FA email delivery is not configured.")
    prune_admin_2fa_challenges()
    challenge_id = secrets.token_urlsafe(24)
    code = f"{secrets.randbelow(1_000_000):06d}"
    ADMIN_2FA_CHALLENGES[challenge_id] = {
        "profile_id": profile.id,
        "code_hash": verification_token_hash(code),
        "expires_at": int(time.time()) + ADMIN_2FA_TTL_SECONDS,
        "attempts": 0,
    }
    send_email_message(build_admin_2fa_message(profile, code))
    create_admin_audit(db, profile.id, "admin_2fa_sent", detail=f"ip={client_ip(request)}")
    db.commit()
    return challenge_id


def build_playmode_turn_message(*, recipient: Profile, actor: Profile, match: PlayMatch, move_summary: str | None = None) -> EmailMessage:
    match_url = f"{APP_BASE_URL}/playmode?match={match.public_id}"
    subject = "Your async Playmode match is ready for your turn"
    summary_html = f"<p style=\"margin:0 0 16px;color:#d7ecff;line-height:1.8;\">Last move: <strong>{move_summary}</strong></p>" if move_summary else ""
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Paladin's Vault <{SMTP_FROM_EMAIL}>"
    message["To"] = recipient.email
    message.set_content(
        f"""Hello {recipient.username},

{actor.username} has finished a move in your async Playmode match on Paladin's Vault.
{f"Last move: {move_summary}\n" if move_summary else ""}
Open the match:
{match_url}

You now have 24 hours to respond.
"""
    )
    body_html = f"""
      <p style="margin:0 0 14px;font-size:15px;line-height:1.75;color:#d7e5ff;">Hello <strong>{recipient.username}</strong>,</p>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.75;color:#d7e5ff;"><strong>{actor.username}</strong> has finished a move in your async Playmode match.</p>
      {summary_html}
      <div style="text-align:center;margin:24px 0 20px;">
        <a href="{match_url}" style="display:inline-block;padding:14px 22px;border-radius:14px;background:linear-gradient(135deg,#7ce7ff,#9fcbff);color:#081018;text-decoration:none;font-weight:800;letter-spacing:0.04em;">Open Match</a>
      </div>
      <p style="margin:0;font-size:13px;line-height:1.7;color:#9fb2d5;">You now have <strong>24 hours</strong> to respond in this async game.</p>
    """
    footer_html = "You are receiving this because you are seated in an async Paladin's Vault Playmode match."
    message.add_alternative(
        build_email_shell(
            eyebrow="Async Playmode",
            title="It is your turn",
            intro="A new async move is waiting for you.",
            body_html=body_html,
            footer_html=footer_html,
        ),
        subtype="html",
    )
    return message


def send_via_resend_api(message: EmailMessage) -> None:
    text_part = message.get_body(preferencelist=("plain",))
    html_part = message.get_body(preferencelist=("html",))
    payload = {
        "from": message.get("From"),
        "to": [message.get("To")],
        "subject": message.get("Subject"),
        "text": text_part.get_content() if text_part else None,
        "html": html_part.get_content() if html_part else None,
    }
    body = json.dumps(payload).encode("utf-8")
    request = UrlRequest(
        "https://api.resend.com/emails",
        data=body,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "PaladinsVault/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            response.read()
            clear_email_error()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        message_detail = f"Resend API error: {exc.code} {detail}"
        record_email_error(message_detail)
        raise RuntimeError(message_detail) from exc
    except URLError as exc:
        message_detail = f"Resend API connection error: {exc}"
        record_email_error(message_detail)
        raise RuntimeError(message_detail) from exc


def send_email_message(message: EmailMessage) -> None:
    if resend_configured():
        send_via_resend_api(message)
        return
    if not smtp_configured():
        record_email_error("Email delivery is not configured.")
        raise RuntimeError("Email delivery is not configured.")
    try:
        if SMTP_USE_TLS:
            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
                server.starttls(context=context)
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20, context=ssl.create_default_context()) as server:
                if SMTP_USERNAME:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(message)
        clear_email_error()
    except Exception as exc:
        record_email_error(str(exc))
        raise


def issue_verification_token(profile: Profile, db: Session) -> str:
    now = datetime.utcnow()
    for existing in profile.verification_tokens:
        if existing.used_at is None:
            db.delete(existing)
    raw_token = secrets.token_urlsafe(32)
    db.add(
        EmailVerificationToken(
            profile_id=profile.id,
            token_hash=verification_token_hash(raw_token),
            expires_at=now + timedelta(hours=EMAIL_VERIFICATION_TTL_HOURS),
            created_at=now,
        )
    )
    profile.verification_sent_at = now
    return raw_token


def issue_password_reset_token(profile: Profile, db: Session) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            profile_id=profile.id,
            token_hash=verification_token_hash(raw_token),
            expires_at=datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
            created_at=datetime.utcnow(),
        )
    )
    profile.verification_sent_at = datetime.utcnow()
    return raw_token


def enforce_password_policy(password: str) -> None:
    if len(password) < 10:
        raise HTTPException(status_code=400, detail="Password must be at least 10 characters long.")
    if not any(char.islower() for char in password):
        raise HTTPException(status_code=400, detail="Password must include a lowercase letter.")
    if not any(char.isupper() for char in password):
        raise HTTPException(status_code=400, detail="Password must include an uppercase letter.")
    if not any(char.isdigit() for char in password):
        raise HTTPException(status_code=400, detail="Password must include a number.")


def card_to_out(card: Card) -> CardOut:
    display_name = canonical_card_name(card.name)
    return CardOut(
        id=card.id,
        slug=card.slug,
        name=display_name,
        civilizations=card.civilizations.split("|"),
        cost=card.cost,
        type=card.type,
        race_label=card.race_label,
        text=card.text,
        power=card.power,
        rarity=card.rarity,
        set_name=card.set_name,
        collector_number=card.collector_number,
        illustrator=card.illustrator,
        flavor=card.flavor,
        image_path=format_image_path(card.id),
        illustration_path=format_illustration_path(display_name),
    )


def deck_to_out(deck: Deck, *, viewer_profile_id: int | None = None) -> DeckOut:
    return DeckOut(
        public_id=deck.public_id,
        title=deck.title,
        visibility=deck.visibility,
        cover_image_url=deck.cover_image_url,
        owner=profile_to_out(deck.profile, viewer_profile_id=viewer_profile_id),
        cards=[DeckCardOut(card=card_to_out(item.card), quantity=item.quantity) for item in deck.items],
        share_url=f"/share/{deck.public_id}",
        pdf_url=f"/api/decks/{deck.public_id}/pdf",
        like_count=len(deck.likes),
        liked_by_viewer=bool(viewer_profile_id and any(like.profile_id == viewer_profile_id for like in deck.likes)),
        liked_by=[profile_to_out(like.profile, viewer_profile_id=viewer_profile_id) for like in deck.likes if like.profile],
    )


def deck_summary_out(
    deck: Deck,
    owner: Profile | None = None,
    *,
    include_owner_email: bool = False,
    viewer_profile_id: int | None = None,
) -> DeckSummaryOut:
    civilizations = sorted({
        civilization
        for item in deck.items
        for civilization in item.card.civilizations.split("|")
        if civilization
    })
    card_names = sorted({item.card.name for item in deck.items})
    owner_profile = owner or deck.profile
    liked_by_profiles = [like.profile for like in deck.likes if like.profile]
    return DeckSummaryOut(
        public_id=deck.public_id,
        title=deck.title,
        visibility=deck.visibility,
        cover_image_url=deck.cover_image_url,
        civilizations=civilizations,
        card_names=card_names,
        card_total=sum(entry.quantity for entry in deck.items),
        updated_at_label=deck.updated_at.strftime("%Y-%m-%d"),
        updated_at=deck.updated_at.isoformat() if deck.updated_at else None,
        created_at=deck.created_at.isoformat() if deck.created_at else None,
        owner=profile_to_out(owner_profile, include_email=include_owner_email, viewer_profile_id=viewer_profile_id),
        share_url=f"/share/{deck.public_id}",
        like_count=len(deck.likes),
        liked_by_viewer=bool(viewer_profile_id and any(like.profile_id == viewer_profile_id for like in deck.likes)),
        liked_by=[profile_to_out(profile, viewer_profile_id=viewer_profile_id) for profile in liked_by_profiles if profile],
    )


PROFILE_DETAIL_LOAD_OPTIONS = (
    selectinload(Profile.decks).selectinload(Deck.items).selectinload(DeckItem.card),
    selectinload(Profile.decks).selectinload(Deck.likes).selectinload(DeckLike.profile),
    selectinload(Profile.following_links).selectinload(ProfileFollow.followed),
    selectinload(Profile.follower_links),
    selectinload(Profile.deck_likes).selectinload(DeckLike.deck).selectinload(Deck.items).selectinload(DeckItem.card),
    selectinload(Profile.deck_likes).selectinload(DeckLike.deck).selectinload(Deck.likes).selectinload(DeckLike.profile),
    selectinload(Profile.deck_likes).selectinload(DeckLike.deck).selectinload(Deck.profile),
)


def notification_to_out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        type=notification.type,
        message=notification.message,
        created_at_label=notification.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        actor=profile_to_out(notification.actor, viewer_profile_id=notification.profile_id) if notification.actor else None,
        deck_public_id=notification.deck.public_id if notification.deck else None,
        deck_title=notification.deck.title if notification.deck else None,
        read=bool(notification.read_at),
    )


def playmode_serialize_card(card: Card) -> dict:
    display_name = canonical_card_name(card.name)
    return {
        "id": card.id,
        "name": display_name,
        "civilizations": [value for value in (card.civilizations or "").split("|") if value],
        "cost": card.cost,
        "type": card.type,
        "race_label": card.race_label or "",
        "text": card.text or "",
        "power": card.power,
        "image_path": format_image_path(card.id),
    }


PLAYMODE_STATE_SEATS = ("player_one", "player_two")
PLAYMODE_STATE_ZONES = ("drawPile", "hand", "shields", "mana", "battle", "graveyard")


def playmode_walk_entry_stack(entry: dict):
    yield entry
    for underlay in entry.get("underlays") or []:
        yield from playmode_walk_entry_stack(underlay)


def playmode_entry_card_id(entry: dict) -> int | None:
    raw_id = entry.get("card_id")
    if raw_id is None:
        raw_id = (entry.get("card") or {}).get("id")
    try:
        return int(raw_id) if raw_id is not None else None
    except (TypeError, ValueError):
        return None


def playmode_walk_entries(state_payload: dict):
    for seat_key in PLAYMODE_STATE_SEATS:
        player_state = state_payload.get(seat_key) or {}
        for zone_name in PLAYMODE_STATE_ZONES:
            for entry in player_state.get(zone_name) or []:
                yield from playmode_walk_entry_stack(entry)


def playmode_hydrate_state_cards(state_payload: dict, db: Session) -> None:
    card_ids = sorted({
        card_id
        for entry in playmode_walk_entries(state_payload)
        for card_id in [playmode_entry_card_id(entry)]
        if card_id is not None
    })
    if not card_ids:
        return
    cards = db.scalars(select(Card).where(Card.id.in_(card_ids))).all()
    card_lookup = {card.id: playmode_serialize_card(card) for card in cards}
    for entry in playmode_walk_entries(state_payload):
        card_id = playmode_entry_card_id(entry)
        if card_id is None:
            continue
        entry["card_id"] = card_id
        if card_id in card_lookup:
            entry["card"] = card_lookup[card_id]


def playmode_minimize_entry(entry: dict) -> None:
    card_id = playmode_entry_card_id(entry)
    if card_id is not None:
        entry["card_id"] = card_id
    entry.pop("card", None)
    for underlay in entry.get("underlays") or []:
        playmode_minimize_entry(underlay)


def playmode_minimize_state_cards(state_payload: dict) -> dict:
    for entry in playmode_walk_entries(state_payload):
        playmode_minimize_entry(entry)
    return state_payload


def playmode_dump_state(state_payload: dict) -> str:
    return json.dumps(playmode_minimize_state_cards(state_payload), separators=(",", ":"))


def playmode_invite_allows(payload: dict, profile_id: int | None, *, match: PlayMatch, admin_override: bool = False) -> bool:
    if admin_override:
        return True
    if not profile_id:
        return False
    if profile_id in {match.player_one_profile_id, match.player_two_profile_id}:
        return True
    invited_profile_id = payload.get("invited_profile_id")
    return bool(payload.get("private_invite") and invited_profile_id == profile_id)


def playmode_spectator_allows(payload: dict, profile: Profile | None, *, match: PlayMatch) -> bool:
    if not profile or match.status != "active":
        return False
    spectator_ids = {int(value) for value in payload.get("spectator_profile_ids", []) if str(value).isdigit()}
    if profile.id in spectator_ids:
        return True
    spectator_emails = {normalize_email(value) for value in payload.get("spectator_emails", []) if value}
    return bool(profile.email and normalize_email(profile.email) in spectator_emails)


def find_invited_profile(db: Session, value: str) -> Profile | None:
    raw = value.strip().lstrip("@")
    if not raw:
        return None
    normalized_email = normalize_email(raw)
    slug = slugify(raw)
    raw_lower = raw.lower()
    criteria = [
        Profile.username == slug,
        func.lower(Profile.username) == raw_lower,
        func.lower(Profile.display_name) == raw_lower,
    ]
    if "@" in raw:
        criteria.append(func.lower(Profile.email) == normalized_email)
    return db.scalars(select(Profile).where(or_(*criteria)).limit(1)).first()


def build_playmode_spectate_message(*, recipient_email: str, recipient_name: str, actor: Profile, match: PlayMatch) -> EmailMessage:
    match_url = f"{APP_BASE_URL}/playmode?match={match.public_id}"
    subject = "You were invited to spectate a Paladin's Vault match"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Paladin's Vault <{SMTP_FROM_EMAIL}>"
    message["To"] = recipient_email
    message.set_content(
        f"""Hello {recipient_name},

{actor.username} invited you to spectate a Duel Masters Playmode match on Paladin's Vault.

Open the match:
{match_url}
"""
    )
    body_html = f"""
      <p style="margin:0 0 14px;font-size:15px;line-height:1.75;color:#d7e5ff;">Hello <strong>{recipient_name}</strong>,</p>
      <p style="margin:0 0 16px;font-size:15px;line-height:1.75;color:#d7e5ff;"><strong>{actor.username}</strong> invited you to spectate a Duel Masters Playmode match.</p>
      <div style="text-align:center;margin:24px 0 20px;">
        <a href="{match_url}" style="display:inline-block;padding:14px 22px;border-radius:14px;background:linear-gradient(135deg,#7ce7ff,#9fcbff);color:#081018;text-decoration:none;font-weight:800;letter-spacing:0.04em;">Spectate Match</a>
      </div>
      <p style="margin:0;font-size:13px;line-height:1.7;color:#9fb2d5;">You can view this match only while it is active and only from the invited account/email.</p>
    """
    message.add_alternative(build_email_shell(eyebrow="Playmode Spectate", title=subject, intro="A live duel is waiting in the vault.", body_html=body_html, footer_html="You are receiving this because a Paladin's Vault player invited you to spectate."), subtype="html")
    return message


def build_playmode_stack_for_deck(deck: Deck) -> list[dict]:
    cards: list[dict] = []
    items = sorted(deck.items, key=lambda item: (item.card.cost, item.card.name, item.card.id))
    counter = 0
    for item in items:
        for _ in range(item.quantity):
            counter += 1
            cards.append({
                "uid": f"{item.card_id}-{counter}-{secrets.token_hex(2)}",
                "card_id": item.card_id,
                "tapped": False,
                "faceDown": False,
                "manaProduced": [],
                "underlays": [],
            })
    rng = secrets.SystemRandom()
    rng.shuffle(cards)
    return cards


def build_playmode_player_state(deck: Deck) -> dict:
    stack = build_playmode_stack_for_deck(deck)
    shields = [{**entry, "faceDown": True} for entry in stack[:5]]
    hand = [{**entry, "faceDown": False} for entry in stack[5:10]]
    draw_pile = stack[10:]
    return {
        "drawPile": draw_pile,
        "hand": hand,
        "shields": shields,
        "mana": [],
        "manaPool": [],
        "battle": [],
        "graveyard": [],
        "turn": 1,
        "ready": True,
        "chargedThisTurn": False,
    }


def build_playmode_match_state(deck_one: Deck, deck_two: Deck | None = None, *, starting_seat: int = 1) -> dict:
    active_seat = starting_seat if starting_seat in {1, 2} else 1
    return {
        "current_turn": 1,
        "active_seat": active_seat,
        "starting_seat": active_seat,
        "first_draw_skipped": False,
        "current_phase": "untap",
        "winner_seat": None,
        "event_log": [f"Match started. Player {active_seat} begins on Untap."],
        "player_one": build_playmode_player_state(deck_one),
        "player_two": build_playmode_player_state(deck_two) if deck_two else {
            "drawPile": [],
            "hand": [],
            "shields": [],
            "mana": [],
            "manaPool": [],
            "battle": [],
            "graveyard": [],
            "turn": 1,
            "ready": False,
        },
    }


def normalize_rule_text(value: str | None) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in (value or "")).split())


def playmode_seat_key(seat: int) -> str:
    return "player_two" if seat == 2 else "player_one"


def playmode_opponent_seat(seat: int) -> int:
    return 1 if seat == 2 else 2


def playmode_append_event(state_payload: dict, message: str | None) -> None:
    if not message:
        return
    active_seat = int(state_payload.get("active_seat") or 1)
    turn = int(state_payload.get("current_turn") or 1)
    phase = str(state_payload.get("current_phase") or "untap").title()
    entry = f"T{turn} • P{active_seat} • {phase}: {message}"
    event_log = list(state_payload.get("event_log") or [])
    event_log.append(entry)
    state_payload["event_log"] = event_log[-80:]


def playmode_append_events(state_payload: dict, messages: list[str]) -> None:
    for message in messages:
        playmode_append_event(state_payload, message)


def playmode_card_civilizations(card: dict) -> list[str]:
    return [value for value in (card.get("civilizations") or []) if value]


def playmode_has_keyword(card: dict, keyword: str) -> bool:
    haystack = f"{card.get('name', '')} {card.get('type', '')} {card.get('race_label', '')} {card.get('text', '')}".lower()
    return keyword.lower() in haystack


def playmode_is_spell(card: dict) -> bool:
    return "spell" in str(card.get("type") or "").lower()


def playmode_is_creature(card: dict) -> bool:
    return "creature" in str(card.get("type") or "").lower()


def playmode_is_light(card: dict) -> bool:
    return any(normalize_rule_text(value) == "light" for value in playmode_card_civilizations(card))


def playmode_is_evolution(card: dict) -> bool:
    return "evolution" in f"{card.get('type', '')} {card.get('text', '')}".lower()


def playmode_is_vortex(card: dict) -> bool:
    return "vortex evolution" in str(card.get("text") or "").lower()


def playmode_power_value(card: dict) -> int:
    match = re.search(r"\d+", str(card.get("power") or ""))
    return int(match.group(0)) if match else 0


def playmode_entry_power_value(entry: dict, *, attacking: bool = False) -> int:
    card = entry.get("card") or {}
    power = playmode_power_value(card) + int(entry.get("temporaryPower") or 0)
    if attacking:
        match = re.search(r"\bpower\s+attacker\s*\+(\d+)", str(card.get("text") or ""), re.I)
        if match:
            power += int(match.group(1))
    return power


def playmode_entry_has_slayer(entry: dict) -> bool:
    return bool(entry.get("temporarySlayer")) or playmode_has_keyword(entry.get("card") or {}, "slayer")


def playmode_can_attack_untapped(entry: dict) -> bool:
    card = entry.get("card") or {}
    return bool(entry.get("temporaryCanAttackUntapped")) or bool(re.search(r"\bcan attack untapped creatures\b", str(card.get("text") or ""), re.I))


def playmode_can_attack_players(entry: dict, defender_state: dict | None = None) -> bool:
    text = str((entry.get("card") or {}).get("text") or "")
    if re.search(r"\bcan(?:not|'t)\s+attack players\b", text, re.I):
        return False
    if re.search(r"\bwhile your opponent has no shields,\s*this creature can(?:not|'t)\s+attack\b", text, re.I) and not (defender_state or {}).get("shields"):
        return False
    return True


def playmode_can_be_attacked(entry: dict, attacker: dict | None = None) -> bool:
    text = str((entry.get("card") or {}).get("text") or "")
    if re.search(r"\bthis creature can(?:not|'t)\s+be attacked\b", text, re.I):
        return False
    if attacker and re.search(r"\bcan(?:not|'t)\s+be attacked by any creature that has dragon in its race\b", text, re.I):
        return "dragon" not in str(((attacker or {}).get("card") or {}).get("race_label") or "").lower()
    return True


def playmode_entry_unblockable(entry: dict, target_kind: str | None = None) -> bool:
    if entry.get("temporaryUnblockable"):
        return True
    text = str((entry.get("card") or {}).get("text") or "")
    if re.search(r"\bcan(?:not|'t)\s+be\s+blocked\b", text, re.I):
        return True
    if target_kind == "creature" and re.search(r"\bcan(?:not|'t)\s+be\s+blocked while attacking (?:a|another)?\s*creature\b", text, re.I):
        return True
    return False


def playmode_breaker_count(card: dict, entry: dict | None = None) -> int:
    text = str(card.get("text") or "").lower()
    temporary_breaker = int((entry or {}).get("temporaryBreaker") or 0)
    if "triple breaker" in text:
        return max(temporary_breaker, 3)
    if "double breaker" in text:
        return max(temporary_breaker, 2)
    return max(temporary_breaker, 1)


def playmode_clear_temporary_effects(player_state: dict) -> None:
    for entry in player_state.get("battle") or []:
        for key in ("temporaryPower", "temporaryBreaker", "temporaryUnblockable", "temporaryCanAttackUntapped", "temporarySlayer", "temporaryBlocker", "temporaryMustAttack", "temporaryAttackable", "temporaryUntapOnWin"):
            entry.pop(key, None)


def playmode_stack_entries(entry: dict) -> list[dict]:
    return [
        {**stack_entry, "underlays": [], "faceDown": False, "tapped": False, "manaProduced": []}
        for stack_entry in [entry, *(entry.get("underlays") or [])]
    ]


def playmode_draw_cards(player_state: dict, amount: int) -> int:
    drawn = 0
    for _ in range(max(0, amount)):
        draw_pile = player_state.get("drawPile") or []
        if not draw_pile:
            break
        card = draw_pile.pop(0)
        player_state.setdefault("hand", []).append({**card, "faceDown": False, "tapped": False})
        drawn += 1
    return drawn


def playmode_top_to_mana(player_state: dict, *, tapped: bool = False) -> dict | None:
    draw_pile = player_state.get("drawPile") or []
    if not draw_pile:
        return None
    card = draw_pile.pop(0)
    moved = {**card, "faceDown": False, "tapped": tapped or len(playmode_card_civilizations(card.get("card") or {})) > 1, "manaProduced": []}
    player_state.setdefault("mana", []).append(moved)
    return moved


def playmode_top_to_shield(player_state: dict) -> dict | None:
    draw_pile = player_state.get("drawPile") or []
    if not draw_pile:
        return None
    card = draw_pile.pop(0)
    moved = {**card, "faceDown": True, "tapped": False, "manaProduced": []}
    player_state.setdefault("shields", []).append(moved)
    return moved


def playmode_move_zone_entries(player_state: dict, source: str, target: str, *, amount: int | None = None, predicate=None, face_down: bool = False, tapped: bool = False) -> list[str]:
    moved_names: list[str] = []
    source_zone = player_state.get(source) or []
    kept: list[dict] = []
    moved_count = 0
    for entry in source_zone:
        if amount is not None and moved_count >= amount:
            kept.append(entry)
            continue
        card = entry.get("card") or {}
        if predicate and not predicate(card, entry):
            kept.append(entry)
            continue
        moved_count += 1
        moved_names.append(card.get("name") or "a card")
        for stack_entry in playmode_stack_entries(entry):
            player_state.setdefault(target, []).append({
                **stack_entry,
                "faceDown": face_down,
                "tapped": tapped or (target == "mana" and len(playmode_card_civilizations(stack_entry.get("card") or {})) > 1),
                "manaProduced": [],
            })
    player_state[source] = kept
    return moved_names


def playmode_move_top_cards(player_state: dict, target: str, amount: int, *, face_down: bool = False, tapped: bool = False) -> list[str]:
    moved_names: list[str] = []
    for _ in range(max(0, amount)):
        draw_pile = player_state.get("drawPile") or []
        if not draw_pile:
            break
        entry = draw_pile.pop(0)
        card = entry.get("card") or {}
        player_state.setdefault(target, []).append({
            **entry,
            "faceDown": face_down,
            "tapped": tapped or (target == "mana" and len(playmode_card_civilizations(card)) > 1),
            "manaProduced": [],
        })
        moved_names.append(card.get("name") or "a card")
    return moved_names


def playmode_apply_temporary_battle_effect(
    player_state: dict,
    *,
    amount: int | None = None,
    predicate=None,
    power: int = 0,
    breaker: int = 0,
    unblockable: bool = False,
    speed_attacker: bool = False,
    slayer: bool = False,
    can_attack_untapped: bool = False,
    blocker: bool = False,
    must_attack: bool = False,
    attackable: bool = False,
    untap_on_win: bool = False,
) -> list[str]:
    affected: list[str] = []
    for battle_entry in player_state.get("battle") or []:
        if amount is not None and len(affected) >= amount:
            break
        card = battle_entry.get("card") or {}
        if predicate and not predicate(card, battle_entry):
            continue
        if power:
            battle_entry["temporaryPower"] = int(battle_entry.get("temporaryPower") or 0) + power
        if breaker:
            battle_entry["temporaryBreaker"] = max(int(battle_entry.get("temporaryBreaker") or 0), breaker)
        if unblockable:
            battle_entry["temporaryUnblockable"] = True
        if speed_attacker:
            battle_entry["summoningSick"] = False
        if slayer:
            battle_entry["temporarySlayer"] = True
        if can_attack_untapped:
            battle_entry["temporaryCanAttackUntapped"] = True
        if blocker:
            battle_entry["temporaryBlocker"] = True
        if must_attack:
            battle_entry["temporaryMustAttack"] = True
        if attackable:
            battle_entry["temporaryAttackable"] = True
        if untap_on_win:
            battle_entry["temporaryUntapOnWin"] = True
        affected.append(card.get("name") or "a creature")
    return affected


def playmode_battle_to_zone_entries(
    state_payload: dict,
    target_zone: str,
    *,
    seat_filter: int | None = None,
    predicate,
    exclude_uid: str | None = None,
    limit: int | None = None,
    face_down: bool = False,
    tapped: bool = False,
) -> list[str]:
    moved: list[str] = []
    seat_keys = [playmode_seat_key(seat_filter)] if seat_filter in {1, 2} else ["player_one", "player_two"]
    for seat_key in seat_keys:
        player_state = state_payload.get(seat_key) or {}
        survivors = []
        for battle_entry in player_state.get("battle") or []:
            if exclude_uid and battle_entry.get("uid") == exclude_uid:
                survivors.append(battle_entry)
                continue
            if limit is not None and len(moved) >= limit:
                survivors.append(battle_entry)
                continue
            card = battle_entry.get("card") or {}
            if predicate(card, battle_entry):
                for stack_entry in playmode_stack_entries(battle_entry):
                    player_state.setdefault(target_zone, []).append({
                        **stack_entry,
                        "faceDown": face_down,
                        "tapped": tapped or (target_zone == "mana" and len(playmode_card_civilizations(stack_entry.get("card") or {})) > 1),
                        "manaProduced": [],
                    })
                moved.append(card.get("name") or "Unknown creature")
                continue
            survivors.append(battle_entry)
        player_state["battle"] = survivors
    return moved


def playmode_discard_from_hand(player_state: dict, amount: int = 1) -> list[str]:
    discarded: list[str] = []
    for _ in range(max(0, amount)):
        hand = player_state.get("hand") or []
        if not hand:
            break
        card = hand.pop(0)
        player_state.setdefault("graveyard", []).extend(playmode_stack_entries(card))
        discarded.append((card.get("card") or {}).get("name") or "a card")
    return discarded


def playmode_shuffle_player_deck(player_state: dict) -> None:
    rng = secrets.SystemRandom()
    draw_pile = player_state.get("drawPile") or []
    rng.shuffle(draw_pile)
    player_state["drawPile"] = draw_pile


def playmode_destroy_battle_entries(
    state_payload: dict,
    *,
    seat_filter: int | None = None,
    predicate,
    exclude_uid: str | None = None,
    limit: int | None = None,
) -> list[str]:
    destroyed: list[str] = []
    seat_keys = [playmode_seat_key(seat_filter)] if seat_filter in {1, 2} else ["player_one", "player_two"]
    for seat_key in seat_keys:
        player_state = state_payload.get(seat_key) or {}
        survivors = []
        for battle_entry in player_state.get("battle") or []:
            if exclude_uid and battle_entry.get("uid") == exclude_uid:
                survivors.append(battle_entry)
                continue
            if limit is not None and len(destroyed) >= limit:
                survivors.append(battle_entry)
                continue
            card = battle_entry.get("card") or {}
            if predicate(card, battle_entry):
                player_state.setdefault("graveyard", []).extend(playmode_stack_entries(battle_entry))
                destroyed.append(card.get("name") or "Unknown creature")
                continue
            survivors.append(battle_entry)
        player_state["battle"] = survivors
    return destroyed


def playmode_tap_battle_entries(
    state_payload: dict,
    *,
    seat_filter: int | None = None,
    predicate,
    exclude_uid: str | None = None,
    limit: int | None = None,
) -> list[str]:
    tapped: list[str] = []
    seat_keys = [playmode_seat_key(seat_filter)] if seat_filter in {1, 2} else ["player_one", "player_two"]
    for seat_key in seat_keys:
        player_state = state_payload.get(seat_key) or {}
        for battle_entry in player_state.get("battle") or []:
            if exclude_uid and battle_entry.get("uid") == exclude_uid:
                continue
            if limit is not None and len(tapped) >= limit:
                continue
            card = battle_entry.get("card") or {}
            if predicate(card, battle_entry):
                battle_entry["tapped"] = True
                tapped.append(card.get("name") or "Unknown creature")
    return tapped


def playmode_bounce_battle_entries(
    state_payload: dict,
    *,
    seat_filter: int | None = None,
    predicate,
    exclude_uid: str | None = None,
    limit: int | None = None,
) -> list[str]:
    bounced: list[str] = []
    seat_keys = [playmode_seat_key(seat_filter)] if seat_filter in {1, 2} else ["player_one", "player_two"]
    for seat_key in seat_keys:
        player_state = state_payload.get(seat_key) or {}
        survivors = []
        for battle_entry in player_state.get("battle") or []:
            if exclude_uid and battle_entry.get("uid") == exclude_uid:
                survivors.append(battle_entry)
                continue
            if limit is not None and len(bounced) >= limit:
                survivors.append(battle_entry)
                continue
            card = battle_entry.get("card") or {}
            if predicate(card, battle_entry):
                player_state.setdefault("hand", []).extend(playmode_stack_entries(battle_entry))
                bounced.append(card.get("name") or "Unknown creature")
                continue
            survivors.append(battle_entry)
        player_state["battle"] = survivors
    return bounced


def playmode_battle_candidates(state_payload: dict, *, seat_filter: int | None = None, predicate) -> list[dict]:
    candidates: list[dict] = []
    seat_keys = [playmode_seat_key(seat_filter)] if seat_filter in {1, 2} else ["player_one", "player_two"]
    for seat_key in seat_keys:
        seat = 2 if seat_key == "player_two" else 1
        for entry in (state_payload.get(seat_key) or {}).get("battle") or []:
            card = entry.get("card") or {}
            if predicate(card, entry):
                candidates.append({
                    "seat": seat,
                    "zone": "battle",
                    "uid": entry.get("uid"),
                    "name": card.get("name") or "Unknown card",
                    "image_path": card.get("image_path"),
                })
    return candidates


def playmode_set_pending_choice(state_payload: dict, choice: dict) -> None:
    if choice.get("candidates"):
        state_payload["pending_choice"] = choice


def playmode_pending_choice_view(state_payload: dict, viewer_seat: int | None, admin_override: bool) -> dict | None:
    choice = state_payload.get("pending_choice")
    if not isinstance(choice, dict):
        return None
    controller = choice.get("controller_seat")
    public_kinds = {"choose_battle_target", "blocker", "attack_response"}
    if choice.get("kind") not in public_kinds and not admin_override and viewer_seat != controller:
        return {
            "kind": "hidden",
            "message": "Opponent is choosing a card.",
            "controller_seat": controller,
            "candidates": [],
        }
    return choice


def playmode_find_zone_entry(player_state: dict, zone_name: str, uid: str | None) -> tuple[int, dict | None]:
    zone = player_state.get(zone_name) or []
    for index, entry in enumerate(zone):
        if entry.get("uid") == uid:
            return index, entry
    return -1, None


def playmode_card_matches_requirement(card: dict, requirement: str) -> bool:
    tokens = [token.rstrip("s") for token in normalize_rule_text(requirement).split() if token]
    candidate = set(
        token.rstrip("s")
        for token in normalize_rule_text(f"{card.get('race_label', '')} {card.get('type', '')}").split()
        if token
    )
    return bool(tokens) and all(token in candidate for token in tokens)


def playmode_extract_evolution_requirement(card: dict) -> str:
    match = re.search(r"put on one of your\s+([^.]+?)(?:\.|$)", str(card.get("text") or ""), re.I)
    return match.group(1) if match else ""


def playmode_extract_vortex_requirements(card: dict) -> list[str]:
    match = re.search(
        r"vortex\s+evolution[\s\S]*?put on one of your\s+(.+?)\s+and\s+one of your\s+(.+?)(?:\.|$)",
        str(card.get("text") or ""),
        re.I,
    )
    return [match.group(1), match.group(2)] if match else []


def playmode_find_evolution_target(player_state: dict, card: dict) -> int | None:
    requirement = playmode_extract_evolution_requirement(card)
    for index, entry in enumerate(player_state.get("battle") or []):
        if playmode_card_matches_requirement(entry.get("card") or {}, requirement):
            return index
    return None


def playmode_find_vortex_targets(player_state: dict, card: dict) -> list[int] | None:
    requirements = playmode_extract_vortex_requirements(card)
    if len(requirements) != 2:
        return None
    battle = player_state.get("battle") or []
    for first_index, first in enumerate(battle):
        if not playmode_card_matches_requirement(first.get("card") or {}, requirements[0]):
            continue
        for second_index, second in enumerate(battle):
            if second_index == first_index:
                continue
            if playmode_card_matches_requirement(second.get("card") or {}, requirements[1]):
                return [first_index, second_index]
    return None


def playmode_can_pay(player_state: dict, card: dict) -> bool:
    pool = player_state.get("manaPool") or []
    cost = max(0, int(card.get("cost") or 0))
    if cost == 0:
        return True
    if len(pool) < cost:
        return False
    civilizations = playmode_card_civilizations(card)
    return not civilizations or any((entry.get("civilization") if isinstance(entry, dict) else entry) in civilizations for entry in pool)


def playmode_consume_mana(player_state: dict, card: dict) -> bool:
    if not playmode_can_pay(player_state, card):
        return False
    cost = max(0, int(card.get("cost") or 0))
    if cost == 0:
        return True
    pool = list(player_state.get("manaPool") or [])
    civilizations = playmode_card_civilizations(card)
    used: list[dict] = []
    if civilizations:
        match_index = next(
            (index for index, entry in enumerate(pool) if (entry.get("civilization") if isinstance(entry, dict) else entry) in civilizations),
            -1,
        )
        if match_index == -1:
            return False
        used.append(pool.pop(match_index))
    while len(used) < cost and pool:
        used.append(pool.pop(0))
    used_sources = {entry.get("sourceUid") for entry in used if isinstance(entry, dict)}
    player_state["manaPool"] = [
        entry for entry in (player_state.get("manaPool") or [])
        if not isinstance(entry, dict) or entry.get("sourceUid") not in used_sources
    ]
    for mana_entry in player_state.get("mana") or []:
        if mana_entry.get("uid") in used_sources:
            mana_entry["manaProduced"] = []
    return True


def playmode_resolve_enter_battle(state_payload: dict, seat: int, entry: dict) -> list[str]:
    name = normalize_rule_text((entry.get("card") or {}).get("name"))
    card_text = str((entry.get("card") or {}).get("text") or "").lower()
    player_state = state_payload.get(playmode_seat_key(seat)) or {}
    opponent_seat = playmode_opponent_seat(seat)
    opponent_state = state_payload.get(playmode_seat_key(opponent_seat)) or {}
    messages: list[str] = []
    if re.search(r"when you put this creature into the battle zone.*draw (?:a|1) card", card_text, re.S):
        if playmode_draw_cards(player_state, 1):
            messages.append("drew 1 card")
    if re.search(r"when you put this creature into the battle zone.*draw up to 2 cards", card_text, re.S):
        drawn = playmode_draw_cards(player_state, 2)
        if drawn:
            messages.append(f"drew {drawn} card(s)")
    if re.search(r"when you put this creature into the battle zone.*draw up to 3 cards", card_text, re.S):
        drawn = playmode_draw_cards(player_state, 3)
        if drawn:
            messages.append(f"drew {drawn} card(s)")
    if "when you put this creature into the battle zone, put the top card of your deck into your mana zone" in card_text:
        moved = playmode_top_to_mana(player_state)
        if moved:
            messages.append("put the top card of deck into mana")
    if "when you put this creature into the battle zone, if you have 5 or more shields, add the top card of your deck to your shields" in card_text:
        if len(player_state.get("shields") or []) >= 5 and playmode_top_to_shield(player_state):
            messages.append("added the top card of deck to shields")
    if "destroy all your other creatures" in card_text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=seat,
            exclude_uid=entry.get("uid"),
            predicate=lambda card, _entry: playmode_is_creature(card),
        )
        if destroyed:
            messages.append(f"destroyed your other creatures: {', '.join(destroyed)}")
    if "destroy all your opponent's creatures that have \"blocker\" and power 3000 or less" in card_text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            predicate=lambda card, _entry: playmode_is_creature(card) and playmode_has_keyword(card, "blocker") and playmode_power_value(card) <= 3000,
        )
        if destroyed:
            messages.append(f"destroyed opponent blockers: {', '.join(destroyed)}")
    if "destroy up to 2 of your opponent's creatures that have \"blocker\"" in card_text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=2,
            predicate=lambda card, _entry: playmode_is_creature(card) and playmode_has_keyword(card, "blocker"),
        )
        if destroyed:
            messages.append(f"destroyed opponent blockers: {', '.join(destroyed)}")
    if "your opponent discards a card at random from his hand" in card_text:
        discarded = playmode_discard_from_hand(opponent_state, 1)
        if discarded:
            messages.append(f"opponent discarded {', '.join(discarded)}")
    if "choose a creature in the battle zone and return it to its owner's hand" in card_text or "choose up to 2 creatures in the battle zone and return them to their owners' hands" in card_text:
        candidates = playmode_battle_candidates(
            state_payload,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        playmode_set_pending_choice(state_payload, {
            "kind": "choose_battle_target",
            "effect": "bounce",
            "controller_seat": seat,
            "message": f"Choose a creature to return to hand for {entry.get('card', {}).get('name', 'this effect')}.",
            "candidates": candidates,
        })
        if candidates:
            messages.append("waiting for bounce target")
    if "choose one of your opponent's creatures in the battle zone and tap it" in card_text or "choose up to 2 of your opponent's creatures in the battle zone and tap them" in card_text:
        candidates = playmode_battle_candidates(
            state_payload,
            seat_filter=opponent_seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and not _entry.get("tapped"),
        )
        playmode_set_pending_choice(state_payload, {
            "kind": "choose_battle_target",
            "effect": "tap",
            "controller_seat": seat,
            "message": f"Choose an opponent creature to tap for {entry.get('card', {}).get('name', 'this effect')}.",
            "candidates": candidates,
        })
        if candidates:
            messages.append("waiting for tap target")
    if "you may destroy one of your opponent's creatures" in card_text or "destroy one of your opponent's creatures" in card_text:
        candidates = playmode_battle_candidates(
            state_payload,
            seat_filter=opponent_seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        playmode_set_pending_choice(state_payload, {
            "kind": "choose_battle_target",
            "effect": "destroy",
            "controller_seat": seat,
            "message": f"Choose an opponent creature to destroy for {entry.get('card', {}).get('name', 'this effect')}.",
            "candidates": candidates,
        })
        if candidates:
            messages.append("waiting for destroy target")
    if name == "ballom master of death":
        destroyed = []
        for seat_key in ("player_one", "player_two"):
            player_state = state_payload.get(seat_key) or {}
            survivors = []
            for battle_entry in player_state.get("battle") or []:
                if battle_entry.get("uid") == entry.get("uid"):
                    survivors.append(battle_entry)
                    continue
                card = battle_entry.get("card") or {}
                if playmode_is_creature(card) and not any(normalize_rule_text(civ) == "darkness" for civ in playmode_card_civilizations(card)):
                    player_state.setdefault("graveyard", []).extend(playmode_stack_entries(battle_entry))
                    destroyed.append(card.get("name") or "Unknown creature")
                    continue
                survivors.append(battle_entry)
            player_state["battle"] = survivors
        if destroyed:
            messages.append(f"destroyed {', '.join(destroyed)}")
    if name == "crystal paladin":
        bounced = []
        for seat_key in ("player_one", "player_two"):
            player_state = state_payload.get(seat_key) or {}
            survivors = []
            for battle_entry in player_state.get("battle") or []:
                if battle_entry.get("uid") == entry.get("uid"):
                    survivors.append(battle_entry)
                    continue
                card = battle_entry.get("card") or {}
                if playmode_is_creature(card) and playmode_has_keyword(card, "blocker"):
                    player_state.setdefault("hand", []).extend(playmode_stack_entries(battle_entry))
                    bounced.append(card.get("name") or "Unknown blocker")
                    continue
                survivors.append(battle_entry)
            player_state["battle"] = survivors
        if bounced:
            messages.append(f"returned blockers to hand: {', '.join(bounced)}")
    if name in {"bombazar dragon of destiny", "bombazaar dragon of destiny"}:
        destroyed = []
        for seat_key in ("player_one", "player_two"):
            player_state = state_payload.get(seat_key) or {}
            survivors = []
            for battle_entry in player_state.get("battle") or []:
                if battle_entry.get("uid") == entry.get("uid"):
                    survivors.append(battle_entry)
                    continue
                card = battle_entry.get("card") or {}
                if playmode_is_creature(card) and playmode_power_value(card) == 6000:
                    player_state.setdefault("graveyard", []).extend(playmode_stack_entries(battle_entry))
                    destroyed.append(card.get("name") or "Unknown creature")
                    continue
                survivors.append(battle_entry)
            player_state["battle"] = survivors
        state_payload["bombazar_extra_turn_seat"] = seat
        if destroyed:
            messages.append(f"destroyed 6000-power creatures: {', '.join(destroyed)}")
    return messages


def playmode_resolve_spell_effect(state_payload: dict, seat: int, entry: dict) -> list[str]:
    card = entry.get("card") or {}
    text = str(card.get("text") or "").lower()
    name = normalize_rule_text(card.get("name"))
    player_state = state_payload.get(playmode_seat_key(seat)) or {}
    opponent_seat = playmode_opponent_seat(seat)
    opponent_state = state_payload.get(playmode_seat_key(opponent_seat)) or {}
    messages: list[str] = []
    if name == "apocalypse day":
        total_creatures = sum(
            1
            for seat_key in ("player_one", "player_two")
            for battle_entry in (state_payload.get(seat_key, {}).get("battle") or [])
            if playmode_is_creature(battle_entry.get("card") or {})
        )
        if total_creatures >= 6:
            destroyed = playmode_destroy_battle_entries(
                state_payload,
                predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            )
            if destroyed:
                messages.append(f"destroyed all creatures: {', '.join(destroyed)}")
    if name in {"brain serum", "energy stream"} or re.search(r"draw up to 2 cards", text):
        drawn = playmode_draw_cards(player_state, 2)
        if drawn:
            messages.append(f"drew {drawn} card(s)")
    elif "draw a card" in text or "draw 1 card" in text:
        drawn = playmode_draw_cards(player_state, 1)
        if drawn:
            messages.append("drew 1 card")
    elif "draw up to 3 cards" in text or "draw 3 cards" in text:
        drawn = playmode_draw_cards(player_state, 3)
        if drawn:
            messages.append(f"drew {drawn} card(s)")
    if name == "emergency typhoon":
        drawn = playmode_draw_cards(player_state, 2)
        discarded = playmode_discard_from_hand(player_state, 1)
        messages.append(f"drew {drawn} and discarded {', '.join(discarded) if discarded else 'nothing'}")
    if "your opponent discards a card at random" in text or "your opponent discards 1 card at random" in text:
        discarded = playmode_discard_from_hand(opponent_state, 1)
        if discarded:
            messages.append(f"opponent discarded {', '.join(discarded)}")
    if "search your deck" in text:
        candidates = []
        for entry in player_state.get("drawPile") or []:
            card_entry = entry.get("card") or {}
            if "take a creature" in text and not playmode_is_creature(card_entry):
                continue
            if "take a spell" in text and not playmode_is_spell(card_entry):
                continue
            candidates.append({
                "seat": seat,
                "zone": "drawPile",
                "uid": entry.get("uid"),
                "name": card_entry.get("name") or "Unknown card",
                "image_path": card_entry.get("image_path"),
            })
        playmode_set_pending_choice(state_payload, {
            "kind": "search_deck",
            "effect": "to_hand",
            "controller_seat": seat,
            "message": f"Choose a card from your deck for {card.get('name', 'search effect')}.",
            "candidates": candidates[:80],
        })
        if candidates:
            messages.append("waiting for deck search choice")
    if name == "faerie life" or "put the top card of your deck into your mana zone" in text:
        moved = playmode_top_to_mana(player_state)
        if moved:
            messages.append("put the top card of deck into mana")
    if "add the top card of your deck to your shields" in text or "put the top card of your deck into your shield zone" in text:
        moved = playmode_top_to_shield(player_state)
        if moved:
            messages.append("added the top card of deck to shields")
    if "add up to 3 cards from the top of your deck to your shields" in text:
        moved = playmode_move_top_cards(player_state, "shields", 3, face_down=True)
        if moved:
            messages.append(f"added {len(moved)} cards from deck to shields")
    if "put the top 2 cards of your deck into your mana zone" in text:
        moved = playmode_move_top_cards(player_state, "mana", 2, tapped=True)
        if moved:
            messages.append(f"put {len(moved)} cards from deck into mana")
    if "for each card in your mana zone, put a card from the top of your deck into your mana zone tapped" in text:
        amount = len(player_state.get("mana") or [])
        moved = playmode_move_top_cards(player_state, "mana", amount, tapped=True)
        if moved:
            messages.append(f"put {len(moved)} cards from deck into mana")
    if "choose any number of your shields and put them into your mana zone" in text:
        moved = playmode_move_zone_entries(player_state, "shields", "mana", face_down=False, tapped=True)
        if moved:
            messages.append(f"moved {len(moved)} shields to mana")
    if "choose any number of your shields and put them into your hand" in text:
        moved = playmode_move_zone_entries(player_state, "shields", "hand", face_down=False)
        if moved:
            messages.append(f"moved {len(moved)} shields to hand")
    if "choose one of your shields and put it into your graveyard" in text:
        moved = playmode_move_zone_entries(player_state, "shields", "graveyard", amount=1, face_down=False)
        if moved:
            messages.append(f"put shield into graveyard: {', '.join(moved)}")
    if "choose up to 3 of your opponent's shields and put them into his graveyard" in text:
        moved = playmode_move_zone_entries(opponent_state, "shields", "graveyard", amount=3, face_down=False)
        if moved:
            messages.append(f"put opponent shields into graveyard: {', '.join(moved)}")
    if "your opponent chooses one of his shields for each shield you have. he puts the rest of his shields into his hand" in text:
        keep_count = len(player_state.get("shields") or [])
        shields = opponent_state.get("shields") or []
        if len(shields) > keep_count:
            moved_count = len(shields) - keep_count
            opponent_state["shields"] = shields[:keep_count]
            opponent_state.setdefault("hand", []).extend({**entry, "faceDown": False, "tapped": False} for entry in shields[keep_count:])
            messages.append(f"opponent moved {moved_count} extra shield(s) to hand")
    power_attacker_match = re.search(r'power attacker \+(\d+)', text)
    flat_power_match = re.search(r'gets? \+(\d+) power', text)
    temporary_power = int((power_attacker_match or flat_power_match).group(1)) if (power_attacker_match or flat_power_match) else 0
    temporary_breaker = 3 if "triple breaker" in text else (2 if "double breaker" in text else 0)
    if temporary_power or temporary_breaker or "can't be blocked this turn" in text or "speed attacker" in text or "slayer" in text:
        affects_all = "each of your creatures" in text or "your creatures in the battle zone" in text
        amount = None if affects_all else (2 if "choose up to 2 of your creatures" in text else 1)
        affected = playmode_apply_temporary_battle_effect(
            player_state,
            amount=amount,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            power=temporary_power,
            breaker=temporary_breaker,
            unblockable="can't be blocked this turn" in text or "your creatures in the battle zone can't be blocked this turn" in text,
            speed_attacker="speed attacker" in text,
            slayer="slayer" in text,
        )
        if affected:
            messages.append(f"temporary effect applied to: {', '.join(affected)}")
    if "ignore any effects that would prevent your creatures from attacking your opponent" in text or "ignore any effects that would prevent that creature from attacking your opponent" in text:
        affected = playmode_apply_temporary_battle_effect(
            player_state,
            amount=1 if "choose one of your creatures" in text else None,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            unblockable="can't be blocked" in text,
            speed_attacker=True,
        )
        if affected:
            messages.append(f"attack restrictions ignored for: {', '.join(affected)}")
    if "whenever any of your opponent's creatures is destroyed this turn" in text:
        state_payload["temporary_slash_and_burn_seat"] = seat
        messages.append("slash and burn delayed trigger armed for this turn")
    if "each creature of that race can attack untapped creatures and can't be blocked while attacking a creature" in text:
        affected = playmode_apply_temporary_battle_effect(
            player_state,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            unblockable=True,
            can_attack_untapped=True,
        )
        if affected:
            messages.append(f"relentless blitz applied to: {', '.join(affected)}")
    if "creatures of that civilization can't attack you" in text:
        affected = playmode_apply_temporary_battle_effect(
            opponent_state,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            must_attack=False,
        )
        for battle_entry in opponent_state.get("battle") or []:
            if playmode_is_creature(battle_entry.get("card") or {}):
                battle_entry["temporaryCannotAttackPlayer"] = True
        if affected:
            messages.append(f"miraculous truce restricted attacks from: {', '.join(affected)}")
    if "your creatures can attack it this turn as though it were tapped" in text:
        affected = playmode_apply_temporary_battle_effect(
            opponent_state,
            amount=1,
            predicate=lambda target_card, battle_entry: playmode_is_creature(target_card) and not battle_entry.get("tapped"),
            attackable=True,
        )
        if affected:
            messages.append(f"marked attackable as tapped: {', '.join(affected)}")
    if "whenever any of your creatures would be destroyed this turn, put it into your mana zone instead" in text:
        state_payload["temporary_destroy_to_mana_seat"] = seat
        messages.append("your creatures will go to mana instead of graveyard this turn")
    if name == "fists of forever":
        affected = playmode_apply_temporary_battle_effect(
            player_state,
            amount=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            untap_on_win=True,
        )
        if affected:
            messages.append(f"will untap after winning battle: {', '.join(affected)}")
    if "each of your opponent's creatures gets \"this creature attacks if able\"" in text or "during your opponent's next turn, each of his creatures attacks if able" in text:
        affected = playmode_apply_temporary_battle_effect(
            opponent_state,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            must_attack=True,
        )
        if affected:
            messages.append(f"opponent creatures must attack: {', '.join(affected)}")
    if "it gets \"this creature attacks if able\"" in text:
        affected = playmode_apply_temporary_battle_effect(
            opponent_state,
            amount=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            must_attack=True,
        )
        if affected:
            messages.append(f"opponent creature must attack: {', '.join(affected)}")
    if "each of your creatures in the battle zone gets \"blocker" in text:
        affected = playmode_apply_temporary_battle_effect(
            player_state,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            blocker=True,
        )
        if affected:
            messages.append(f"temporary blocker applied to: {', '.join(affected)}")
    if re.search(r"tap all creatures in the battle zone that don.?t have \"blocker", text):
        tapped = playmode_tap_battle_entries(
            state_payload,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and not playmode_has_keyword(target_card, "blocker"),
        )
        if tapped:
            messages.append(f"tapped non-blockers: {', '.join(tapped)}")
    if "tap all your opponent's creatures in the battle zone" in text:
        tapped = playmode_tap_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if tapped:
            messages.append(f"tapped opponent creatures: {', '.join(tapped)}")
    if "tap all darkness creatures in the battle zone" in text:
        tapped = playmode_tap_battle_entries(
            state_payload,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and "Darkness" in playmode_card_civilizations(target_card),
        )
        if tapped:
            messages.append(f"tapped darkness creatures: {', '.join(tapped)}")
    elif "tap all fire creatures in the battle zone" in text:
        tapped = playmode_tap_battle_entries(
            state_payload,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and "Fire" in playmode_card_civilizations(target_card),
        )
        if tapped:
            messages.append(f"tapped fire creatures: {', '.join(tapped)}")
    if "tap all creatures in the battle zone except light creatures" in text:
        tapped = playmode_tap_battle_entries(
            state_payload,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and "Light" not in playmode_card_civilizations(target_card),
        )
        if tapped:
            messages.append(f"tapped non-light creatures: {', '.join(tapped)}")
    if re.search(r"choose (?:one|1) of your opponent's creatures in the battle zone", text) and "tap it" in text:
        candidates = playmode_battle_candidates(
            state_payload,
            seat_filter=opponent_seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and not _entry.get("tapped"),
        )
        playmode_set_pending_choice(state_payload, {
            "kind": "choose_battle_target",
            "effect": "tap",
            "controller_seat": seat,
            "message": f"Choose an opponent creature to tap for {card.get('name', 'this spell')}.",
            "candidates": candidates,
        })
        if candidates:
            messages.append("waiting for tap target")
    if "choose up to 2 of your opponent's creatures in the battle zone and tap them" in text:
        tapped = playmode_tap_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=2,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and not _entry.get("tapped"),
        )
        if tapped:
            messages.append(f"tapped opponent creatures: {', '.join(tapped)}")
    if name == "cloned deflector":
        amount = 1 + sum(
            1
            for target_state in (player_state, opponent_state)
            for grave_entry in (target_state.get("graveyard") or [])
            if normalize_rule_text((grave_entry.get("card") or {}).get("name")) == "cloned deflector"
        )
        tapped = playmode_tap_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=amount,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and not _entry.get("tapped"),
        )
        if tapped:
            messages.append(f"cloned deflector tapped: {', '.join(tapped)}")
    if not state_payload.get("pending_choice") and (
        "choose a creature in battle zone" in text
        or "choose a creature in the battle zone" in text
    ) and "return" in text and "hand" in text:
        candidates = playmode_battle_candidates(
            state_payload,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        playmode_set_pending_choice(state_payload, {
            "kind": "choose_battle_target",
            "effect": "bounce",
            "controller_seat": seat,
            "message": f"Choose a creature to return to hand for {card.get('name', 'this spell')}.",
            "candidates": candidates,
        })
        if candidates:
            messages.append("waiting for bounce target")
    if not state_payload.get("pending_choice") and (
        "return one of your opponent's creatures" in text
        or "return up to 2 of your opponent's creatures" in text
        or "return an opponent's creature" in text
        or ("choose one of your opponent's non-evolution creatures" in text and name != "hide and seek")
    ):
        candidates = playmode_battle_candidates(
            state_payload,
            seat_filter=opponent_seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        playmode_set_pending_choice(state_payload, {
            "kind": "choose_battle_target",
            "effect": "bounce",
            "controller_seat": seat,
            "message": f"Choose an opponent creature to return to hand for {card.get('name', 'this spell')}.",
            "candidates": candidates,
        })
        if candidates:
            messages.append("waiting for bounce target")
    if not state_payload.get("pending_choice") and "choose up to 2 creatures in the battle zone and return them to their owners' hands" in text:
        bounced = playmode_bounce_battle_entries(
            state_payload,
            limit=2,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if bounced:
            messages.append(f"returned creatures to hand: {', '.join(bounced)}")
    if name == "cloned spiral":
        amount = 1 + sum(
            1
            for target_state in (player_state, opponent_state)
            for grave_entry in (target_state.get("graveyard") or [])
            if normalize_rule_text((grave_entry.get("card") or {}).get("name")) == "cloned spiral"
        )
        bounced = playmode_bounce_battle_entries(
            state_payload,
            limit=amount,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if bounced:
            messages.append(f"cloned spiral returned: {', '.join(bounced)}")
    if name == "hide and seek":
        bounced = playmode_bounce_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and not playmode_is_evolution(target_card),
        )
        discarded = playmode_discard_from_hand(opponent_state, 1)
        if bounced or discarded:
            messages.append(f"returned non-evolution creature: {', '.join(bounced) if bounced else 'none'}; opponent discarded {', '.join(discarded) if discarded else 'nothing'}")
    if "destroy all creatures that have power 2000 or less" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and playmode_power_value(target_card) <= 2000,
        )
        if destroyed:
            messages.append(f"destroyed 2000-or-less creatures: {', '.join(destroyed)}")
    if "destroy all creatures that have power 4000 or less" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and playmode_power_value(target_card) <= 4000,
        )
        if destroyed:
            messages.append(f"destroyed 4000-or-less creatures: {', '.join(destroyed)}")
    if "destroy all your opponent's creatures that have power 3000 or less" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and playmode_power_value(target_card) <= 3000,
        )
        if destroyed:
            messages.append(f"destroyed opponent 3000-or-less creatures: {', '.join(destroyed)}")
    if "destroy all your opponent's creatures" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if destroyed:
            messages.append(f"destroyed all opponent creatures: {', '.join(destroyed)}")
    if "destroy any number of your opponent's creatures that have total power 8000 or less" in text:
        remaining_power = 8000
        destroyed: list[str] = []
        opponent_battle = list(opponent_state.get("battle") or [])
        for target in sorted(opponent_battle, key=lambda battle_entry: playmode_power_value(battle_entry.get("card") or {})):
            target_card = target.get("card") or {}
            power = playmode_power_value(target_card)
            if playmode_is_creature(target_card) and power <= remaining_power:
                remaining_power -= power
                destroyed.extend(playmode_destroy_battle_entries(
                    state_payload,
                    seat_filter=opponent_seat,
                    limit=1,
                    predicate=lambda card, battle_entry, uid=target.get("uid"): battle_entry.get("uid") == uid,
                ))
        if destroyed:
            messages.append(f"destroyed total 8000 power or less: {', '.join(destroyed)}")
    if name == "cloned blade":
        amount = 1 + sum(
            1
            for target_state in (player_state, opponent_state)
            for grave_entry in (target_state.get("graveyard") or [])
            if normalize_rule_text((grave_entry.get("card") or {}).get("name")) == "cloned blade"
        )
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=amount,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and playmode_power_value(target_card) <= 3000,
        )
        if destroyed:
            messages.append(f"cloned blade destroyed: {', '.join(destroyed)}")
    if "choose a number less than or equal to 6000. destroy all creatures that have that power" in text:
        powers = [
            playmode_power_value(battle_entry.get("card") or {})
            for seat_key in ("player_one", "player_two")
            for battle_entry in (state_payload.get(seat_key, {}).get("battle") or [])
            if playmode_is_creature(battle_entry.get("card") or {}) and playmode_power_value(battle_entry.get("card") or {}) <= 6000
        ]
        chosen_power = max(powers) if powers else 0
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            predicate=lambda target_card, _entry, power=chosen_power: playmode_is_creature(target_card) and playmode_power_value(target_card) == power,
        )
        if destroyed:
            messages.append(f"destroyed {chosen_power}-power creatures: {', '.join(destroyed)}")
    if not state_payload.get("pending_choice") and "destroy one of your opponent's creatures that has \"blocker\" and power 6000 or less" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and playmode_has_keyword(target_card, "blocker") and playmode_power_value(target_card) <= 6000,
        )
        if destroyed:
            messages.append(f"destroyed blocker: {', '.join(destroyed)}")
    elif not state_payload.get("pending_choice") and "destroy one of your opponent's creatures that has \"blocker\"" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and playmode_has_keyword(target_card, "blocker"),
        )
        if destroyed:
            messages.append(f"destroyed blocker: {', '.join(destroyed)}")
    elif not state_payload.get("pending_choice") and re.search(r"destroy (?:one|1) of your opponent's creatures that has power 2000 or less", text):
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and playmode_power_value(target_card) <= 2000,
        )
        if destroyed:
            messages.append(f"destroyed creature: {', '.join(destroyed)}")
    elif not state_payload.get("pending_choice") and re.search(r"destroy (?:one|1) of your opponent's creatures that has power 4000 or less", text):
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and playmode_power_value(target_card) <= 4000,
        )
        if destroyed:
            messages.append(f"destroyed creature: {', '.join(destroyed)}")
    elif not state_payload.get("pending_choice") and ("destroy one of your opponent's creatures" in text or name == "terror pit"):
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if destroyed:
            messages.append(f"destroyed creature: {', '.join(destroyed)}")
    if not state_payload.get("pending_choice") and "destroy one of your opponent's untapped creatures" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, battle_entry: playmode_is_creature(target_card) and not battle_entry.get("tapped"),
        )
        if destroyed:
            messages.append(f"destroyed untapped creature: {', '.join(destroyed)}")
    if "destroy up to 2 of your opponent's creatures" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=2,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if destroyed:
            messages.append(f"destroyed up to 2 creatures: {', '.join(destroyed)}")
    if "destroy one of your creatures" in text or "destroy up to 2 of your creatures" in text:
        limit = 2 if "up to 2" in text else 1
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=seat,
            limit=limit,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if destroyed:
            messages.append(f"destroyed your creature(s): {', '.join(destroyed)}")
    if "destroy any number of your creatures. then draw that many cards" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        drawn = playmode_draw_cards(player_state, len(destroyed))
        if destroyed:
            messages.append(f"destroyed your creatures and drew {drawn}: {', '.join(destroyed)}")
    if name == "eldritch poison":
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and "Darkness" in playmode_card_civilizations(target_card),
        )
        moved = playmode_move_zone_entries(player_state, "mana", "hand", amount=1, predicate=lambda target_card, _entry: playmode_is_creature(target_card))
        if destroyed or moved:
            messages.append(f"eldritch poison destroyed {', '.join(destroyed) if destroyed else 'nothing'} and returned {', '.join(moved) if moved else 'nothing'}")
    if "your opponent chooses one of his creatures in the battle zone and destroys it" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if destroyed:
            messages.append(f"opponent sacrificed creature: {', '.join(destroyed)}")
    if "your opponent chooses one of his creatures in the battle zone or a card in his mana zone and puts it into his graveyard" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if destroyed:
            messages.append(f"opponent put creature into graveyard: {', '.join(destroyed)}")
        else:
            moved = playmode_move_zone_entries(opponent_state, "mana", "graveyard", amount=1)
            if moved:
                messages.append(f"opponent put mana into graveyard: {', '.join(moved)}")
    if "your opponent chooses one of his creatures in the battle zone or one of his shields and puts it into his graveyard" in text:
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if destroyed:
            messages.append(f"opponent put creature into graveyard: {', '.join(destroyed)}")
        else:
            moved = playmode_move_zone_entries(opponent_state, "shields", "graveyard", amount=1, face_down=False)
            if moved:
                messages.append(f"opponent put shield into graveyard: {', '.join(moved)}")
    if name == "cloned nightmare":
        amount = 1 + sum(
            1
            for target_state in (player_state, opponent_state)
            for grave_entry in (target_state.get("graveyard") or [])
            if normalize_rule_text((grave_entry.get("card") or {}).get("name")) == "cloned nightmare"
        )
        discarded = playmode_discard_from_hand(opponent_state, amount)
        if discarded:
            messages.append(f"cloned nightmare discarded: {', '.join(discarded)}")
    if "your opponent discards all cards from his hand" in text:
        discarded = playmode_discard_from_hand(opponent_state, len(opponent_state.get("hand") or []))
        if discarded:
            messages.append(f"opponent discarded all cards: {', '.join(discarded)}")
    if "your opponent chooses and discards 2 cards from his hand" in text:
        discarded = playmode_discard_from_hand(opponent_state, 2)
        if discarded:
            messages.append(f"opponent discarded {', '.join(discarded)}")
    if "your opponent chooses and discards a card from his hand for each light creature he has in the battle zone" in text:
        amount = sum(1 for battle_entry in opponent_state.get("battle") or [] if "Light" in playmode_card_civilizations(battle_entry.get("card") or {}))
        discarded = playmode_discard_from_hand(opponent_state, amount)
        if discarded:
            messages.append(f"opponent discarded for light creatures: {', '.join(discarded)}")
    if "return a card from your mana zone to your hand" in text:
        mana = player_state.get("mana") or []
        if mana:
            player_state.setdefault("hand", []).extend(playmode_stack_entries(mana.pop(0)))
            messages.append("returned a mana card to hand")
    if "return a spell from your mana zone to your hand" in text:
        moved = playmode_move_zone_entries(player_state, "mana", "hand", amount=1, predicate=lambda target_card, _entry: playmode_is_spell(target_card))
        if moved:
            messages.append(f"returned spell from mana to hand: {', '.join(moved)}")
    if "return a creature that costs 6 or more from your mana zone to your hand" in text:
        moved = playmode_move_zone_entries(player_state, "mana", "hand", amount=1, predicate=lambda target_card, _entry: playmode_is_creature(target_card) and int(target_card.get("cost") or 0) >= 6)
        if moved:
            messages.append(f"returned 6+ cost creature from mana to hand: {', '.join(moved)}")
    if "return up to 2 cards from your mana zone to your hand" in text:
        moved = playmode_move_zone_entries(player_state, "mana", "hand", amount=2)
        if moved:
            messages.append(f"returned mana cards to hand: {', '.join(moved)}")
    if "return up to 3 cards from your mana zone to your hand" in text:
        moved = playmode_move_zone_entries(player_state, "mana", "hand", amount=3)
        if moved:
            messages.append(f"returned mana cards to hand: {', '.join(moved)}")
    if "each player returns all cards from his mana zone to his hand" in text:
        moved_counts = []
        for target in (player_state, opponent_state):
            moved = playmode_move_zone_entries(target, "mana", "hand")
            moved_counts.append(len(moved))
        messages.append(f"returned mana to hands: {moved_counts[0]} / {moved_counts[1]}")
    if "return a creature from your graveyard to your hand" in text:
        graveyard = player_state.get("graveyard") or []
        index = next((idx for idx, grave_entry in enumerate(graveyard) if playmode_is_creature(grave_entry.get("card") or {})), -1)
        if index >= 0:
            player_state.setdefault("hand", []).extend(playmode_stack_entries(graveyard.pop(index)))
            messages.append("returned a creature from graveyard to hand")
    if "return up to 2 creatures from your graveyard to your hand" in text:
        moved = playmode_move_zone_entries(player_state, "graveyard", "hand", amount=2, predicate=lambda target_card, _entry: playmode_is_creature(target_card))
        if moved:
            messages.append(f"returned creatures from graveyard to hand: {', '.join(moved)}")
    if "put up to 2 creatures from your graveyard into your mana zone" in text:
        moved = playmode_move_zone_entries(player_state, "graveyard", "mana", amount=2, predicate=lambda target_card, _entry: playmode_is_creature(target_card), tapped=True)
        if moved:
            messages.append(f"put graveyard creatures into mana: {', '.join(moved)}")
    if "put any number of cards from your mana zone into your graveyard" in text:
        amount = len(player_state.get("mana") or [])
        moved = playmode_move_zone_entries(player_state, "mana", "graveyard")
        drawn = playmode_draw_cards(player_state, len(moved))
        if moved:
            messages.append(f"moved {amount} mana to graveyard and drew {drawn}")
    if "discard any number of cards from your hand. then draw that many cards" in text:
        amount = len(player_state.get("hand") or [])
        discarded = playmode_discard_from_hand(player_state, amount)
        drawn = playmode_draw_cards(player_state, len(discarded))
        if discarded:
            messages.append(f"discarded {len(discarded)} and drew {drawn}")
    if "each player counts the cards in his hand, shuffles these cards into his deck, then draws that many cards" in text:
        counts = []
        for target_state in (player_state, opponent_state):
            hand = target_state.get("hand") or []
            amount = len(hand)
            target_state.setdefault("drawPile", []).extend(hand)
            target_state["hand"] = []
            playmode_shuffle_player_deck(target_state)
            counts.append(playmode_draw_cards(target_state, amount))
        messages.append(f"cycled hands and drew {counts[0]} / {counts[1]}")
    if name == "cosmic darts":
        shields = player_state.get("shields") or []
        if shields:
            shield = shields[0]
            shield_card = shield.get("card") or {}
            if playmode_is_spell(shield_card):
                shields.pop(0)
                triggered = {**shield, "faceDown": False, "tapped": False, "manaProduced": []}
                nested_messages = playmode_resolve_spell_effect(state_payload, seat, triggered)
                player_state.setdefault("graveyard", []).append(triggered)
                messages.append(f"cosmic darts cast {shield_card.get('name', 'a spell')} from shield" + (f" ({'; '.join(nested_messages)})" if nested_messages else ""))
            else:
                messages.append("cosmic darts checked a shield and left it in place")
    if "search your opponent's deck" in text and "put it into his graveyard" in text:
        moved = playmode_move_zone_entries(opponent_state, "drawPile", "graveyard", amount=2)
        playmode_shuffle_player_deck(opponent_state)
        if moved:
            messages.append(f"milled opponent deck cards: {', '.join(moved)}")
    if "reveal the top 4 cards of your deck" in text and "put all water cards from among them into your hand" in text:
        revealed = []
        for _ in range(4):
            draw_pile = player_state.get("drawPile") or []
            if not draw_pile:
                break
            revealed.append(draw_pile.pop(0))
        water = [card_entry for card_entry in revealed if "Water" in playmode_card_civilizations(card_entry.get("card") or {})]
        others = [card_entry for card_entry in revealed if card_entry not in water]
        player_state.setdefault("hand", []).extend({**card_entry, "faceDown": False, "tapped": False} for card_entry in water)
        player_state.setdefault("graveyard", []).extend({**card_entry, "faceDown": False, "tapped": False} for card_entry in others)
        messages.append(f"revealed 4; kept {len(water)} water card(s)")
    if "look at the top 4 cards of your deck. put one of them into your hand" in text:
        revealed = []
        for _ in range(4):
            draw_pile = player_state.get("drawPile") or []
            if not draw_pile:
                break
            revealed.append(draw_pile.pop(0))
        if revealed:
            player_state.setdefault("hand", []).append({**revealed.pop(0), "faceDown": False, "tapped": False})
            player_state.setdefault("drawPile", []).extend(revealed)
            messages.append("looked at top 4 and put one card into hand")
    if "reveal the top 4 cards of your deck" in text and "has \"blocker\" into your hand" in text:
        revealed = []
        for _ in range(4):
            draw_pile = player_state.get("drawPile") or []
            if not draw_pile:
                break
            revealed.append(draw_pile.pop(0))
        blocker_index = next((index for index, card_entry in enumerate(revealed) if playmode_has_keyword(card_entry.get("card") or {}, "blocker")), -1)
        if blocker_index >= 0:
            player_state.setdefault("hand", []).append({**revealed.pop(blocker_index), "faceDown": False, "tapped": False})
        player_state.setdefault("drawPile", []).extend(revealed)
        messages.append("revealed top 4 and kept a blocker" if blocker_index >= 0 else "revealed top 4 and found no blocker")
    if "look at your opponent's hand and shields" in text:
        messages.append(f"looked at opponent hand ({len(opponent_state.get('hand') or [])}) and shields ({len(opponent_state.get('shields') or [])})")
    if "look at up to 3 of your opponent's shields" in text:
        messages.append(f"looked at {min(3, len(opponent_state.get('shields') or []))} opponent shield(s)")
    if "look at your opponent's hand" in text and "discards all darkness spells" in text:
        discarded = playmode_move_zone_entries(opponent_state, "hand", "graveyard", predicate=lambda target_card, _entry: playmode_is_spell(target_card) and "Darkness" in playmode_card_civilizations(target_card))
        if discarded:
            messages.append(f"discarded opponent darkness spells: {', '.join(discarded)}")
    if "look at your opponent's hand and choose a card from it" in text:
        discarded = playmode_discard_from_hand(opponent_state, 1)
        if discarded:
            messages.append(f"opponent discarded chosen card: {', '.join(discarded)}")
    if "choose a number. show your hand to your opponent and discard from it each card that has that cost" in text:
        all_costs = [
            int((hand_entry.get("card") or {}).get("cost") or 0)
            for hand_entry in (player_state.get("hand") or []) + (opponent_state.get("hand") or [])
        ]
        chosen_cost = max(set(all_costs), key=all_costs.count) if all_costs else 0
        own = playmode_move_zone_entries(player_state, "hand", "graveyard", predicate=lambda target_card, _entry, cost=chosen_cost: int(target_card.get("cost") or 0) == cost)
        opp = playmode_move_zone_entries(opponent_state, "hand", "graveyard", predicate=lambda target_card, _entry, cost=chosen_cost: int(target_card.get("cost") or 0) == cost)
        messages.append(f"roulette discarded cost {chosen_cost}: {len(own)} / {len(opp)}")
    if "choose one of your opponent's water or darkness creatures" in text and "mana zone" in text:
        moved = playmode_battle_to_zone_entries(
            state_payload,
            "mana",
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and any(civ in {"Water", "Darkness"} for civ in playmode_card_civilizations(target_card)),
            tapped=True,
        )
        if moved:
            messages.append(f"put opponent creature into mana: {', '.join(moved)}")
    if "choose 1 of your opponent's creatures in the battle zone and put it into his mana zone" in text:
        moved = playmode_battle_to_zone_entries(
            state_payload,
            "mana",
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            tapped=True,
        )
        if moved:
            messages.append(f"put opponent creature into mana: {', '.join(moved)}")
    if "add a card from your mana zone to your shields face down" in text:
        moved = playmode_move_zone_entries(player_state, "mana", "shields", amount=1, face_down=True)
        if moved:
            messages.append(f"added mana card to shields: {', '.join(moved)}")
    if "choose a card in your opponent's mana zone and put it into his graveyard" in text:
        moved = playmode_move_zone_entries(opponent_state, "mana", "graveyard", amount=1)
        if moved:
            messages.append(f"put opponent mana into graveyard: {', '.join(moved)}")
    if "add a card from your hand to your shields face down" in text:
        moved = playmode_move_zone_entries(player_state, "hand", "shields", amount=1, face_down=True)
        if moved:
            messages.append(f"added hand card to shields: {', '.join(moved)}")
    if name == "dance of the sproutlings":
        hand = player_state.get("hand") or []
        first_creature = next((hand_entry for hand_entry in hand if playmode_is_creature(hand_entry.get("card") or {})), None)
        race = (first_creature.get("card") or {}).get("race_label") if first_creature else ""
        moved = playmode_move_zone_entries(
            player_state,
            "hand",
            "mana",
            predicate=lambda target_card, _entry, wanted=race: bool(wanted) and playmode_is_creature(target_card) and target_card.get("race_label") == wanted,
            tapped=True,
        )
        if moved:
            messages.append(f"moved {race} creatures from hand to mana: {', '.join(moved)}")
    if "put a card from your mana zone into your hand. then put a card from your hand into your mana zone" in text:
        to_hand = playmode_move_zone_entries(player_state, "mana", "hand", amount=1)
        to_mana = playmode_move_zone_entries(player_state, "hand", "mana", amount=1, tapped=True)
        messages.append(f"swapped mana/hand: {len(to_hand)} to hand, {len(to_mana)} to mana")
    if "each player puts all the cards from his mana zone into his hand" in text and "puts all the cards from his hand into his mana zone tapped" in text:
        for target_state in (player_state, opponent_state):
            old_mana = list(target_state.get("mana") or [])
            old_hand = list(target_state.get("hand") or [])
            target_state["mana"] = []
            target_state["hand"] = []
            target_state["hand"].extend({**entry, "faceDown": False, "tapped": False, "manaProduced": []} for entry in old_mana)
            target_state["mana"].extend({**entry, "faceDown": False, "tapped": True, "manaProduced": []} for entry in old_hand)
        messages.append("swapped both players' mana and hands")
    if "put 1 of your creatures from the battle zone into your mana zone" in text:
        moved = playmode_battle_to_zone_entries(
            state_payload,
            "mana",
            seat_filter=seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            tapped=True,
        )
        if moved:
            messages.append(f"put your creature into mana: {', '.join(moved)}")
    if "choose a non-evolution creature in the battle zone and add it to its owner's shields" in text:
        moved = playmode_battle_to_zone_entries(
            state_payload,
            "shields",
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card) and not playmode_is_evolution(target_card),
            face_down=True,
        )
        if moved:
            messages.append(f"added creature to shields: {', '.join(moved)}")
    if name == "hydro hurricane":
        light_count = sum(1 for battle_entry in player_state.get("battle") or [] if "Light" in playmode_card_civilizations(battle_entry.get("card") or {}))
        darkness_count = sum(1 for battle_entry in player_state.get("battle") or [] if "Darkness" in playmode_card_civilizations(battle_entry.get("card") or {}))
        mana_moved = playmode_move_zone_entries(opponent_state, "mana", "hand", amount=light_count)
        creatures_bounced = playmode_bounce_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=darkness_count,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if mana_moved or creatures_bounced:
            messages.append(f"hydro hurricane returned {len(mana_moved)} mana and {len(creatures_bounced)} creature(s)")
    if name == "miraculous plague":
        bounced = playmode_bounce_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        to_hand = playmode_move_zone_entries(opponent_state, "mana", "hand", amount=1)
        to_grave = playmode_move_zone_entries(opponent_state, "mana", "graveyard", amount=1)
        messages.append(f"miraculous plague returned {len(bounced)} creature, destroyed {len(destroyed)}, moved mana {len(to_hand)} hand/{len(to_grave)} grave")
    if name == "shock hurricane":
        own_bounced = playmode_bounce_battle_entries(
            state_payload,
            seat_filter=seat,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        opp_bounced = playmode_bounce_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=len(own_bounced),
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
        )
        if own_bounced or opp_bounced:
            messages.append(f"shock hurricane returned {len(own_bounced)} of yours and {len(opp_bounced)} opponent creature(s)")
    if name == "soulswap":
        moved_to_mana = playmode_battle_to_zone_entries(
            state_payload,
            "mana",
            limit=1,
            predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            tapped=True,
        )
        mana_count = len(player_state.get("mana") or [])
        mana_zone = player_state.get("mana") or []
        target_index = next((index for index, mana_entry in enumerate(mana_zone) if playmode_is_creature(mana_entry.get("card") or {}) and not playmode_is_evolution(mana_entry.get("card") or {}) and int((mana_entry.get("card") or {}).get("cost") or 0) <= mana_count), -1)
        if target_index >= 0:
            summoned = mana_zone.pop(target_index)
            player_state.setdefault("battle", []).append({**summoned, "faceDown": False, "tapped": False, "manaProduced": [], "summoningSick": True})
        messages.append(f"soulswap moved {len(moved_to_mana)} creature to mana and summoned {1 if target_index >= 0 else 0}")
    if name == "static warp":
        for target_state in (player_state, opponent_state):
            battle = target_state.get("battle") or []
            keep_uid = next((battle_entry.get("uid") for battle_entry in battle if playmode_is_creature(battle_entry.get("card") or {})), None)
            for battle_entry in battle:
                if battle_entry.get("uid") != keep_uid and playmode_is_creature(battle_entry.get("card") or {}):
                    battle_entry["tapped"] = True
        messages.append("static warp tapped all but one creature for each player")
    if name == "transmogrify":
        target_states = (player_state, opponent_state)
        destroyed_owner = None
        for target_state in target_states:
            destroyed = playmode_destroy_battle_entries(
                state_payload,
                seat_filter=seat if target_state is player_state else opponent_seat,
                limit=1,
                predicate=lambda target_card, _entry: playmode_is_creature(target_card),
            )
            if destroyed:
                destroyed_owner = target_state
                break
        if destroyed_owner is not None:
            revealed_to_grave = []
            while destroyed_owner.get("drawPile"):
                revealed = destroyed_owner["drawPile"].pop(0)
                revealed_card = revealed.get("card") or {}
                if playmode_is_creature(revealed_card) and not playmode_is_evolution(revealed_card):
                    destroyed_owner.setdefault("battle", []).append({**revealed, "faceDown": False, "tapped": False, "manaProduced": [], "summoningSick": True})
                    messages.append(f"transmogrify put {revealed_card.get('name', 'a creature')} into battle")
                    break
                revealed_to_grave.append(revealed)
            destroyed_owner.setdefault("graveyard", []).extend({**grave_entry, "faceDown": False, "tapped": False} for grave_entry in revealed_to_grave)
    if name == "vacuum gel":
        destroyed = playmode_destroy_battle_entries(
            state_payload,
            seat_filter=opponent_seat,
            limit=1,
            predicate=lambda target_card, battle_entry: playmode_is_creature(target_card) and not battle_entry.get("tapped") and any(civ in {"Light", "Nature"} for civ in playmode_card_civilizations(target_card)),
        )
        if destroyed:
            messages.append(f"destroyed untapped light/nature creature: {', '.join(destroyed)}")
    if name == "whisking whirlwind":
        for battle_entry in player_state.get("battle") or []:
            if playmode_is_creature(battle_entry.get("card") or {}):
                battle_entry["tapped"] = False
        messages.append("untapped all your creatures")
    if name == "zombie carnival":
        graveyard = player_state.get("graveyard") or []
        first_creature = next((grave_entry for grave_entry in graveyard if playmode_is_creature(grave_entry.get("card") or {})), None)
        race = (first_creature.get("card") or {}).get("race_label") if first_creature else ""
        moved = playmode_move_zone_entries(
            player_state,
            "graveyard",
            "hand",
            amount=3,
            predicate=lambda target_card, _entry, wanted=race: bool(wanted) and playmode_is_creature(target_card) and target_card.get("race_label") == wanted,
        )
        if moved:
            messages.append(f"returned {race} creatures from graveyard: {', '.join(moved)}")
    return messages


def playmode_resolve_attack_trigger(state_payload: dict, seat: int, entry: dict) -> list[str]:
    card = entry.get("card") or {}
    text = str(card.get("text") or "").lower()
    name = normalize_rule_text(card.get("name"))
    player_state = state_payload.get(playmode_seat_key(seat)) or {}
    opponent_state = state_payload.get(playmode_seat_key(playmode_opponent_seat(seat))) or {}
    messages: list[str] = []
    if "whenever this creature attacks, you may draw a card" in text:
        if playmode_draw_cards(player_state, 1):
            messages.append("drew 1 card")
    if "whenever this creature attacks, your opponent discards a card at random from his hand" in text:
        discarded = playmode_discard_from_hand(opponent_state, 1)
        if discarded:
            messages.append(f"opponent discarded {', '.join(discarded)}")
    if "whenever this creature attacks, reveal the top card of your deck" in text:
        draw_pile = player_state.get("drawPile") or []
        if draw_pile:
            revealed = draw_pile.pop(0)
            revealed_card = revealed.get("card") or {}
            if playmode_is_creature(revealed_card) and not playmode_is_evolution(revealed_card):
                player_state.setdefault("battle", []).append({**revealed, "faceDown": False, "tapped": False})
                messages.append(f"put {revealed_card.get('name', 'a creature')} into battle")
            else:
                player_state.setdefault("hand", []).append({**revealed, "faceDown": False, "tapped": False})
                messages.append(f"put {revealed_card.get('name', 'a card')} into hand")
    if name == "aura pegasus avatar of life":
        playmode_top_to_shield(player_state)
    if "whenever this creature attacks, search your deck" in text:
        candidates = []
        for deck_entry in player_state.get("drawPile") or []:
            deck_card = deck_entry.get("card") or {}
            if "take a water card" in text and "Water" not in playmode_card_civilizations(deck_card):
                continue
            if "take a spell" in text and not playmode_is_spell(deck_card):
                continue
            candidates.append({
                "seat": seat,
                "zone": "drawPile",
                "uid": deck_entry.get("uid"),
                "name": deck_card.get("name") or "Unknown card",
                "image_path": deck_card.get("image_path"),
            })
        playmode_set_pending_choice(state_payload, {
            "kind": "search_deck",
            "effect": "to_hand",
            "controller_seat": seat,
            "message": f"Choose a card from your deck for {card.get('name', 'attack trigger')}.",
            "candidates": candidates[:80],
        })
        if candidates:
            messages.append("waiting for deck search choice")
    return messages


def playmode_resolve_pending_choice(state_payload: dict, payload: PlaymodeActionIn) -> tuple[str, int | None]:
    choice = state_payload.get("pending_choice")
    if not isinstance(choice, dict):
        raise HTTPException(status_code=400, detail="There is no pending choice.")
    controller = int(choice.get("controller_seat") or state_payload.get("active_seat") or 1)
    if payload.seat and payload.seat != controller:
        raise HTTPException(status_code=400, detail="This choice belongs to the other player.")
    kind = choice.get("kind")
    if payload.action == "pass_pending":
        if kind in {"blocker", "attack_response"}:
            pending_attack = choice.get("pending_attack") or {}
            state_payload["pending_attack"] = pending_attack
            state_payload.pop("pending_choice", None)
            if kind == "attack_response":
                return playmode_resolve_pending_attack_target(state_payload, pending_attack)
            return "No blocker chosen. Choose a shield to break.", None
        state_payload.pop("pending_choice", None)
        return "Choice skipped.", None
    target_uid = payload.target_uid or payload.uid
    candidates = choice.get("candidates") or []
    selected = next((candidate for candidate in candidates if candidate.get("uid") == target_uid), None)
    if not selected:
        raise HTTPException(status_code=400, detail="Invalid choice target.")
    target_seat = int(selected.get("seat") or controller)
    target_state = state_payload.get(playmode_seat_key(target_seat)) or {}
    if kind == "choose_battle_target":
        effect = choice.get("effect")
        index, entry = playmode_find_zone_entry(target_state, "battle", target_uid)
        if index == -1 or not entry:
            raise HTTPException(status_code=404, detail="Target is no longer available.")
        card_name = (entry.get("card") or {}).get("name") or "target"
        if effect == "destroy":
            target_state["battle"].pop(index)
            target_state.setdefault("graveyard", []).extend(playmode_stack_entries(entry))
            state_payload.pop("pending_choice", None)
            return f"Destroyed {card_name}.", None
        if effect == "bounce":
            target_state["battle"].pop(index)
            target_state.setdefault("hand", []).extend(playmode_stack_entries(entry))
            state_payload.pop("pending_choice", None)
            return f"Returned {card_name} to hand.", None
        if effect == "tap":
            entry["tapped"] = True
            state_payload.pop("pending_choice", None)
            return f"Tapped {card_name}.", None
    if kind == "search_deck":
        player_state = state_payload.get(playmode_seat_key(controller)) or {}
        index, entry = playmode_find_zone_entry(player_state, "drawPile", target_uid)
        if index == -1 or not entry:
            raise HTTPException(status_code=404, detail="Searched card is no longer available.")
        player_state["drawPile"].pop(index)
        player_state.setdefault("hand", []).append({**entry, "faceDown": False, "tapped": False})
        playmode_shuffle_player_deck(player_state)
        state_payload.pop("pending_choice", None)
        return f"Searched {entry.get('card', {}).get('name', 'a card')} into hand.", None
    if kind in {"blocker", "attack_response"}:
        blocker_state = state_payload.get(playmode_seat_key(target_seat)) or {}
        index, blocker = playmode_find_zone_entry(blocker_state, "battle", target_uid)
        if index == -1 or not blocker:
            raise HTTPException(status_code=404, detail="Blocker is no longer available.")
        blocker["tapped"] = True
        pending_attack = choice.get("pending_attack") or {}
        attacker_seat = int(pending_attack.get("seat") or state_payload.get("active_seat") or 1)
        attacker_state = state_payload.get(playmode_seat_key(attacker_seat)) or {}
        _, attacker = playmode_find_zone_entry(attacker_state, "battle", pending_attack.get("uid"))
        if attacker:
            attacker_power = playmode_entry_power_value(attacker, attacking=True)
            blocker_power = playmode_entry_power_value(blocker)
            attacker_destroyed = attacker_power <= blocker_power or playmode_entry_has_slayer(blocker)
            blocker_destroyed = blocker_power <= attacker_power or playmode_entry_has_slayer(attacker)
            if attacker_destroyed:
                attacker_state["battle"] = [entry for entry in (attacker_state.get("battle") or []) if entry.get("uid") != attacker.get("uid")]
                attacker_state.setdefault("graveyard", []).extend(playmode_stack_entries(attacker))
            if blocker_destroyed:
                blocker_state["battle"] = [entry for entry in (blocker_state.get("battle") or []) if entry.get("uid") != blocker.get("uid")]
                blocker_state.setdefault("graveyard", []).extend(playmode_stack_entries(blocker))
        state_payload.pop("pending_choice", None)
        state_payload.pop("pending_attack", None)
        return f"Blocked with {blocker.get('card', {}).get('name', 'a blocker')}.", None
    raise HTTPException(status_code=400, detail="Unsupported pending choice.")


def playmode_available_blockers(state_payload: dict, defender_seat: int) -> list[dict]:
    defender_state = state_payload.get(playmode_seat_key(defender_seat)) or {}
    return [
        {
            "seat": defender_seat,
            "zone": "battle",
            "uid": blocker.get("uid"),
            "name": (blocker.get("card") or {}).get("name") or "Blocker",
            "image_path": (blocker.get("card") or {}).get("image_path"),
        }
        for blocker in (defender_state.get("battle") or [])
        if playmode_is_creature(blocker.get("card") or {}) and (playmode_has_keyword(blocker.get("card") or {}, "blocker") or blocker.get("temporaryBlocker")) and not blocker.get("tapped")
    ]


def playmode_set_attack_response_choice(state_payload: dict, pending_attack: dict) -> tuple[str, int | None]:
    attacker_seat = int(pending_attack.get("seat") or state_payload.get("active_seat") or 1)
    defender_seat = playmode_opponent_seat(attacker_seat)
    attacker_state = state_payload.get(playmode_seat_key(attacker_seat)) or {}
    _, attacker = playmode_find_zone_entry(attacker_state, "battle", pending_attack.get("uid"))
    attacker_name = (attacker.get("card") or {}).get("name") if attacker else "the attacker"
    target_kind = pending_attack.get("target_kind")
    target_label = "a shield"
    if target_kind == "creature":
        defender_state = state_payload.get(playmode_seat_key(defender_seat)) or {}
        _, defender = playmode_find_zone_entry(defender_state, "battle", pending_attack.get("target_uid"))
        target_label = (defender.get("card") or {}).get("name") if defender else "a creature"
    elif target_kind == "direct":
        target_label = "the opponent directly"
    candidates = [] if playmode_entry_unblockable(attacker or {}, target_kind) else playmode_available_blockers(state_payload, defender_seat)
    state_payload["pending_attack"] = pending_attack
    state_payload["pending_choice"] = {
        "kind": "attack_response",
        "controller_seat": defender_seat,
        "message": f"{attacker_name} is attacking {target_label}. Choose a blocker, or pass.",
        "pending_attack": pending_attack,
        "candidates": candidates,
    }
    return f"Player {attacker_seat} targeted {target_label}. Waiting for defender response.", None


def playmode_resolve_pending_attack_target(state_payload: dict, pending_attack: dict) -> tuple[str, int | None]:
    target_kind = pending_attack.get("target_kind")
    if target_kind == "shield":
        return playmode_resolve_shield_attack(state_payload, pending_attack)
    if target_kind == "creature":
        return playmode_resolve_creature_attack(state_payload, pending_attack)
    if target_kind == "direct":
        attacker_seat = int(pending_attack.get("seat") or state_payload.get("active_seat") or 1)
        attacker_state = state_payload.get(playmode_seat_key(attacker_seat)) or {}
        defender_state = state_payload.get(playmode_seat_key(playmode_opponent_seat(attacker_seat))) or {}
        _, attacker = playmode_find_zone_entry(attacker_state, "battle", pending_attack.get("uid"))
        if attacker and not playmode_can_attack_players(attacker, defender_state):
            raise HTTPException(status_code=400, detail="This creature cannot attack players.")
        state_payload.pop("pending_attack", None)
        return f"Player {attacker_seat} attacked directly and won.", attacker_seat
    raise HTTPException(status_code=400, detail="Choose a target for the attack first.")


def playmode_choose_computer_blocker(state_payload: dict, choice: dict) -> dict | None:
    candidates = choice.get("candidates") or []
    if not candidates:
        return None
    pending_attack = choice.get("pending_attack") or {}
    attacker_seat = int(pending_attack.get("seat") or playmode_opponent_seat(2))
    attacker_state = state_payload.get(playmode_seat_key(attacker_seat)) or {}
    _, attacker = playmode_find_zone_entry(attacker_state, "battle", pending_attack.get("uid"))
    attacker_power = playmode_entry_power_value(attacker or {}, attacking=True)
    target_kind = pending_attack.get("target_kind")
    scored: list[tuple[int, int, dict]] = []
    for candidate in candidates:
        blocker_state = state_payload.get(playmode_seat_key(int(candidate.get("seat") or 2))) or {}
        _, blocker = playmode_find_zone_entry(blocker_state, "battle", candidate.get("uid"))
        blocker_power = playmode_entry_power_value(blocker or {})
        if target_kind == "direct":
            score = 100000 + blocker_power
        elif blocker_power >= attacker_power:
            score = 50000 + blocker_power - attacker_power
        else:
            score = blocker_power - attacker_power
        scored.append((score, blocker_power, candidate))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not scored:
        return None
    best_score, _blocker_power, candidate = scored[0]
    if target_kind != "direct" and best_score < 0:
        return None
    return candidate


def playmode_resolve_computer_pending_choice(state_payload: dict) -> tuple[list[str], int | None]:
    choice = state_payload.get("pending_choice")
    if not isinstance(choice, dict) or int(choice.get("controller_seat") or 0) != 2:
        return [], None
    kind = choice.get("kind")
    messages: list[str] = []
    winner_seat: int | None = None
    if kind in {"attack_response", "blocker"}:
        candidate = playmode_choose_computer_blocker(state_payload, choice)
        action = PlaymodeActionIn(profile_id=0, action="choose_pending", seat=2, target_seat=2, target_uid=candidate.get("uid")) if candidate else PlaymodeActionIn(profile_id=0, action="pass_pending", seat=2)
        message, winner_seat = playmode_resolve_pending_choice(state_payload, action)
        messages.append(f"Computer {'blocked' if candidate else 'declined to block'}. {message}")
        return messages, winner_seat
    candidates = choice.get("candidates") or []
    if candidates:
        candidate = candidates[0]
        message, winner_seat = playmode_resolve_pending_choice(
            state_payload,
            PlaymodeActionIn(profile_id=0, action="choose_pending", seat=2, target_seat=candidate.get("seat"), target_uid=candidate.get("uid")),
        )
    else:
        message, winner_seat = playmode_resolve_pending_choice(state_payload, PlaymodeActionIn(profile_id=0, action="pass_pending", seat=2))
    messages.append(f"Computer resolved choice. {message}")
    return messages, winner_seat


def playmode_resolve_shield_attack(state_payload: dict, pending_attack: dict) -> tuple[str, int | None]:
    attacker_seat = int(pending_attack.get("seat") or state_payload.get("active_seat") or 1)
    target_seat = int(pending_attack.get("target_seat") or playmode_opponent_seat(attacker_seat))
    if target_seat != playmode_opponent_seat(attacker_seat):
        raise HTTPException(status_code=400, detail="Choose an opponent shield.")
    target_state = state_payload.get(playmode_seat_key(target_seat)) or {}
    shields = target_state.get("shields") or []
    if not shields:
        state_payload.pop("pending_attack", None)
        return f"Player {attacker_seat} attacked directly and won.", attacker_seat
    chosen_index = next((index for index, shield in enumerate(shields) if shield.get("uid") == pending_attack.get("target_uid")), 0)
    breaks = max(1, int(pending_attack.get("breaks_remaining") or 1))
    broken_names = []
    trigger_names = []
    for _ in range(min(breaks, len(shields))):
        index = min(chosen_index, len(shields) - 1)
        shield = shields.pop(index)
        card = shield.get("card") or {}
        broken_names.append(card.get("name") or "a shield")
        revealed = {**shield, "faceDown": False, "tapped": False, "manaProduced": []}
        if playmode_is_spell(card) and playmode_has_keyword(card, "shield trigger"):
            trigger_names.append(card.get("name") or "a shield trigger")
            playmode_resolve_spell_effect(state_payload, target_seat, revealed)
            target_state.setdefault("graveyard", []).append(revealed)
        elif playmode_is_creature(card) and playmode_has_keyword(card, "shield trigger"):
            trigger_names.append(card.get("name") or "a shield trigger")
            target_state.setdefault("battle", []).append(revealed)
            playmode_resolve_enter_battle(state_payload, target_seat, revealed)
        else:
            target_state.setdefault("hand", []).append(revealed)
        chosen_index = 0
    state_payload.pop("pending_attack", None)
    trigger_suffix = f" Shield Trigger! {', '.join(trigger_names)} triggered." if trigger_names else ""
    return f"Player {attacker_seat} broke {', '.join(broken_names)}.{trigger_suffix}", None


def playmode_resolve_creature_attack(state_payload: dict, pending_attack: dict) -> tuple[str, int | None]:
    attacker_seat = int(pending_attack.get("seat") or state_payload.get("active_seat") or 1)
    target_seat = int(pending_attack.get("target_seat") or playmode_opponent_seat(attacker_seat))
    if target_seat != playmode_opponent_seat(attacker_seat):
        raise HTTPException(status_code=400, detail="Choose an opponent creature.")
    attacker_state = state_payload.get(playmode_seat_key(attacker_seat)) or {}
    defender_state = state_payload.get(playmode_seat_key(target_seat)) or {}
    attacker_index, attacker = playmode_find_zone_entry(attacker_state, "battle", pending_attack.get("uid"))
    defender_index, defender = playmode_find_zone_entry(defender_state, "battle", pending_attack.get("target_uid"))
    if attacker_index == -1 or not attacker:
        raise HTTPException(status_code=404, detail="Attacking creature not found.")
    if defender_index == -1 or not defender:
        raise HTTPException(status_code=404, detail="Target creature not found.")
    if not playmode_can_be_attacked(defender, attacker):
        raise HTTPException(status_code=400, detail="This creature cannot be attacked by that attacker.")
    if not defender.get("tapped") and not defender.get("temporaryAttackable") and not playmode_can_attack_untapped(attacker):
        raise HTTPException(status_code=400, detail="Only tapped creatures can be attacked.")
    attacker_power = playmode_entry_power_value(attacker, attacking=True)
    defender_power = playmode_entry_power_value(defender)
    attacker_name = (attacker.get("card") or {}).get("name") or "attacker"
    defender_name = (defender.get("card") or {}).get("name") or "defender"
    attacker_destroyed = attacker_power <= defender_power or playmode_entry_has_slayer(defender)
    defender_destroyed = defender_power <= attacker_power or playmode_entry_has_slayer(attacker)
    if attacker_destroyed:
        attacker_state["battle"] = [entry for entry in (attacker_state.get("battle") or []) if entry.get("uid") != attacker.get("uid")]
        attacker_state.setdefault("graveyard", []).extend(playmode_stack_entries(attacker))
    if defender_destroyed:
        defender_state["battle"] = [entry for entry in (defender_state.get("battle") or []) if entry.get("uid") != defender.get("uid")]
        defender_state.setdefault("graveyard", []).extend(playmode_stack_entries(defender))
    if defender_destroyed and not attacker_destroyed and attacker.get("temporaryUntapOnWin"):
        attacker["tapped"] = False
    state_payload.pop("pending_attack", None)
    if defender_destroyed and not attacker_destroyed:
        result = f"{defender_name} was destroyed."
    elif attacker_destroyed and not defender_destroyed:
        result = f"{attacker_name} was destroyed."
    else:
        result = "Both creatures were destroyed."
    return f"{attacker_name} attacked {defender_name}. {attacker_power} vs {defender_power}. {result}", None


def playmode_advance_phase(state_payload: dict) -> tuple[str, int | None]:
    if state_payload.get("pending_choice"):
        return "Resolve the pending choice first.", None
    phase = str(state_payload.get("current_phase") or "untap")
    active_seat = int(state_payload.get("active_seat") or 1)
    player_state = state_payload.get(playmode_seat_key(active_seat)) or {}
    if phase == "untap":
        for zone_name in ("mana", "battle"):
            for entry in player_state.get(zone_name) or []:
                entry["tapped"] = False
                entry["manaProduced"] = []
        player_state["manaPool"] = []
        player_state["chargedThisTurn"] = False
        state_payload["current_phase"] = "draw"
        return f"Player {active_seat} resolved untap.", None
    if phase == "draw":
        if (
            int(state_payload.get("current_turn") or 1) == 1
            and active_seat == int(state_payload.get("starting_seat") or active_seat)
            and not state_payload.get("first_draw_skipped")
        ):
            state_payload["first_draw_skipped"] = True
            state_payload["current_phase"] = "charge"
            return f"Player {active_seat} skipped their first draw.", None
        draw_pile = player_state.get("drawPile") or []
        if not draw_pile:
            winner = playmode_opponent_seat(active_seat)
            state_payload["winner_seat"] = winner
            return f"Player {active_seat} decked out.", winner
        card = draw_pile.pop(0)
        player_state.setdefault("hand", []).append({**card, "faceDown": False, "tapped": False})
        state_payload["current_phase"] = "charge"
        return f"Player {active_seat} drew a card.", None
    if phase == "charge":
        state_payload["current_phase"] = "play"
        return f"Player {active_seat} moved to play phase.", None
    if phase == "play":
        state_payload["current_phase"] = "attack"
        return f"Player {active_seat} moved to attack phase.", None
    if phase == "attack":
        state_payload.pop("pending_attack", None)
        state_payload["current_phase"] = "end"
        playmode_clear_temporary_effects(player_state)
        return f"Player {active_seat} finished attack phase.", None
    previous_seat = active_seat
    next_seat = playmode_opponent_seat(active_seat)
    state_payload["active_seat"] = next_seat
    state_payload["current_turn"] = int(state_payload.get("current_turn") or 1) + 1
    state_payload["current_phase"] = "untap"
    state_payload.pop("pending_attack", None)
    next_state = state_payload.get(playmode_seat_key(next_seat)) or {}
    next_state["manaPool"] = []
    next_state["chargedThisTurn"] = False
    return f"Player {previous_seat} passed the turn to Player {next_seat}.", None


def playmode_auto_resolve_mandatory_phases(state_payload: dict) -> tuple[list[str], int | None]:
    messages: list[str] = []
    winner_seat: int | None = None
    safety = 0
    while (
        str(state_payload.get("current_phase") or "untap") in {"untap", "draw", "end"}
        and not state_payload.get("pending_choice")
        and not state_payload.get("winner_seat")
        and safety < 8
    ):
        safety += 1
        message, winner_seat = playmode_advance_phase(state_payload)
        messages.append(message)
        if winner_seat:
            break
    return messages, winner_seat


def playmode_apply_action(state_payload: dict, payload: PlaymodeActionIn) -> tuple[str, int | None]:
    action = payload.action
    active_seat = int(state_payload.get("active_seat") or 1)
    phase = str(state_payload.get("current_phase") or "untap")
    if action == "concede":
        conceding_seat = payload.seat or active_seat
        if conceding_seat not in {1, 2}:
            raise HTTPException(status_code=400, detail="Choose the conceding player.")
        winner = playmode_opponent_seat(conceding_seat)
        state_payload["winner_seat"] = winner
        state_payload["conceded_seat"] = conceding_seat
        state_payload.pop("pending_choice", None)
        state_payload.pop("pending_attack", None)
        return f"Player {conceding_seat} conceded. Player {winner} wins.", winner
    if action in {"choose_pending", "pass_pending"}:
        return playmode_resolve_pending_choice(state_payload, payload)
    if state_payload.get("pending_choice") and action != "advance_phase":
        raise HTTPException(status_code=400, detail="Resolve the pending choice first.")
    if action == "advance_phase":
        return playmode_advance_phase(state_payload)
    seat = payload.seat or active_seat
    if seat != active_seat and action not in {"break_shield", "battle_creature"}:
        raise HTTPException(status_code=400, detail="Only the active player's cards can be controlled.")
    player_state = state_payload.get(playmode_seat_key(seat)) or {}

    if action == "tap_mana":
        index, entry = playmode_find_zone_entry(player_state, "mana", payload.uid)
        if index == -1 or not entry:
            raise HTTPException(status_code=404, detail="Mana card not found.")
        if entry.get("tapped"):
            entry["tapped"] = False
            entry["manaProduced"] = []
            player_state["manaPool"] = [
                pool_entry for pool_entry in (player_state.get("manaPool") or [])
                if not isinstance(pool_entry, dict) or pool_entry.get("sourceUid") != entry.get("uid")
            ]
            return f"Player {seat} readied mana.", None
        civilizations = playmode_card_civilizations(entry.get("card") or {})
        chosen = payload.civilization if payload.civilization in civilizations else (civilizations[0] if civilizations else None)
        entry["tapped"] = True
        entry["manaProduced"] = [chosen] if chosen else []
        player_state["manaPool"] = [
            pool_entry for pool_entry in (player_state.get("manaPool") or [])
            if not isinstance(pool_entry, dict) or pool_entry.get("sourceUid") != entry.get("uid")
        ]
        if chosen:
            player_state.setdefault("manaPool", []).append({
                "id": f"{entry.get('uid')}-{chosen}",
                "sourceUid": entry.get("uid"),
                "civilization": chosen,
            })
        pool_size = len(player_state.get("manaPool") or [])
        mana_label = f"{chosen} mana" if chosen else "mana"
        return f"Player {seat} tapped {entry.get('card', {}).get('name', 'a card')} for {mana_label}. Mana pool: {pool_size}.", None

    if action == "charge":
        if phase != "charge":
            raise HTTPException(status_code=400, detail="Cards can only be charged during charge phase.")
        if player_state.get("chargedThisTurn"):
            raise HTTPException(status_code=400, detail="You can only charge one card each turn.")
        index, entry = playmode_find_zone_entry(player_state, "hand", payload.uid)
        if index == -1 or not entry:
            raise HTTPException(status_code=404, detail="Hand card not found.")
        player_state["hand"].pop(index)
        player_state.setdefault("mana", []).append({
            **entry,
            "faceDown": False,
            "tapped": len(playmode_card_civilizations(entry.get("card") or {})) > 1,
            "manaProduced": [],
        })
        player_state["chargedThisTurn"] = True
        state_payload["current_phase"] = "play"
        return f"Player {seat} charged {entry.get('card', {}).get('name', 'a card')}.", None

    if action == "play_card":
        if phase != "play":
            raise HTTPException(status_code=400, detail="Cards can only be played during play phase.")
        index, entry = playmode_find_zone_entry(player_state, "hand", payload.uid)
        if index == -1 or not entry:
            raise HTTPException(status_code=404, detail="Hand card not found.")
        card = entry.get("card") or {}
        if not card.get("id"):
            raise HTTPException(status_code=400, detail="Card data is not loaded yet.")
        alcadeias_active = any(
            normalize_rule_text((battle_entry.get("card") or {}).get("name")) == "alcadeias lord of spirits"
            for seat_key in ("player_one", "player_two")
            for battle_entry in (state_payload.get(seat_key, {}).get("battle") or [])
        )
        if alcadeias_active:
            if playmode_is_spell(card) and not playmode_is_light(card):
                raise HTTPException(status_code=400, detail="Alcadeias prevents non-light spells from being cast.")
        if not playmode_consume_mana(player_state, card):
            raise HTTPException(status_code=400, detail="Not enough tapped mana for this card.")
        player_state["hand"].pop(index)
        if playmode_is_spell(card):
            effect_messages = playmode_resolve_spell_effect(state_payload, seat, entry)
            target_zone = "mana" if playmode_has_keyword(card, "charger") else "graveyard"
            player_state.setdefault(target_zone, []).append({**entry, "faceDown": False, "tapped": False, "manaProduced": []})
            if not effect_messages:
                effect_messages = ["resolved with no automated effect"]
            suffix = f" ({'; '.join(effect_messages)})" if effect_messages else ""
            return f"Player {seat} cast {card.get('name', 'a spell')}.{suffix}", None
        battle_entry = {**entry, "faceDown": False, "tapped": False, "manaProduced": []}
        if playmode_is_evolution(card):
            if playmode_is_vortex(card):
                target_indexes = playmode_find_vortex_targets(player_state, card)
            else:
                target_index = playmode_find_evolution_target(player_state, card)
                target_indexes = [target_index] if target_index is not None else None
            if not target_indexes:
                raise HTTPException(status_code=400, detail="No valid evolution target is in your battle zone.")
            underlays = []
            for target_index in sorted(target_indexes, reverse=True):
                base = player_state["battle"].pop(target_index)
                underlays.extend(playmode_stack_entries(base))
            battle_entry["underlays"] = underlays
        battle_entry["summoningSick"] = playmode_is_creature(card) and not playmode_is_evolution(card) and not playmode_has_keyword(card, "speed attacker")
        player_state.setdefault("battle", []).append(battle_entry)
        messages = playmode_resolve_enter_battle(state_payload, seat, battle_entry)
        suffix = f" ({'; '.join(messages)})" if messages else ""
        return f"Player {seat} played {card.get('name', 'a creature')}.{suffix}", None

    if action == "attack":
        if phase != "attack":
            raise HTTPException(status_code=400, detail="Creatures can only attack during attack phase.")
        index, entry = playmode_find_zone_entry(player_state, "battle", payload.uid)
        if index == -1 or not entry:
            raise HTTPException(status_code=404, detail="Battle zone card not found.")
        card = entry.get("card") or {}
        if not playmode_is_creature(card):
            raise HTTPException(status_code=400, detail="Only creatures can attack.")
        if playmode_has_keyword(card, "blocker"):
            raise HTTPException(status_code=400, detail="Blocker creatures cannot attack.")
        if entry.get("tapped"):
            raise HTTPException(status_code=400, detail="This creature is already tapped.")
        if entry.get("summoningSick"):
            raise HTTPException(status_code=400, detail="This creature has summoning sickness.")
        entry["tapped"] = True
        trigger_messages = playmode_resolve_attack_trigger(state_payload, seat, entry)
        opponent_state = state_payload.get(playmode_seat_key(playmode_opponent_seat(seat))) or {}
        pending_attack = {
            "seat": seat,
            "uid": entry.get("uid"),
            "breaks_remaining": playmode_breaker_count(card, entry),
        }
        if not opponent_state.get("shields"):
            if not playmode_can_attack_players(entry, opponent_state):
                raise HTTPException(status_code=400, detail="This creature cannot attack players.")
            pending_attack["target_kind"] = "direct"
            return playmode_set_attack_response_choice(state_payload, pending_attack)
        state_payload["pending_attack"] = pending_attack
        suffix = f" ({'; '.join(trigger_messages)})" if trigger_messages else ""
        return f"Player {seat} attacked with {card.get('name', 'a creature')}.{suffix} Choose an opponent shield or tapped creature.", None

    if action == "break_shield":
        pending = state_payload.get("pending_attack") or {}
        if not pending.get("uid") and not pending.get("effect_can_break_shield"):
            raise HTTPException(status_code=400, detail="You can only break shields with a successful attack or a card effect.")
        if pending.get("target_kind") and pending.get("target_kind") != "shield":
            raise HTTPException(status_code=400, detail="This attack is already targeting something else.")
        attacker_seat = int(pending.get("seat") or active_seat)
        target_seat = payload.target_seat or payload.seat
        if target_seat != playmode_opponent_seat(attacker_seat):
            raise HTTPException(status_code=400, detail="Choose an opponent shield.")
        target_state = state_payload.get(playmode_seat_key(target_seat)) or {}
        shields = target_state.get("shields") or []
        attacker_state = state_payload.get(playmode_seat_key(attacker_seat)) or {}
        _, attacker = playmode_find_zone_entry(attacker_state, "battle", pending.get("uid"))
        if attacker and not playmode_can_attack_players(attacker, target_state):
            raise HTTPException(status_code=400, detail="This creature cannot attack players.")
        if not shields:
            state_payload.pop("pending_attack", None)
            return f"Player {attacker_seat} attacked directly and won.", attacker_seat
        if payload.target_uid and not any(shield.get("uid") == payload.target_uid for shield in shields):
            raise HTTPException(status_code=404, detail="Shield is no longer available.")
        pending.update({
            "target_kind": "shield",
            "target_seat": target_seat,
            "target_uid": payload.target_uid,
        })
        return playmode_set_attack_response_choice(state_payload, pending)

    if action == "battle_creature":
        pending = state_payload.get("pending_attack") or {}
        attacker_seat = int(pending.get("seat") or active_seat)
        target_seat = payload.target_seat or payload.seat
        if target_seat != playmode_opponent_seat(attacker_seat):
            raise HTTPException(status_code=400, detail="Choose an opponent creature.")
        attacker_state = state_payload.get(playmode_seat_key(attacker_seat)) or {}
        defender_state = state_payload.get(playmode_seat_key(target_seat)) or {}
        attacker_index, attacker = playmode_find_zone_entry(attacker_state, "battle", pending.get("uid"))
        defender_index, defender = playmode_find_zone_entry(defender_state, "battle", payload.target_uid)
        if attacker_index == -1 or not attacker:
            raise HTTPException(status_code=404, detail="Attacking creature not found.")
        if defender_index == -1 or not defender:
            raise HTTPException(status_code=404, detail="Target creature not found.")
        if not playmode_can_be_attacked(defender, attacker):
            raise HTTPException(status_code=400, detail="This creature cannot be attacked by that attacker.")
        if not defender.get("tapped") and not defender.get("temporaryAttackable") and not playmode_can_attack_untapped(attacker):
            raise HTTPException(status_code=400, detail="Only tapped creatures can be attacked.")
        pending.update({
            "target_kind": "creature",
            "target_seat": target_seat,
            "target_uid": payload.target_uid,
        })
        return playmode_set_attack_response_choice(state_payload, pending)

    raise HTTPException(status_code=400, detail="Unsupported Playmode action.")


def playmode_take_computer_turn(state_payload: dict) -> tuple[list[str], int | None]:
    messages: list[str] = []
    winner_seat: int | None = None
    steps = 0
    while int(state_payload.get("active_seat") or 1) == 2 and not winner_seat and steps < 40:
        steps += 1
        if state_payload.get("pending_choice"):
            if int((state_payload.get("pending_choice") or {}).get("controller_seat") or 0) == 2:
                choice_messages, winner_seat = playmode_resolve_computer_pending_choice(state_payload)
                messages.extend(choice_messages)
                continue
            break
        phase = str(state_payload.get("current_phase") or "untap")
        computer_state = state_payload.get("player_two") or {}
        try:
            if phase in {"untap", "draw"}:
                message, winner_seat = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="advance_phase", seat=2))
                messages.append(message)
                continue
            if phase == "charge":
                hand = computer_state.get("hand") or []
                if hand:
                    message, winner_seat = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="charge", seat=2, zone="hand", uid=hand[0].get("uid")))
                else:
                    message, winner_seat = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="advance_phase", seat=2))
                messages.append(message)
                continue
            if phase == "play":
                for mana_card in list(computer_state.get("mana") or []):
                    if not mana_card.get("tapped"):
                        try:
                            message, _ = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="tap_mana", seat=2, zone="mana", uid=mana_card.get("uid")))
                            messages.append(message)
                        except HTTPException:
                            continue
                played = False
                for hand_card in list(computer_state.get("hand") or []):
                    try:
                        message, winner_seat = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="play_card", seat=2, zone="hand", uid=hand_card.get("uid")))
                        messages.append(message)
                        played = True
                        break
                    except HTTPException:
                        continue
                if not played:
                    message, winner_seat = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="advance_phase", seat=2))
                    messages.append(message)
                continue
            if phase == "attack":
                attacked = False
                for battle_card in list(computer_state.get("battle") or []):
                    if battle_card.get("tapped") or battle_card.get("summoningSick"):
                        continue
                    try:
                        message, winner_seat = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="attack", seat=2, zone="battle", uid=battle_card.get("uid")))
                        messages.append(message)
                        attacked = True
                        if winner_seat or state_payload.get("pending_choice"):
                            break
                        pending = state_payload.get("pending_attack")
                        opponent_shields = (state_payload.get("player_one") or {}).get("shields") or []
                        if pending and opponent_shields:
                            message, winner_seat = playmode_apply_action(
                                state_payload,
                                PlaymodeActionIn(profile_id=0, action="break_shield", seat=2, target_seat=1, target_uid=opponent_shields[0].get("uid")),
                            )
                            messages.append(message)
                    except HTTPException:
                        continue
                if state_payload.get("pending_choice") or winner_seat:
                    break
                message, winner_seat = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="advance_phase", seat=2))
                messages.append(message)
                if not attacked:
                    continue
                continue
            message, winner_seat = playmode_apply_action(state_payload, PlaymodeActionIn(profile_id=0, action="advance_phase", seat=2))
            messages.append(message)
        except HTTPException as error:
            messages.append(str(error.detail))
            break
    return messages, winner_seat


def maybe_run_computer_turn(match: PlayMatch, db: Session) -> None:
    if match.mode != "computer" or match.status != "active" or match.active_seat != 2:
        return
    state_payload = json.loads(match.state_json or "{}")
    if not state_payload.get("computer_opponent"):
        return
    playmode_hydrate_state_cards(state_payload, db)
    messages, winner_seat = playmode_take_computer_turn(state_payload)
    if not messages and winner_seat is None:
        return
    summary = " ".join(messages[-4:]) if messages else "Computer turn resolved."
    state_payload["last_move_summary"] = summary
    now = datetime.utcnow()
    auto_messages, auto_winner = playmode_auto_resolve_mandatory_phases(state_payload)
    if auto_messages:
        state_payload["last_move_summary"] = " ".join((messages + auto_messages)[-4:])
        playmode_append_events(state_payload, auto_messages)
    if auto_winner:
        winner_seat = auto_winner
    playmode_append_events(state_payload, messages)
    match.current_turn = int(state_payload.get("current_turn") or match.current_turn or 1)
    match.active_seat = int(state_payload.get("active_seat") or match.active_seat or 1)
    match.updated_at = now
    match.state_json = playmode_dump_state(state_payload)
    if winner_seat in {1, 2}:
        match.status = "finished"
        match.winner_profile_id = match.player_one_profile_id if winner_seat == 1 else None
    db.commit()


def maybe_auto_resolve_playmode_match(match: PlayMatch, db: Session) -> None:
    if match.status != "active":
        return
    state_payload = json.loads(match.state_json or "{}")
    messages, winner_seat = playmode_auto_resolve_mandatory_phases(state_payload)
    if not messages and winner_seat is None:
        return
    match.current_turn = int(state_payload.get("current_turn") or match.current_turn or 1)
    match.active_seat = int(state_payload.get("active_seat") or match.active_seat or 1)
    match.state_json = playmode_dump_state(state_payload)
    match.updated_at = datetime.utcnow()
    state_payload["last_move_summary"] = " ".join(messages[-4:])
    match.state_json = playmode_dump_state(state_payload)
    if winner_seat in {1, 2}:
        match.status = "finished"
        match.winner_profile_id = match.player_one_profile_id if winner_seat == 1 else match.player_two_profile_id
    db.commit()


def ensure_owned_deck(db: Session, public_id: str, profile_id: int) -> Deck:
    deck = db.scalar(
        select(Deck)
        .where(Deck.public_id == public_id)
        .options(joinedload(Deck.items).joinedload(DeckItem.card))
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    if deck.profile_id != profile_id:
        raise HTTPException(status_code=403, detail="You can only start Playmode with your own saved deck.")
    if not deck.items:
        raise HTTPException(status_code=400, detail="This deck has no cards.")
    card_total = sum(item.quantity for item in deck.items)
    if card_total < 40:
        raise HTTPException(status_code=400, detail="Playmode requires a deck with at least 40 cards.")
    return deck


def playmode_card_view(entry: dict, *, face_down_override: bool | None = None) -> PlaymodeCardViewOut:
    card = entry.get("card") or {}
    face_down = entry.get("faceDown", False) if face_down_override is None else face_down_override
    return PlaymodeCardViewOut(
        uid=entry.get("uid", ""),
        id=None if face_down else card.get("id"),
        name="Hidden card" if face_down else (card.get("name") or "Unknown card"),
        civilizations=[] if face_down else list(card.get("civilizations") or []),
        cost=0 if face_down else int(card.get("cost") or 0),
        type="" if face_down else (card.get("type") or ""),
        race_label="" if face_down else (card.get("race_label") or ""),
        text="" if face_down else (card.get("text") or ""),
        power=None if face_down else card.get("power"),
        image_path=None if face_down else card.get("image_path"),
        face_down=face_down,
        tapped=bool(entry.get("tapped")),
        mana_produced=[] if face_down else list(entry.get("manaProduced") or []),
        underlay_count=len(entry.get("underlays") or []),
    )


def playmode_zone_view(player_state: dict, *, hide_hand: bool) -> PlaymodeZoneViewOut:
    hand_entries = list(player_state.get("hand") or [])
    return PlaymodeZoneViewOut(
        hand_count=len(hand_entries),
        deck_count=len(player_state.get("drawPile") or []),
        shield_count=len(player_state.get("shields") or []),
        graveyard_count=len(player_state.get("graveyard") or []),
        hand=[] if hide_hand else [playmode_card_view(entry) for entry in hand_entries],
        shields=[playmode_card_view(entry, face_down_override=bool(entry.get("faceDown", True))) for entry in (player_state.get("shields") or [])],
        mana=[playmode_card_view(entry) for entry in (player_state.get("mana") or [])],
        battle=[playmode_card_view(entry) for entry in (player_state.get("battle") or [])],
        graveyard=[playmode_card_view(entry) for entry in (player_state.get("graveyard") or [])],
        mana_pool=[entry for entry in (player_state.get("manaPool") or []) if isinstance(entry, str)] or [entry.get("civilization") for entry in (player_state.get("manaPool") or []) if isinstance(entry, dict) and entry.get("civilization")],
    )


def playmode_match_summary(match: PlayMatch, viewer_profile_id: int | None = None) -> PlaymodeMatchSummaryOut:
    payload = json.loads(match.state_json or "{}")
    viewer_seat = 1 if viewer_profile_id == match.player_one_profile_id else (2 if viewer_profile_id == match.player_two_profile_id else None)
    player_two_username = match.player_two_profile.username if match.player_two_profile else (payload.get("computer_username") if payload.get("computer_opponent") else None)
    return PlaymodeMatchSummaryOut(
        public_id=match.public_id,
        mode=match.mode,
        status=match.status,
        current_turn=match.current_turn,
        active_seat=match.active_seat,
        viewer_seat=viewer_seat,
        needs_action=bool(match.status == "active" and viewer_seat and match.active_seat == viewer_seat),
        current_phase=str(payload.get("current_phase") or "untap"),
        deadline_label=playmode_deadline_label(match.turn_deadline_at),
        player_one_username=match.player_one_profile.username if match.player_one_profile else None,
        player_two_username=player_two_username,
        player_one_deck_title=match.player_one_deck.title if match.player_one_deck else None,
        player_two_deck_title=match.player_two_deck.title if match.player_two_deck else None,
    )


def playmode_match_view(match: PlayMatch, viewer_profile_id: int | None, db: Session, *, admin_override: bool = False) -> PlaymodeMatchViewOut:
    payload = json.loads(match.state_json)
    playmode_hydrate_state_cards(payload, db)
    viewer_seat = 1 if viewer_profile_id == match.player_one_profile_id else (2 if viewer_profile_id == match.player_two_profile_id else None)
    player_two_username = match.player_two_profile.username if match.player_two_profile else (payload.get("computer_username") if payload.get("computer_opponent") else None)
    return PlaymodeMatchViewOut(
        public_id=match.public_id,
        mode=match.mode,
        status=match.status,
        current_turn=match.current_turn,
        active_seat=match.active_seat,
        current_phase=str(payload.get("current_phase") or "untap"),
        last_move_summary=payload.get("last_move_summary"),
        event_log=list(payload.get("event_log") or [])[-80:],
        pending_attack=payload.get("pending_attack"),
        pending_choice=playmode_pending_choice_view(payload, viewer_seat, admin_override),
        viewer_seat=viewer_seat,
        admin_override=admin_override,
        deadline_label=playmode_deadline_label(match.turn_deadline_at),
        player_one=PlaymodePlayerViewOut(
            seat=1,
            profile_id=match.player_one_profile_id,
            username=match.player_one_profile.username if match.player_one_profile else None,
            avatar_url=match.player_one_profile.avatar_url if match.player_one_profile else None,
            deck_public_id=match.player_one_deck.public_id if match.player_one_deck else None,
            deck_title=match.player_one_deck.title if match.player_one_deck else None,
            ready=bool(payload.get("player_one", {}).get("ready")),
            zones=playmode_zone_view(payload.get("player_one", {}), hide_hand=(viewer_seat != 1)),
        ),
        player_two=PlaymodePlayerViewOut(
            seat=2,
            profile_id=match.player_two_profile_id,
            username=player_two_username,
            avatar_url=match.player_two_profile.avatar_url if match.player_two_profile else ("/assets/shobu-cpu-avatar.png" if payload.get("computer_opponent") else None),
            deck_public_id=match.player_two_deck.public_id if match.player_two_deck else None,
            deck_title=match.player_two_deck.title if match.player_two_deck else None,
            ready=bool(payload.get("player_two", {}).get("ready")),
            zones=playmode_zone_view(payload.get("player_two", {}), hide_hand=(viewer_seat != 2)),
        ),
    )


def build_deck_snapshot(title: str, visibility: str, items: list[DeckItem]) -> str:
    payload = {
        "title": title,
        "visibility": visibility,
        "cards": [
            {"card_id": item.card_id, "quantity": item.quantity}
            for item in sorted(items, key=lambda current: current.card_id)
        ],
    }
    return json.dumps(payload, sort_keys=True)


def create_deck_revision(deck: Deck, change_note: str | None = None) -> None:
    snapshot_json = build_deck_snapshot(deck.title, deck.visibility, deck.items)
    latest = deck.revisions[0] if deck.revisions else None
    if latest and latest.snapshot_json == snapshot_json and latest.change_note == change_note:
        return

    next_version = (latest.version_number + 1) if latest else 1
    revision = DeckRevision(
        deck=deck,
        version_number=next_version,
        title=deck.title,
        visibility=deck.visibility,
        card_total=sum(item.quantity for item in deck.items),
        change_note=change_note,
        snapshot_json=snapshot_json,
        created_at=datetime.utcnow(),
    )
    deck.revisions.append(revision)


def parse_history_entry(change_note: str | None) -> tuple[str, str] | None:
    if not change_note:
        return None
    if change_note.startswith("Added "):
        return ("added", change_note.removeprefix("Added ").strip())
    if change_note.startswith("Removed "):
        return ("removed", change_note.removeprefix("Removed ").strip())
    return None


def render_page(filename: str) -> HTMLResponse:
    html = (FRONTEND_DIR / filename).read_text()
    styles_url = f"/assets/styles.css?v={ASSET_VERSION}"
    app_url = f"/assets/app.js?v={ASSET_VERSION}"
    logo_url = f"/assets/assets/crystal-vault-logo.png?v={ASSET_VERSION}"
    html = re.sub(r'\./styles\.css(?:\?v=[^"]+)?', styles_url, html)
    html = re.sub(r'\./app\.js(?:\?v=[^"]+)?', app_url, html)
    html = html.replace('./assets/crystal-vault-logo.png', logo_url)
    html = html.replace('./assets/', '/assets/assets/')
    if 'rel="icon"' not in html:
        html = html.replace(
            "</head>",
            f'  <link rel="icon" type="image/png" href="{logo_url}">\n</head>',
        )
    return HTMLResponse(html)


def render_error_page(filename: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(render_page(filename).body.decode("utf-8"), status_code=status_code)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> Response:
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found."}, status_code=404)
    return render_error_page("not-found.html", 404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception) -> Response:
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Internal server error."}, status_code=500)
    return render_error_page("error.html", 500)


@app.get("/", response_class=HTMLResponse)
@app.get("/welcome", response_class=HTMLResponse)
def welcome_page() -> HTMLResponse:
    return render_page("index.html")


@app.get("/builder", response_class=HTMLResponse)
def builder_page() -> HTMLResponse:
    return render_page("builder.html")


@app.get("/builder/editor", response_class=HTMLResponse)
def builder_editor_page() -> HTMLResponse:
    return render_page("deck-editor.html")


@app.get("/builder/history", response_class=HTMLResponse)
def builder_history_page() -> HTMLResponse:
    return render_page("history.html")


@app.get("/playtest", response_class=HTMLResponse)
def playtest_page() -> HTMLResponse:
    return render_page("playtest.html")


@app.get("/playmode", response_class=HTMLResponse)
def playmode_page() -> HTMLResponse:
    return render_page("playmode.html")


@app.get("/cards", response_class=HTMLResponse)
def cards_page() -> HTMLResponse:
    return render_page("cards.html")


@app.get("/cards/{card_id}", response_class=HTMLResponse)
def card_detail_page(card_id: int) -> HTMLResponse:
    return render_page("card-detail.html")


@app.get("/import", response_class=HTMLResponse)
def import_page() -> HTMLResponse:
    return render_page("import.html")


@app.get("/print", response_class=HTMLResponse)
def print_page() -> HTMLResponse:
    return render_page("print.html")


@app.get("/profile", response_class=HTMLResponse)
def profile_page() -> HTMLResponse:
    return render_page("profile.html")


@app.get("/admin", response_class=HTMLResponse)
def admin_page() -> HTMLResponse:
    return render_page("admin.html")


@app.get("/terms", response_class=HTMLResponse)
def terms_page() -> HTMLResponse:
    return render_page("terms.html")


@app.get("/privacy", response_class=HTMLResponse)
def privacy_page() -> HTMLResponse:
    return render_page("privacy.html")


@app.get("/fan-policy", response_class=HTMLResponse)
def fan_policy_page() -> HTMLResponse:
    return render_page("fan-policy.html")


@app.get("/contact", response_class=HTMLResponse)
def contact_page() -> HTMLResponse:
    return render_page("contact.html")


@app.get("/my-decks")
def my_decks_page() -> RedirectResponse:
    return RedirectResponse(url="/profile#my-decks", status_code=307)


@app.get("/explore-decks", response_class=HTMLResponse)
def explore_decks_page() -> HTMLResponse:
    return render_page("explore-decks.html")


@app.get("/share/{public_id}", response_class=HTMLResponse)
def shared_builder_page(public_id: str) -> HTMLResponse:
    return render_page("deck-editor.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/metadata", response_model=MetadataResponse)
def metadata(db: Session = Depends(get_db)) -> MetadataResponse:
    civilizations = sorted({
        civilization
        for value in db.scalars(select(Card.civilizations)).all()
        for civilization in value.split("|")
        if civilization
    })
    types = sorted(db.scalars(select(Card.type).distinct()).all())
    max_cost = db.scalar(select(func.max(Card.cost))) or 14
    return MetadataResponse(civilizations=civilizations, types=types, max_cost=max_cost)


@app.get("/api/rules/coverage")
def rules_coverage(db: Session = Depends(get_db)) -> dict:
    cards = db.scalars(select(Card).order_by(Card.id)).all()
    return build_rules_coverage(cards)


@app.get("/api/rules/spell-coverage")
def spell_coverage(db: Session = Depends(get_db)) -> dict:
    cards = db.scalars(select(Card).where(Card.type.ilike("%spell%")).order_by(Card.name.asc(), Card.id.asc())).all()
    return build_spell_coverage(cards)


@app.get("/api/rules/creature-coverage")
def creature_coverage(db: Session = Depends(get_db)) -> dict:
    cards = db.scalars(select(Card).where(Card.type.ilike("%creature%")).order_by(Card.name.asc(), Card.id.asc())).all()
    return build_creature_coverage(cards)


@app.get("/api/profiles", response_model=ProfileListResponse)
def list_profiles(request: Request, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> ProfileListResponse:
    viewer_id = authenticated_viewer_id(request, db)
    profiles = db.execute(
        select(Profile)
        .options(joinedload(Profile.follower_links), joinedload(Profile.following_links))
        .order_by(Profile.username.asc())
    ).unique().scalars().all()
    profiles.sort(key=lambda profile: (-len(profile.follower_links), profile.username.lower(), profile.id))
    return ProfileListResponse(items=[profile_to_out(profile, viewer_profile_id=viewer_id) for profile in profiles if profile])


@app.post("/api/profiles", response_model=ProfileOut)
def create_profile(payload: ProfileCreateIn, db: Session = Depends(get_db)) -> ProfileOut:
    username = slugify(payload.username)
    existing = db.scalar(select(Profile).where(Profile.username == username))
    if existing:
        raise HTTPException(status_code=400, detail="Profile handle already exists.")

    email = normalize_email(payload.email) if payload.email else None
    if email and db.scalar(select(Profile).where(Profile.email == email)):
        raise HTTPException(status_code=400, detail="Email already exists.")

    profile = Profile(
        username=username,
        display_name=username,
        email=email,
        avatar_url=payload.avatar_url,
        bio=payload.bio,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile_to_out(profile, include_email=True)


@app.post("/api/auth/register", response_model=AuthResponse)
def register(payload: AuthRegisterIn, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    enforce_rate_limit("register", request, extra_key=normalize_email(payload.email))
    email = normalize_email(payload.email)
    username = slugify(payload.username)

    enforce_password_policy(payload.password)
    if db.scalar(select(Profile).where(Profile.email == email)):
        raise HTTPException(status_code=400, detail="Email already exists.")
    if db.scalar(select(Profile).where(Profile.username == username)):
        raise HTTPException(status_code=400, detail="Username already exists.")

    profile = Profile(
        email=email,
        password_hash=hash_password(payload.password),
        username=username,
        display_name=username,
        avatar_url=payload.avatar_url,
        email_verified_at=None,
    )
    db.add(profile)
    db.flush()
    raw_token = issue_verification_token(profile, db)
    db.commit()
    db.refresh(profile)

    if local_verification_fallback_enabled():
        profile.email_verified_at = datetime.utcnow()
        db.commit()
        db.refresh(profile)
        auth_token = create_auth_token(profile)
        csrf_token = create_csrf_token()
        set_auth_cookies(response, request, auth_token, csrf_token)
        return AuthResponse(
            profile=profile_to_out(profile, include_email=True),
            auth_token=auth_token,
            csrf_token=csrf_token,
            verification_required=False,
            verification_email_sent=False,
            message="Account created and auto-verified for local development. You can log in now.",
            verification_url=None,
        )

    verification_email_sent = False
    verification_url: str | None = None
    message = "Account created. Check your email to verify your account before logging in."
    try:
        send_email_message(build_verification_message(profile, raw_token))
        verification_email_sent = True
    except Exception as error:
        logger.exception("Verification email could not be sent: %s", error)
        if local_verification_fallback_enabled():
            verification_url = build_verification_link(raw_token)
            message = "Account created. Email sending is not configured locally, so you can verify directly from the app."
        else:
            message = "Account created, but the verification email could not be sent yet. Use resend verification after SMTP is configured."

    return AuthResponse(
        profile=profile_to_out(profile, include_email=True),
        verification_required=True,
        verification_email_sent=verification_email_sent,
        message=message,
        verification_url=verification_url,
    )


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: AuthLoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    enforce_rate_limit("login", request, extra_key=normalize_email(payload.email))
    email = normalize_email(payload.email)
    profile = db.scalar(select(Profile).where(Profile.email == email))
    if not profile or not verify_password(payload.password, profile.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if profile.banned_at:
        reason = f" Reason: {profile.ban_reason}" if profile.ban_reason else ""
        raise HTTPException(status_code=403, detail=f"This account is banned.{reason}")
    if not is_email_verified(profile):
        raise HTTPException(status_code=403, detail="Verify your email before logging in.")
    if profile.is_admin and ADMIN_2FA_ENABLED:
        challenge_id = issue_admin_2fa_challenge(profile, request, db)
        return AuthResponse(
            profile=profile_to_out(profile, include_email=True),
            admin_2fa_required=True,
            admin_2fa_challenge_id=challenge_id,
            verification_required=False,
            verification_email_sent=False,
            message="Admin security code sent to your email.",
        )
    auth_token = create_auth_token(profile)
    csrf_token = create_csrf_token()
    set_auth_cookies(response, request, auth_token, csrf_token)
    return AuthResponse(
        profile=profile_to_out(profile, include_email=True),
        auth_token=auth_token,
        csrf_token=csrf_token,
        verification_required=False,
        verification_email_sent=False,
        message="Login successful.",
    )


@app.post("/api/auth/admin-2fa/verify", response_model=AuthResponse)
def verify_admin_2fa(payload: AdminTwoFactorVerifyIn, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    enforce_rate_limit("admin_2fa", request, extra_key=payload.challenge_id)
    prune_admin_2fa_challenges()
    challenge = ADMIN_2FA_CHALLENGES.get(payload.challenge_id)
    if not challenge:
        raise HTTPException(status_code=401, detail="Admin security code expired. Please log in again.")
    attempts = int(challenge.get("attempts", 0)) + 1
    challenge["attempts"] = attempts
    if attempts > 5:
        ADMIN_2FA_CHALLENGES.pop(payload.challenge_id, None)
        raise HTTPException(status_code=429, detail="Too many incorrect admin security codes. Please log in again.")
    profile_id = int(challenge.get("profile_id", 0))
    profile = db.get(Profile, profile_id)
    if not profile or not profile.is_admin or profile.banned_at:
        ADMIN_2FA_CHALLENGES.pop(payload.challenge_id, None)
        raise HTTPException(status_code=403, detail="Admin access is required.")
    code_hash = verification_token_hash(payload.code.strip())
    if not hmac.compare_digest(str(challenge.get("code_hash", "")), code_hash):
        create_admin_audit(db, profile.id, "admin_2fa_failed", detail=f"ip={client_ip(request)}")
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid admin security code.")
    ADMIN_2FA_CHALLENGES.pop(payload.challenge_id, None)
    auth_token = create_auth_token(profile)
    csrf_token = create_csrf_token()
    set_auth_cookies(response, request, auth_token, csrf_token)
    create_admin_audit(db, profile.id, "admin_login", detail=f"ip={client_ip(request)}")
    db.commit()
    return AuthResponse(
        profile=profile_to_out(profile, include_email=True),
        auth_token=auth_token,
        csrf_token=csrf_token,
        verification_required=False,
        verification_email_sent=False,
        message="Admin login confirmed.",
    )


@app.post("/api/auth/logout", response_model=GenericMessageOut)
def logout(request: Request, response: Response) -> GenericMessageOut:
    clear_auth_cookies(response, request)
    return GenericMessageOut(status="ok", message="Logged out.")


@app.post("/api/auth/password-reset/request", response_model=GenericMessageOut)
def request_password_reset(payload: PasswordResetRequestIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    email = normalize_email(payload.email)
    enforce_rate_limit("password_reset", request, extra_key=email)
    generic = GenericMessageOut(status="ok", message="If the account exists, a password reset email has been sent.")
    if not email_delivery_configured():
        return GenericMessageOut(status="error", message="Password reset email delivery is not configured yet.")
    profile = db.scalar(select(Profile).where(Profile.email == email))
    if not profile or profile.banned_at or not profile.email_verified_at:
        return generic
    raw_token = issue_password_reset_token(profile, db)
    db.commit()
    try:
        send_email_message(build_password_reset_message(profile, raw_token))
    except Exception as error:
        logger.exception("Password reset email failed: %s", error)
        return GenericMessageOut(status="error", message="Password reset email could not be sent right now.")
    return generic


@app.post("/api/auth/password-reset/confirm", response_model=GenericMessageOut)
def confirm_password_reset(payload: PasswordResetConfirmIn, request: Request, response: Response, db: Session = Depends(get_db)) -> GenericMessageOut:
    enforce_rate_limit("password_reset", request, extra_key=client_ip(request))
    enforce_password_policy(payload.password)
    hashed = verification_token_hash(payload.token)
    reset = db.execute(
        select(PasswordResetToken)
        .options(joinedload(PasswordResetToken.profile))
        .where(PasswordResetToken.token_hash == hashed)
    ).unique().scalar_one_or_none()
    now = datetime.utcnow()
    if not reset or reset.used_at or reset.expires_at < now or not reset.profile:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired.")
    profile = reset.profile
    if profile.banned_at:
        raise HTTPException(status_code=403, detail="This account is banned.")
    profile.password_hash = hash_password(payload.password)
    profile.email_verified_at = profile.email_verified_at or now
    reset.used_at = now
    for token_row in db.scalars(select(PasswordResetToken).where(PasswordResetToken.profile_id == profile.id)).all():
        if token_row.id != reset.id and token_row.used_at is None:
            token_row.used_at = now
    if profile.is_admin:
        create_admin_audit(db, profile.id, "admin_password_reset", detail=f"ip={client_ip(request)}")
    db.commit()
    clear_auth_cookies(response, request)
    return GenericMessageOut(status="ok", message="Password updated. Please log in again.")


@app.post("/api/auth/resend-verification", response_model=GenericMessageOut)
def resend_verification(payload: VerificationResendIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    enforce_rate_limit("resend_verification", request, extra_key=normalize_email(payload.email))
    email = normalize_email(payload.email)
    profile = db.execute(
        select(Profile)
        .options(joinedload(Profile.verification_tokens))
        .where(Profile.email == email)
    ).unique().scalar_one_or_none()

    if not profile:
        return GenericMessageOut(status="ok", message="If the account exists, a verification email has been queued.")
    if is_email_verified(profile):
        return GenericMessageOut(status="ok", message="This email is already verified. You can log in.")

    now = datetime.utcnow()
    if local_verification_fallback_enabled():
        profile.email_verified_at = now
        db.commit()
        return GenericMessageOut(status="ok", message="This local account has been auto-verified. You can log in now.")

    if profile.verification_sent_at and (now - profile.verification_sent_at).total_seconds() < EMAIL_RESEND_COOLDOWN_SECONDS:
        return GenericMessageOut(status="ok", message="A recent verification email already exists. Please wait a moment and check your inbox.")

    raw_token = issue_verification_token(profile, db)
    db.commit()
    db.refresh(profile)
    try:
        send_email_message(build_verification_message(profile, raw_token))
    except Exception as error:
        logger.exception("Resend verification email failed: %s", error)
        if local_verification_fallback_enabled():
            return GenericMessageOut(
                status="ok",
                message="Email sending is not configured locally, so you can verify directly from the app.",
                verification_url=build_verification_link(raw_token),
            )
        return GenericMessageOut(status="error", message="The account exists, but the verification email could not be sent right now.")

    return GenericMessageOut(status="ok", message="If the account exists, a verification email has been sent.")


@app.get("/api/auth/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)) -> RedirectResponse:
    hashed = verification_token_hash(token)
    verification = db.execute(
        select(EmailVerificationToken)
        .options(joinedload(EmailVerificationToken.profile))
        .where(EmailVerificationToken.token_hash == hashed)
    ).unique().scalar_one_or_none()

    if not verification or verification.used_at is not None:
        return RedirectResponse(url="/profile?verification=invalid", status_code=303)
    if verification.expires_at < datetime.utcnow():
        return RedirectResponse(url="/profile?verification=expired", status_code=303)

    profile = verification.profile
    if not profile:
        return RedirectResponse(url="/profile?verification=invalid", status_code=303)

    verification.used_at = datetime.utcnow()
    profile.email_verified_at = datetime.utcnow()
    for token_row in profile.verification_tokens:
        if token_row.id != verification.id and token_row.used_at is None:
            db.delete(token_row)
    db.commit()
    return RedirectResponse(url="/profile?verification=success", status_code=303)


@app.patch("/api/profiles/{profile_id}", response_model=ProfileOut)
def update_profile(profile_id: int, payload: ProfileUpdateIn, request: Request, db: Session = Depends(get_db)) -> ProfileOut:
    require_authenticated_profile(profile_id, request, db)
    profile = db.execute(
        select(Profile)
        .options(joinedload(Profile.follower_links), joinedload(Profile.following_links))
        .where(Profile.id == profile_id)
    ).unique().scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    if payload.username is not None:
        username = slugify(payload.username)
        if not username:
            raise HTTPException(status_code=400, detail="Username is required.")
        existing = db.scalar(select(Profile).where(Profile.username == username).where(Profile.id != profile_id))
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists.")
        profile.username = username
        profile.display_name = username
    if "avatar_url" in payload.model_fields_set:
        profile.avatar_url = payload.avatar_url
    if "bio" in payload.model_fields_set and payload.bio is not None:
        profile.bio = payload.bio
    db.commit()
    db.refresh(profile)
    return profile_to_out(profile, include_email=True)


@app.post("/api/profiles/{profile_id}/delete", response_model=GenericMessageOut)
def delete_profile(profile_id: int, payload: ProfileDeleteIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    require_authenticated_profile(profile_id, request, db)
    profile = db.execute(
        select(Profile)
        .options(
            joinedload(Profile.decks).joinedload(Deck.items),
            joinedload(Profile.decks).joinedload(Deck.revisions),
            joinedload(Profile.decks).joinedload(Deck.likes),
            joinedload(Profile.following_links),
            joinedload(Profile.follower_links),
            joinedload(Profile.verification_tokens),
            joinedload(Profile.deck_likes),
            joinedload(Profile.notifications),
            joinedload(Profile.actor_notifications),
        )
        .where(Profile.id == profile_id)
    ).unique().scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    if not verify_password(payload.password, profile.password_hash):
        raise HTTPException(status_code=400, detail="The password you entered is incorrect.")

    for notification in list(profile.actor_notifications):
        notification.actor_profile_id = None

    for deck in list(profile.decks):
        db.delete(deck)

    db.delete(profile)
    db.commit()
    return GenericMessageOut(status="ok", message="Your account and owned decks were deleted.")


@app.post("/api/profiles/{profile_id}/follow", response_model=ProfileOut)
def follow_profile(profile_id: int, payload: FollowToggleIn, request: Request, db: Session = Depends(get_db)) -> ProfileOut:
    enforce_rate_limit("follow", request, extra_key=str(payload.follower_profile_id))
    require_authenticated_profile(payload.follower_profile_id, request, db)
    if payload.follower_profile_id == profile_id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself.")

    follower = db.get(Profile, payload.follower_profile_id)
    followed = db.get(Profile, profile_id)
    if not follower or not followed:
        raise HTTPException(status_code=404, detail="Profile not found.")

    existing = db.scalar(
        select(ProfileFollow)
        .where(ProfileFollow.follower_id == payload.follower_profile_id)
        .where(ProfileFollow.followed_id == profile_id)
    )
    if existing:
        db.delete(existing)
    else:
        db.add(ProfileFollow(follower_id=payload.follower_profile_id, followed_id=profile_id))
        db.add(Notification(profile_id=profile_id, actor_profile_id=payload.follower_profile_id, type="follow", created_at=datetime.utcnow()))

    db.commit()
    refreshed = db.execute(
        select(Profile)
        .options(joinedload(Profile.follower_links), joinedload(Profile.following_links))
        .where(Profile.id == profile_id)
    ).unique().scalar_one()
    return profile_to_out(refreshed)


@app.get("/api/playmode/matches", response_model=PlaymodeMatchListOut)
def list_playmode_matches(profile_id: int, request: Request, db: Session = Depends(get_db)) -> PlaymodeMatchListOut:
    profile = require_authenticated_profile(profile_id, request, db)
    query = (
        select(PlayMatch)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
        .order_by(PlayMatch.updated_at.desc(), PlayMatch.created_at.desc())
    )
    query = query.where((PlayMatch.player_one_profile_id == profile_id) | (PlayMatch.player_two_profile_id == profile_id))
    query = query.where(PlayMatch.status.in_(("active", "waiting")))
    matches = db.execute(query).unique().scalars().all()
    for match in matches:
        maybe_run_computer_turn(match, db)
        maybe_auto_resolve_playmode_match(match, db)
    return PlaymodeMatchListOut(items=[playmode_match_summary(match, profile_id) for match in matches])


@app.post("/api/playmode/matches", response_model=PlaymodeMatchViewOut)
def create_playmode_match(payload: PlaymodeMatchCreateIn, request: Request, db: Session = Depends(get_db)) -> PlaymodeMatchViewOut:
    profile = require_authenticated_profile(payload.profile_id, request, db)
    if payload.mode not in {"live", "async", "computer"}:
        raise HTTPException(status_code=400, detail="Mode must be live, async, or computer.")
    deck = ensure_owned_deck(db, payload.deck_public_id, payload.profile_id)
    if payload.mode == "computer":
        starting_seat = secrets.SystemRandom().choice([1, 2])
        state_payload = build_playmode_match_state(deck, deck, starting_seat=starting_seat)
        state_payload["computer_opponent"] = True
        state_payload["computer_username"] = "Crystal CPU"
        state_payload["last_move_summary"] = "Computer match started."
        playmode_hydrate_state_cards(state_payload, db)
        winner_seat = None
        if starting_seat == 2:
            messages, winner_seat = playmode_take_computer_turn(state_payload)
            if messages:
                state_payload["last_move_summary"] = " ".join(messages[-3:])
                playmode_append_events(state_payload, messages)
        if not winner_seat:
            auto_messages, winner_seat = playmode_auto_resolve_mandatory_phases(state_payload)
            if auto_messages:
                state_payload["last_move_summary"] = " ".join(auto_messages[-3:])
                playmode_append_events(state_payload, auto_messages)
        match = PlayMatch(
            public_id=generate_public_id(),
            mode="computer",
            status="finished" if winner_seat else "active",
            player_one_profile_id=payload.profile_id,
            player_one_deck_id=deck.id,
            player_two_profile_id=None,
            player_two_deck_id=deck.id,
            active_seat=int(state_payload.get("active_seat") or 1),
            current_turn=int(state_payload.get("current_turn") or 1),
            winner_profile_id=payload.profile_id if winner_seat == 1 else None,
            turn_deadline_at=None,
            state_json=playmode_dump_state(state_payload),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(match)
        db.commit()
        loaded = db.scalar(
            select(PlayMatch)
            .where(PlayMatch.public_id == match.public_id)
            .options(
                joinedload(PlayMatch.player_one_profile),
                joinedload(PlayMatch.player_two_profile),
                joinedload(PlayMatch.player_one_deck),
                joinedload(PlayMatch.player_two_deck),
            )
        )
        return playmode_match_view(loaded, payload.profile_id, db, admin_override=bool(profile.is_admin))
    invited_profile = None
    invite_username = slugify(payload.invite_username or "")
    if invite_username:
        invited_profile = find_invited_profile(db, payload.invite_username or "")
        if not invited_profile:
            raise HTTPException(status_code=404, detail="Invited user was not found. Use their exact username, profile display name, or verified email.")
        if invited_profile.id == payload.profile_id:
            raise HTTPException(status_code=400, detail="You cannot invite yourself to your own match.")
        if invited_profile.banned_at:
            raise HTTPException(status_code=400, detail="This user cannot be invited right now.")
    state_payload = build_playmode_match_state(deck)
    if invited_profile:
        state_payload["private_invite"] = True
        state_payload["invited_profile_id"] = invited_profile.id
        state_payload["invited_username"] = invited_profile.username
    match = PlayMatch(
        public_id=generate_public_id(),
        mode=payload.mode,
        status="waiting",
        player_one_profile_id=payload.profile_id,
        player_one_deck_id=deck.id,
        active_seat=1,
        current_turn=1,
        turn_deadline_at=None,
        state_json=playmode_dump_state(state_payload),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(match)
    if invited_profile:
        db.add(Notification(
            profile_id=invited_profile.id,
            actor_profile_id=profile.id,
            type="playmode_invite",
            message=f"{profile.username} invited you to a private Playmode match. Match code: {match.public_id}",
            created_at=datetime.utcnow(),
        ))
    db.commit()
    loaded = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == match.public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    return playmode_match_view(loaded, payload.profile_id, db, admin_override=bool(profile.is_admin))


@app.post("/api/playmode/matches/{public_id}/join", response_model=PlaymodeMatchViewOut)
def join_playmode_match(public_id: str, payload: PlaymodeMatchJoinIn, request: Request, db: Session = Depends(get_db)) -> PlaymodeMatchViewOut:
    profile = require_authenticated_profile(payload.profile_id, request, db)
    match = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck).joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    same_player_admin_join = bool(profile.is_admin and match.player_one_profile_id == payload.profile_id and not match.player_two_profile_id)
    if match.player_one_profile_id == payload.profile_id and not same_player_admin_join:
        raise HTTPException(status_code=400, detail="You are already seated in this match.")
    if match.player_two_profile_id and match.player_two_profile_id != payload.profile_id:
        raise HTTPException(status_code=400, detail="This match already has two players.")
    state_meta = json.loads(match.state_json or "{}")
    if state_meta.get("private_invite") and not bool(profile.is_admin) and state_meta.get("invited_profile_id") != payload.profile_id:
        raise HTTPException(status_code=403, detail="This is a private invited match.")
    deck = ensure_owned_deck(db, payload.deck_public_id, payload.profile_id)
    if not match.player_two_profile_id:
        starting_seat = secrets.SystemRandom().choice([1, 2])
        match.player_two_profile_id = payload.profile_id
        match.player_two_deck_id = deck.id
        match.status = "active"
        match.active_seat = starting_seat
        match.current_turn = 1
        next_state = build_playmode_match_state(match.player_one_deck, deck, starting_seat=starting_seat)
        if state_meta.get("private_invite"):
            next_state["private_invite"] = True
            next_state["invited_profile_id"] = state_meta.get("invited_profile_id")
            next_state["invited_username"] = state_meta.get("invited_username")
        auto_messages, _auto_winner = playmode_auto_resolve_mandatory_phases(next_state)
        playmode_append_event(next_state, f"Player 2 joined. Player {starting_seat} starts.")
        playmode_append_events(next_state, auto_messages)
        match.active_seat = int(next_state.get("active_seat") or starting_seat)
        match.current_turn = int(next_state.get("current_turn") or 1)
        match.state_json = playmode_dump_state(next_state)
        match.turn_deadline_at = datetime.utcnow() + timedelta(hours=24) if match.mode == "async" else None
        match.updated_at = datetime.utcnow()
        db.commit()
    loaded = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    return playmode_match_view(loaded, payload.profile_id, db, admin_override=bool(profile.is_admin))


@app.get("/api/playmode/matches/{public_id}", response_model=PlaymodeMatchViewOut)
def get_playmode_match(public_id: str, request: Request, profile_id: int | None = None, db: Session = Depends(get_db)) -> PlaymodeMatchViewOut:
    viewer_profile = optional_authenticated_profile(request, db)
    trusted_profile_id = viewer_profile.id if viewer_profile else None
    match = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    maybe_run_computer_turn(match, db)
    maybe_auto_resolve_playmode_match(match, db)
    state_meta = json.loads(match.state_json or "{}")
    if viewer_profile and viewer_profile.is_admin:
        return playmode_match_view(match, trusted_profile_id, db, admin_override=True)
    if playmode_spectator_allows(state_meta, viewer_profile, match=match):
        return playmode_match_view(match, trusted_profile_id, db)
    if not playmode_invite_allows(state_meta, trusted_profile_id, match=match):
        raise HTTPException(status_code=403, detail="This private match can only be viewed by invited players.")
    invited_profile_id = state_meta.get("invited_profile_id")
    if trusted_profile_id and trusted_profile_id not in {match.player_one_profile_id, match.player_two_profile_id, invited_profile_id}:
        raise HTTPException(status_code=403, detail="You do not have access to this match.")
    return playmode_match_view(match, trusted_profile_id, db)


@app.post("/api/playmode/matches/{public_id}/spectate-invites", response_model=GenericMessageOut)
def invite_playmode_spectator(public_id: str, payload: PlaymodeSpectateInviteIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    actor = require_authenticated_profile(payload.profile_id, request, db)
    match = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.status != "active":
        raise HTTPException(status_code=400, detail="Spectators can only be invited after the match is active.")
    if not actor.is_admin and payload.profile_id not in {match.player_one_profile_id, match.player_two_profile_id}:
        raise HTTPException(status_code=403, detail="Only players in this match can invite spectators.")
    raw_target = payload.invite_to.strip()
    if not raw_target:
        raise HTTPException(status_code=400, detail="Choose a user or enter an email address.")
    target_profile = find_invited_profile(db, raw_target)
    target_email = normalize_email(raw_target) if "@" in raw_target else None
    state_payload = json.loads(match.state_json or "{}")
    now = datetime.utcnow()
    if target_profile:
        if target_profile.id in {match.player_one_profile_id, match.player_two_profile_id}:
            raise HTTPException(status_code=400, detail="That user is already playing in this match.")
        spectator_ids = {int(value) for value in state_payload.get("spectator_profile_ids", []) if str(value).isdigit()}
        spectator_ids.add(target_profile.id)
        state_payload["spectator_profile_ids"] = sorted(spectator_ids)
        db.add(Notification(
            profile_id=target_profile.id,
            actor_profile_id=actor.id,
            type="playmode_spectate",
            message=f"{actor.username} invited you to spectate Playmode match {match.public_id}.",
            created_at=now,
        ))
        recipient_email = target_profile.email
        recipient_name = target_profile.username
    elif target_email:
        spectator_emails = {normalize_email(value) for value in state_payload.get("spectator_emails", []) if value}
        spectator_emails.add(target_email)
        state_payload["spectator_emails"] = sorted(spectator_emails)
        recipient_email = target_email
        recipient_name = target_email
    else:
        raise HTTPException(status_code=404, detail="User was not found. Use a followed user, username, or email address.")
    match.state_json = playmode_dump_state(state_payload)
    match.updated_at = now
    db.commit()
    if recipient_email:
        try:
            send_email_message(build_playmode_spectate_message(recipient_email=recipient_email, recipient_name=recipient_name, actor=actor, match=match))
        except Exception as error:
            logger.exception("Playmode spectate invite email failed: %s", error)
    return GenericMessageOut(status="ok", message=f"Spectate invite sent to {recipient_name}.")


@app.post("/api/playmode/matches/{public_id}/action", response_model=PlaymodeMatchViewOut)
def apply_playmode_action(public_id: str, payload: PlaymodeActionIn, request: Request, db: Session = Depends(get_db)) -> PlaymodeMatchViewOut:
    acting_profile = require_authenticated_profile(payload.profile_id, request, db)
    is_admin_override = bool(acting_profile.is_admin)
    match = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.status not in {"active", "waiting"}:
        raise HTTPException(status_code=400, detail="This match can no longer be updated.")
    mover_seat = 1 if payload.profile_id == match.player_one_profile_id else (2 if payload.profile_id == match.player_two_profile_id else None)
    if not mover_seat and not is_admin_override:
        raise HTTPException(status_code=403, detail="You are not seated in this match.")
    if payload.action == "concede":
        conceding_seat = payload.seat or mover_seat
        if conceding_seat not in {1, 2}:
            raise HTTPException(status_code=400, detail="Choose the player who is conceding.")
        if not is_admin_override and conceding_seat != mover_seat:
            raise HTTPException(status_code=403, detail="You can only concede your own seat.")
        payload.seat = conceding_seat
    previous_active_seat = match.active_seat
    state_payload = json.loads(match.state_json or "{}")
    playmode_hydrate_state_cards(state_payload, db)
    pending_controller = (state_payload.get("pending_choice") or {}).get("controller_seat")
    can_resolve_pending = payload.action in {"choose_pending", "pass_pending"} and pending_controller == mover_seat
    if not is_admin_override and match.active_seat != mover_seat and not can_resolve_pending and payload.action != "concede":
        raise HTTPException(status_code=403, detail="It is not your turn.")
    move_summary, winner_seat = playmode_apply_action(state_payload, payload)
    if winner_seat is None:
        auto_messages, auto_winner = playmode_auto_resolve_mandatory_phases(state_payload)
        if auto_messages:
            move_summary = f"{move_summary} {' '.join(auto_messages[-3:])}"
        winner_seat = auto_winner
    computer_choice_messages: list[str] = []
    computer_choice_steps = 0
    while match.mode == "computer" and winner_seat is None and int((state_payload.get("pending_choice") or {}).get("controller_seat") or 0) == 2 and computer_choice_steps < 6:
        computer_choice_steps += 1
        computer_messages, computer_winner = playmode_resolve_computer_pending_choice(state_payload)
        computer_choice_messages.extend(computer_messages)
        winner_seat = computer_winner
    if computer_choice_messages:
        move_summary = f"{move_summary} {' '.join(computer_choice_messages[-3:])}"
    if match.mode == "computer" and winner_seat is None and int(state_payload.get("active_seat") or match.active_seat or 1) == 2:
        computer_messages, computer_winner = playmode_take_computer_turn(state_payload)
        if computer_messages:
            move_summary = f"{move_summary} {' '.join(computer_messages[-3:])}"
        winner_seat = computer_winner
        if winner_seat is None:
            auto_messages, auto_winner = playmode_auto_resolve_mandatory_phases(state_payload)
            if auto_messages:
                move_summary = f"{move_summary} {' '.join(auto_messages[-3:])}"
        winner_seat = auto_winner
    state_payload["last_move_summary"] = move_summary
    playmode_append_event(state_payload, move_summary)
    now = datetime.utcnow()
    match.current_turn = int(state_payload.get("current_turn") or match.current_turn or 1)
    match.active_seat = int(state_payload.get("active_seat") or match.active_seat or 1)
    match.updated_at = now
    match.state_json = playmode_dump_state(state_payload)
    if winner_seat in {1, 2}:
        winner_profile = match.player_one_profile if winner_seat == 1 else match.player_two_profile
        match.status = "finished"
        match.winner_profile_id = winner_profile.id if winner_profile else None
        match.turn_deadline_at = None
    else:
        match.status = "active"
        match.winner_profile_id = None
        match.turn_deadline_at = now + timedelta(hours=24) if match.mode == "async" else None
    opponent_profile = match.player_one_profile if match.active_seat == 1 else match.player_two_profile
    should_notify_async_opponent = (
        match.mode == "async"
        and match.status == "active"
        and previous_active_seat != match.active_seat
        and opponent_profile is not None
        and opponent_profile.id != payload.profile_id
    )
    if should_notify_async_opponent:
        db.add(
            Notification(
                profile_id=opponent_profile.id,
                actor_profile_id=payload.profile_id,
                type="playmode_turn",
                message=f"Your async Playmode match {match.public_id} is waiting for your turn. {move_summary}",
                created_at=now,
            )
        )
    db.commit()
    if should_notify_async_opponent and opponent_profile and opponent_profile.email and opponent_profile.email_verified_at:
        try:
            send_email_message(
                build_playmode_turn_message(
                    recipient=opponent_profile,
                    actor=acting_profile,
                    match=match,
                    move_summary=move_summary,
                )
            )
        except Exception as error:
            logger.exception("Async Playmode action email failed: %s", error)
    loaded = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    return playmode_match_view(loaded, payload.profile_id, db, admin_override=is_admin_override)


@app.post("/api/playmode/matches/{public_id}/state", response_model=PlaymodeMatchViewOut)
def update_playmode_match(public_id: str, payload: PlaymodeMatchUpdateIn, request: Request, db: Session = Depends(get_db)) -> PlaymodeMatchViewOut:
    acting_profile = require_authenticated_profile(payload.profile_id, request, db)
    is_admin_override = bool(acting_profile.is_admin)
    match = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")
    if match.status not in {"active", "waiting"}:
        raise HTTPException(status_code=400, detail="This match can no longer be updated.")

    mover_seat = 1 if payload.profile_id == match.player_one_profile_id else (2 if payload.profile_id == match.player_two_profile_id else None)
    if not mover_seat and not is_admin_override:
        raise HTTPException(status_code=403, detail="You are not seated in this match.")
    if not is_admin_override and match.active_seat != mover_seat:
        raise HTTPException(status_code=403, detail="It is not your turn.")
    if payload.active_seat not in {1, 2}:
        raise HTTPException(status_code=400, detail="Active seat must be 1 or 2.")
    if payload.current_turn < 1:
        raise HTTPException(status_code=400, detail="Turn number must be at least 1.")
    if payload.current_phase not in {"untap", "draw", "charge", "play", "attack", "end"}:
        raise HTTPException(status_code=400, detail="Phase must be untap, draw, charge, play, attack, or end.")

    now = datetime.utcnow()
    state_payload = dict(payload.state or {})
    state_payload["current_phase"] = payload.current_phase
    state_payload["current_turn"] = payload.current_turn
    state_payload["active_seat"] = payload.active_seat
    if payload.move_summary:
        state_payload["last_move_summary"] = payload.move_summary
        playmode_append_event(state_payload, payload.move_summary)
    match.current_turn = payload.current_turn
    match.active_seat = payload.active_seat
    match.updated_at = now
    match.state_json = playmode_dump_state(state_payload)

    winner_profile: Profile | None = None
    if payload.winner_seat in {1, 2}:
        winner_profile = match.player_one_profile if payload.winner_seat == 1 else match.player_two_profile
        match.status = "finished"
        match.winner_profile_id = winner_profile.id if winner_profile else None
        match.turn_deadline_at = None
    else:
        match.status = "active"
        match.winner_profile_id = None
        match.turn_deadline_at = now + timedelta(hours=24) if match.mode == "async" else None

    opponent_profile = match.player_one_profile if payload.active_seat == 1 else match.player_two_profile
    should_notify_async_opponent = (
        match.mode == "async"
        and match.status == "active"
        and opponent_profile is not None
        and opponent_profile.id != payload.profile_id
    )
    if should_notify_async_opponent:
        summary = payload.move_summary or f"{acting_profile.username} ended their turn."
        db.add(
            Notification(
                profile_id=opponent_profile.id,
                actor_profile_id=payload.profile_id,
                type="playmode_turn",
                message=f"Your async Playmode match {match.public_id} is waiting for your turn. {summary}",
                created_at=now,
            )
        )

    db.commit()

    if should_notify_async_opponent and opponent_profile and opponent_profile.email and opponent_profile.email_verified_at:
        actor_profile = acting_profile
        if actor_profile:
            try:
                send_email_message(
                    build_playmode_turn_message(
                        recipient=opponent_profile,
                        actor=actor_profile,
                        match=match,
                        move_summary=payload.move_summary,
                    )
                )
            except Exception as error:
                logger.exception("Async Playmode turn email failed: %s", error)

    loaded = db.scalar(
        select(PlayMatch)
        .where(PlayMatch.public_id == public_id)
        .options(
            joinedload(PlayMatch.player_one_profile),
            joinedload(PlayMatch.player_two_profile),
            joinedload(PlayMatch.player_one_deck),
            joinedload(PlayMatch.player_two_deck),
        )
    )
    return playmode_match_view(loaded, payload.profile_id, db, admin_override=is_admin_override)


@app.get("/api/profiles/{profile_id}/notifications", response_model=NotificationListResponse)
def list_notifications(profile_id: int, request: Request, db: Session = Depends(get_db)) -> NotificationListResponse:
    require_authenticated_profile(profile_id, request, db)
    notifications = db.execute(
        select(Notification)
        .options(
            joinedload(Notification.actor).joinedload(Profile.follower_links),
            joinedload(Notification.actor).joinedload(Profile.following_links),
            joinedload(Notification.deck),
        )
        .where(Notification.profile_id == profile_id)
        .order_by(Notification.created_at.desc())
        .limit(30)
    ).unique().scalars().all()
    return NotificationListResponse(items=[notification_to_out(item) for item in notifications])


@app.post("/api/profiles/{profile_id}/notifications/read", response_model=GenericMessageOut)
def mark_notifications_read(profile_id: int, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    require_authenticated_profile(profile_id, request, db)
    notifications = db.scalars(
        select(Notification)
        .where(Notification.profile_id == profile_id)
        .where(Notification.read_at.is_(None))
    ).all()
    now = datetime.utcnow()
    for notification in notifications:
        notification.read_at = now
    db.commit()
    return GenericMessageOut(status="ok", message="Notifications marked as read.")


def contact_message_to_out(message: ContactMessage) -> ContactMessageOut:
    return ContactMessageOut(
        id=message.id,
        username=message.username,
        email=message.email,
        subject=message.subject,
        message=message.message,
        created_at_label=(message.created_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S"),
        read=bool(message.read_at),
    )


@app.post("/api/contact-messages", response_model=GenericMessageOut)
def create_contact_message(payload: ContactMessageIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    username = slugify(payload.username)
    email = normalize_email(payload.email)
    subject = payload.subject.strip()
    message = payload.message.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if not subject:
        raise HTTPException(status_code=400, detail="Subject is required.")
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")
    profile_id = payload.profile_id
    if profile_id:
        require_authenticated_profile(profile_id, request, db)
        profile = db.get(Profile, profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found.")
        username = profile.username
        email = profile.email or email
    db.add(ContactMessage(profile_id=profile_id, username=username, email=email, subject=subject, message=message, created_at=datetime.utcnow()))
    db.commit()
    return GenericMessageOut(status="ok", message="Your message was sent to the Paladin's Vault admin inbox.")


@app.get("/api/admin/overview", response_model=AdminOverviewOut)
def admin_overview(admin_profile_id: int, request: Request, db: Session = Depends(get_db)) -> AdminOverviewOut:
    require_admin(admin_profile_id, db, request=request)
    profiles = db.execute(
        select(Profile)
        .options(joinedload(Profile.follower_links), joinedload(Profile.following_links))
        .order_by(Profile.id.desc())
    ).unique().scalars().all()
    decks = db.execute(
        select(Deck)
        .options(
            joinedload(Deck.profile).joinedload(Profile.follower_links),
            joinedload(Deck.profile).joinedload(Profile.following_links),
            joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Deck.likes).joinedload(DeckLike.profile),
        )
        .order_by(Deck.created_at.desc())
    ).unique().scalars().all()
    recent_profiles = [profile_to_out(profile, include_email=True, viewer_profile_id=admin_profile_id) for profile in profiles[:12] if profile]
    all_profiles = [profile_to_out(profile, include_email=True, viewer_profile_id=admin_profile_id) for profile in profiles if profile]
    recent_decks = [deck_summary_out(deck, deck.profile, include_owner_email=True, viewer_profile_id=admin_profile_id) for deck in decks[:18]]
    audits = db.scalars(select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(30)).all()
    contact_messages = db.scalars(select(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(40)).all()
    profile_months = [MonthlyStatOut(**item) for item in monthly_counts([profile.email_verified_at or profile.verification_sent_at or datetime.utcnow() for profile in profiles if profile])]
    deck_months = [MonthlyStatOut(**item) for item in monthly_counts([deck.created_at for deck in decks if deck.created_at])]
    return AdminOverviewOut(
        total_profiles=len(profiles),
        total_decks=len(decks),
        public_decks=sum(1 for deck in decks if deck.visibility == "public"),
        private_decks=sum(1 for deck in decks if deck.visibility == "private"),
        banned_profiles=sum(1 for profile in profiles if profile.banned_at),
        database_tables={
            "profiles": len(profiles),
            "decks": len(decks),
            "cards": db.scalar(select(func.count(Card.id))) or 0,
            "notifications": db.scalar(select(func.count(Notification.id))) or 0,
            "likes": db.scalar(select(func.count(DeckLike.id))) or 0,
            "contact_messages": db.scalar(select(func.count(ContactMessage.id))) or 0,
        },
        email_diagnostics={
            "delivery_mode": "resend" if resend_configured() else ("smtp" if smtp_configured() else "disabled"),
            "from_email": SMTP_FROM_EMAIL or None,
            "app_base_url": APP_BASE_URL or None,
            "resend_configured": resend_configured(),
            "smtp_fallback_configured": smtp_configured(),
            "last_error": LAST_EMAIL_ERROR,
        },
        recent_profiles=recent_profiles,
        all_profiles=all_profiles,
        recent_decks=recent_decks,
        profiles_by_month=profile_months,
        decks_by_month=deck_months,
        audit_log=[
            {
                "id": audit.id,
                "action": audit.action,
                "detail": audit.detail,
                "target_profile_id": audit.target_profile_id,
                "created_at": audit.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for audit in audits
        ],
        recent_contact_messages=[contact_message_to_out(item) for item in contact_messages],
    )


@app.get("/api/admin/month-details", response_model=AdminMonthDetailsOut)
def admin_month_details(admin_profile_id: int, month: str, request: Request, db: Session = Depends(get_db)) -> AdminMonthDetailsOut:
    require_admin(admin_profile_id, db, request=request)
    try:
        month_start = datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Month must use YYYY-MM format.") from exc
    if month_start.month == 12:
        month_end = datetime(month_start.year + 1, 1, 1)
    else:
        month_end = datetime(month_start.year, month_start.month + 1, 1)

    profiles = db.execute(
        select(Profile)
        .where(
            func.coalesce(Profile.email_verified_at, Profile.verification_sent_at) >= month_start,
            func.coalesce(Profile.email_verified_at, Profile.verification_sent_at) < month_end,
        )
        .order_by(func.coalesce(Profile.email_verified_at, Profile.verification_sent_at).desc(), Profile.id.desc())
    ).scalars().all()
    decks = db.execute(
        select(Deck)
        .options(joinedload(Deck.profile), joinedload(Deck.items).joinedload(DeckItem.card))
        .where(Deck.created_at >= month_start, Deck.created_at < month_end)
        .order_by(Deck.created_at.desc(), Deck.id.desc())
    ).unique().scalars().all()

    return AdminMonthDetailsOut(
        label=month,
        profiles=[
            AdminMonthProfileOut(
                id=profile.id,
                username=profile.username,
                email=profile.email,
                email_verified=bool(profile.email_verified_at),
                created_at_label=(profile.email_verified_at or profile.verification_sent_at or month_start).strftime("%Y-%m-%d %H:%M"),
            )
            for profile in profiles
        ],
        decks=[
            AdminMonthDeckOut(
                public_id=deck.public_id,
                title=deck.title,
                visibility=deck.visibility,
                owner_username=deck.profile.username if deck.profile else None,
                card_total=sum(item.quantity for item in deck.items),
                created_at_label=deck.created_at.strftime("%Y-%m-%d %H:%M"),
            )
            for deck in decks
        ],
    )


@app.post("/api/admin/notify", response_model=GenericMessageOut)
def admin_notify(payload: AdminNotificationIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    enforce_rate_limit("admin_notify", request, extra_key=str(payload.admin_profile_id))
    admin = require_admin(payload.admin_profile_id, db, request=request)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Notification message is required.")
    if payload.target_profile_id:
        target = db.get(Profile, payload.target_profile_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target profile not found.")
        db.add(Notification(profile_id=target.id, actor_profile_id=admin.id, type="admin_message", message=message, created_at=datetime.utcnow()))
        create_admin_audit(db, admin.id, "notify_user", target_profile_id=target.id, detail=message)
        db.commit()
        return GenericMessageOut(status="ok", message=f"Notification sent to {target.username}.")
    targets = db.scalars(select(Profile).where(Profile.id != admin.id).where(Profile.banned_at.is_(None))).all()
    now = datetime.utcnow()
    for target in targets:
        db.add(Notification(profile_id=target.id, actor_profile_id=admin.id, type="admin_message", message=message, created_at=now))
    create_admin_audit(db, admin.id, "notify_all", detail=message)
    db.commit()
    return GenericMessageOut(status="ok", message=f"Notification sent to {len(targets)} users.")


@app.post("/api/admin/email", response_model=GenericMessageOut)
def admin_email(payload: AdminEmailIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    enforce_rate_limit("admin_notify", request, extra_key=str(payload.admin_profile_id))
    admin = require_admin(payload.admin_profile_id, db, request=request)
    target = db.get(Profile, payload.target_profile_id) if payload.target_profile_id else None
    target_email = normalize_email(payload.target_email) if payload.target_email else None
    if not target and not target_email:
        raise HTTPException(status_code=400, detail="Choose a target user or enter an email address manually.")
    if target and not target.email and not target_email:
        raise HTTPException(status_code=400, detail="That user does not have an email address on file.")

    subject = payload.subject.strip()
    message = payload.message.strip()
    if not subject:
        raise HTTPException(status_code=400, detail="Email subject is required.")
    if not message:
        raise HTTPException(status_code=400, detail="Email message is required.")

    recipient_email = target_email or normalize_email(target.email or "")
    recipient_name = target.username if target else "Paladin's Vault user"

    email = build_admin_email_message(
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        subject=subject,
        body_message=message,
    )
    try:
        send_email_message(email)
    except Exception as error:
        logger.exception("Admin email sending failed: %s", error)
        raise HTTPException(status_code=502, detail=str(error) or "Email sending failed.") from error
    if target:
        db.add(Notification(profile_id=target.id, actor_profile_id=admin.id, type="admin_message", message=f"Admin email sent: {subject}", created_at=datetime.utcnow()))
    create_admin_audit(db, admin.id, "email_user", target_profile_id=target.id if target else None, detail=f"{mask_email(recipient_email)} • {subject}")
    db.commit()
    return GenericMessageOut(status="ok", message=f"Email sent to {recipient_name} at {recipient_email}.")


@app.post("/api/admin/verify", response_model=GenericMessageOut)
def admin_verify(payload: AdminVerifyIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    admin = require_admin(payload.admin_profile_id, db, request=request)
    target = db.get(Profile, payload.target_profile_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target profile not found.")
    if target.email_verified_at:
        return GenericMessageOut(status="ok", message=f"{target.username} is already verified.")
    target.email_verified_at = datetime.utcnow()
    db.add(Notification(profile_id=target.id, actor_profile_id=admin.id, type="admin_message", message="Your email address has been manually verified by the Paladin's Vault admin.", created_at=datetime.utcnow()))
    create_admin_audit(db, admin.id, "verify_email", target_profile_id=target.id, detail=mask_email(target.email))
    db.commit()
    return GenericMessageOut(status="ok", message=f"{target.username} has been verified.")


@app.post("/api/admin/ban", response_model=GenericMessageOut)
def admin_ban(payload: AdminBanIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    enforce_rate_limit("admin_ban", request, extra_key=str(payload.admin_profile_id))
    admin = require_admin(payload.admin_profile_id, db, request=request)
    target = db.get(Profile, payload.target_profile_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target profile not found.")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot ban your own admin account.")
    if payload.banned:
        target.banned_at = datetime.utcnow()
        target.ban_reason = payload.reason.strip() if payload.reason else None
        db.add(Notification(profile_id=target.id, actor_profile_id=admin.id, type="admin_message", message=f"Your account has been banned.{f' Reason: {target.ban_reason}' if target.ban_reason else ''}", created_at=datetime.utcnow()))
        create_admin_audit(db, admin.id, "ban", target_profile_id=target.id, detail=target.ban_reason)
        db.commit()
        return GenericMessageOut(status="ok", message=f"{target.username} has been banned.")
    target.banned_at = None
    target.ban_reason = None
    db.add(Notification(profile_id=target.id, actor_profile_id=admin.id, type="admin_message", message="Your account ban has been lifted.", created_at=datetime.utcnow()))
    create_admin_audit(db, admin.id, "unban", target_profile_id=target.id)
    db.commit()
    return GenericMessageOut(status="ok", message=f"{target.username} has been unbanned.")


@app.get("/api/profiles/{profile_id}/decks", response_model=ProfileDecksResponse)
def get_profile_decks(profile_id: int, request: Request, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> ProfileDecksResponse:
    viewer_id = authenticated_viewer_id(request, db)
    profile = db.execute(
        select(Profile)
        .options(
            selectinload(Profile.decks).selectinload(Deck.items).selectinload(DeckItem.card),
            selectinload(Profile.decks).selectinload(Deck.likes).selectinload(DeckLike.profile),
            selectinload(Profile.deck_likes).selectinload(DeckLike.deck).selectinload(Deck.items).selectinload(DeckItem.card),
            selectinload(Profile.deck_likes).selectinload(DeckLike.deck).selectinload(Deck.likes).selectinload(DeckLike.profile),
            selectinload(Profile.deck_likes).selectinload(DeckLike.deck).selectinload(Deck.profile),
        )
        .where(Profile.id == profile_id)
    ).unique().scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    summaries = []
    for deck in sorted(profile.decks, key=lambda item: item.updated_at, reverse=True):
        if deck.visibility != "public" and viewer_id != profile.id:
            continue
        summaries.append(deck_summary_out(deck, profile, include_owner_email=viewer_id == profile.id, viewer_profile_id=viewer_id))

    liked_summaries = []
    for like in sorted(profile.deck_likes, key=lambda item: item.created_at, reverse=True):
        deck = like.deck
        if not deck:
            continue
        if deck.visibility != "public" and viewer_id != profile.id:
            continue
        liked_summaries.append(deck_summary_out(deck, deck.profile, include_owner_email=viewer_id == (deck.profile_id or -1), viewer_profile_id=viewer_id))

    return ProfileDecksResponse(decks=summaries, liked_decks=liked_summaries)


@app.get("/api/profiles/{profile_id}", response_model=ProfileDetailOut)
def get_profile(profile_id: int, request: Request, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> ProfileDetailOut:
    viewer_id = authenticated_viewer_id(request, db)
    profile = db.execute(
        select(Profile)
        .options(*PROFILE_DETAIL_LOAD_OPTIONS)
        .where(Profile.id == profile_id)
    ).unique().scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    summaries = []
    for deck in sorted(profile.decks, key=lambda item: item.updated_at, reverse=True):
        if deck.visibility != "public" and viewer_id != profile.id:
            continue
        summaries.append(deck_summary_out(deck, profile, include_owner_email=viewer_id == profile.id, viewer_profile_id=viewer_id))

    liked_summaries = []
    for like in sorted(profile.deck_likes, key=lambda item: item.created_at, reverse=True):
        deck = like.deck
        if not deck:
            continue
        if deck.visibility != "public" and viewer_id != profile.id:
            continue
        liked_summaries.append(deck_summary_out(deck, deck.profile, include_owner_email=viewer_id == (deck.profile_id or -1), viewer_profile_id=viewer_id))

    return ProfileDetailOut(
        id=profile.id,
        username=profile.username,
        display_name=profile.username,
        email=profile.email if viewer_id == profile.id else None,
        email_verified=bool(profile.email_verified_at),
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        follower_count=len(profile.follower_links),
        following_count=len(profile.following_links),
        decks=summaries,
        following=[profile_to_out(link.followed, viewer_profile_id=viewer_id) for link in profile.following_links if link.followed],
        liked_decks=liked_summaries,
    )


@app.get("/api/profiles/by-username/{username}", response_model=ProfileDetailOut)
def get_profile_by_username(username: str, request: Request, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> ProfileDetailOut:
    viewer_id = authenticated_viewer_id(request, db)
    profile = db.execute(
        select(Profile)
        .options(*PROFILE_DETAIL_LOAD_OPTIONS)
        .where(Profile.username == slugify(username))
    ).unique().scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    summaries = []
    for deck in sorted(profile.decks, key=lambda item: item.updated_at, reverse=True):
        if deck.visibility != "public" and viewer_id != profile.id:
            continue
        summaries.append(deck_summary_out(deck, profile, include_owner_email=viewer_id == profile.id, viewer_profile_id=viewer_id))

    liked_summaries = []
    for like in sorted(profile.deck_likes, key=lambda item: item.created_at, reverse=True):
        deck = like.deck
        if not deck:
            continue
        if deck.visibility != "public" and viewer_id != profile.id:
            continue
        liked_summaries.append(deck_summary_out(deck, deck.profile, include_owner_email=viewer_id == (deck.profile_id or -1), viewer_profile_id=viewer_id))

    return ProfileDetailOut(
        id=profile.id,
        username=profile.username,
        display_name=profile.username,
        email=profile.email if viewer_id == profile.id else None,
        email_verified=bool(profile.email_verified_at),
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        follower_count=len(profile.follower_links),
        following_count=len(profile.following_links),
        decks=summaries,
        following=[profile_to_out(link.followed, viewer_profile_id=viewer_id) for link in profile.following_links if link.followed],
        liked_decks=liked_summaries,
    )


@app.get("/api/cards", response_model=CardListResponse)
def list_cards(
    search: str | None = None,
    civilization: str | None = None,
    type: str | None = None,
    max_cost: int | None = None,
    limit: int = 120,
    db: Session = Depends(get_db),
) -> CardListResponse:
    query: Select[tuple[Card]] = select(Card).order_by(Card.cost.asc(), Card.name.asc())

    if search:
        token = f"%{search.strip()}%"
        query = query.where((Card.name.ilike(token)) | (Card.text.ilike(token)) | (Card.race_label.ilike(token)))
    if civilization and civilization != "all":
        query = query.where(Card.civilizations.ilike(f"%{civilization}%"))
    if type and type != "all":
        query = query.where(Card.type == type)
    if max_cost is not None:
        query = query.where(Card.cost <= max_cost)

    cards = db.scalars(query.limit(limit)).all()
    return CardListResponse(items=[card_to_out(card) for card in cards], total=len(cards))


@app.get("/api/cards/by-ids", response_model=CardListResponse)
def cards_by_ids(ids: str, db: Session = Depends(get_db)) -> CardListResponse:
    parsed_ids = [int(piece) for piece in ids.split(",") if piece.strip().isdigit()]
    if not parsed_ids:
        return CardListResponse(items=[], total=0)
    cards = db.scalars(select(Card).where(Card.id.in_(parsed_ids))).all()
    ordered = sorted(cards, key=lambda card: parsed_ids.index(card.id))
    return CardListResponse(items=[card_to_out(card) for card in ordered], total=len(ordered))


@app.get("/api/cards/{card_id}", response_model=CardOut)
def card_detail(card_id: int, db: Session = Depends(get_db)) -> CardOut:
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")
    return card_to_out(card)


@app.post("/api/decks", response_model=DeckCreateOut)
def create_deck(payload: DeckCreateIn, request: Request, db: Session = Depends(get_db)) -> DeckCreateOut:
    if payload.profile_id is not None:
        enforce_rate_limit("create_deck", request, extra_key=str(payload.profile_id))
    card_ids = [entry.card_id for entry in payload.cards]
    cards = db.scalars(select(Card).where(Card.id.in_(card_ids))).all() if card_ids else []
    cards_by_id = {card.id: card for card in cards}
    if len(cards_by_id) != len(payload.cards):
        raise HTTPException(status_code=400, detail="One or more cards were not found.")

    profile_id = payload.profile_id
    if profile_id is None:
        raise HTTPException(status_code=400, detail="Profile is required to save a deck.")

    if not db.get(Profile, profile_id):
        raise HTTPException(status_code=400, detail="Profile not found.")
    require_authenticated_profile(profile_id, request, db)

    visibility = payload.visibility.strip().lower()
    if visibility not in {"public", "private"}:
        raise HTTPException(status_code=400, detail="Visibility must be public or private.")

    valid_cover_urls = {format_image_path(card.id) for card in cards_by_id.values()}
    valid_illustration_urls = {format_illustration_path(card.name) for card in cards_by_id.values()}
    if payload.cover_image_url and payload.cover_image_url in valid_illustration_urls:
        cover_image_url = payload.cover_image_url
    elif payload.cards:
        representative_entry = max(
            payload.cards,
            key=lambda entry: (
                entry.quantity,
                -(cards_by_id[entry.card_id].cost),
                cards_by_id[entry.card_id].name,
            ),
        )
        representative_card = cards_by_id[representative_entry.card_id]
        cover_image_url = format_illustration_path(representative_card.name)
    else:
        cover_image_url = None

    normalized_title = payload.title.strip()
    deck = None
    if payload.public_id:
        deck = db.scalar(
            select(Deck)
            .where(Deck.public_id == payload.public_id)
            .where(Deck.profile_id == profile_id)
        )
        if not deck:
            raise HTTPException(status_code=403, detail="You can only update your own deck.")
    else:
        deck = db.scalar(
            select(Deck)
            .where(Deck.profile_id == profile_id)
            .where(func.lower(Deck.title) == normalized_title.lower())
        )

    if deck:
        deck.title = normalized_title
        deck.visibility = visibility
        deck.cover_image_url = cover_image_url
        deck.updated_at = datetime.utcnow()
        deck.items.clear()
        db.flush()
    else:
        deck = Deck(
            public_id=generate_public_id(),
            title=normalized_title,
            visibility=visibility,
            cover_image_url=cover_image_url,
            profile_id=profile_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(deck)
        db.flush()

    for entry in payload.cards:
        deck.items.append(DeckItem(card_id=entry.card_id, quantity=entry.quantity))

    db.flush()
    create_deck_revision(deck, payload.change_note.strip() if payload.change_note else None)
    db.commit()
    return DeckCreateOut(
        public_id=deck.public_id,
        title=deck.title,
        visibility=deck.visibility,
        cover_image_url=deck.cover_image_url,
        share_url=f"/share/{deck.public_id}",
        pdf_url=f"/api/decks/{deck.public_id}/pdf",
    )


@app.get("/api/decks", response_model=DeckListResponse)
def list_decks(request: Request, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> DeckListResponse:
    viewer_id = authenticated_viewer_id(request, db)
    decks = db.execute(
        select(Deck)
        .options(
            joinedload(Deck.profile),
            joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Deck.likes).joinedload(DeckLike.profile),
        )
        .order_by(Deck.updated_at.desc(), Deck.created_at.desc())
    ).unique().scalars().all()

    public_decks = [deck for deck in decks if deck.visibility == "public"]
    public_decks.sort(
        key=lambda deck: (
            -len(deck.likes),
            -((deck.updated_at or deck.created_at or datetime.min).timestamp()),
            deck.title.lower(),
            deck.id,
        )
    )
    items = [deck_summary_out(deck, viewer_profile_id=viewer_id) for deck in public_decks]
    return DeckListResponse(items=items)


@app.get("/api/decks/{public_id}", response_model=DeckOut)
def get_deck(public_id: str, request: Request, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> DeckOut:
    viewer_id = authenticated_viewer_id(request, db)
    deck = db.execute(
        select(Deck)
        .options(
            joinedload(Deck.profile),
            joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Deck.likes).joinedload(DeckLike.profile),
        )
        .where(Deck.public_id == public_id)
    ).unique().scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    if deck.visibility != "public" and deck.profile_id != viewer_id:
        raise HTTPException(status_code=403, detail="This deck is private.")
    return deck_to_out(deck, viewer_profile_id=viewer_id)


@app.get("/api/decks/{public_id}/history", response_model=DeckHistoryResponse)
def get_deck_history(public_id: str, request: Request, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> DeckHistoryResponse:
    viewer_id = authenticated_viewer_id(request, db)
    deck = db.execute(
        select(Deck)
        .options(joinedload(Deck.revisions))
        .where(Deck.public_id == public_id)
    ).unique().scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    if deck.visibility != "public" and deck.profile_id != viewer_id:
        raise HTTPException(status_code=403, detail="This deck is private.")

    items = []
    for revision in sorted(deck.revisions, key=lambda current: current.version_number, reverse=True):
        parsed = parse_history_entry(revision.change_note)
        if not parsed:
            continue
        change_type, card_name = parsed
        items.append(
            DeckHistoryEntryOut(
                card_name=card_name,
                change_type=change_type,
                created_at_label=revision.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )

    return DeckHistoryResponse(
        items=items
    )


@app.post("/api/decks/{public_id}/like", response_model=DeckSummaryOut)
def toggle_deck_like(public_id: str, payload: DeckLikeToggleIn, request: Request, db: Session = Depends(get_db)) -> DeckSummaryOut:
    enforce_rate_limit("like", request, extra_key=str(payload.profile_id))
    profile = require_authenticated_profile(payload.profile_id, request, db)

    deck = db.execute(
        select(Deck)
        .options(
            joinedload(Deck.profile),
            joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Deck.likes).joinedload(DeckLike.profile),
        )
        .where(Deck.public_id == public_id)
    ).unique().scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    if deck.visibility != "public" and deck.profile_id != payload.profile_id:
        raise HTTPException(status_code=403, detail="This deck is private.")
    if deck.profile_id == payload.profile_id:
        raise HTTPException(status_code=400, detail="You cannot like your own deck.")

    existing = next((like for like in deck.likes if like.profile_id == payload.profile_id), None)
    send_like_email = False
    if existing:
        db.delete(existing)
        db.flush()
    else:
        db.add(DeckLike(profile_id=payload.profile_id, deck_id=deck.id, created_at=datetime.utcnow()))
        db.add(Notification(profile_id=deck.profile_id, actor_profile_id=payload.profile_id, deck_id=deck.id, type="deck_like", created_at=datetime.utcnow()))
        db.flush()
        send_like_email = True

    refreshed = db.execute(
        select(Deck)
        .options(
            joinedload(Deck.profile),
            joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Deck.likes).joinedload(DeckLike.profile),
        )
        .where(Deck.id == deck.id)
    ).unique().scalar_one()
    db.commit()
    if (
        send_like_email
        and refreshed.profile
        and refreshed.profile.id != payload.profile_id
        and refreshed.profile.email
        and smtp_configured()
    ):
        try:
            send_email_message(build_deck_like_message(refreshed.profile, profile, refreshed))
        except Exception as error:
            logger.exception("Deck like notification email failed: %s", error)
    return deck_summary_out(refreshed, refreshed.profile, viewer_profile_id=payload.profile_id)


@app.delete("/api/decks/{public_id}")
def delete_deck(public_id: str, profile_id: int, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    require_authenticated_profile(profile_id, request, db)
    deck = db.execute(
        select(Deck)
        .options(joinedload(Deck.profile), joinedload(Deck.items))
        .where(Deck.public_id == public_id)
    ).unique().scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    if deck.profile_id != profile_id:
        raise HTTPException(status_code=403, detail="You can only delete your own decks.")

    db.delete(deck)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/decks/{public_id}/pdf")
def deck_pdf(public_id: str, db: Session = Depends(get_db)) -> Response:
    if not PDF_GENERATION_SEMAPHORE.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A PDF export is already running. Please try again in a moment.")
    try:
        deck = db.execute(
            select(Deck)
            .options(joinedload(Deck.profile), joinedload(Deck.items).joinedload(DeckItem.card))
            .where(Deck.public_id == public_id)
        ).unique().scalar_one_or_none()
        if not deck:
            raise HTTPException(status_code=404, detail="Deck not found.")

        for item in deck.items:
            if item.card.image_status != "ready":
                try:
                    ensure_card_image(item.card)
                    item.card.image_status = "ready"
                except Exception:
                    item.card.image_status = "missing"
        db.commit()

        pdf_bytes = build_deck_pdf(deck)
        filename = f"{slugify(deck.title or 'paladins-vault-deck')}.pdf"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
    finally:
        PDF_GENERATION_SEMAPHORE.release()


@app.get("/api/cards/{card_id}/image")
def get_card_image(card_id: int, db: Session = Depends(get_db)) -> FileResponse:
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")

    image_path = ensure_card_image(card)
    if not image_path:
        raise HTTPException(status_code=404, detail="Image not found.")

    card.image_status = "ready"
    db.commit()
    return FileResponse(image_path, media_type="image/webp")
