from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

from bingo.config import Settings
from bingo.engine import Engine, GameError, LINES, winning_cells


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = self.make_settings(str(Path(self.temp.name) / "game.db"))
        self.engine = Engine(self.settings)
        for uid in ("a", "b", "c"):
            self.engine.register_user(uid, uid.upper())
        self.initial = self.engine.state("a")
        self.round = self.initial["game"]["id"]
        self.now = self.initial["game"]["server_time"]
        self.deadline = self.initial["game"]["deadline"]
        # Most scenarios below deliberately exercise manual marking.
        for uid in ("a", "b", "c"):
            self.engine.act(uid, self.round, "automatic", enabled=False, now=self.now)

    def make_settings(self, path):
        return Settings(database_path=path, min_players=1, seat_limit=600)

    def select(self, uid, card):
        state = self.engine.act(uid, self.round, "select", card_id=card, now=self.now)
        self.deadline = state["game"]["deadline"]
        return state

    def prepare_play(self, *, called=None, marks=None, deadline=None):
        with self.engine._transaction() as db:
            game = self.engine._game(db)
            game["phase"] = "playing"
            game["called"] = list(range(1, 76)) if called is None else called
            game["deck"] = [n for n in range(1, 76) if n not in game["called"]]
            game["deadline"] = deadline or self.now + 10
            self.engine._save(db, game)
            if marks is not None:
                db.execute("UPDATE entries SET marks=? WHERE round_id=?", (json.dumps(marks), self.round))
        return game

    def test_catalog_has_600_unique_valid_cards_and_is_stable(self):
        with self.engine._transaction() as db:
            cards = db.execute("SELECT cells FROM cards").fetchall()
        self.assertEqual(len(cards), 600)
        self.assertEqual(len({row[0] for row in cards}), 600)
        for row in cards:
            cells = json.loads(row[0])
            self.assertEqual(cells[12], 0)
            self.assertEqual(len(set(cells)), 25)
            for i, n in enumerate(cells):
                if i != 12:
                    self.assertTrue((i % 5) * 15 + 1 <= n <= (i % 5 + 1) * 15)
        self.assertEqual(self.engine.card(600), Engine(self.settings).card(600))

    def test_all_winning_patterns_and_incomplete_lines(self):
        self.assertEqual(len(LINES), 13)
        for line in LINES:
            with self.subTest(line=line):
                self.assertTrue(winning_cells(line))
                remaining = [cell for cell in line if cell != 12]
                self.assertFalse(winning_cells(remaining[:-1]))
        self.assertFalse(winning_cells([1, 8, 12, 17, 21]))

    def test_two_card_limit_and_balance(self):
        self.select("a", 1)
        state = self.select("a", 2)
        self.assertEqual(state["user"]["balance"], "980")
        self.assertEqual(state["game"]["pool"], "16")
        self.assertNotIn("gross_pool", state["game"])
        self.assertNotIn("house_fee", state["game"])
        with self.assertRaisesRegex(GameError, "two cards"):
            self.select("a", 3)
        self.assertEqual(self.engine.state("a", self.now)["user"]["balance"], "980")

    def test_reservation_and_release_retries_are_idempotent(self):
        self.select("a", 1)
        self.select("a", 1)
        self.assertEqual(self.engine.state("a", self.now)["user"]["balance"], "990")
        with self.assertRaisesRegex(GameError, "another player"):
            self.select("b", 1)
        for _ in range(2):
            state = self.engine.act("a", self.round, "release", card_id=1, now=self.now)
        self.assertEqual(state["user"]["balance"], "1000")
        self.assertEqual(state["game"]["pool"], "0")

    def test_two_simultaneous_reservations_have_one_owner(self):
        def reserve(uid):
            try:
                self.select(uid, 80)
                return uid
            except GameError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, ["a", "b"]))
        self.assertEqual(sum(result is not None for result in results), 1)
        state = self.engine.state("a", self.now)
        self.assertEqual(state["game"]["reserved"], [80])
        self.assertEqual(state["game"]["pool"], "8")

    def test_concurrent_third_card_is_rejected(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            def reserve(card):
                try:
                    self.select("a", card)
                    return True
                except GameError:
                    return False
            results = list(pool.map(reserve, [1, 2, 3]))
        self.assertEqual(sum(results), 2)
        self.assertEqual(self.engine.state("a", self.now)["user"]["balance"], "980")

    def test_insufficient_balance_does_not_reserve_or_charge(self):
        with self.engine._transaction() as db:
            db.execute("UPDATE users SET balance='5' WHERE id='a'")
        with self.assertRaisesRegex(GameError, "enough"):
            self.select("a", 1)
        state = self.engine.state("a", self.now)
        self.assertEqual(state["game"]["reserved"], [])
        self.assertEqual(state["game"]["pool"], "0")

    def test_empty_registration_waits_without_drawing(self):
        state = self.engine.state("a", self.deadline)
        self.assertEqual(state["game"]["phase"], "registration")
        self.assertEqual(state["game"]["called"], [])
        self.assertTrue(state["game"]["waiting_for_players"])
        self.assertEqual(state["game"]["id"], self.round)

    def test_registration_closes_at_deadline_and_transition_persists_after_error(self):
        self.select("a", 1)
        with self.assertRaisesRegex(GameError, "closed"):
            self.engine.act("b", self.round, "select", card_id=2, now=self.deadline)
        state = Engine(self.settings).state("a", self.deadline)
        self.assertEqual(state["game"]["phase"], "playing")
        self.assertEqual(len(state["game"]["called"]), 1)
        with self.assertRaisesRegex(GameError, "closed"):
            self.engine.act("a", self.round, "release", card_id=1, now=self.deadline)

    def test_uncalled_numbers_and_other_players_cards_cannot_be_marked(self):
        self.select("a", 1)
        self.prepare_play(called=[])
        for uid in ("a", "b"):
            with self.assertRaises(GameError):
                self.engine.act(uid, self.round, "mark", card_id=1, cell=0, now=self.now)
        for bad in (-1, 25, True):
            with self.assertRaises(GameError):
                self.engine.act("a", self.round, "mark", card_id=1, cell=bad, now=self.now)

    def test_automatic_catches_up_called_numbers(self):
        self.select("a", 1)
        card = self.engine.card(1)
        called = card["cells"][:3]
        self.prepare_play(called=called)
        state = self.engine.act("a", self.round, "automatic", enabled=True, now=self.now)
        self.assertEqual(state["game"]["my_cards"][0]["marks"], [0, 1, 2, 12])

    def test_new_players_auto_mark_by_default_and_saved_manual_choice_survives_restart(self):
        self.engine.register_user("fresh", "New player")
        self.assertTrue(self.engine.state("fresh", self.now)["user"]["automatic"])
        self.engine.act("fresh", self.round, "select", card_id=1, now=self.now)
        number = self.engine.card(1)["cells"][0]
        with self.engine._transaction() as db:
            game = self.engine._game(db)
            game.update(phase="playing", called=[], deck=[number], deadline=self.now)
            self.engine._save(db, game)
        state = self.engine.state("fresh", self.now)
        self.assertIn(0, state["game"]["my_cards"][0]["marks"])
        self.engine.act("fresh", self.round, "automatic", enabled=False, now=self.now)
        restarted = Engine(self.settings)
        restarted.register_user("fresh", "Returning player")
        self.assertFalse(restarted.state("fresh", self.now)["user"]["automatic"])

    def test_complete_automatic_round_finds_real_winning_pattern_and_awards_pool(self):
        self.select("a", 1)
        self.select("b", 2)
        for uid in ("a", "b"):
            self.engine.act(uid, self.round, "automatic", enabled=True, now=self.now)
        now = self.deadline
        for _ in range(76):
            state = self.engine.state("a", now)
            if state["game"]["phase"] == "finished":
                break
            now = state["game"]["deadline"]
        self.assertEqual(state["game"]["reason"], "bingo")
        self.assertGreaterEqual(len(state["game"]["winners"]), 1)
        called = set(state["game"]["called"])
        for winner in state["game"]["winners"]:
            for card_id in winner["card_ids"]:
                card = self.engine.card(card_id)
                marks = [i for i, n in enumerate(card["cells"]) if n in called or i == 12]
                self.assertTrue(winning_cells(marks))
        total = sum(Fraction(self.engine.state(uid, now)["user"]["balance"]) for uid in ["a", "b", "c"])
        self.assertEqual(total, 2996)
        with self.engine._transaction() as db:
            self.assertEqual(Fraction(db.execute("SELECT fee FROM house_ledger WHERE round_id=?", (self.round,)).fetchone()[0]) + total, 3000)

    def test_manual_tie_waits_for_end_of_call_interval(self):
        self.select("a", 1)
        self.select("b", 2)
        game = self.prepare_play(marks=[0, 1, 2, 3, 12])
        self.engine.act("a", self.round, "mark", card_id=1, cell=4, now=self.now + 1)
        state = self.engine.act("b", self.round, "mark", card_id=2, cell=4, now=self.now + 2)
        self.assertEqual(state["game"]["phase"], "playing")
        state = self.engine.state("a", game["deadline"])
        self.assertEqual(len(state["game"]["winners"]), 2)
        self.assertEqual([w["share"] for w in state["game"]["winners"]], ["8", "8"])

    def test_prize_splits_exactly_per_player_and_settles_once_after_restart(self):
        for uid, card in [("a", 1), ("a", 2), ("b", 3), ("c", 4)]:
            self.select(uid, card)
        game = self.prepare_play(marks=[0, 1, 2, 3, 4, 12])
        state = self.engine.state("a", game["deadline"])
        self.assertEqual(len(state["game"]["winners"]), 3)
        self.assertEqual({w["share"] for w in state["game"]["winners"]}, {"32/3"})
        total = sum(Fraction(self.engine.state(uid, game["deadline"])["user"]["balance"]) for uid in ["a", "b", "c"])
        self.assertEqual(total, 2992)
        restarted = Engine(self.settings)
        self.assertEqual(restarted.state("a", game["deadline"])["user"]["balance"], state["user"]["balance"])
        with restarted._transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ledger WHERE reason='prize'").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT fee FROM house_ledger WHERE round_id=?", (self.round,)).fetchone()[0], "8")

    def test_all_75_calls_are_unique_and_no_winner_refunds_entries(self):
        self.select("a", 1)
        now = self.deadline
        seen = []
        for _ in range(75):
            state = self.engine.state("a", now)
            self.assertEqual(state["game"]["phase"], "playing")
            self.assertEqual(len(state["game"]["called"]), len(seen) + 1)
            seen = state["game"]["called"]
            now = state["game"]["deadline"]
        self.assertEqual(set(seen), set(range(1, 76)))
        state = self.engine.state("a", now)
        self.assertEqual(state["game"]["reason"], "no_marked_winner")
        self.assertEqual(state["user"]["balance"], "1000")

    def test_restart_resumes_one_draw_and_preserves_marks_and_cards(self):
        self.select("a", 99)
        first = self.engine.state("a", self.deadline)
        restarted = Engine(self.settings)
        state = restarted.state("a", first["game"]["deadline"] + 3600)
        self.assertEqual(len(state["game"]["called"]), 2)
        self.assertEqual(state["game"]["my_cards"][0]["id"], 99)
        self.assertNotIn("deck", state["game"])

    def test_stale_round_rejected_and_next_round_has_no_reserved_cards(self):
        self.select("a", 1)
        game = self.prepare_play(marks=[0, 1, 2, 3, 4, 12])
        finished = self.engine.state("a", game["deadline"])
        state = self.engine.state("a", finished["game"]["deadline"])
        self.assertNotEqual(state["game"]["id"], self.round)
        self.assertEqual(state["game"]["reserved"], [])
        with self.assertRaisesRegex(GameError, "new round"):
            self.engine.act("a", self.round, "select", card_id=3, now=finished["game"]["deadline"])

    def test_welcome_credit_cannot_be_reissued(self):
        self.select("a", 1)
        self.engine.register_user("a", "Updated name")
        self.assertEqual(self.engine.state("a", self.now)["user"],
                         {"name": "Updated name", "balance": "990", "automatic": False})

    def test_concurrent_instances_settle_a_round_only_once(self):
        self.select("a", 1)
        self.select("b", 2)
        game = self.prepare_play(marks=[0, 1, 2, 3, 4, 12])
        instances = [self.engine, Engine(self.settings)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            states = list(pool.map(lambda engine: engine.state("a", game["deadline"]), instances))
        self.assertEqual([state["user"]["balance"] for state in states], ["998", "998"])
        with self.engine._transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ledger WHERE reason='prize'").fetchone()[0], 2)

    def test_webhook_leases_and_completed_updates_survive_new_instances(self):
        self.assertEqual(self.engine.claim_update(7, now=10), "claimed")
        restarted = Engine(self.settings)
        self.assertEqual(restarted.claim_update(7, now=11), "busy")
        self.assertEqual(restarted.claim_update(7, now=56), "claimed")
        restarted.complete_update(7)
        self.assertEqual(self.engine.claim_update(7, now=100), "done")

    def test_invalid_config_and_invalid_cards(self):
        with self.assertRaises(ValueError):
            replace(self.settings, entry_credits=-1)
        for bad in (0, 601, True, "1"):
            with self.assertRaises(GameError):
                self.engine.card(bad)


if __name__ == "__main__":
    unittest.main()
