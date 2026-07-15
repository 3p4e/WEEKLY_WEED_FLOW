"""
Database session management for Cannabis EU GMP QMS Creator.

Handles SQLAlchemy session creation, configuration, and lifecycle.
"""

import logging
import os
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine, event, pool
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database configuration.

        Args:
            database_url: PostgreSQL connection URL or None to use environment variable
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "postgresql://qmsuser:qmspassword@localhost:5432/qms"
        )
        self.echo = os.getenv("DATABASE_ECHO", "false").lower() == "true"
        self.pool_size = int(os.getenv("DATABASE_POOL_SIZE", "20"))
        self.max_overflow = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
        self.pool_recycle = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))
        self.pool_pre_ping = True  # Test connections before using them


class DatabaseManager:
    """Manages database connections and sessions."""

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, config: Optional[DatabaseConfig] = None) -> None:
        """
        Initialize the database engine and session factory.

        Args:
            config: DatabaseConfig instance or None to use defaults
        """
        if config is None:
            config = DatabaseConfig()

        logger.info(f"Initializing database with URL: {config.database_url}")

        cls._engine = create_engine(
            config.database_url,
            echo=config.echo,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_recycle=config.pool_recycle,
            pool_pre_ping=config.pool_pre_ping,
            connect_args={"check_same_thread": False}
            if "sqlite" in config.database_url
            else {},
        )

        # Add event listener for connection pool logging
        @event.listens_for(cls._engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            logger.debug("Database connection acquired")

        @event.listens_for(cls._engine, "close")
        def receive_close(dbapi_conn, connection_record):
            logger.debug("Database connection released")

        cls._session_factory = sessionmaker(
            bind=cls._engine,
            expire_on_commit=False,
            autoflush=False,
        )

        logger.info("Database initialization complete")

    @classmethod
    def get_engine(cls) -> Engine:
        """Get the SQLAlchemy engine."""
        if cls._engine is None:
            cls.initialize()
        return cls._engine

    @classmethod
    def get_session_factory(cls) -> sessionmaker:
        """Get the session factory."""
        if cls._session_factory is None:
            cls.initialize()
        return cls._session_factory

    @classmethod
    def create_session(cls) -> Session:
        """Create a new database session."""
        factory = cls.get_session_factory()
        return factory()

    @classmethod
    def create_all(cls) -> None:
        """Create all database tables."""
        engine = cls.get_engine()
        logger.info("Creating database tables")
        Base.metadata.create_all(engine)
        logger.info("Database tables created successfully")

    @classmethod
    def drop_all(cls) -> None:
        """Drop all database tables (dangerous!)."""
        engine = cls.get_engine()
        logger.warning("Dropping all database tables")
        Base.metadata.drop_all(engine)
        logger.warning("All database tables dropped")

    @classmethod
    def close(cls) -> None:
        """Close all database connections."""
        if cls._engine is not None:
            logger.info("Closing database connections")
            cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Usage in FastAPI:
        @app.get("/documents")
        def get_documents(db: Session = Depends(get_db_session)):
            return db.query(Document).all()

    Yields:
        SQLAlchemy Session
    """
    session = DatabaseManager.create_session()
    try:
        yield session
    finally:
        session.close()


def init_db(database_url: Optional[str] = None) -> None:
    """
    Initialize the database.

    Args:
        database_url: Optional database URL to override environment variable
    """
    config = DatabaseConfig(database_url)
    DatabaseManager.initialize(config)
    DatabaseManager.create_all()


def close_db() -> None:
    """Close the database connection."""
    DatabaseManager.close()


# Convenience functions
def get_db() -> Session:
    """Get a new database session (non-async version)."""
    return DatabaseManager.create_session()
