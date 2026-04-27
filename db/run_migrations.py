"""
Database migration runner for the VW California AI Trip Planner.

Executes SQL migration files against the configured database
using the SQLAlchemy engine from tools/db.py.

Usage:
    python3 -m db.run_migrations
"""

import os
import sys
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.db import get_engine


# Directory containing migration SQL files
MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "migrations"
)


def run_migration(filepath):
    """
    Execute a single SQL migration file against the database.

    Args:
        filepath (str): Absolute path to the .sql file.

    Returns:
        bool: True if migration succeeded, False otherwise.
    """
    filename = os.path.basename(filepath)
    print(f"  ▶ Running: {filename}")

    try:
        with open(filepath, "r") as f:
            sql_content = f.read()

        engine = get_engine()
        with engine.connect() as conn:
            # Execute the entire SQL file as a single transaction
            conn.execute(text(sql_content))
            conn.commit()

        print(f"  ✅ {filename} — applied successfully")
        return True

    except Exception as e:
        print(f"  ❌ {filename} — failed: {e}")
        return False


def run_all_migrations():
    """
    Discover and run all SQL migration files in order.

    Returns:
        tuple: (total_count, success_count)
    """
    # Find all .sql files, sorted by name (number prefix)
    migration_files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR)
        if f.endswith(".sql")
    )

    if not migration_files:
        print("  ⚠️  No migration files found.")
        return 0, 0

    total = len(migration_files)
    success = 0

    for filename in migration_files:
        filepath = os.path.join(MIGRATIONS_DIR, filename)
        if run_migration(filepath):
            success += 1

    return total, success


def run_seed():
    """
    Execute the seed.sql file to populate sample data.

    Returns:
        bool: True if seeding succeeded, False otherwise.
    """
    seed_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "seed.sql"
    )

    if not os.path.exists(seed_path):
        print("  ⚠️  No seed.sql found.")
        return False

    return run_migration(seed_path)


if __name__ == "__main__":
    print("🗄️  VW Trip Planner — Database Setup")
    print("=" * 55)

    # Run migrations
    print("\n📦 Running migrations...")
    total, success = run_all_migrations()
    print(f"\n  Migrations: {success}/{total} applied")

    # Ask about seeding
    if success == total and total > 0:
        print("\n🌱 Running seed data...")
        if run_seed():
            print("\n✅ Database fully set up and seeded!")
        else:
            print("\n⚠️  Seeding had issues (see above).")
    elif total == 0:
        print("\n⚠️  No migrations to run.")
    else:
        print(
            "\n⚠️  Some migrations failed. "
            "Fix errors before seeding."
        )

    print("=" * 55)
