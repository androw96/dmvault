from __future__ import annotations

import json

from sqlalchemy import inspect, select

from .database import RAW_DIR, SessionLocal, engine
from .models import Base, Card
from .utils import card_key, slugify

RAW_FILE = RAW_DIR / "DuelMastersCards.json"


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    Base.metadata.create_all(bind=engine)


def ensure_schema_updates() -> None:
    if engine.dialect.name != "sqlite":
        # Fresh Render Postgres databases are created from SQLAlchemy models, so
        # the legacy SQLite-only ALTER/PRAGMA migration path is not needed there.
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        if "decks" in existing_tables:
            deck_columns = {column["name"] for column in inspector.get_columns("decks")}
            if "profile_id" not in deck_columns:
                connection.exec_driver_sql("ALTER TABLE decks ADD COLUMN profile_id INTEGER")
            if "cover_image_url" not in deck_columns:
                connection.exec_driver_sql("ALTER TABLE decks ADD COLUMN cover_image_url TEXT")
            if "visibility" not in deck_columns:
                connection.exec_driver_sql("ALTER TABLE decks ADD COLUMN visibility TEXT DEFAULT 'public'")

        if "profiles" in existing_tables:
            profile_columns = {column["name"] for column in inspector.get_columns("profiles")}
            if "email" not in profile_columns:
                connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN email VARCHAR(255)")
            if "password_hash" not in profile_columns:
                connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN password_hash VARCHAR(255)")
            if "email_verified_at" not in profile_columns:
                connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN email_verified_at DATETIME")
                connection.exec_driver_sql(
                    "UPDATE profiles SET email_verified_at = CURRENT_TIMESTAMP WHERE email IS NOT NULL AND password_hash IS NOT NULL"
                )
            if "verification_sent_at" not in profile_columns:
                connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN verification_sent_at DATETIME")
            if "is_admin" not in profile_columns:
                connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN is_admin INTEGER DEFAULT 0")
            if "banned_at" not in profile_columns:
                connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN banned_at DATETIME")
            if "ban_reason" not in profile_columns:
                connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN ban_reason TEXT")
            if "avatar_url" not in profile_columns:
                connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN avatar_url TEXT")

        if "profile_follows" not in existing_tables:
            connection.exec_driver_sql(
                """
                CREATE TABLE profile_follows (
                    id INTEGER NOT NULL PRIMARY KEY,
                    follower_id INTEGER NOT NULL,
                    followed_id INTEGER NOT NULL,
                    CONSTRAINT uq_profile_follow UNIQUE (follower_id, followed_id),
                    FOREIGN KEY(follower_id) REFERENCES profiles (id) ON DELETE CASCADE,
                    FOREIGN KEY(followed_id) REFERENCES profiles (id) ON DELETE CASCADE
                )
                """
            )
        if "deck_revisions" not in existing_tables:
            connection.exec_driver_sql(
                """
                CREATE TABLE deck_revisions (
                    id INTEGER NOT NULL PRIMARY KEY,
                    deck_id INTEGER NOT NULL,
                    version_number INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    visibility VARCHAR(20) DEFAULT 'public',
                    card_total INTEGER DEFAULT 0,
                    change_note VARCHAR(255),
                    snapshot_json TEXT NOT NULL,
                    created_at DATETIME,
                    FOREIGN KEY(deck_id) REFERENCES decks (id) ON DELETE CASCADE
                )
                """
            )
        if "email_verification_tokens" not in existing_tables:
            connection.exec_driver_sql(
                """
                CREATE TABLE email_verification_tokens (
                    id INTEGER NOT NULL PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    token_hash VARCHAR(128) NOT NULL UNIQUE,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME,
                    used_at DATETIME,
                    FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
                )
                """
            )
        if "deck_likes" not in existing_tables:
            connection.exec_driver_sql(
                """
                CREATE TABLE deck_likes (
                    id INTEGER NOT NULL PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    deck_id INTEGER NOT NULL,
                    created_at DATETIME,
                    CONSTRAINT uq_profile_deck_like UNIQUE (profile_id, deck_id),
                    FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE,
                    FOREIGN KEY(deck_id) REFERENCES decks (id) ON DELETE CASCADE
                )
                """
            )
        if "notifications" not in existing_tables:
            connection.exec_driver_sql(
                """
                CREATE TABLE notifications (
                    id INTEGER NOT NULL PRIMARY KEY,
                    profile_id INTEGER NOT NULL,
                    actor_profile_id INTEGER,
                    deck_id INTEGER,
                    type VARCHAR(40) NOT NULL,
                    created_at DATETIME,
                    read_at DATETIME,
                    FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE,
                    FOREIGN KEY(actor_profile_id) REFERENCES profiles (id) ON DELETE SET NULL,
                    FOREIGN KEY(deck_id) REFERENCES decks (id) ON DELETE CASCADE
                )
                """
            )
        else:
            notification_columns = {column["name"] for column in inspector.get_columns("notifications")}
            if "message" not in notification_columns:
                connection.exec_driver_sql("ALTER TABLE notifications ADD COLUMN message TEXT")
        if "admin_audit_logs" not in existing_tables:
            connection.exec_driver_sql(
                """
                CREATE TABLE admin_audit_logs (
                    id INTEGER NOT NULL PRIMARY KEY,
                    admin_profile_id INTEGER NOT NULL,
                    target_profile_id INTEGER,
                    action VARCHAR(60) NOT NULL,
                    detail TEXT,
                    created_at DATETIME,
                    FOREIGN KEY(admin_profile_id) REFERENCES profiles (id) ON DELETE CASCADE,
                    FOREIGN KEY(target_profile_id) REFERENCES profiles (id) ON DELETE SET NULL
                )
                """
            )
        if "contact_messages" not in existing_tables:
            connection.exec_driver_sql(
                """
                CREATE TABLE contact_messages (
                    id INTEGER NOT NULL PRIMARY KEY,
                    profile_id INTEGER,
                    username VARCHAR(80) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    subject VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    created_at DATETIME,
                    read_at DATETIME,
                    FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE SET NULL
                )
                """
            )


def seed_cards_if_needed() -> int:
    initialize_database()
    with SessionLocal() as session:
        existing = session.scalar(select(Card.id).limit(1))
        if not existing:
            seed_cards(session)
        return session.query(Card).count()


def seed_cards(session) -> int:
    payload = json.loads(RAW_FILE.read_text())
    cards = payload.get("cards", [])

    inserted = 0
    for entry in cards:
        civilizations = entry.get("civilizations") or ([entry["civilization"]] if entry.get("civilization") else [])
        race_bits = entry.get("subtypes") or entry.get("races") or ([entry["race"]] if entry.get("race") else [])
        printing = (entry.get("printings") or [{}])[0]
        current = Card(
            card_key=card_key(entry["name"], printing.get("set"), printing.get("id")),
            slug=slugify(entry["name"]),
            name=entry["name"],
            civilizations="|".join(civilizations),
            cost=int(entry.get("cost", 0)),
            type=entry.get("type", "Unknown"),
            race_label=" / ".join(race_bits),
            text=entry.get("text", ""),
            power=str(entry.get("power")) if entry.get("power") is not None else None,
            rarity=printing.get("rarity"),
            set_name=printing.get("set"),
            collector_number=printing.get("id"),
            illustrator=printing.get("illustrator"),
            flavor=printing.get("flavor"),
        )
        session.add(current)
        inserted += 1

    session.commit()
    return inserted


if __name__ == "__main__":
    initialize_database()
    with SessionLocal() as session:
        total = seed_cards(session)
    print(f"Seeded {total} cards.")
