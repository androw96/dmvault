# Paladin's Vault

Ez a verzio mar Paladin's Vault branddel, profilalapu deck ownership szemlelettel, SQLite adatbazissal, megoszthato paklikkal es PDF exporttal keszult.

Jelenlegi statusz: `Beta`

## Fobb kepessegek

- valodi Duel Masters adatbazis seedelve nyilvanos JSON forrasbol
- FastAPI backend
- SQLite adatbazis
- profilalapu dashboard es sajat deck lista
- keresheto kartyaadatbazis es deck builder
- publikus pakli linkek: `/share/<public_id>`
- valodi kartyakepek cache-elese es beagyazasa a PDF exportba
- browser print view es letoltheto PDF
- Paladin's Vault logo es kristalyos brand megjelenes

## Futtatas

1. Aktiváld a venv-et:

```bash
source "/Users/ozymandias/Documents/GitHub/DMVault/.venv/bin/activate"
```

2. Inditsd a backendet:

```bash
uvicorn backend.main:app --app-dir "/Users/ozymandias/Documents/GitHub/DMVault" --reload
```

3. Nyisd meg bongeszoben:

[http://127.0.0.1:8000](http://127.0.0.1:8000)

## Publikalas

Deploy elokeszites keszult ehhez a projekthez:

- Render config: [render.yaml](/Users/ozymandias/Documents/Crystal%20Vault/render.yaml)
- Caddy config: [deploy/Caddyfile](/Users/ozymandias/Documents/Crystal%20Vault/deploy/Caddyfile)
- systemd service: [deploy/paladinsvault.service](/Users/ozymandias/Documents/Crystal%20Vault/deploy/paladinsvault.service)
- reszletes leiras: [deploy/DEPLOY.md](/Users/ozymandias/Documents/Crystal%20Vault/deploy/DEPLOY.md)
- launch checklist: [deploy/LAUNCH_CHECKLIST.md](/Users/ozymandias/Documents/Crystal%20Vault/deploy/LAUNCH_CHECKLIST.md)
- Resend email setup: [deploy/RESEND_SETUP.md](/Users/ozymandias/Documents/Crystal%20Vault/deploy/RESEND_SETUP.md)

Ha a `paladinsvault.com` domaint akarod hasznalni, innen mar ket gyors utad van:

- Render
- sajat VPS + Caddy

## Megjegyzesek

- Az adatbazis seed forrasa a `backend/data/raw/DuelMastersCards.json`.
- A kepfeloldas jelenleg a `db.duelmasters.us` keresojebol olvassa ki a kepazonositot, majd az `img.duelmasters.us` kepforrast cache-eli.
- Azonos nevu, tobb nyomtatasos lapoknal jelenleg az elso pontos talalat kepet hasznalja.
- Publikus hasznalatnal erdemes kesobb SQLite-rol Postgresre valtani.
- A tenyleges publikalashoz meg szukseges a Render account, a DNS beallitas, a Resend API key, es a mailboxok tenyleges letrehozasa.
