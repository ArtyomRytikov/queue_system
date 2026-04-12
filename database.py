import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def _load_legacy_database_url() -> str | None:
    try:
        from config import Config  # type: ignore

        return getattr(Config, "SQLALCHEMY_DATABASE_URI", None)
    except Exception:
        return None


def _resolve_database_url() -> str:
    return (
        os.getenv("DATABASE_URL")
        or _load_legacy_database_url()
        or "sqlite:///./queue_system.db"
    )


DATABASE_URL = _resolve_database_url()


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
