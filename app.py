"""Vercel's FastAPI entrypoint. Database access is deferred until requests."""
from bingo.server import create_app

app = create_app()
