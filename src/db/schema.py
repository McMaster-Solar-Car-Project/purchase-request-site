import sys

from sqlalchemy import Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.core.logging_utils import setup_logger
from src.core.settings import get_settings

logger = setup_logger(__name__)


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _resolve_database_url() -> str:
    settings = get_settings()
    if "pytest" in sys.modules:
        return "sqlite:////tmp/purchase_request_site_pytest.sqlite3"
    raw_url = settings.aiven_database_url.strip()
    if raw_url:
        return _normalize_postgres_url(raw_url)
    if settings.is_testing:
        return "sqlite:////tmp/purchase_request_site_pytest.sqlite3"
    raise ValueError("❌ Database URL not set. Provide AIVEN_DATABASE_URL.")


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
    signature_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"


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
