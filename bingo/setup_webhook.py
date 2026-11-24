"""Run once after deployment. Secrets come from the environment, never argv."""
import argparse
import json
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from .bot import configure_bot, telegram, TelegramError
from .config import Settings


def setup(settings, *, check=False):
    url = urlsplit(settings.webapp_url)
    if (url.scheme != "https" or not url.netloc or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/")):
        raise ValueError("WEBAPP_URL must be the public HTTPS origin, without a path or query")
    if not settings.bot_token or len(settings.webhook_secret) < 32:
        raise ValueError("Configure BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET (at least 32 characters)")
    base = settings.webapp_url.rstrip("/")
    target = base + "/api/telegram/webhook"
    if not check:
        try:
            with urlopen(base + "/health", timeout=20) as response:
                healthy = response.status == 200 and json.load(response).get("status") == "ok"
        except (URLError, OSError, ValueError):
            healthy = False
        if not healthy:
            raise ValueError("Public /health check failed. Verify the database and deployment access before registering the webhook")
        configure_bot(settings)
        telegram(settings.bot_token, "setWebhook", {
            "url": target, "secret_token": settings.webhook_secret,
            "allowed_updates": ["message"], "max_connections": 10,
        })
    info = telegram(settings.bot_token, "getWebhookInfo", {})
    matches = info.get("url") == target
    if not matches:
        raise ValueError("Telegram webhook does not match WEBAPP_URL")
    return {"webhook_matches": True, "pending_updates": info.get("pending_update_count", 0),
            "delivery_error": bool(info.get("last_error_message"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check the existing registration without changing it")
    args = parser.parse_args()
    try:
        result = setup(Settings.from_env(), check=args.check)
    except (ValueError, TelegramError) as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
