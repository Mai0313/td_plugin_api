"""Tables, sessions and the timestamp form every table uses."""

import os
from typing import Any, ClassVar
from pathlib import Path
from datetime import UTC, datetime

from alembic import command
from sqlalchemy import JSON, Text, Index, String, ForeignKey, LargeBinary, create_engine
from alembic.config import Config
from sqlalchemy.orm import Mapped, Session, DeclarativeBase, sessionmaker, mapped_column
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.dialects.postgresql import JSONB

DEFAULT_DATABASE_URL = "sqlite:///data/td_plugin_api.db"


def database_url() -> str:
    return os.getenv("TD_PLUGIN_API_DATABASE_URL", DEFAULT_DATABASE_URL)


def now() -> datetime:
    """The current time as naive UTC, the form every timestamp column holds."""
    return datetime.now(UTC).replace(tzinfo=None)


def parse_time(text: str) -> datetime:
    """A client's ISO 8601 time with an offset, as naive UTC."""
    return datetime.fromisoformat(text).astimezone(UTC).replace(tzinfo=None)


def format_time(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat(timespec="seconds") + "Z"


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSON().with_variant(JSONB(), "postgresql")
    }


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    handle: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(16), default="member")
    created_at: Mapped[datetime] = mapped_column(default=now)


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    machine_id: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    scopes: Mapped[str] = mapped_column(String(64))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=now)
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    seen_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    machine_id: Mapped[str | None] = mapped_column(String(64))
    slug: Mapped[str | None] = mapped_column(String(200))
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    benchmark: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    visibility: Mapped[str] = mapped_column(String(16))
    has_holding: Mapped[bool]
    language: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]
    payload: Mapped[dict[str, Any]]


class Blob(Base):
    """A body stored once per content hash, shared by every artifact and call output that has it."""

    __tablename__ = "blobs"

    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    size: Mapped[int]
    data: Mapped[bytes] = mapped_column(LargeBinary)


class Artifact(Base):
    __tablename__ = "artifacts"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    path: Mapped[str] = mapped_column(String(500), primary_key=True)
    sha256: Mapped[str] = mapped_column(ForeignKey("blobs.sha256"))
    content_type: Mapped[str] = mapped_column(String(200))
    size: Mapped[int]
    role: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime]


class Call(Base):
    __tablename__ = "calls"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    n: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    sha256: Mapped[str] = mapped_column(ForeignKey("blobs.sha256"))
    payload: Mapped[dict[str, Any]]


class Ruling(Base):
    __tablename__ = "rulings"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    ruled_at: Mapped[datetime] = mapped_column(index=True)
    direction: Mapped[str] = mapped_column(String(16))
    probability: Mapped[float | None]
    confidence: Mapped[str | None] = mapped_column(String(16))
    target_low: Mapped[float]
    target_likely: Mapped[float]
    target_high: Mapped[float]
    check_date: Mapped[str] = mapped_column(String(10))
    action: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(200), index=True)
    reference_date: Mapped[str | None] = mapped_column(String(10))
    reference_close: Mapped[float | None]
    payload: Mapped[dict[str, Any]]


class Followup(Base):
    __tablename__ = "followups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]


class Standing(Base):
    __tablename__ = "standings"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    as_of: Mapped[str] = mapped_column(String(10), primary_key=True)
    payload: Mapped[dict[str, Any]]


class Settlement(Base):
    __tablename__ = "settlements"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    settled_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]


class Reflection(Base):
    __tablename__ = "reflections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]


class Watch(Base):
    __tablename__ = "watchlist"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    updated_at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]


class StartOver(Base):
    __tablename__ = "start_overs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    at: Mapped[datetime]
    payload: Mapped[dict[str, Any]]


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    machine_id: Mapped[str | None] = mapped_column(String(64))
    # No foreign key: a local-first client may report the job before the run reaches the server.
    run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(64))
    ticker: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime] = mapped_column(index=True)
    payload: Mapped[dict[str, Any]]


class Change(Base):
    """One entry of the feed every reader follows, numbered in write order."""

    __tablename__ = "changes"
    __table_args__ = (Index("ix_changes_run_seq", "run_id", "seq"),)

    seq: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(default=now)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    run_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(32))
    ref: Mapped[str] = mapped_column(Text)
    op: Mapped[str] = mapped_column(String(8), default="put")


def open_database(url: str) -> tuple[Engine, sessionmaker[Session]]:
    """Connect to the database at `url`, migrating its tables, and creating its folder for a SQLite file."""
    options: dict[str, Any] = {}
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        # Requests run on a thread pool, so one connection may be used from several threads.
        options["connect_args"] = {"check_same_thread": False}
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **options)
    migrate(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def migrate(engine: Engine) -> None:
    """Bring the database's tables up to the newest migration."""
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
