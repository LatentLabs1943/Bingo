"""Telegram command launcher using the official Bot API (long polling)."""
import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .config import Settings
from .rules import rules_for

logger = logging.getLogger("bingo.bot")


class TelegramError(Exception):
    pass


def telegram(token, method, data, timeout=40):
    request = Request(f"https://api.telegram.org/bot{token}/{method}",
                      data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except HTTPError as exc:
        # HTTPError's URL contains the token. Never log the raw exception.
        raise TelegramError(f"Telegram returned HTTP {exc.code}") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise TelegramError("Telegram network request failed") from None
    if not result.get("ok"):
        raise TelegramError("Telegram rejected the bot request")
    return result["result"]


def reply_for(update, settings):
    """Build a reply for polling or webhook delivery, without sending it."""
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat, text = message.get("chat", {}), message.get("text", "")
    if not isinstance(chat, dict) or chat.get("type") != "private" or type(chat.get("id")) is not int:
        return None
    if not isinstance(text, str):
        return None
    command = text.split(maxsplit=1)[0].split("@")[0].lower() if text.strip() else ""
    if command not in ("/start", "/play", "/rules", "/help"):
        return None
    sender = message.get("from", {})
    language = sender.get("language_code", "") if isinstance(sender, dict) else ""
    amharic = isinstance(language, str) and language.startswith("am")
    if command == "/rules":
        answer = rules_for(settings, "am" if amharic else "en")
    else:
        answer = ("እንኳን ወደ ቢንጎ በደህና መጡ! 🎱\nእስከ 2 ካርዶች ይምረጡ።\n\n"
                  if amharic else "Welcome to Bingo! 🎱\nChoose up to 2 cards, follow the calls, and complete a winning pattern.\n\n")
        answer += ("1 credit = 1 birr · Manual deposit and withdrawal review.\n/rules — How to play"
                   if settings.funds_mode == "manual" else "Demo credits only · No deposits or cash prizes.\n/rules — How to play")
    return {"chat_id": chat["id"], "text": answer,
            "reply_markup": {"inline_keyboard": [[{"text": "🎱 Play Bingo / ይጫወቱ",
                "web_app": {"url": settings.webapp_url}}]]}}


def configure_bot(settings):
    """Configure the same commands and menu in either deployment mode."""
    telegram(settings.bot_token, "setMyCommands", {"commands": [
        {"command": "start", "description": "Open Bingo / ቢንጎ ይጫወቱ"},
        {"command": "play", "description": "Choose your cards"},
        {"command": "rules", "description": "Game rules / የጨዋታ ህጎች"},
        {"command": "help", "description": "How to play"},
    ]})
    telegram(settings.bot_token, "setChatMenuButton", {"menu_button": {
        "type": "web_app", "text": "Play Bingo", "web_app": {"url": settings.webapp_url}}})


def run():
    settings = Settings.from_env()
    if not settings.bot_token:
        raise SystemExit("Set BOT_TOKEN in .env before starting the bot.")
    url = urlsplit(settings.webapp_url)
    if url.scheme != "https" or not url.netloc or url.username or url.password:
        raise SystemExit("Set WEBAPP_URL to the public HTTPS address of this app.")
    token = settings.bot_token
    if telegram(token, "getWebhookInfo", {}).get("url"):
        raise SystemExit("This bot has a webhook. Remove it before using the polling launcher.")
    configure_bot(settings)
    offset = 0
    logger.info("Bot launcher is listening. Credits are for demonstration only.")
    while True:
        try:
            updates = telegram(token, "getUpdates", {"offset": offset, "timeout": 30,
                                                      "allowed_updates": ["message"]})
            for update in updates:
                reply = reply_for(update, settings)
                if reply:
                    telegram(token, "sendMessage", reply)
                offset = update["update_id"] + 1
        except TelegramError as exc:
            logger.warning("%s; retrying in 3 seconds", exc)
            time.sleep(3)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        run()
    except KeyboardInterrupt:
        pass

