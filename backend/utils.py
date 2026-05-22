from __future__ import annotations

import re
import secrets

CARD_NAME_ALIASES = {
    "Ãœberdragon Bajula": "Uberdragon Bajula",
    "Ãœberdragon Jabaha": "Uberdragon Jabaha",
    "Ãœberdragon Zaschack": "Uberdragon Zaschack",
}


def canonical_card_name(value: str) -> str:
    return CARD_NAME_ALIASES.get(value, value)


def slugify(value: str) -> str:
    value = canonical_card_name(value)
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "card"


def card_key(name: str, set_name: str | None, collector_number: str | None) -> str:
    return f"{slugify(name)}::{slugify(set_name or 'unknown-set')}::{slugify(collector_number or 'unknown-id')}"


def format_image_path(card_id: int) -> str:
    return f"/api/cards/{card_id}/image"


def format_illustration_path(name: str) -> str:
    return f"/assets/assets/card_illustrations/{slugify(name)}.png"


def generate_public_id() -> str:
    return secrets.token_urlsafe(8).lower().replace("_", "").replace("-", "")[:12]
