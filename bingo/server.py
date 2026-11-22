import asyncio
from contextlib import asynccontextmanager
import hashlib
import hmac
import logging
import secrets
import threading
import time
from functools import lru_cache
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .auth import AuthError, Identity, telegram_identity
from .bot import reply_for, telegram, TelegramError
from .config import ROOT, Settings
from .engine import Engine, GameError
from .rules import RULES_AM, RULES_EN

logger = logging.getLogger("bingo")


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round_id: str = Field(min_length=32, max_length=32)
    card_id: StrictInt | None = Field(default=None, ge=1, le=600)
    cell: StrictInt | None = Field(default=None, ge=0, le=24)
    enabled: StrictBool | None = None


class TelegramUpdate(BaseModel):
    update_id: StrictInt = Field(ge=0)
    message: dict | None = None


class LazyEngine:
    """Allow Vercel's build/static inspection without opening the database."""
    def __init__(self, settings):
        self.settings = settings
        self.value = None
        self.lock = threading.Lock()

    def __getattr__(self, name):
        if self.value is None:
            with self.lock:
                if self.value is None:
                    self.value = Engine(self.settings)
        return getattr(self.value, name)


def create_app(settings=None):
    settings = settings or Settings.from_env()
    engine = LazyEngine(settings)

    @lru_cache(maxsize=1)
    def demo_key():
        return engine.demo_signing_key()

    async def clock():
        while True:
            try:
                await asyncio.to_thread(engine.tick)
            except Exception:
                logger.exception("Round clock failed; retrying")
            await asyncio.sleep(0.2)

    @asynccontextmanager
    async def lifespan(app):
        if settings.serverless:
            # Each game request advances due state under the database room lock.
            # Never depend on an asyncio task surviving a function invocation.
            yield
            return
        task = asyncio.create_task(clock())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(title="Bingo Telegram Mini App", lifespan=lifespan)
    app.state.engine = engine

    def demo_identity(request):
        raw = request.cookies.get("bingo_demo", "")
        try:
            uid, issued, signature = raw.split(".")
            expected = hmac.new(demo_key(), f"{uid}.{issued}".encode(), hashlib.sha256).hexdigest()
            age = time.time() - int(issued)
            if not hmac.compare_digest(signature, expected) or not 0 <= age < 86400:
                return None
            if not uid.startswith("demo-") or len(uid) != 21:
                return None
            return Identity(uid, "Guest " + uid[-4:].upper())
        except (ValueError, TypeError):
            return None

    def identity(request: Request):
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        if init_data:
            if not settings.bot_token:
                raise HTTPException(401, "Configure BOT_TOKEN to play inside Telegram.")
            try:
                return telegram_identity(init_data, settings.bot_token, settings.auth_max_age_seconds)
            except AuthError as exc:
                raise HTTPException(401, str(exc)) from None
        if settings.demo_mode:
            user = demo_identity(request)
            if user:
                return user
        raise HTTPException(401, "Open the game from the Telegram bot or start a local demo session.")

    @app.middleware("http")
    async def headers_and_origin(request, call_next):
        # Browser mutations must originate from this app. Telegram auth is also
        # required in production; no user-provided Telegram ID is accepted.
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            allowed = {request.headers.get("host", "")}
            if settings.webapp_url:
                allowed.add(urlsplit(settings.webapp_url).netloc)
            if origin and urlsplit(origin).netloc not in allowed:
                return JSONResponse({"detail": "Cross-origin request rejected."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://telegram.org; "
            "style-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "base-uri 'none'; form-action 'self'; "
            "frame-ancestors https://web.telegram.org https://*.telegram.org"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(GameError)
    async def game_error(request, exc):
        return JSONResponse({"detail": str(exc), "code": exc.code},
                            status_code=401 if exc.code == "unauthorized" else 409)

    @app.get("/health")
    def health():
        engine.ping()
        return {"status": "ok"}

    @app.post("/api/telegram/webhook")
    def webhook(body: TelegramUpdate, request: Request):
        if not settings.webhook_secret or not settings.bot_token or not settings.webapp_url:
            raise HTTPException(503, "Telegram webhook is not configured.")
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(supplied.encode(), settings.webhook_secret.encode()):
            raise HTTPException(403, "Invalid webhook secret.")
        claimed = engine.claim_update(body.update_id)
        if claimed == "done":
            return {"ok": True}
        if claimed == "busy":
            raise HTTPException(503, "This update is being processed. Retry shortly.")
        try:
            reply = reply_for(body.model_dump(exclude_none=True), settings)
            if reply:
                telegram(settings.bot_token, "sendMessage", reply, timeout=12)
            engine.complete_update(body.update_id)
        except TelegramError:
            engine.release_update(body.update_id)
            raise HTTPException(503, "Telegram delivery failed. Please retry.") from None
        return {"ok": True}

    @app.get("/api/config")
    def config():
        return {"demo_mode": settings.demo_mode, "rules": {"en": RULES_EN, "am": RULES_AM}}

    @app.post("/api/session")
    def session(request: Request):
        cookie = None
        if settings.demo_mode and not request.headers.get("X-Telegram-Init-Data"):
            user = demo_identity(request)
            if not user:
                uid, issued = "demo-" + secrets.token_hex(8), str(int(time.time()))
                signature = hmac.new(demo_key(), f"{uid}.{issued}".encode(), hashlib.sha256).hexdigest()
                cookie = f"{uid}.{issued}.{signature}"
                user = Identity(uid, "Guest " + uid[-4:].upper())
        else:
            user = identity(request)
        engine.register_user(user.id, user.name)
        response = JSONResponse(engine.state(user.id))
        if cookie:
            response.set_cookie("bingo_demo", cookie, httponly=True, samesite="strict",
                                secure=request.url.scheme == "https", max_age=86400)
        return response

    @app.get("/api/state")
    def state(user=Depends(identity)):
        return engine.state(user.id)

    @app.get("/api/cards/{card_id}")
    def card(card_id: int, user=Depends(identity)):
        return engine.card(card_id)

    @app.post("/api/actions/{action}")
    def action(action: str, body: Action, user=Depends(identity)):
        return engine.act(user.id, body.round_id, action,
                          card_id=body.card_id, cell=body.cell, enabled=body.enabled)

    @app.get("/")
    def index():
        return FileResponse(ROOT / "web" / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
    return app

