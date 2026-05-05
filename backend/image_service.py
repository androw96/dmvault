from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .database import IMAGE_CACHE_DIR
from .models import Card

SEARCH_URL = "https://db.duelmasters.us/search?search_term={query}"
IMAGE_URL_TEMPLATE = "https://img.duelmasters.us/{image_id}.webp"
ROW_PATTERN = re.compile(r'<tr class="results-row" data-id="(?P<image_id>\d+)">\s*<td>\d+\.\s*</td>\s*<td>(?P<name>[^<]+)</td>', re.IGNORECASE)


def resolve_image_metadata(card: Card) -> tuple[str, str] | None:
    query = quote_plus(card.name)
    request = Request(SEARCH_URL.format(query=query), headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", errors="ignore")

    matches = ROW_PATTERN.findall(html)
    normalized_name = card.name.casefold()
    for image_id, candidate_name in matches:
        if candidate_name.casefold() == normalized_name:
            return image_id, IMAGE_URL_TEMPLATE.format(image_id=image_id)
    if matches:
        image_id, _ = matches[0]
        return image_id, IMAGE_URL_TEMPLATE.format(image_id=image_id)
    return None


def ensure_card_image(card: Card) -> Path | None:
    if not card.source_card_image_id:
        metadata = resolve_image_metadata(card)
        if not metadata:
            return None
        card.source_card_image_id, card.source_image_url = metadata

    cache_path = IMAGE_CACHE_DIR / f"{card.source_card_image_id}.webp"
    if cache_path.exists():
        return cache_path

    request = Request(card.source_image_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        cache_path.write_bytes(response.read())

    return cache_path
