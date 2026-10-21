"""Password hashing (scrypt), session tokens (JWT in an HttpOnly cookie) and login throttling."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import jwt

COOKIE_NAME = "pc_session"
_N, _R, _P = 2 ** 14, 8, 1
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(_N, _R, _P, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def password_problem(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 128:
        return "Password is too long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def make_token(user_id: int, secret: str, days: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=days)
    return jwt.encode({"sub": str(user_id), "exp": exp}, secret, algorithm="HS256")


def read_token(token: str, secret: str) -> int | None:
    try:
        return int(jwt.decode(token, secret, algorithms=["HS256"])["sub"])
    except Exception:
        return None


class LoginThrottle:
    """Small in-memory brake on repeated failed logins (per process; resets on restart)."""

    def __init__(self, limit: int = 8, window: int = 600):
        self.limit, self.window = limit, window
        self._fails: dict[str, list[float]] = defaultdict(list)

    def _recent(self, key: str) -> list[float]:
        now = time.time()
        self._fails[key] = [t for t in self._fails[key] if now - t < self.window]
        return self._fails[key]

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.limit

    def fail(self, key: str) -> None:
        self._recent(key).append(time.time())

    def clear(self, key: str) -> None:
        self._fails.pop(key, None)
