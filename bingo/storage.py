"""Transactional storage for the local demo and shared Vercel instances.

One room is serialized by BEGIN IMMEDIATE locally, or a transaction-scoped
PostgreSQL advisory lock in production. No session lock or in-memory state is
required, so a transaction-pooling database URL can be used on Vercel.
"""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

ROOM_LOCK = 468879738075  # Stable lock ID shared by this single-room application.

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, balance TEXT NOT NULL,
    automatic INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY, cells TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS rounds (
    id TEXT PRIMARY KEY, created {timestamp} NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS round_created ON rounds(created DESC);
CREATE TABLE IF NOT EXISTS entries (
    round_id TEXT NOT NULL REFERENCES rounds(id),
    card_id INTEGER NOT NULL REFERENCES cards(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    marks TEXT NOT NULL DEFAULT '[12]', PRIMARY KEY (round_id, card_id)
);
CREATE INDEX IF NOT EXISTS entry_user ON entries(round_id, user_id);
CREATE TABLE IF NOT EXISTS ledger (
    id {identity}, user_id TEXT NOT NULL, round_id TEXT,
    amount TEXT NOT NULL, reason TEXT NOT NULL, created {timestamp} NOT NULL
);
CREATE TABLE IF NOT EXISTS telegram_updates (
    update_id BIGINT PRIMARY KEY, done INTEGER NOT NULL DEFAULT 0,
    lease_until {timestamp} NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_events (
    id {identity}, user_id TEXT NOT NULL, created {timestamp} NOT NULL,
    settings TEXT NOT NULL, version INTEGER NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS admin_members (
    user_id TEXT PRIMARY KEY, added_by TEXT NOT NULL, created {timestamp} NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_revocations (
    user_id TEXT PRIMARY KEY, revoked_by TEXT NOT NULL, created {timestamp} NOT NULL
);
CREATE TABLE IF NOT EXISTS owner_events (
    id {identity}, user_id TEXT NOT NULL, action TEXT NOT NULL,
    target TEXT NOT NULL, created {timestamp} NOT NULL
);
CREATE TABLE IF NOT EXISTS wallets (
    user_id TEXT PRIMARY KEY REFERENCES users(id), balance TEXT NOT NULL DEFAULT '0'
);
CREATE TABLE IF NOT EXISTS wallet_ledger (
    id {identity}, user_id TEXT NOT NULL, round_id TEXT, request_id TEXT,
    amount TEXT NOT NULL, reason TEXT NOT NULL, created {timestamp} NOT NULL
);
CREATE TABLE IF NOT EXISTS money_requests (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL,
    status TEXT NOT NULL, amount TEXT NOT NULL, reference TEXT UNIQUE, account TEXT NOT NULL,
    receipt TEXT, created {timestamp} NOT NULL, reviewed {timestamp}, reviewer TEXT,
    note TEXT NOT NULL DEFAULT '', payment_reference TEXT UNIQUE, idempotency_key TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS request_user_created ON money_requests(user_id,created DESC);
CREATE TABLE IF NOT EXISTS house_ledger (
    round_id TEXT PRIMARY KEY REFERENCES rounds(id), funds_mode TEXT NOT NULL,
    gross TEXT NOT NULL, fee TEXT NOT NULL, prize_pool TEXT NOT NULL,
    created {timestamp} NOT NULL
);
"""


class Row(dict):
    """Support named columns and scalar [0] reads on both database backends."""
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        row = self.cursor.fetchone()
        return Row(row) if row is not None else None

    def fetchall(self):
        return [Row(row) for row in self.cursor.fetchall()]


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, parameters=()):
        # Engine queries are static SQL; '?' is used only as a value placeholder.
        return Cursor(self.connection.execute(query.replace("?", "%s"), parameters))

    def executemany(self, query, rows):
        with self.connection.cursor() as cursor:
            cursor.executemany(query.replace("?", "%s"), rows)


class Store:
    def __init__(self, settings):
        self.url = settings.database_url
        self.path = settings.database_path
        if not self.url:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def transaction(self):
        if self.url:
            import psycopg
            from psycopg.rows import dict_row
            # Disable prepared statements for compatibility with pooled URLs.
            with psycopg.connect(self.url, connect_timeout=10, prepare_threshold=None,
                                 row_factory=dict_row) as connection:
                connection.execute("SET LOCAL lock_timeout = '10s'")
                connection.execute("SET LOCAL statement_timeout = '20s'")
                connection.execute("SELECT pg_advisory_xact_lock(%s)", (ROOM_LOCK,))
                yield PostgresConnection(connection)
            return
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def initialize(self, db):
        schema = SCHEMA.format(
            timestamp="DOUBLE PRECISION" if self.url else "REAL",
            identity="BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY" if self.url else "INTEGER PRIMARY KEY",
        )
        # Execute statements separately: sqlite executescript would commit and
        # release the initialization lock before the catalog has been created.
        for statement in schema.split(";"):
            if statement.strip():
                db.execute(statement)
