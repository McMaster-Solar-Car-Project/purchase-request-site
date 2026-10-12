import logging
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.core.settings import get_settings

logger = logging.getLogger(__name__)


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _resolve_database_url() -> str:
    settings = get_settings()
    raw_url = settings.database_url
    if raw_url:
        return _normalize_postgres_url(raw_url)
    if settings.is_testing:
        return "sqlite:////tmp/purchase_request_site_pytest.sqlite3"
    raise ValueError("❌ Database URL not set. Provide DATABASE_URL.")


DATABASE_URL = _resolve_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class User(Base):
    """User model for storing user profiles."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    personal_email: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    team: Mapped[str] = mapped_column(String(100), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    void_cheque: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)

    @property
    def has_valid_signature(self) -> bool:
        return bool(self.signature_data) and self.signature_data.startswith(
            b"\x89PNG\r\n\x1a\n"
        )

    @property
    def has_valid_void_cheque(self) -> bool:
        return bool(self.void_cheque) and self.void_cheque.startswith(b"%PDF-")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"


class DraftSubmission(Base):
    """Submission receipts, without locally saved draft contents or attachments."""

    __tablename__ = "draft_submissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'succeeded', 'rejected', 'needs_review')",
            name="draft_submission_status",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    draft_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


def get_db():
    """Yield a database session (for use as a FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """Initialize the database by creating tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database initialized successfully")
