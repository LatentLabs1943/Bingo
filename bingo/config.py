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
    seat_limit: int = 20
    min_players: int = 2
    admin_telegram_ids: tuple[str, ...] = ()
    owner_telegram_id: str = ""
    funds_mode: str = "practice"
    deposit_instructions: str = ""

    def __post_init__(self):
        for field in ("registration_seconds", "call_interval_seconds", "result_seconds",
                      "entry_credits", "starting_credits", "auth_max_age_seconds"):
            if getattr(self, field) <= 0:
                raise ValueError(f"{field} must be positive")
        if type(self.seat_limit) is not int or not 2 <= self.seat_limit <= 600:
            raise ValueError("seat_limit must be between 2 and 600 reserved cards")
        if type(self.min_players) is not int or not 1 <= self.min_players <= self.seat_limit:
            raise ValueError("min_players must be between 1 and seat_limit")
        if any(not uid.isascii() or not uid.isdigit() or int(uid) <= 0 for uid in self.admin_telegram_ids):
            raise ValueError("ADMIN_TELEGRAM_IDS must contain positive numeric Telegram user IDs")
        if self.owner_telegram_id and (not self.owner_telegram_id.isascii() or not self.owner_telegram_id.isdigit() or int(self.owner_telegram_id) <= 0):
            raise ValueError("OWNER_TELEGRAM_ID must be a positive numeric Telegram user ID")
        if self.funds_mode not in ("practice", "manual"):
            raise ValueError("FUNDS_MODE must be practice or manual")
        if self.funds_mode == "manual" and (self.demo_mode or not self.owner_telegram_id):
            raise ValueError("Manual funding requires Telegram sign-in and OWNER_TELEGRAM_ID")
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
            admin_telegram_ids=tuple(uid.strip() for uid in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if uid.strip()),
            owner_telegram_id=os.getenv("OWNER_TELEGRAM_ID", ""),
            funds_mode=os.getenv("FUNDS_MODE", "practice"),
            deposit_instructions=os.getenv("DEPOSIT_INSTRUCTIONS", ""),
            **{name: int(os.getenv(name.upper(), default)) for name, default in {
                "registration_seconds": 60, "call_interval_seconds": 6,
                "result_seconds": 20, "entry_credits": 10, "starting_credits": 1000,
                "auth_max_age_seconds": 86400,
                "seat_limit": 20, "min_players": 2,
            }.items()},
        )

