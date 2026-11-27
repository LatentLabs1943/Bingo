import hashlib
import hmac
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from bingo.auth import AuthError, telegram_identity
from bingo.config import Settings
from bingo.server import create_app

TOKEN = "123456:test-token-for-unit-tests"


def signed_data(fields=None):
    fields = fields or {"user": json.dumps({"id": 1234, "first_name": "Test player"}),
                        "auth_date": str(int(time.time())), "query_id": "query"}
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


class AuthTests(unittest.TestCase):
    def test_verified_user_id(self):
        user = telegram_identity(signed_data(), TOKEN)
        self.assertEqual(user.id, "1234")
        self.assertEqual(user.name, "Test player")

    def test_tampering_and_wrong_token_are_rejected(self):
        for data, token in [(signed_data().replace("query", "forged"), TOKEN), (signed_data(), "wrong")]:
            with self.assertRaises(AuthError):
                telegram_identity(data, token)

    def test_expired_future_and_duplicate_launch_fields_are_rejected(self):
        for date in (0, int(time.time()) + 300):
            with self.assertRaises(AuthError):
                telegram_identity(signed_data({"auth_date": str(date), "user": '{"id":1}'}), TOKEN)
        with self.assertRaises(AuthError):
            telegram_identity(signed_data() + "&auth_date=0", TOKEN)

    def test_malformed_and_nonpositive_id_are_rejected(self):
        for data in ("", "garbage", signed_data({"auth_date": str(int(time.time())), "user": '{"id":true}'})):
            with self.assertRaises(AuthError):
                telegram_identity(data, TOKEN)


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = self.make_settings(str(Path(self.temp.name) / "api.db"))
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def make_settings(self, path):
        return Settings(database_path=path, seat_limit=600)

    def test_demo_session_gameplay_and_static_assets(self):
        self.assertEqual(self.client.get("/api/state").status_code, 401)
        response = self.client.post("/api/session", json={})
        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertEqual(state["user"]["balance"], "1000")
        self.assertTrue(state["user"]["automatic"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        body = {"round_id": state["game"]["id"], "card_id": 600}
        response = self.client.post("/api/actions/select", json=body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["game"]["my_cards"][0]["id"], 600)
        self.assertEqual(self.client.get("/api/cards/600").status_code, 200)
        self.assertEqual(self.client.get("/api/cards/601").status_code, 409)
        self.assertNotIn("deck", self.client.get("/api/state").json()["game"])
        for path in ("/", "/static/app.js", "/static/style.css", "/health"):
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_demo_identity_survives_server_restart_and_does_not_refill(self):
        state = self.client.post("/api/session", json={}).json()
        self.client.post("/api/actions/select", json={"round_id": state["game"]["id"], "card_id": 1})
        self.client.post("/api/actions/automatic", json={"round_id": state["game"]["id"], "enabled": False})
        with TestClient(create_app(self.settings)) as restarted:
            restarted.cookies.update(self.client.cookies)
            response = restarted.post("/api/session", json={})
            self.assertEqual(response.json()["user"]["balance"], "990")
            self.assertFalse(response.json()["user"]["automatic"])

    def test_validation_cross_origin_and_auth_cannot_be_bypassed(self):
        state = self.client.post("/api/session", json={}).json()
        self.assertEqual(self.client.post("/api/session", headers={"origin": "https://attacker.invalid"}, json={}).status_code, 403)
        for value in (True, "1", -1, 601):
            response = self.client.post("/api/actions/select", json={"round_id": state["game"]["id"], "card_id": value})
            self.assertEqual(response.status_code, 422)
        response = self.client.post("/api/actions/select", json={"round_id": state["game"]["id"], "card_id": 1, "user_id": "someone"})
        self.assertEqual(response.status_code, 422)
        self.client.cookies.set("bingo_demo", "demo-forged.0.signature")
        self.assertEqual(self.client.get("/api/state").status_code, 401)

    def test_production_requires_signed_telegram_identity(self):
        settings = replace(self.settings, demo_mode=False, bot_token=TOKEN, webhook_secret="test_webhook_secret_" + "x" * 32)
        with TestClient(create_app(settings)) as client:
            self.assertEqual(client.post("/api/session", json={}).status_code, 401)
            self.assertEqual(client.get("/api/state", headers={"X-Telegram-Init-Data": "fake"}).status_code, 401)
            headers = {"X-Telegram-Init-Data": signed_data()}
            self.assertEqual(client.post("/api/session", headers=headers, json={}).status_code, 200)
            response = client.get("/api/state", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["user"]["name"], "Test player")


if __name__ == "__main__":
    unittest.main()
