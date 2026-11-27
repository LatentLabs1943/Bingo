"""Run the complete engine/API suites on PostgreSQL in isolated test schemas.

Opt in with TEST_DATABASE_URL. No existing tables are modified or dropped.
"""
import os
import unittest
import uuid
from dataclasses import replace
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from bingo.config import Settings
from tests import test_api, test_engine, test_room_controls, test_wallet, test_owner_and_fees


def postgres_settings(case, path):
    import psycopg
    from psycopg import sql
    url = os.environ["TEST_DATABASE_URL"]
    schema = "bingo_test_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    def cleanup():
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))

    case.addCleanup(cleanup)
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["options"] = f"-c search_path={schema}"
    test_url = urlunsplit(parts._replace(query=urlencode(query, quote_via=quote)))
    return Settings(database_path=path, database_url=test_url,
                    serverless=True, min_players=1, seat_limit=600)


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to run PostgreSQL integration tests")
class PostgresEngineTests(test_engine.EngineTests):
    def make_settings(self, path):
        return postgres_settings(self, path)


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to run PostgreSQL integration tests")
class PostgresAPITests(test_api.APITests):
    def make_settings(self, path):
        return postgres_settings(self, path)


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to run PostgreSQL integration tests")
class PostgresRoomTests(test_room_controls.RoomControlTests):
    def make_settings(self, path):
        return replace(postgres_settings(self, path), owner_telegram_id="1234", seat_limit=4, min_players=2)


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to run PostgreSQL integration tests")
class PostgresWalletTests(test_wallet.WalletTests):
    def make_settings(self, path):
        return replace(postgres_settings(self, path), demo_mode=False, bot_token=test_api.TOKEN,
                       owner_telegram_id="1234", funds_mode="manual", webhook_secret="test_secret_" + "x" * 32,
                       deposit_instructions="Test Bank: beneficiary Test, account 123456")


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Set TEST_DATABASE_URL to run PostgreSQL integration tests")
class PostgresOwnerFeeTests(test_owner_and_fees.OwnerFeeTests):
    def make_settings(self, path):
        return replace(postgres_settings(self, path), demo_mode=False, bot_token=test_api.TOKEN,
                       owner_telegram_id=test_owner_and_fees.OWNER, admin_telegram_ids=("300",), funds_mode="manual",
                       webhook_secret="test_secret_" + "x" * 32, entry_credits=50, min_players=1,
                       deposit_instructions="Test receiving account for owner/fee tests")
