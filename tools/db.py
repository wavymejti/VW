"""
Database connection module for the VW California AI Trip Planner.

Provides a reusable database engine and session factory
using SQLAlchemy with PostGIS support.
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Load environment variables from .env file
load_dotenv()

# Database connection URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_engine():
    """
    Create and return a SQLAlchemy engine using the DATABASE_URL.

    Returns:
        sqlalchemy.engine.Engine: Configured database engine.

    Raises:
        ValueError: If DATABASE_URL is not set.
    """
    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL is not set. "
            "Please configure it in your .env file."
        )
    return create_engine(DATABASE_URL, echo=False)


def get_session():
    """
    Create and return a new database session.

    Returns:
        sqlalchemy.orm.Session: A new session bound to the engine.
    """
    engine = get_engine()
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def verify_connection():
    """
    Verify that the database connection is working and PostGIS
    is available.

    Returns:
        dict: Connection status and PostGIS version info.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # Test basic connectivity
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

            # Check PostGIS availability
            try:
                postgis_result = conn.execute(
                    text("SELECT PostGIS_Version()")
                )
                postgis_version = postgis_result.fetchone()[0]
                postgis_available = True
            except Exception:
                postgis_version = None
                postgis_available = False

            return {
                "status": "connected",
                "database_url": DATABASE_URL.split("@")[-1],
                "postgis_available": postgis_available,
                "postgis_version": postgis_version,
            }
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Run as standalone handshake verification
    print("🔗 Verifying PostgreSQL + PostGIS connection...")
    result = verify_connection()

    if result["status"] == "connected":
        print(f"  ✅ Connected to: {result['database_url']}")
        if result["postgis_available"]:
            print(f"  ✅ PostGIS version: {result['postgis_version']}")
        else:
            print("  ⚠️  PostGIS extension not found. "
                  "Run: CREATE EXTENSION postgis;")
    else:
        print(f"  ❌ Connection failed: {result['message']}")
        sys.exit(1)
