from getpass import getpass
from app.config import Settings
from app.db import Database
from app.security import hash_password, password_problem

email = input("Enter your registered email: ").strip().lower()
new_password = getpass("Enter a NEW password (input stays hidden): ")
problem = password_problem(new_password)

if problem:
    print(problem)
    raise SystemExit(1)

confirm = getpass("Enter the new password again: ")
if new_password != confirm:
    print("Passwords do not match. Nothing changed.")
    raise SystemExit(1)

settings = Settings()
database = Database(settings.db_path)

with database.conn() as connection:
    user = connection.execute(
        "SELECT id FROM users WHERE lower(email) = ?",
        (email,)
    ).fetchone()

    if user is None:
        print("No account found for that email. Nothing changed.")
        raise SystemExit(1)

    connection.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(new_password), user["id"])
    )

print("Password updated successfully. Your account and plant records are preserved.")