# Paladin's Vault Launch Checklist

## 1. Brand and Legal

- Confirm that `Paladin's Vault` and the final logo pass a real trademark clearance search.
- Review the Duel Masters / Kaijudo fan-content risk with an IP attorney before public launch.
- Decide whether proxy / printable export should remain public, logged-in only, or disabled until legal review is complete.
- Verify that these public legal pages are live and linked:
  - `/terms`
  - `/privacy`
  - `/fan-policy`
  - `/contact`

## 2. Domain and Mailboxes

- Point `paladinsvault.com` and `www.paladinsvault.com` to Render.
- Create and test these mailboxes or forwarding aliases:
  - `support@paladinsvault.com`
  - `privacy@paladinsvault.com`
  - `legal@paladinsvault.com`
  - `no-reply@paladinsvault.com`

## 3. Resend Email Setup

Recommended provider: `Resend`.

1. Create a Resend account.
2. Add your sending domain, preferably a subdomain like `mail.paladinsvault.com`.
3. Add the DNS records Resend gives you.
4. Wait until the domain shows as verified.
5. Create an API key.
6. Configure these environment variables in Render:

```text
APP_BASE_URL=https://paladinsvault.com
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=<your_resend_api_key>
SMTP_FROM_EMAIL=no-reply@paladinsvault.com
SMTP_USE_TLS=1
EMAIL_VERIFICATION_TTL_HOURS=24
EMAIL_RESEND_COOLDOWN_SECONDS=60
```

## 4. Render Production Settings

- Create a `Web Service` from the GitHub repository.
- Use the included `render.yaml`.
- Confirm build command:

```bash
pip install -r requirements.txt
```

- Confirm start command:

```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

- Set the production environment variables in Render.
- Add custom domains:
  - `paladinsvault.com`
  - `www.paladinsvault.com`

## 5. Data and Storage

- Decide whether SQLite is acceptable for launch.
- If not, migrate to Postgres before launch.
- Set up a backup plan for the production database.
- Decide how long you keep deleted-account data in backups.

## 6. Security and Account Flows

- Test signup.
- Test email verification.
- Test resend verification.
- Test login / logout.
- Test account deletion.
- Test private deck visibility from another account.
- Test public deck sharing from another account.
- Test follow / like notifications.

## 7. Content and Moderation

- Decide who monitors:
  - `support@`
  - `privacy@`
  - `legal@`
- Define your response process for:
  - takedown requests
  - privacy deletion requests
  - account abuse
  - impersonation reports

## 8. Final Browser QA

- Hard refresh and verify the latest CSS/JS.
- Test mobile nav and dropdowns.
- Test deck builder autosave.
- Test PDF export.
- Test PNG export.
- Test account deletion modal.
- Test cookie/privacy notice banner.

## 9. Go / No-Go Risk Notes

Current highest-risk areas for public launch:

- third-party card art and card-frame usage
- printable / proxy export features
- Duel Masters trademark and fan-content compliance
- brand-name clearance for `Paladin's Vault`

If any of those are unresolved, treat launch as `soft launch / private beta`, not full public release.
