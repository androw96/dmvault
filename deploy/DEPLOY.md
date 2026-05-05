# Deploy Guide

Paladin's Vault ket egyszeru modon publikalhato:

## 1. Render

Ez a legegyszerubb ut:

1. Toltsd fel a projektet GitHub-ra.
2. Renderben hozz letre egy uj `Web Service`-t.
3. Valaszd ki a repository-t.
4. A Render automatikusan fel tudja venni a gyokerben levo `render.yaml` konfiguraciot.
5. A service indulasa utan add hozza a custom domaint:
   - `paladinsvault.com`
   - `www.paladinsvault.com`
6. A registrar/DNS szolgaltatodnal allitsd be a Render altal kiirt rekordokat.
7. Verify utan a HTTPS-et a Render automatikusan intezi.
8. Allitsd be a production env varokat is, kulonosen:
   - `APP_BASE_URL=https://paladinsvault.com`
   - `SMTP_HOST=smtp.resend.com`
   - `SMTP_PORT=587`
   - `SMTP_USERNAME=resend`
   - `SMTP_PASSWORD=<Resend API key>`
   - `SMTP_FROM_EMAIL=no-reply@paladinsvault.com`
9. Ellenorizd, hogy a `support@`, `privacy@`, `legal@`, `no-reply@` cimkek tenyleg mukodnek.

Start command:

```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Healthcheck:

```text
/api/health
```

## 2. VPS + Caddy

Ha sajat szerverre akarod rakni:

1. Masold fel a projektet peldaul ide:

```text
/opt/paladinsvault
```

2. Hozz letre virtualis kornyezetet es telepits:

```bash
cd /opt/paladinsvault
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Masold be a systemd service filet:

```bash
sudo cp deploy/paladinsvault.service /etc/systemd/system/paladinsvault.service
```

4. A service fileban, ha kell, igazitsd:
   - `User`
   - `Group`
   - `WorkingDirectory`
   - `ExecStart`

5. Inditsd el:

```bash
sudo systemctl daemon-reload
sudo systemctl enable paladinsvault
sudo systemctl start paladinsvault
```

6. Caddy config:

```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

7. A domain DNS-ben az `A` rekord mutasson a VPS publikus IP-jere:
   - `@` -> a szerver IP-je
   - `www` -> vagy `CNAME @`, vagy kulon `A`

Caddy automatikusan kezeli a HTTPS certet.

## Ellenorzes

Render vagy VPS eseten ezeknek menniuk kell:

- `/api/health`
- `/`
- `/builder`
- `/builder/editor`

## Fontos

- A SQLite adatbazis most lokalis fajlban van, ez egy kisebb projekthez jo.
- Ha komolyabb publikus hasznalatot akarsz, kovetkezo lepeskent erdemes Postgresre valtani.
- Kulon nezd at a `deploy/LAUNCH_CHECKLIST.md` es `deploy/RESEND_SETUP.md` fajlokat is indulasi ellenorzolistanak.
