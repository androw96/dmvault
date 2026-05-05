# Resend Setup For Paladin's Vault

## Recommended Sending Setup

Use a dedicated mail subdomain, for example:

```text
mail.paladinsvault.com
```

Keep the visible sender as:

```text
no-reply@paladinsvault.com
```

If Resend requires it for your domain plan, you can also send from the verified subdomain directly.

## Steps

1. Create a Resend account.
2. Add your domain or subdomain.
3. Copy every DNS record Resend shows.
4. Add those records at your domain registrar / DNS provider.
5. Wait for verification.
6. Create an API key.
7. Put the key into Render as `SMTP_PASSWORD`.

## Render Environment Variables

```text
APP_BASE_URL=https://paladinsvault.com
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=re_xxxxxxxxxxxxxxxxx
SMTP_FROM_EMAIL=no-reply@paladinsvault.com
SMTP_USE_TLS=1
EMAIL_VERIFICATION_TTL_HOURS=24
EMAIL_RESEND_COOLDOWN_SECONDS=60
```

## Smoke Test

After deploy:

1. Register a fresh account.
2. Confirm the verification email arrives.
3. Click the verification link.
4. Confirm login works.
5. Like a deck from a second account and verify the notification email is sent.
