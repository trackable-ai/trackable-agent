"""
Database connection management for Cloud SQL.

Uses Cloud SQL Python Connector with IAM authentication and SQLAlchemy connection pooling.
"""

import os
from contextlib import contextmanager
from typing import Generator

from google.cloud.sql.connector import Connector
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class DatabaseConnection:
    """
    Manages database connections with Cloud SQL Python Connector.

    This class provides connection pooling optimized for Cloud Run environments.
    Uses IAM authentication for secure, password-less connections.

    Usage:
        # Initialize at app startup
        DatabaseConnection.initialize(
            instance_connection_name="project:region:instance",
            db_name="trackable",
            db_user="service-account@project.iam"
        )

        # Use sessions
        with DatabaseConnection.session() as session:
            # perform database operations
            pass

        # Close at app shutdown
        DatabaseConnection.close()
    """

    _engine: Engine | None = None
    _connector: Connector | None = None
    _session_factory: sessionmaker | None = None
    _initialized: bool = False

    @classmethod
    def initialize(
        cls,
        instance_connection_name: str | None = None,
        db_name: str | None = None,
        db_user: str | None = None,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: int = 30,
        pool_recycle: int = 1800,
    ):
        """
        Initialize the database connection pool.

        Args:
            instance_connection_name: Cloud SQL instance (project:region:instance)
            db_name: Database name
            db_user: Database user (service account email for IAM auth)
            pool_size: Base connection pool size
            max_overflow: Additional connections allowed beyond pool_size
            pool_timeout: Seconds to wait for a connection
            pool_recycle: Recycle connections after this many seconds
        """
        if cls._initialized:
            return

        # Get config from environment if not provided
        instance_connection_name = instance_connection_name or os.getenv(
            "INSTANCE_CONNECTION_NAME"
        )
        db_name = db_name or os.getenv("DB_NAME", "trackable")
        db_user = db_user or os.getenv("DB_USER")

        if not instance_connection_name:
            raise ValueError(
                "INSTANCE_CONNECTION_NAME environment variable is required. "
                "Format: project:region:instance"
            )

        if not db_user:
            raise ValueError(
                "DB_USER environment variable is required. "
                "Should be service account email for IAM auth."
            )

        cls._connector = Connector()

        def getconn():
            assert cls._connector is not None
            return cls._connector.connect(
                instance_connection_name,
                "pg8000",
                user=db_user,
                db=db_name,
                enable_iam_auth=True,
            )

        cls._engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Verify connections before use
        )

        cls._session_factory = sessionmaker(bind=cls._engine)
        cls._initialized = True

    @classmethod
    def get_engine(cls) -> Engine:
        """Get the SQLAlchemy engine."""
        if not cls._initialized or cls._engine is None:
            raise RuntimeError(
                "Database not initialized. Call DatabaseConnection.initialize() first."
            )
        return cls._engine

    @classmethod
    @contextmanager
    def session(cls) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.

        Automatically commits on success and rolls back on exception.

        Yields:
            SQLAlchemy Session

        Example:
            with DatabaseConnection.session() as session:
                session.execute(...)
        """
        if not cls._initialized or cls._session_factory is None:
            raise RuntimeError(
                "Database not initialized. Call DatabaseConnection.initialize() first."
            )

        session = cls._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @classmethod
    def close(cls):
        """Close the connection pool and connector."""
        if cls._engine:
            cls._engine.dispose()
            cls._engine = None

        if cls._connector:
            cls._connector.close()
            cls._connector = None

        cls._session_factory = None
        cls._initialized = False

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the database connection is initialized."""
        return cls._initialized

    @classmethod
    def get_session(cls) -> Session:
        """
        Get a new database session.

        The caller is responsible for committing/rolling back and closing the session.
        For automatic lifecycle management, use the session() context manager instead.

        Returns:
            SQLAlchemy Session

        Example:
            session = DatabaseConnection.get_session()
            try:
                session.execute(...)
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        """
        if not cls._initialized or cls._session_factory is None:
            raise RuntimeError(
                "Database not initialized. Call DatabaseConnection.initialize() first."
            )

        return cls._session_factory()
