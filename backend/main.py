from __future__ import annotations

from datetime import datetime
from datetime import timedelta
import hashlib
import json
import logging
import os
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from .database import BASE_DIR, SessionLocal
from .image_service import ensure_card_image
from .models import AdminAuditLog, Card, ContactMessage, Deck, DeckItem, DeckLike, DeckRevision, EmailVerificationToken, Notification, Profile, ProfileFollow
from .pdf_service import build_deck_pdf
from .schemas import (
    AdminBanIn,
    AdminEmailIn,
    AdminNotificationIn,
    AdminOverviewOut,
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
    ProfileCreateIn,
    ProfileDeleteIn,
    ProfileDetailOut,
    ProfileListResponse,
    ProfileOut,
    ProfileUpdateIn,
    VerificationResendIn,
)
from .seed import seed_cards_if_needed
from .utils import format_image_path, format_illustration_path, generate_public_id, slugify

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
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@paladinsvault.com").strip().lower()
DEFAULT_ADMIN_USERNAME = slugify(os.getenv("DEFAULT_ADMIN_USERNAME", "paladins-vault-admin"))
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "PaladinsVaultAdmin96")
RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}
LAST_EMAIL_ERROR: str | None = None
RATE_LIMIT_RULES = {
    "register": (5, 900),
    "login": (10, 900),
    "resend_verification": (6, 900),
    "follow": (60, 300),
    "like": (90, 300),
    "create_deck": (180, 300),
    "admin_notify": (20, 300),
    "admin_ban": (30, 300),
}

app = FastAPI(title="Paladin's Vault")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


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


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${derived.hex()}"


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


def require_admin(profile_id: int, db: Session) -> Profile:
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


def enforce_rate_limit(name: str, request: Request, *, extra_key: str = "") -> None:
    limit, window_seconds = RATE_LIMIT_RULES[name]
    key = f"{name}:{client_ip(request)}:{extra_key}"
    now = time.time()
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


def build_email_shell(*, eyebrow: str, title: str, intro: str, body_html: str, footer_html: str = "") -> str:
    return f"""
    <html>
      <body style="margin:0;padding:0;background:#070b14;color:#f5faff;font-family:Arial,sans-serif;">
        <div style="max-width:640px;margin:0 auto;padding:32px 18px;">
          <div style="background:linear-gradient(160deg,#0f1728 0%,#101a30 45%,#12233f 100%);border:1px solid rgba(118,227,255,0.18);border-radius:28px;padding:32px 28px;box-shadow:0 22px 60px rgba(6,12,30,0.45);">
            <div style="text-align:center;margin-bottom:22px;">
              <img src="{APP_BASE_URL}/assets/crystal-vault-logo.png" alt="Paladin's Vault" style="width:92px;height:auto;display:block;margin:0 auto 12px;">
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
    return CardOut(
        id=card.id,
        slug=card.slug,
        name=card.name,
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
        illustration_path=format_illustration_path(card.name),
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
        owner=profile_to_out(owner_profile, include_email=include_owner_email, viewer_profile_id=viewer_profile_id),
        share_url=f"/share/{deck.public_id}",
        like_count=len(deck.likes),
        liked_by_viewer=bool(viewer_profile_id and any(like.profile_id == viewer_profile_id for like in deck.likes)),
        liked_by=[profile_to_out(profile, viewer_profile_id=viewer_profile_id) for profile in liked_by_profiles if profile],
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
    html = (
        html
        .replace('./styles.css', '/assets/styles.css?v=20260505w')
        .replace('./app.js', '/assets/app.js?v=20260505w')
        .replace('./assets/crystal-vault-logo.png', '/assets/assets/crystal-vault-logo.png?v=20260505w')
        .replace('./assets/', '/assets/assets/')
    )
    if 'rel="icon"' not in html:
        html = html.replace(
            "</head>",
            '  <link rel="icon" type="image/png" href="/assets/assets/crystal-vault-logo.png?v=20260505w">\n</head>',
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


@app.get("/api/profiles", response_model=ProfileListResponse)
def list_profiles(viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> ProfileListResponse:
    profiles = db.execute(
        select(Profile)
        .options(joinedload(Profile.follower_links), joinedload(Profile.following_links))
        .order_by(Profile.username.asc())
    ).unique().scalars().all()
    return ProfileListResponse(items=[profile_to_out(profile, viewer_profile_id=viewer_profile_id) for profile in profiles if profile])


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
def register(payload: AuthRegisterIn, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
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
        return AuthResponse(
            profile=profile_to_out(profile, include_email=True),
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
def login(payload: AuthLoginIn, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
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
    return AuthResponse(
        profile=profile_to_out(profile, include_email=True),
        verification_required=False,
        verification_email_sent=False,
        message="Login successful.",
    )


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
def update_profile(profile_id: int, payload: ProfileUpdateIn, db: Session = Depends(get_db)) -> ProfileOut:
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
def delete_profile(profile_id: int, payload: ProfileDeleteIn, db: Session = Depends(get_db)) -> GenericMessageOut:
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


@app.get("/api/profiles/{profile_id}/notifications", response_model=NotificationListResponse)
def list_notifications(profile_id: int, db: Session = Depends(get_db)) -> NotificationListResponse:
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
def mark_notifications_read(profile_id: int, db: Session = Depends(get_db)) -> GenericMessageOut:
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
def create_contact_message(payload: ContactMessageIn, db: Session = Depends(get_db)) -> GenericMessageOut:
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
        profile = db.get(Profile, profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found.")
        username = profile.username
        email = profile.email or email
    db.add(ContactMessage(profile_id=profile_id, username=username, email=email, subject=subject, message=message, created_at=datetime.utcnow()))
    db.commit()
    return GenericMessageOut(status="ok", message="Your message was sent to the Paladin's Vault admin inbox.")


@app.get("/api/admin/overview", response_model=AdminOverviewOut)
def admin_overview(admin_profile_id: int, db: Session = Depends(get_db)) -> AdminOverviewOut:
    require_admin(admin_profile_id, db)
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


@app.post("/api/admin/notify", response_model=GenericMessageOut)
def admin_notify(payload: AdminNotificationIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    enforce_rate_limit("admin_notify", request, extra_key=str(payload.admin_profile_id))
    admin = require_admin(payload.admin_profile_id, db)
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
    admin = require_admin(payload.admin_profile_id, db)
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
    create_admin_audit(db, admin.id, "email_user", target_profile_id=target.id if target else None, detail=f"{recipient_email} • {subject}")
    db.commit()
    return GenericMessageOut(status="ok", message=f"Email sent to {recipient_name} at {recipient_email}.")


@app.post("/api/admin/verify", response_model=GenericMessageOut)
def admin_verify(payload: AdminVerifyIn, db: Session = Depends(get_db)) -> GenericMessageOut:
    admin = require_admin(payload.admin_profile_id, db)
    target = db.get(Profile, payload.target_profile_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target profile not found.")
    if target.email_verified_at:
        return GenericMessageOut(status="ok", message=f"{target.username} is already verified.")
    target.email_verified_at = datetime.utcnow()
    db.add(Notification(profile_id=target.id, actor_profile_id=admin.id, type="admin_message", message="Your email address has been manually verified by the Paladin's Vault admin.", created_at=datetime.utcnow()))
    create_admin_audit(db, admin.id, "verify_email", target_profile_id=target.id, detail=target.email)
    db.commit()
    return GenericMessageOut(status="ok", message=f"{target.username} has been verified.")


@app.post("/api/admin/ban", response_model=GenericMessageOut)
def admin_ban(payload: AdminBanIn, request: Request, db: Session = Depends(get_db)) -> GenericMessageOut:
    enforce_rate_limit("admin_ban", request, extra_key=str(payload.admin_profile_id))
    admin = require_admin(payload.admin_profile_id, db)
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


@app.get("/api/profiles/{profile_id}", response_model=ProfileDetailOut)
def get_profile(profile_id: int, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> ProfileDetailOut:
    profile = db.execute(
        select(Profile)
        .options(
            joinedload(Profile.decks).joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Profile.decks).joinedload(Deck.likes).joinedload(DeckLike.profile),
            joinedload(Profile.following_links).joinedload(ProfileFollow.followed),
            joinedload(Profile.follower_links),
            joinedload(Profile.deck_likes).joinedload(DeckLike.deck).joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Profile.deck_likes).joinedload(DeckLike.deck).joinedload(Deck.likes).joinedload(DeckLike.profile),
            joinedload(Profile.deck_likes).joinedload(DeckLike.deck).joinedload(Deck.profile),
        )
        .where(Profile.id == profile_id)
    ).unique().scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    summaries = []
    for deck in sorted(profile.decks, key=lambda item: item.updated_at, reverse=True):
        if deck.visibility != "public" and viewer_profile_id != profile.id:
            continue
        summaries.append(deck_summary_out(deck, profile, include_owner_email=viewer_profile_id == profile.id, viewer_profile_id=viewer_profile_id))

    liked_summaries = []
    for like in sorted(profile.deck_likes, key=lambda item: item.created_at, reverse=True):
        deck = like.deck
        if not deck:
            continue
        if deck.visibility != "public" and viewer_profile_id != profile.id:
            continue
        liked_summaries.append(deck_summary_out(deck, deck.profile, include_owner_email=viewer_profile_id == (deck.profile_id or -1), viewer_profile_id=viewer_profile_id))

    return ProfileDetailOut(
        id=profile.id,
        username=profile.username,
        display_name=profile.username,
        email=profile.email if viewer_profile_id == profile.id else None,
        email_verified=bool(profile.email_verified_at),
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        follower_count=len(profile.follower_links),
        following_count=len(profile.following_links),
        decks=summaries,
        following=[profile_to_out(link.followed, viewer_profile_id=viewer_profile_id) for link in profile.following_links if link.followed],
        liked_decks=liked_summaries,
    )


@app.get("/api/profiles/by-username/{username}", response_model=ProfileDetailOut)
def get_profile_by_username(username: str, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> ProfileDetailOut:
    profile = db.execute(
        select(Profile)
        .options(
            joinedload(Profile.decks).joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Profile.decks).joinedload(Deck.likes).joinedload(DeckLike.profile),
            joinedload(Profile.following_links).joinedload(ProfileFollow.followed),
            joinedload(Profile.follower_links),
            joinedload(Profile.deck_likes).joinedload(DeckLike.deck).joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Profile.deck_likes).joinedload(DeckLike.deck).joinedload(Deck.likes).joinedload(DeckLike.profile),
            joinedload(Profile.deck_likes).joinedload(DeckLike.deck).joinedload(Deck.profile),
        )
        .where(Profile.username == slugify(username))
    ).unique().scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    summaries = []
    for deck in sorted(profile.decks, key=lambda item: item.updated_at, reverse=True):
        if deck.visibility != "public" and viewer_profile_id != profile.id:
            continue
        summaries.append(deck_summary_out(deck, profile, include_owner_email=viewer_profile_id == profile.id, viewer_profile_id=viewer_profile_id))

    liked_summaries = []
    for like in sorted(profile.deck_likes, key=lambda item: item.created_at, reverse=True):
        deck = like.deck
        if not deck:
            continue
        if deck.visibility != "public" and viewer_profile_id != profile.id:
            continue
        liked_summaries.append(deck_summary_out(deck, deck.profile, include_owner_email=viewer_profile_id == (deck.profile_id or -1), viewer_profile_id=viewer_profile_id))

    return ProfileDetailOut(
        id=profile.id,
        username=profile.username,
        display_name=profile.username,
        email=profile.email if viewer_profile_id == profile.id else None,
        email_verified=bool(profile.email_verified_at),
        avatar_url=profile.avatar_url,
        bio=profile.bio,
        follower_count=len(profile.follower_links),
        following_count=len(profile.following_links),
        decks=summaries,
        following=[profile_to_out(link.followed, viewer_profile_id=viewer_profile_id) for link in profile.following_links if link.followed],
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
def list_decks(viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> DeckListResponse:
    decks = db.execute(
        select(Deck)
        .options(
            joinedload(Deck.profile),
            joinedload(Deck.items).joinedload(DeckItem.card),
            joinedload(Deck.likes).joinedload(DeckLike.profile),
        )
        .order_by(Deck.updated_at.desc(), Deck.created_at.desc())
    ).unique().scalars().all()

    items = [deck_summary_out(deck, viewer_profile_id=viewer_profile_id) for deck in decks if deck.visibility == "public"]
    return DeckListResponse(items=items)


@app.get("/api/decks/{public_id}", response_model=DeckOut)
def get_deck(public_id: str, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> DeckOut:
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
    if deck.visibility != "public" and deck.profile_id != viewer_profile_id:
        raise HTTPException(status_code=403, detail="This deck is private.")
    return deck_to_out(deck, viewer_profile_id=viewer_profile_id)


@app.get("/api/decks/{public_id}/history", response_model=DeckHistoryResponse)
def get_deck_history(public_id: str, viewer_profile_id: int | None = None, db: Session = Depends(get_db)) -> DeckHistoryResponse:
    deck = db.execute(
        select(Deck)
        .options(joinedload(Deck.revisions))
        .where(Deck.public_id == public_id)
    ).unique().scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    if deck.visibility != "public" and deck.profile_id != viewer_profile_id:
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
    profile = db.get(Profile, payload.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

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
def delete_deck(public_id: str, profile_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
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
    headers = {"Content-Disposition": f'attachment; filename="{deck.public_id}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


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
