"""Verify Telegram's signed launch data; never trust initDataUnsafe."""
from dataclasses import dataclass
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class AuthError(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    id: str
    name: str


def telegram_identity(init_data, bot_token, max_age=86400, now=None):
    if not init_data or len(init_data) > 8192:
        raise AuthError("Open the game from the Telegram bot.")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        fields = dict(pairs)
        if len(fields) != len(pairs):
            raise ValueError("Duplicate fields")
        supplied_hash = fields.pop("hash")
        check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied_hash):
            raise AuthError("Telegram authentication failed. Reopen the game.")
        age = (time.time() if now is None else now) - int(fields["auth_date"])
        if age < -30 or age > max_age:
            raise AuthError("Your Telegram session expired. Reopen the game.")
        user = json.loads(fields["user"])
        if type(user["id"]) is not int or user["id"] <= 0:
            raise ValueError("Invalid Telegram ID")
        name = user.get("first_name") or user.get("username") or "Player"
        if not isinstance(name, str):
            raise ValueError("Invalid name")
        return Identity(str(user["id"]), name[:80])
    except (KeyError, ValueError, TypeError) as exc:
        if isinstance(exc, AuthError):
            raise
        raise AuthError("Invalid Telegram launch data. Reopen the game.") from None

