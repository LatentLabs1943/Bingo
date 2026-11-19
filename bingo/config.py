from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> None:
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


@dataclass(frozen=True)
class Settings:
    database_path: str = str(ROOT / "data" / "bingo.sqlite3")
    database_url: str = ""
    serverless: bool = False
    demo_mode: bool = True
    bot_token: str = ""
    webapp_url: str = ""
    webhook_secret: str = ""
    registration_seconds: int = 60
    call_interval_seconds: int = 6
    result_seconds: int = 20
    entry_credits: int = 10
    starting_credits: int = 1000
    auth_max_age_seconds: int = 86400

    def __post_init__(self):
        for field in ("registration_seconds", "call_interval_seconds", "result_seconds",
                      "entry_credits", "starting_credits", "auth_max_age_seconds"):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be positive")
        if not self.demo_mode and not self.bot_token:
            raise ValueError("BOT_TOKEN is required when DEMO_MODE=false")
        if self.serverless and not self.database_url:
            raise ValueError("DATABASE_URL is required on Vercel; local SQLite cannot persist there")
        if self.database_url and not self.database_url.startswith(("postgres://", "postgresql://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL")
        if self.serverless and not self.demo_mode and len(self.webhook_secret) < 32:
            raise ValueError("TELEGRAM_WEBHOOK_SECRET must have at least 32 characters on Vercel")
        if self.webhook_secret and (len(self.webhook_secret) > 256 or
                any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in self.webhook_secret)):
            raise ValueError("TELEGRAM_WEBHOOK_SECRET must use Telegram's supported secret-token characters")

    @classmethod
    def from_env(cls):
        load_env()
        serverless = os.getenv("VERCEL") == "1" or os.getenv("SERVERLESS_MODE", "false").lower() == "true"
        return cls(
            database_path=os.getenv("DATABASE_PATH", str(ROOT / "data" / "bingo.sqlite3")),
            database_url=os.getenv("DATABASE_URL", ""),
            serverless=serverless,
            demo_mode=os.getenv("DEMO_MODE", "false" if serverless else "true").lower() == "true",
            bot_token=os.getenv("BOT_TOKEN", ""),
            webapp_url=os.getenv("WEBAPP_URL", ""),
            webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET", ""),
            **{name: int(os.getenv(name.upper(), default)) for name, default in {
                "registration_seconds": 60, "call_interval_seconds": 6,
                "result_seconds": 20, "entry_credits": 10, "starting_credits": 1000,
                "auth_max_age_seconds": 86400,
            }.items()},
        )

