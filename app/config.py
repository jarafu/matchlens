import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    secrets_file: Path = field(default_factory=lambda: ROOT / '.env', repr=False)
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/matchlens.db"))
    password_hash: str = field(default_factory=lambda: os.getenv("OWNER_PASSWORD_HASH", ""), repr=False)
    football_token: str = field(default_factory=lambda: os.getenv("FOOTBALL_DATA_TOKEN", ""), repr=False)
    odds_key: str = field(default_factory=lambda: os.getenv("ODDS_API_KEY", ""), repr=False)
    secure_cookies: bool = field(default_factory=lambda: os.getenv("SECURE_COOKIES", "false").lower() == "true")
    timezone: str = field(default_factory=lambda: os.getenv("APP_TIMEZONE", "Africa/Lagos"))
    allowed_hosts: list[str] = field(default_factory=lambda: os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(","))
