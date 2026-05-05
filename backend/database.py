from __future__ import annotations

from pathlib import Path
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
IMAGE_CACHE_DIR = CACHE_DIR / "images"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "duel_masters.sqlite3"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL.split("://", 1)[0]:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

for directory in (DATA_DIR, CACHE_DIR, IMAGE_CACHE_DIR, RAW_DIR):
    directory.mkdir(parents=True, exist_ok=True)

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
else:
    engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass
