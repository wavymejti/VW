"""
Migration runner entrypoint.
Executes all SQL migrations and seeds initial database records.
"""
from db.run_migrations import run_all_migrations, run_seed

if __name__ == "__main__":
    print("🚀 Applying database migrations...")
    total, success = run_all_migrations()
    if total > 0 and success == total:
        print("🌱 Seeding database...")
        run_seed()
    print("✨ Database setup complete.")
