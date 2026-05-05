from __future__ import annotations

from pydantic import BaseModel, Field


class CardOut(BaseModel):
    id: int
    name: str
    civilizations: list[str]
    cost: int
    type: str
    race_label: str
    text: str
    power: str | None = None
    rarity: str | None = None
    set_name: str | None = None
    collector_number: str | None = None
    image_path: str | None = None


class CardListResponse(BaseModel):
    items: list[CardOut]
    total: int


class MetadataResponse(BaseModel):
    civilizations: list[str]
    types: list[str]
    max_cost: int


class ProfileOut(BaseModel):
    id: int
    username: str
    display_name: str
    email: str | None = None
    email_verified: bool = False
    is_admin: bool = False
    is_banned: bool = False
    avatar_url: str | None = None
    bio: str | None = None
    follower_count: int = 0
    following_count: int = 0
    followed_by_viewer: bool = False


class ProfileListResponse(BaseModel):
    items: list[ProfileOut]


class ProfileCreateIn(BaseModel):
    username: str
    display_name: str
    email: str | None = None
    avatar_url: str | None = None
    bio: str | None = None


class ProfileUpdateIn(BaseModel):
    username: str | None = None
    avatar_url: str | None = None
    bio: str | None = None


class ProfileDeleteIn(BaseModel):
    password: str


class AuthRegisterIn(BaseModel):
    email: str
    password: str
    username: str
    display_name: str
    avatar_url: str | None = None


class AuthLoginIn(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    profile: ProfileOut
    verification_required: bool = False
    verification_email_sent: bool = False
    message: str | None = None
    verification_url: str | None = None


class VerificationResendIn(BaseModel):
    email: str


class GenericMessageOut(BaseModel):
    status: str
    message: str
    verification_url: str | None = None


class NotificationOut(BaseModel):
    id: int
    type: str
    message: str | None = None
    created_at_label: str
    actor: ProfileOut | None = None
    deck_public_id: str | None = None
    deck_title: str | None = None
    read: bool = False


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]


class DeckCardIn(BaseModel):
    card_id: int
    quantity: int = Field(ge=1, le=4)


class DeckCreateIn(BaseModel):
    public_id: str | None = None
    title: str
    visibility: str = "public"
    cover_image_url: str | None = None
    profile_id: int | None = None
    change_note: str | None = None
    cards: list[DeckCardIn]


class DeckCardOut(BaseModel):
    card: CardOut
    quantity: int


class DeckSummaryOut(BaseModel):
    public_id: str
    title: str
    visibility: str = "public"
    cover_image_url: str | None = None
    civilizations: list[str] = []
    card_names: list[str] = []
    card_total: int
    updated_at_label: str
    owner: ProfileOut | None = None
    share_url: str | None = None
    like_count: int = 0
    liked_by_viewer: bool = False
    liked_by: list[ProfileOut] = []


class ProfileDetailOut(ProfileOut):
    decks: list[DeckSummaryOut]
    following: list[ProfileOut]
    liked_decks: list[DeckSummaryOut] = []


class DeckListResponse(BaseModel):
    items: list[DeckSummaryOut]


class DeckOut(BaseModel):
    public_id: str
    title: str
    visibility: str = "public"
    cover_image_url: str | None = None
    owner: ProfileOut | None = None
    cards: list[DeckCardOut]
    share_url: str
    pdf_url: str
    like_count: int = 0
    liked_by_viewer: bool = False
    liked_by: list[ProfileOut] = []


class DeckCreateOut(BaseModel):
    public_id: str
    title: str
    visibility: str = "public"
    cover_image_url: str | None = None
    share_url: str
    pdf_url: str


class DeckHistoryEntryOut(BaseModel):
    card_name: str
    change_type: str
    created_at_label: str


class DeckHistoryResponse(BaseModel):
    items: list[DeckHistoryEntryOut]


class FollowToggleIn(BaseModel):
    follower_profile_id: int


class DeckLikeToggleIn(BaseModel):
    profile_id: int


class AdminNotificationIn(BaseModel):
    admin_profile_id: int
    message: str
    target_profile_id: int | None = None


class AdminBanIn(BaseModel):
    admin_profile_id: int
    target_profile_id: int
    banned: bool = True
    reason: str | None = None


class MonthlyStatOut(BaseModel):
    label: str
    count: int


class AdminOverviewOut(BaseModel):
    total_profiles: int
    total_decks: int
    public_decks: int
    private_decks: int
    banned_profiles: int
    database_tables: dict[str, int]
    recent_profiles: list[ProfileOut]
    all_profiles: list[ProfileOut]
    recent_decks: list[DeckSummaryOut]
    profiles_by_month: list[MonthlyStatOut]
    decks_by_month: list[MonthlyStatOut]
    audit_log: list[dict[str, str | int | None]]
