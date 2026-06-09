from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    civilizations: Mapped[str] = mapped_column(Text)
    cost: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(100), index=True)
    race_label: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    power: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rarity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    set_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    collector_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    illustrator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    flavor: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_card_image_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    source_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[int] = mapped_column(Integer, default=0, index=True)
    banned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    decks: Mapped[list["Deck"]] = relationship(back_populates="profile")
    following_links: Mapped[list["ProfileFollow"]] = relationship(
        foreign_keys="ProfileFollow.follower_id",
        back_populates="follower",
        cascade="all, delete-orphan",
    )
    follower_links: Mapped[list["ProfileFollow"]] = relationship(
        foreign_keys="ProfileFollow.followed_id",
        back_populates="followed",
        cascade="all, delete-orphan",
    )
    verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    deck_likes: Mapped[list["DeckLike"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        foreign_keys="Notification.profile_id",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    actor_notifications: Mapped[list["Notification"]] = relationship(
        foreign_keys="Notification.actor_profile_id",
        back_populates="actor",
    )


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    visibility: Mapped[str] = mapped_column(String(20), default="public", index=True)
    deck_format: Mapped[str] = mapped_column(String(40), default="full-tcg", index=True)
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    profile: Mapped[Profile | None] = relationship(back_populates="decks")
    items: Mapped[list["DeckItem"]] = relationship(back_populates="deck", cascade="all, delete-orphan")
    revisions: Mapped[list["DeckRevision"]] = relationship(
        back_populates="deck",
        cascade="all, delete-orphan",
        order_by="DeckRevision.version_number.desc()",
    )
    likes: Mapped[list["DeckLike"]] = relationship(
        back_populates="deck",
        cascade="all, delete-orphan",
    )


class DeckItem(Base):
    __tablename__ = "deck_items"
    __table_args__ = (UniqueConstraint("deck_id", "card_id", name="uq_deck_card"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)

    deck: Mapped[Deck] = relationship(back_populates="items")
    card: Mapped[Card] = relationship()


class DeckRevision(Base):
    __tablename__ = "deck_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(255))
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    card_total: Mapped[int] = mapped_column(Integer, default=0)
    change_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    deck: Mapped[Deck] = relationship(back_populates="revisions")


class ProfileFollow(Base):
    __tablename__ = "profile_follows"
    __table_args__ = (UniqueConstraint("follower_id", "followed_id", name="uq_profile_follow"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    follower_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    followed_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)

    follower: Mapped[Profile] = relationship(foreign_keys=[follower_id], back_populates="following_links")
    followed: Mapped[Profile] = relationship(foreign_keys=[followed_id], back_populates="follower_links")


class DeckLike(Base):
    __tablename__ = "deck_likes"
    __table_args__ = (UniqueConstraint("profile_id", "deck_id", name="uq_profile_deck_like"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    profile: Mapped[Profile] = relationship(back_populates="deck_likes")
    deck: Mapped[Deck] = relationship(back_populates="likes")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    profile: Mapped[Profile] = relationship(back_populates="verification_tokens")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    profile: Mapped[Profile] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    actor_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    deck_id: Mapped[int | None] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    profile: Mapped[Profile] = relationship(foreign_keys=[profile_id], back_populates="notifications")
    actor: Mapped[Profile | None] = relationship(foreign_keys=[actor_profile_id], back_populates="actor_notifications")
    deck: Mapped[Deck | None] = relationship()


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    target_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(80), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    profile: Mapped[Profile | None] = relationship()


class PlayMatch(Base):
    __tablename__ = "play_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="live", index=True)
    status: Mapped[str] = mapped_column(String(20), default="waiting", index=True)
    player_one_profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    player_one_deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), index=True)
    player_two_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    player_two_deck_id: Mapped[int | None] = mapped_column(ForeignKey("decks.id", ondelete="SET NULL"), nullable=True, index=True)
    active_seat: Mapped[int] = mapped_column(Integer, default=1)
    current_turn: Mapped[int] = mapped_column(Integer, default=1)
    turn_deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    winner_profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    state_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    player_one_profile: Mapped[Profile] = relationship(foreign_keys=[player_one_profile_id])
    player_one_deck: Mapped[Deck] = relationship(foreign_keys=[player_one_deck_id])
    player_two_profile: Mapped[Profile | None] = relationship(foreign_keys=[player_two_profile_id])
    player_two_deck: Mapped[Deck | None] = relationship(foreign_keys=[player_two_deck_id])
    winner_profile: Mapped[Profile | None] = relationship(foreign_keys=[winner_profile_id])
