from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from backend.database import SessionLocal
from backend.models import Card, Deck, DeckItem, DeckLike, DeckRevision, Notification, Profile, ProfileFollow
from backend.seed import initialize_database

SOURCE_DB = Path(os.getenv("SOURCE_SQLITE_PATH", "/Users/ozymandias/Documents/Crystal Vault/backend/data/duel_masters.sqlite3"))


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_rows(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return connection.execute(f"SELECT * FROM {table}").fetchall()


def ensure_card_map(source_rows: list[sqlite3.Row], db) -> dict[int, int]:
    target_by_key = {card.card_key: card for card in db.scalars(select(Card)).all()}
    card_id_map: dict[int, int] = {}

    for row in source_rows:
        card_key = row["card_key"]
        target = target_by_key.get(card_key)
        if not target:
            target = Card(
                card_key=card_key,
                slug=row["slug"],
                name=row["name"],
                civilizations=row["civilizations"],
                cost=row["cost"],
                type=row["type"],
                race_label=row["race_label"] or "",
                text=row["text"] or "",
                power=row["power"],
                rarity=row["rarity"],
                set_name=row["set_name"],
                collector_number=row["collector_number"],
                illustrator=row["illustrator"],
                flavor=row["flavor"],
                source_card_image_id=row["source_card_image_id"],
                source_image_url=row["source_image_url"],
                image_status=row["image_status"] or "pending",
            )
            db.add(target)
            db.flush()
            target_by_key[card_key] = target
        card_id_map[row["id"]] = target.id
    return card_id_map


def migrate() -> None:
    if not SOURCE_DB.exists():
        raise SystemExit(f"Source SQLite database not found: {SOURCE_DB}")

    initialize_database()

    source = sqlite3.connect(SOURCE_DB)
    source.row_factory = sqlite3.Row

    cards = load_rows(source, "cards")
    profiles = load_rows(source, "profiles")
    decks = load_rows(source, "decks")
    deck_items = load_rows(source, "deck_items")

    try:
        deck_revisions = load_rows(source, "deck_revisions")
    except sqlite3.OperationalError:
        deck_revisions = []
    try:
        profile_follows = load_rows(source, "profile_follows")
    except sqlite3.OperationalError:
        profile_follows = []
    try:
        deck_likes = load_rows(source, "deck_likes")
    except sqlite3.OperationalError:
        deck_likes = []
    try:
        notifications = load_rows(source, "notifications")
    except sqlite3.OperationalError:
        notifications = []

    with SessionLocal() as db:
        card_id_map = ensure_card_map(cards, db)

        profile_id_map: dict[int, int] = {}
        for row in profiles:
            target = db.scalar(select(Profile).where(Profile.username == row["username"]))
            if not target:
                target = Profile(
                    username=row["username"],
                    display_name=row["username"],
                    email=row["email"],
                    email_verified_at=parse_dt(row["email_verified_at"]),
                    verification_sent_at=parse_dt(row["verification_sent_at"]),
                    password_hash=row["password_hash"],
                    is_admin=row["is_admin"] or 0,
                    banned_at=parse_dt(row["banned_at"]),
                    ban_reason=row["ban_reason"],
                    avatar_url=row["avatar_url"],
                    bio=row["bio"],
                )
                db.add(target)
                db.flush()
            else:
                target.email = row["email"]
                target.password_hash = row["password_hash"]
                target.avatar_url = row["avatar_url"]
                target.bio = row["bio"]
                target.email_verified_at = parse_dt(row["email_verified_at"])
                target.verification_sent_at = parse_dt(row["verification_sent_at"])
                target.is_admin = row["is_admin"] or 0
                target.banned_at = parse_dt(row["banned_at"])
                target.ban_reason = row["ban_reason"]
            profile_id_map[row["id"]] = target.id

        deck_id_map: dict[int, int] = {}
        for row in decks:
            target = db.scalar(select(Deck).where(Deck.public_id == row["public_id"]))
            mapped_profile_id = profile_id_map.get(row["profile_id"]) if row["profile_id"] is not None else None
            if not target:
                target = Deck(
                    public_id=row["public_id"],
                    title=row["title"],
                    visibility=row["visibility"] or "public",
                    cover_image_url=row["cover_image_url"],
                    profile_id=mapped_profile_id,
                    created_at=parse_dt(row["created_at"]) or datetime.utcnow(),
                    updated_at=parse_dt(row["updated_at"]) or datetime.utcnow(),
                )
                db.add(target)
                db.flush()
            else:
                target.title = row["title"]
                target.visibility = row["visibility"] or "public"
                target.cover_image_url = row["cover_image_url"]
                target.profile_id = mapped_profile_id
                target.created_at = parse_dt(row["created_at"]) or target.created_at
                target.updated_at = parse_dt(row["updated_at"]) or target.updated_at
            deck_id_map[row["id"]] = target.id

        existing_items = {
            (item.deck_id, item.card_id): item
            for item in db.scalars(select(DeckItem)).all()
        }
        for row in deck_items:
            mapped_deck_id = deck_id_map[row["deck_id"]]
            mapped_card_id = card_id_map[row["card_id"]]
            key = (mapped_deck_id, mapped_card_id)
            item = existing_items.get(key)
            if item:
                item.quantity = row["quantity"]
            else:
                item = DeckItem(deck_id=mapped_deck_id, card_id=mapped_card_id, quantity=row["quantity"])
                db.add(item)
                existing_items[key] = item

        existing_revisions = {
            (revision.deck_id, revision.version_number): revision
            for revision in db.scalars(select(DeckRevision)).all()
        }
        for row in deck_revisions:
            mapped_deck_id = deck_id_map[row["deck_id"]]
            key = (mapped_deck_id, row["version_number"])
            revision = existing_revisions.get(key)
            if revision:
                continue
            revision = DeckRevision(
                deck_id=mapped_deck_id,
                version_number=row["version_number"],
                title=row["title"],
                visibility=row["visibility"] or "public",
                card_total=row["card_total"] or 0,
                change_note=row["change_note"],
                snapshot_json=row["snapshot_json"] or json.dumps({}),
                created_at=parse_dt(row["created_at"]) or datetime.utcnow(),
            )
            db.add(revision)
            existing_revisions[key] = revision

        existing_follows = {(follow.follower_id, follow.followed_id) for follow in db.scalars(select(ProfileFollow)).all()}
        for row in profile_follows:
            key = (profile_id_map[row["follower_id"]], profile_id_map[row["followed_id"]])
            if key in existing_follows:
                continue
            db.add(ProfileFollow(follower_id=key[0], followed_id=key[1]))
            existing_follows.add(key)

        existing_likes = {(like.profile_id, like.deck_id) for like in db.scalars(select(DeckLike)).all()}
        for row in deck_likes:
            key = (profile_id_map[row["profile_id"]], deck_id_map[row["deck_id"]])
            if key in existing_likes:
                continue
            db.add(DeckLike(profile_id=key[0], deck_id=key[1], created_at=parse_dt(row["created_at"]) or datetime.utcnow()))
            existing_likes.add(key)

        existing_notifications = {
            (notification.profile_id, notification.actor_profile_id, notification.deck_id, notification.type, notification.created_at)
            for notification in db.scalars(select(Notification)).all()
        }
        for row in notifications:
            created_at = parse_dt(row["created_at"]) or datetime.utcnow()
            key = (
                profile_id_map[row["profile_id"]],
                profile_id_map.get(row["actor_profile_id"]) if row["actor_profile_id"] is not None else None,
                deck_id_map.get(row["deck_id"]) if row["deck_id"] is not None else None,
                row["type"],
                created_at,
            )
            if key in existing_notifications:
                continue
            db.add(
                Notification(
                    profile_id=key[0],
                    actor_profile_id=key[1],
                    deck_id=key[2],
                    type=row["type"],
                    message=row["message"],
                    created_at=created_at,
                    read_at=parse_dt(row["read_at"]),
                )
            )
            existing_notifications.add(key)

        db.commit()

        print(
            json.dumps(
                {
                    "cards": len(card_id_map),
                    "profiles": len(profile_id_map),
                    "decks": len(deck_id_map),
                    "deck_items": len(deck_items),
                    "deck_revisions": len(deck_revisions),
                    "profile_follows": len(profile_follows),
                    "deck_likes": len(deck_likes),
                    "notifications": len(notifications),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    migrate()
