from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import tempfile
from pathlib import Path
import time
import unittest

from fastapi.testclient import TestClient

from bingo.config import Settings
from bingo.engine import Engine, GameError
from bingo.server import create_app
from tests.test_api import TOKEN, signed_data


class RoomControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = self.make_settings(str(Path(self.temp.name) / "room.db"))
        self.engine = Engine(self.settings)
        for uid in ("a", "b", "c"):
            self.engine.register_user(uid, uid)
        self.now = time.time()
        self.round = self.engine.state("a", self.now)["game"]["id"]
        for uid in ("a", "b", "c"):
            self.engine.act(uid, self.round, "automatic", enabled=False, now=self.now)

    def make_settings(self, path):
        return Settings(database_path=path, owner_telegram_id="1234", seat_limit=4, min_players=2)

    def select(self, uid, card, now=None):
        return self.engine.act(uid, self.round, "select", card_id=card, now=self.now if now is None else now)

    def update(self, **changes):
        current = self.engine.admin_settings("1234")
        return self.engine.update_room_settings("1234", current["version"], {**current["settings"], **changes}, self.now)

    def test_empty_and_single_player_with_two_cards_wait_indefinitely(self):
        for _ in range(3):
            state = self.engine.state("a", self.now + 100000)
            self.assertEqual(state["game"]["id"], self.round)
            self.assertEqual(state["game"]["called"], [])
        self.select("a", 1)
        self.select("a", 2)
        state = self.engine.state("a", self.now + 100000)
        self.assertTrue(state["game"]["waiting_for_players"])
        self.assertEqual(state["game"]["phase"], "registration")
        self.assertEqual(state["game"]["players"], 1)

    def test_countdown_starts_at_minimum_and_resets_when_player_leaves(self):
        self.select("a", 1)
        state = self.select("b", 2, self.now + 600)
        self.assertFalse(state["game"]["waiting_for_players"])
        self.assertEqual(state["game"]["deadline"], self.now + 660)
        state = self.engine.act("b", self.round, "release", card_id=2, now=self.now + 610)
        self.assertTrue(state["game"]["waiting_for_players"])
        state = self.select("b", 3, self.now + 900)
        self.assertEqual(state["game"]["deadline"], self.now + 960)
        state = self.engine.state("a", self.now + 960)
        self.assertEqual(state["game"]["phase"], "playing")
        self.assertEqual(len(state["game"]["called"]), 1)

    def test_seat_limit_and_room_for_required_distinct_players(self):
        self.update(seat_limit=2)
        self.select("a", 1)
        with self.assertRaisesRegex(GameError, "Leave a seat"):
            self.select("a", 2)
        self.select("b", 2)
        with self.assertRaisesRegex(GameError, "full"):
            self.select("c", 3)
        self.assertEqual(self.engine.state("c", self.now)["user"]["balance"], "1000")

    def test_reservations_outside_displayed_cartelas_are_rejected_without_charging(self):
        self.update(seat_limit=4)
        for card in (5, 600):
            with self.assertRaises(GameError) as error:
                self.select("a", card)
            self.assertEqual(error.exception.code, "card_outside_room")
        state = self.engine.state("a", self.now)
        self.assertEqual(state["user"]["balance"], "1000")
        self.assertEqual(state["game"]["reserved"], [])
        self.assertEqual(self.select("a", 4)["game"]["reserved"], [4])

    def test_previously_paid_card_outside_new_visible_range_stays_releasable(self):
        # Simulate a reservation made before the visible-range restriction.
        self.update(seat_limit=600)
        self.select("a", 600)
        with self.engine._transaction() as db:
            game = self.engine._game(db)
            game["seat_limit"] = 20
            self.engine._save(db, game)
        self.assertEqual(self.select("a", 600)["user"]["balance"], "990")
        state = self.engine.act("a", self.round, "release", card_id=600, now=self.now)
        self.assertEqual(state["user"]["balance"], "1000")
        self.assertEqual(state["game"]["reserved"], [])

    def test_selected_pool_uses_reserved_card_numbers_only_and_freezes_rules(self):
        self.update(draw_mode="selected_cards", call_interval_seconds=2)
        self.select("a", 1)
        self.select("b", 2)
        result = self.update(draw_mode="full_75", seat_limit=10, entry_credits=20)
        self.assertEqual(result["applies"], "next_round")
        game = self.engine.state("a", self.now + 60)["game"]
        expected = (set(self.engine.card(1)["cells"]) | set(self.engine.card(2)["cells"])) - {0}
        with self.engine._transaction() as db:
            private = self.engine._game(db)
        self.assertEqual(set(private["deck"] + private["called"]), expected)
        self.assertEqual(game["draw_pool_size"], len(expected))
        self.assertEqual(game["draw_mode"], "selected_cards")
        self.assertEqual(game["entry_credits"], 10)
        self.assertNotIn("deck", game)
        # Exhaustion uses this pool's length, not 75, and refunds once.
        now = game["deadline"]
        for _ in range(len(expected)):
            game = self.engine.state("a", now)["game"]
            now = game["deadline"]
        self.assertEqual(game["phase"], "finished")
        self.assertEqual(len(game["called"]), len(expected))
        new = self.engine.state("a", now)["game"]
        self.assertEqual(new["draw_mode"], "full_75")
        self.assertEqual(new["seat_limit"], 10)
        self.assertEqual(new["entry_credits"], 20)
        self.assertEqual(Engine(self.settings).admin_settings("1234")["settings"]["seat_limit"], 10)

    def test_competing_admin_updates_use_version_and_audit_once(self):
        current = self.engine.admin_settings("1234")
        def save(limit):
            try:
                self.engine.update_room_settings("1234", 0, {**current["settings"], "seat_limit": limit})
                return True
            except GameError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(save, [5, 6])), 1)
        with self.engine._transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM admin_events").fetchone()[0], 1)

    def test_admin_api_requires_signed_allowlisted_identity(self):
        settings = replace(self.settings, bot_token=TOKEN)
        with TestClient(create_app(settings)) as client:
            client.post("/api/session", json={})
            self.assertEqual(client.get("/api/admin/settings").status_code, 403)
            self.assertEqual(client.get("/api/admin/settings", headers={"X-Telegram-Init-Data": "fake"}).status_code, 401)
            headers = {"X-Telegram-Init-Data": signed_data()}
            data = client.get("/api/admin/settings", headers=headers).json()
            body = {"version": data["version"], **data["settings"]}
            self.assertEqual(client.put("/api/admin/settings", headers=headers, json={**body, "min_players": 9}).status_code, 409)
            self.assertEqual(client.put("/api/admin/settings", headers=headers, json={**body, "seat_limit": True}).status_code, 422)
            self.assertEqual(client.put("/api/admin/settings", headers=headers, json=body).status_code, 200)
