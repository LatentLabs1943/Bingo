from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import time
import unittest

from fastapi.testclient import TestClient

from bingo.config import Settings
from bingo.engine import Engine, GameError
from bingo.server import create_app
from bingo.wallet import Wallet
from tests.test_api import TOKEN, signed_data
from tests.test_wallet import RECEIPT

OWNER = "638145780"


class OwnerFeeTests(unittest.TestCase):
    def make_settings(self, path):
        return Settings(database_path=path, demo_mode=False, bot_token=TOKEN,
                        owner_telegram_id=OWNER, admin_telegram_ids=("300",), funds_mode="manual",
                        deposit_instructions="Test receiving account for owner/fee tests", entry_credits=50, min_players=1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = self.make_settings(str(Path(self.temp.name) / "owner.db"))
        self.engine = Engine(self.settings)
        self.wallet = Wallet(self.engine)
        for uid in (OWNER, "200", "300", "400"):
            self.engine.register_user(uid, "User " + uid)
        for uid in ("200", "400"):
            request = self.wallet.create(uid, "deposit", "100", "owner-fee-test-key-" + uid,
                                         reference="OWNER-TEST-" + uid, account="Test bank sender account 12345", receipt=RECEIPT)
            self.wallet.review(OWNER, request["id"], "approve", verified=True)
        self.now = time.time()
        self.round = self.engine.state("200", self.now)["game"]["id"]

    def book(self):
        self.engine.act("200", self.round, "select", card_id=1, now=self.now)
        return self.engine.act("400", self.round, "select", card_id=2, now=self.now)

    def ready_to_finish(self, winners=(1,)):
        with self.engine._transaction() as db:
            game = self.engine._game(db)
            game.update(phase="playing", called=list(range(1, 76)), deck=[], deadline=self.now + 1)
            for card in (1, 2):
                db.execute("UPDATE entries SET marks=? WHERE round_id=? AND card_id=?",
                           ("[0,1,2,3,4,12]" if card in winners else "[12]", self.round, card))
            self.engine._save(db, game)
        return game["deadline"]

    def test_100_entries_become_80_prize_and_20_house_with_conserved_real_balances(self):
        state = self.book()
        owner_state = self.engine.state(OWNER, self.now)
        self.assertEqual(owner_state["game"]["gross_pool"], "100")
        self.assertEqual(owner_state["game"]["house_fee"], "20")
        self.assertEqual(state["game"]["pool"], "80")
        self.assertEqual(state["game"]["house_cut_percent"], 20)
        self.assertEqual(self.wallet.members(OWNER)["house"]["manual"]["fee"], "0")
        state = self.engine.state("200", self.ready_to_finish())
        self.assertEqual(state["game"]["winners"][0]["share"], "80")
        self.assertEqual(self.engine.state(OWNER, self.now + 1)["game"]["house_fee_charged"], "20")
        self.assertEqual(self.wallet.state("200")["balance"], "130")
        self.assertEqual(self.wallet.state("400")["balance"], "50")
        self.assertEqual(self.wallet.members(OWNER)["house"]["manual"]["fee"], "20")
        self.assertEqual(self.wallet.members(OWNER)["house"]["practice"]["fee"], "0")
        self.assertEqual(sum(Fraction(self.wallet.state(uid)["balance"]) for uid in ("200", "400")) + 20, 200)

    def test_ties_and_concurrent_restarts_settle_net_prize_and_fee_only_once(self):
        self.book()
        deadline = self.ready_to_finish((1, 2))
        engines = [self.engine, Engine(self.settings)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            states = list(pool.map(lambda engine: engine.state("200", deadline), engines))
        self.assertEqual([state["user"]["balance"] for state in states], ["90", "90"])
        self.assertEqual({winner["share"] for winner in states[0]["game"]["winners"]}, {"40"})
        with self.engine._transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM house_ledger WHERE round_id=?", (self.round,)).fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM wallet_ledger WHERE reason='prize'").fetchone()[0], 2)

    def test_no_winner_refunds_every_entry_without_house_income(self):
        self.book()
        state = self.engine.state("200", self.ready_to_finish(()))
        self.assertEqual(state["game"]["reason"], "no_marked_winner")
        self.assertEqual(state["game"]["pool"], "0")
        self.assertEqual(self.engine.state(OWNER, self.now + 1)["game"]["house_fee_charged"], "0")
        self.assertEqual(self.wallet.state("200")["balance"], "100")
        self.assertEqual(self.wallet.state("400")["balance"], "100")
        self.assertEqual(self.wallet.members(OWNER)["house"]["manual"]["fee"], "0")

    def test_existing_paid_round_keeps_its_old_fee_and_next_round_uses_20_percent(self):
        self.book()
        with self.engine._transaction() as db:
            game = self.engine._game(db)
            del game["house_cut_percent"]
            del game["house_fee_charged"]
            self.engine._save(db, game)
        self.assertEqual(Engine(self.settings).state("200", self.now)["game"]["house_cut_percent"], 0)
        state = self.engine.state("200", self.ready_to_finish())
        self.assertEqual(state["game"]["winners"][0]["share"], "100")
        self.assertEqual(self.engine.state(OWNER, self.now + 1)["game"]["house_fee_charged"], "0")
        next_round = self.engine.state("200", state["game"]["deadline"])["game"]
        self.assertEqual(next_round["house_cut_percent"], 20)

    def test_owner_can_revoke_static_admin_immediately_and_restore_after_restart(self):
        self.assertTrue(self.engine.is_admin("300"))
        self.wallet.update_members(OWNER, member="300", remove=True)
        restarted = Engine(self.settings)
        self.assertFalse(restarted.is_admin("300"))
        with self.assertRaises(GameError):
            restarted.admin_settings("300")
        with self.assertRaises(GameError):
            Wallet(restarted).queue("300")
        member = self.wallet.members(OWNER)["members"][0]
        self.assertEqual(member["id"], "300")
        self.assertEqual(member["name"], "User 300")
        self.assertFalse(member["active"])
        self.wallet.update_members(OWNER, member="300")
        self.assertTrue(restarted.is_admin("300"))

    def test_admins_cannot_change_owner_or_other_admin_access(self):
        for actor in ("200", "300"):
            with self.assertRaises(GameError):
                self.wallet.update_members(actor, member=OWNER, remove=True)
            with self.assertRaises(GameError):
                self.wallet.update_members(actor, member="400")
            with self.assertRaises(GameError):
                self.wallet.members(actor)
        with self.assertRaises(GameError):
            self.wallet.update_members(OWNER, member=OWNER, remove=True)
        self.assertTrue(self.engine.is_admin(OWNER))

    def test_owner_can_take_over_a_claimed_withdrawal_and_revoked_admin_cannot_finish_it(self):
        request = self.wallet.create("200", "withdrawal", "20", "owner-withdrawal-key-001")
        self.wallet.claim("300", request["id"])
        self.wallet.update_members(OWNER, member="300", remove=True)
        result = self.wallet.claim(OWNER, request["id"], takeover=True)
        self.assertEqual(result["reviewer"], OWNER)
        self.assertEqual(self.wallet.state("200")["held"], "20")
        with self.assertRaises(GameError):
            self.wallet.review("300", request["id"], "paid", verified=True, payment_reference="BANK-PAYOUT-123")
        self.wallet.review(OWNER, request["id"], "reject", note="Owner checked and cancelled before bank transfer")
        self.assertEqual(self.wallet.state("200")["balance"], "100")
        self.assertTrue(any(event["action"] == "takeover_withdrawal" for event in self.wallet.members(OWNER)["activity"]))

    def test_owner_cancel_refunds_all_entries_once_and_is_audited(self):
        self.book()
        with self.assertRaises(GameError):
            self.engine.cancel_round("300", self.round, "Admin cannot cancel")
        state = self.engine.cancel_round(OWNER, self.round, "Owner cancelled this test round", now=self.now)
        self.assertEqual(state["game"]["reason"], "owner_cancelled")
        self.assertEqual(state["game"]["house_fee_charged"], "0")
        for uid in ("200", "400"):
            self.assertEqual(self.wallet.state(uid)["balance"], "100")
        with self.assertRaises(GameError):
            self.engine.cancel_round(OWNER, self.round, "Retry should not double refund", now=self.now)
        self.assertTrue(any(event["action"] == "cancel_round" for event in self.wallet.members(OWNER)["activity"]))

    def test_owner_funding_history_is_filterable_paginated_and_private(self):
        with self.engine._transaction() as db:
            for index in range(51):
                db.execute("INSERT INTO money_requests(id,user_id,kind,status,amount,reference,account,created,idempotency_key) "
                           "VALUES (?,?,'deposit','rejected','1',?,'Test history account',?,?)",
                           (f"{index:032x}", "200", f"HISTORY-{index}", index, f"history-key-{index}"))
        first = self.wallet.funding_history(OWNER, status="rejected")
        second = self.wallet.funding_history(OWNER, before=first["next_cursor"], status="rejected")
        self.assertEqual(len(first["requests"]), 50)
        self.assertEqual(len(second["requests"]), 1)
        self.assertEqual(len({row["id"] for row in first["requests"] + second["requests"]}), 51)
        self.assertIsNone(second["next_cursor"])
        self.assertNotIn("receipt", first["requests"][0])
        with self.assertRaises(GameError):
            self.wallet.funding_history("300")

    def test_owner_api_checks_signed_identity_and_revocation_on_every_request(self):
        def headers(uid):
            return {"X-Telegram-Init-Data": signed_data({"auth_date": str(int(time.time())),
                    "user": json.dumps({"id": int(uid), "first_name": "API user"})})}
        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get("/api/owner/settings", headers=headers(OWNER)).status_code, 200)
            self.assertEqual(client.get("/api/owner/settings", headers=headers("300")).status_code, 403)
            self.assertEqual(client.get("/api/owner/funding", headers=headers("300")).status_code, 403)
            self.assertEqual(client.post("/api/owner/cancel-round", headers=headers("300"), json={"round_id":self.round,"note":"Attempt"}).status_code, 403)
            response = client.put("/api/owner/settings", headers=headers(OWNER), json={"member":"300","remove":True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(client.get("/api/admin/settings", headers=headers("300")).status_code, 403)
            self.assertEqual(client.get("/api/owner/settings", headers={"X-Telegram-Init-Data":"forged"}).status_code, 401)

    def test_public_snapshots_exclude_owner_bookkeeping_on_all_player_endpoints(self):
        self.book()
        private = {"gross_pool", "house_fee", "house_fee_charged", "cancellation_note", "deck"}
        for uid in ("200", "300"):
            state = self.engine.state(uid, self.now)
            self.assertTrue(private.isdisjoint(state["game"]))
            self.assertEqual(state["game"]["pool"], "80")
            self.assertEqual(state["game"]["house_cut_percent"], 20)  # Betting terms remain disclosed.
        owner_state = self.engine.state(OWNER, self.now)
        self.assertEqual(owner_state["game"]["gross_pool"], "100")
        headers = {"X-Telegram-Init-Data": signed_data({"auth_date":str(int(time.time())), "user":json.dumps({"id":200})})}
        with TestClient(create_app(self.settings)) as client:
            for response in (client.post("/api/session", headers=headers, json={}), client.get("/api/state", headers=headers),
                             client.post("/api/actions/automatic", headers=headers, json={"round_id":self.round,"enabled":False})):
                self.assertEqual(response.status_code, 200)
                self.assertTrue(private.isdisjoint(response.json()["game"]))
        self.engine.cancel_round(OWNER, self.round, "Private operator cancellation reason", now=self.now)
        self.assertNotIn("cancellation_note", self.engine.state("200", self.now)["game"])

    def test_admins_can_change_operations_but_cannot_change_owner_pricing(self):
        current = self.engine.admin_settings("300")
        self.assertFalse(current["can_edit_price"])
        self.assertNotIn("entry_credits", current["settings"])
        self.assertNotIn("house_cut_percent", current["current_round"])
        values = {**current["settings"], "seat_limit":10}
        result = self.engine.update_room_settings("300", current["version"], values)
        self.assertEqual(result["settings"]["seat_limit"], 10)
        with self.assertRaises(GameError) as error:
            self.engine.update_room_settings("300", result["version"], {**values,"entry_credits":51})
        self.assertEqual(error.exception.code, "forbidden")
        owner_settings = self.engine.admin_settings(OWNER)
        self.assertEqual(owner_settings["settings"]["entry_credits"], 50)
        self.engine.update_room_settings(OWNER, owner_settings["version"], {**owner_settings["settings"],"entry_credits":51})
        self.assertEqual(self.engine.state("200")["game"]["entry_credits"], 51)
        headers = {"X-Telegram-Init-Data": signed_data({"auth_date":str(int(time.time())), "user":json.dumps({"id":300})})}
        with TestClient(create_app(self.settings)) as client:
            data = client.get("/api/admin/settings", headers=headers).json()
            response = client.put("/api/admin/settings", headers=headers, json={"version":data["version"], **data["settings"], "entry_credits":1})
            self.assertEqual(response.status_code, 403)

    def test_staff_only_see_pending_or_their_own_claimed_funding_and_no_archive(self):
        first = self.wallet.create("200", "withdrawal", "20", "scoped-withdrawal-key-200")
        second = self.wallet.create("400", "withdrawal", "20", "scoped-withdrawal-key-400")
        self.wallet.claim("300", first["id"])
        self.wallet.claim(OWNER, second["id"])
        self.assertEqual({r["id"] for r in self.wallet.queue("300")["requests"]}, {first["id"]})
        self.assertEqual({r["id"] for r in self.wallet.queue(OWNER)["requests"]}, {first["id"],second["id"]})
        deposit = self.wallet.create("200", "deposit", "1", "scoped-deposit-key-200", reference="SCOPED-DEPOSIT-200", account="Test sender account 12345", receipt=RECEIPT)
        self.assertEqual(self.wallet.receipt("300", deposit["id"])["data_url"], RECEIPT)
        self.wallet.review(OWNER, deposit["id"], "approve", verified=True)
        with self.assertRaises(GameError) as error:
            self.wallet.receipt("300", deposit["id"])
        self.assertEqual(error.exception.code, "forbidden")
        self.assertEqual(self.wallet.receipt(OWNER, deposit["id"])["data_url"], RECEIPT)
        with self.assertRaises(GameError):
            self.wallet.review("300", deposit["id"], "approve", verified=True)
