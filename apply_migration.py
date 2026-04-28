from tools.db import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.begin() as conn:
    with open("db/migrations/002_add_user_password.sql") as f:
        conn.execute(text(f.read()))
print("Migration applied successfully.")
