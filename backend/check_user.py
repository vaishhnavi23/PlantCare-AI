from app.config import Settings
from app.db import Database

settings = Settings()
database = Database(settings.db_path)

with database.conn() as connection:
    rows = connection.execute(
        "SELECT id, email, name, created_at FROM users WHERE lower(email) = lower(?)",
        ("ushabanakara2004@gmail.com",)
    ).fetchall()

    print([dict(row) for row in rows])