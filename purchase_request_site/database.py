import base64
import os
from datetime import datetime

from logging_utils import setup_logger
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Set up the logger
logger = setup_logger(__name__)
# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")


engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


class User(Base):
    """User model for storing user profiles"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(
        String(255), nullable=False, unique=True, index=True
    )  # McMaster email
    personal_email = Column(String(255), nullable=False)  # E-transfer email
    address = Column(Text, nullable=False)
    team = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)  # User password
    signature_data = Column(
        LargeBinary, nullable=True
    )  # Store signature image as binary (always PNG, always named signature.png)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"

    def get_signature_as_base64(self) -> str:
        """Convert signature binary data to base64 string for display"""
        if self.signature_data:
            return base64.b64encode(self.signature_data).decode("utf-8")
        return None

    def set_signature_from_base64(self, base64_data: str):
        """Set signature from base64 string"""
        if base64_data:
            self.signature_data = base64.b64decode(base64_data)


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """Initialize database - create tables if they don't exist"""
    create_tables()
    logger.info("✅ Database initialized successfully")
