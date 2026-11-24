from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from bingo.bot import reply_for, TelegramError
from bingo.config import Settings
from bingo.engine import Engine
from bingo.server import create_app
from bingo.setup_webhook import setup

SECRET = "local_webhook_test_" + "x" * 32
TOKEN = "123456:unit-test-not-a-real-token"


def update(update_id=1, text="/start", language="en"):
    return {"update_id": update_id, "message": {"chat": {"id": 1234, "type": "private"},
                                              "from": {"language_code": language}, "text": text}}


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(database_path=str(Path(self.temp.name) / "webhook.db"),
                                 bot_token=TOKEN, webapp_url="https://bingo.example",
                                 webhook_secret=SECRET)
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}

    def deliver(self, body, headers=None):
        return self.client.post("/api/telegram/webhook", json=body,
                                headers=self.headers if headers is None else headers)

    def test_webhook_requires_secret_and_valid_update_id(self):
        self.assertEqual(self.deliver(update(), {}).status_code, 403)
        self.assertEqual(self.deliver(update(), {"X-Telegram-Bot-Api-Secret-Token": "wrong"}).status_code, 403)
        self.assertEqual(self.deliver({"update_id": True}).status_code, 422)
        self.assertEqual(self.deliver({"update_id": -1}).status_code, 422)
        self.assertEqual(self.deliver({}).status_code, 422)

    @patch("bingo.server.telegram")
    def test_duplicate_delivery_and_restart_do_not_repeat_reply(self, send):
        self.assertEqual(self.deliver(update()).status_code, 200)
        self.assertEqual(self.deliver(update()).status_code, 200)
        with TestClient(create_app(self.settings)) as restarted:
            self.assertEqual(restarted.post("/api/telegram/webhook", json=update(), headers=self.headers).status_code, 200)
        send.assert_called_once()
        reply = send.call_args.args[2]
        self.assertEqual(reply["chat_id"], 1234)
        self.assertEqual(reply["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"], self.settings.webapp_url)

    @patch("bingo.server.telegram")
    def test_delivery_failure_releases_lease_for_retry(self, send):
        send.side_effect = TelegramError("temporary network error")
        self.assertEqual(self.deliver(update()).status_code, 503)
        send.side_effect = None
        self.assertEqual(self.deliver(update()).status_code, 200)
        self.assertEqual(send.call_count, 2)

    @patch("bingo.server.telegram")
    def test_inflight_delivery_is_retried_and_expired_lease_can_be_reclaimed(self, send):
        self.assertEqual(self.app.state.engine.claim_update(9), "claimed")
        self.assertEqual(self.deliver(update(9)).status_code, 503)
        send.assert_not_called()
        self.assertEqual(self.app.state.engine.claim_update(10, now=1), "claimed")
        self.assertEqual(self.deliver(update(10)).status_code, 200)

    @patch("bingo.server.telegram")
    def test_unknown_messages_are_acknowledged_without_sending(self, send):
        self.assertEqual(self.deliver(update(text="hello")).status_code, 200)
        self.assertEqual(self.deliver({"update_id": 2}).status_code, 200)
        send.assert_not_called()

    def test_rules_and_malformed_message_handling(self):
        self.assertIn("የሙከራ", reply_for(update(text="/rules", language="am"), self.settings)["text"])
        for body in ({}, {"message": None}, {"message": {"chat": "wrong"}},
                     {"message": {"chat": {"id": 1, "type": "private"}, "text": True}}):
            self.assertIsNone(reply_for(body, self.settings))

    def test_serverless_static_inspection_is_lazy_and_no_clock_runs(self):
        settings = replace(self.settings, database_url="postgresql://example.invalid/unused", serverless=True)
        real_engine = Engine(self.settings)
        with patch("bingo.server.Engine", return_value=real_engine) as construct:
            app = create_app(settings)
            with TestClient(app) as client:
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/api/config").status_code, 200)
                construct.assert_not_called()
                self.assertEqual(client.get("/health").status_code, 200)
                construct.assert_called_once()

    def test_serverless_configuration_rejects_ephemeral_database(self):
        with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
            replace(self.settings, serverless=True)
        with self.assertRaisesRegex(ValueError, "TELEGRAM_WEBHOOK_SECRET"):
            replace(self.settings, serverless=True, demo_mode=False,
                    database_url="postgresql://example.invalid/db", webhook_secret="")

    @patch("bingo.setup_webhook.telegram")
    @patch("bingo.setup_webhook.configure_bot")
    @patch("bingo.setup_webhook.urlopen")
    def test_setup_checks_health_and_configures_secret_without_dropping_updates(self, open_url, configure, call):
        health = io.BytesIO(b'{"status":"ok"}')
        health.status = 200
        open_url.return_value = health
        call.side_effect = [True, {"url": "https://bingo.example/api/telegram/webhook", "pending_update_count": 0}]
        result = setup(self.settings)
        self.assertTrue(result["webhook_matches"])
        configure.assert_called_once_with(self.settings)
        payload = call.call_args_list[0].args[2]
        self.assertEqual(payload["secret_token"], SECRET)
        self.assertNotIn("drop_pending_updates", payload)

    @patch("bingo.setup_webhook.telegram")
    @patch("bingo.setup_webhook.urlopen", side_effect=OSError("unreachable"))
    def test_setup_does_not_change_bot_when_deployment_is_unhealthy(self, open_url, call):
        with self.assertRaisesRegex(ValueError, "health"):
            setup(self.settings)
        call.assert_not_called()
