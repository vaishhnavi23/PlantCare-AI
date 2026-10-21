"""Application settings. Values come from environment variables or backend/.env (never hard-coded secrets)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")


def _secret_key(data_dir: Path) -> str:
    """Use SECRET_KEY if provided, otherwise create one once and keep it in data/.secret_key (git-ignored)."""
    env = os.getenv("SECRET_KEY")
    if env:
        return env
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / ".secret_key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", BASE_DIR / "data")))
    model_dir: Path = field(default_factory=lambda: Path(os.getenv("MODEL_DIR", BASE_DIR / "models")))
    model_id: str = field(default_factory=lambda: os.getenv("MODEL_ID", "mesabo/agri-plant-disease-resnet50"))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "5")))
    cookie_secure: bool = field(default_factory=lambda: os.getenv("COOKIE_SECURE", "false").lower() == "true")
    session_days: int = field(default_factory=lambda: int(os.getenv("SESSION_DAYS", "7")))
    low_confidence: float = field(default_factory=lambda: float(os.getenv("LOW_CONFIDENCE", "0.60")))
    cors_origins: list = field(default_factory=lambda: [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()])
    openweather_key: str = field(default_factory=lambda: os.getenv("OPENWEATHER_API_KEY", ""))
    secret_key: str = ""

    def __post_init__(self):
        self.data_dir = Path(self.data_dir)
        self.model_dir = Path(self.model_dir)
        if not self.secret_key:
            self.secret_key = _secret_key(self.data_dir)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "plantcare.db"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def experts_file(self) -> Path:
        return self.data_dir / "experts.json"

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)
