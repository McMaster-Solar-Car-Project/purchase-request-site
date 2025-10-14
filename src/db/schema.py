import base64
import os

from sqlalchemy import Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.core.logging_utils import setup_logger

logger = setup_logger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL environment variable is not set.")

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

    def get_signature_as_base64(self) -> str | None:
        """Return the signature as a base64-encoded string (for display)."""
        if self.signature_data:
            return base64.b64encode(self.signature_data).decode("utf-8")
        return None

    def set_signature_from_base64(self, base64_data: str):
        """Set the signature binary data from a base64-encoded string."""
        if base64_data:
            self.signature_data = base64.b64decode(base64_data)


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
