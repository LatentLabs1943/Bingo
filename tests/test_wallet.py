import base64
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

RECEIPT = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"test receipt").decode()


class WalletTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = self.make_settings(str(Path(self.temp.name) / "wallet.db"))
        self.engine = Engine(self.settings)
        self.wallet = Wallet(self.engine)
        for uid in ("1234", "200", "300"):
            self.engine.register_user(uid, uid)

    def make_settings(self, path):
        return Settings(database_path=path, demo_mode=False, bot_token=TOKEN, owner_telegram_id="1234",
                        funds_mode="manual", deposit_instructions="Test Bank: beneficiary Test, account 123456", min_players=1)

    def deposit(self, uid="200", reference="BANK-12345", amount="100.25", key="request-key-123456"):
        return self.wallet.create(uid, "deposit", amount, key, reference=reference,
                                  account="Test payer, Bank, account 99999", receipt=RECEIPT)

    def fund(self):
        request = self.deposit()
        self.wallet.review("1234", request["id"], "approve", verified=True)
        return request

    def test_no_practice_money_is_spendable_or_withdrawable(self):
        self.assertEqual(self.engine.state("200")["user"]["balance"], "0")
        game = self.engine.state("200")["game"]
        with self.assertRaises(GameError):
            self.engine.act("200", game["id"], "select", card_id=1)
        with self.assertRaises(GameError):
            self.wallet.create("200", "withdrawal", "10", "withdrawal-key-12345")
        self.assertEqual(self.wallet.state("200")["balance"], "0")

    def test_each_seat_requires_the_full_price_in_available_funded_credits(self):
        request = self.deposit(amount="9.99")
        self.wallet.review("1234", request["id"], "approve", verified=True)
        game = self.engine.state("200")["game"]
        with self.assertRaises(GameError) as error:
            self.engine.act("200", game["id"], "select", card_id=1)
        self.assertEqual(error.exception.code, "insufficient_balance")
        state = self.engine.state("200")
        self.assertEqual(state["game"]["reserved"], [])
        self.assertEqual(state["game"]["pool"], "0")
        self.assertEqual(Fraction(state["user"]["balance"]), Fraction("9.99"))
        topup = self.deposit(reference="BANK-TOPUP-01", amount="0.01", key="topup-request-key01")
        self.wallet.review("1234", topup["id"], "approve", verified=True)
        state = self.engine.act("200", game["id"], "select", card_id=1)
        self.assertEqual(state["user"]["balance"], "0")
        with self.assertRaises(GameError):
            self.engine.act("200", game["id"], "select", card_id=2)
        self.assertEqual(self.engine.state("200")["game"]["reserved"], [1])

    def test_deposit_needs_actual_verification_and_credits_only_once_concurrently(self):
        request = self.deposit()
        self.assertEqual(self.wallet.state("200")["balance"], "0")
        with self.assertRaisesRegex(GameError, "Confirm"):
            self.wallet.review("1234", request["id"], "approve")
        with self.assertRaises(GameError):
            self.wallet.review("200", request["id"], "approve", verified=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: Wallet(Engine(self.settings)).review("1234", request["id"], "approve", verified=True), [1, 2]))
        self.assertEqual([r["status"] for r in results], ["approved", "approved"])
        self.assertEqual(Fraction(self.wallet.state("200")["balance"]), Fraction("100.25"))
        with self.engine._transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM wallet_ledger WHERE reason='deposit'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT balance FROM users WHERE id='200'").fetchone()[0], "1000")

    def test_duplicate_reference_and_request_retries_never_duplicate_credit(self):
        first = self.deposit()
        self.assertEqual(self.deposit()["id"], first["id"])
        with self.assertRaises(GameError):
            self.deposit(uid="300")
        with self.assertRaises(GameError):
            self.deposit(amount="200")
        with self.assertRaises(GameError):
            self.deposit(key="another-key-1234567")
        self.wallet.review("1234", first["id"], "reject", note="No matching transfer")
        self.assertEqual(self.wallet.state("200")["balance"], "0")

    def test_receipts_amounts_and_references_are_validated(self):
        for amount in ("0", "-1", "1/3", "1.001", "NaN", "1000001", 5):
            with self.subTest(amount=amount), self.assertRaises(GameError):
                self.deposit(amount=amount)
        for receipt in ("data:image/svg+xml;base64,PHN2Zz4=", "data:image/png;base64,invalid!", "data:image/png;base64," + base64.b64encode(b"not an image").decode(), "x" * 1400001):
            with self.assertRaises(GameError):
                self.wallet.create("200", "deposit", "10", "valid-request-key-01", reference="BANK123", account="Bank account 123", receipt=receipt)

    def test_withdrawal_reserves_once_blocks_double_spend_and_refunds_once(self):
        self.fund()
        request = self.wallet.create("200", "withdrawal", "90", "withdrawal-key-12345")
        again = self.wallet.create("200", "withdrawal", "90", "withdrawal-key-12345")
        self.assertEqual(request["id"], again["id"])
        self.assertEqual(Fraction(self.wallet.state("200")["balance"]), Fraction("10.25"))
        self.assertEqual(self.wallet.state("200")["held"], "90")
        with self.assertRaises(GameError):
            self.wallet.create("200", "withdrawal", "20", "withdrawal-key-23456")
        with self.assertRaises(GameError):
            self.wallet.review("1234", request["id"], "reject")
        for _ in range(2):
            self.wallet.review("1234", request["id"], "reject", note="Account could not be verified")
        self.assertEqual(Fraction(self.wallet.state("200")["balance"]), Fraction("100.25"))
        self.assertEqual(self.wallet.state("200")["held"], "0")

    def test_paid_withdrawal_requires_reference_and_does_not_debit_again(self):
        self.fund()
        request = self.wallet.create("200", "withdrawal", "20.25", "withdrawal-key-12345")
        with self.assertRaises(GameError):
            self.wallet.review("1234", request["id"], "paid", verified=True)
        with self.assertRaisesRegex(GameError, "Claim"):
            self.wallet.review("1234", request["id"], "paid", verified=True, payment_reference="PAYOUT-123")
        self.wallet.claim("1234", request["id"])
        self.wallet.review("1234", request["id"], "paid", verified=True, payment_reference="PAYOUT-123")
        self.wallet.review("1234", request["id"], "paid", verified=True, payment_reference="PAYOUT-123")
        self.assertEqual(self.wallet.state("200")["balance"], "80")
        self.assertEqual(self.wallet.state("200")["held"], "0")
        with self.assertRaises(GameError):
            self.wallet.review("1234", request["id"], "reject", note="No")

    def test_game_entries_and_refunds_use_real_ledger_and_persist(self):
        self.fund()
        game = self.engine.state("200")["game"]
        state = self.engine.act("200", game["id"], "select", card_id=1)
        self.assertEqual(Fraction(state["user"]["balance"]), Fraction("90.25"))
        restarted = Engine(self.settings)
        state = restarted.act("200", game["id"], "release", card_id=1)
        self.assertEqual(Fraction(state["user"]["balance"]), Fraction("100.25"))
        with restarted._transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM wallet_ledger WHERE reason IN ('entry','release')").fetchone()[0], 2)

    def test_prize_settlement_credits_real_wallet_once_and_keeps_subcent_remainders(self):
        self.fund()
        game = self.engine.state("200")["game"]
        self.engine.act("200", game["id"], "select", card_id=1)
        with self.engine._transaction() as db:
            game = self.engine._game(db)
            game.update(phase="playing", called=list(range(1, 76)), deck=[], deadline=time.time())
            db.execute("UPDATE entries SET marks='[0,1,2,3,4,12]' WHERE round_id=?", (game["id"],))
            self.engine._save(db, game)
        for engine in (self.engine, Engine(self.settings)):
            engine.state("200", game["deadline"] + 1)
        self.assertEqual(Fraction(self.wallet.state("200")["balance"]), Fraction("98.25"))
        with self.engine._transaction() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM wallet_ledger WHERE reason='prize'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT fee FROM house_ledger WHERE round_id=?", (game["id"],)).fetchone()[0], "2")
            db.execute("UPDATE wallets SET balance='20/3' WHERE user_id='200'")
        self.assertEqual(self.wallet.state("200")["withdrawable"], "333/50")

    def test_owner_controls_admin_membership_and_admins_cannot_promote_themselves(self):
        self.wallet.update_members("1234", member="300")
        self.assertTrue(self.engine.is_admin("300"))
        self.assertFalse(self.engine.is_admin("200"))
        request = self.deposit()
        self.wallet.review("300", request["id"], "approve", verified=True)
        with self.assertRaises(GameError):
            self.wallet.update_members("300", member="200")
        self.wallet.update_members("1234", member="300", remove=True)
        self.assertFalse(self.engine.is_admin("300"))
        with self.assertRaises(GameError):
            self.wallet.queue("300")

    def test_withdrawal_claim_has_one_admin_and_held_balance_survives_claim(self):
        self.fund()
        self.wallet.update_members("1234", member="300")
        request = self.wallet.create("200", "withdrawal", "20", "withdrawal-key-12345")
        def claim(uid):
            try:
                return self.wallet.claim(uid, request["id"])["reviewer"]
            except GameError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ["1234", "300"]))
        self.assertEqual(len([r for r in results if r]), 1)
        self.assertEqual(self.wallet.state("200")["held"], "20")
        with self.assertRaises(GameError):
            self.wallet.review("200", request["id"], "paid", verified=True, payment_reference="PAYOUT-456")

    def test_api_protects_receipts_and_money_mutations(self):
        with TestClient(create_app(self.settings)) as client:
            owner = {"X-Telegram-Init-Data": signed_data()}
            user = {"X-Telegram-Init-Data": signed_data({"user": json.dumps({"id": 200, "first_name": "Payer"}), "auth_date": str(int(time.time()))})}
            self.assertEqual(client.get("/api/wallet").status_code, 401)
            self.assertEqual(client.get("/api/admin/funding", headers=user).status_code, 403)
            body = {"amount":"20", "key":"deposit-request-key01", "reference":"BANK-API-123", "account":"Test bank account 123", "receipt":RECEIPT}
            response = client.post("/api/wallet/deposits", headers=user, json=body)
            self.assertEqual(response.status_code, 200, response.text)
            rid = response.json()["id"]
            url = f"/api/admin/funding/{rid}/receipt"
            self.assertEqual(client.get(url, headers=user).status_code, 403)
            self.assertEqual(client.get(url, headers=owner).json()["data_url"], RECEIPT)
            self.assertNotIn("receipt", str(client.get("/api/wallet", headers=user).json()))
            self.assertEqual(client.post(f"/api/admin/funding/{rid}/review", headers=user, json={"decision":"approve", "verified":True}).status_code, 403)
            self.assertEqual(client.put("/api/owner/settings", headers=user, json={"member":"200"}).status_code, 403)
            large = client.post("/api/wallet/deposits", headers=user, content=b"x" * 1450001)
            self.assertEqual(large.status_code, 413)

    def test_manual_mode_cannot_use_guest_auth_or_unconfigured_owner(self):
        with self.assertRaises(ValueError):
            replace(self.settings, demo_mode=True)
        with self.assertRaises(ValueError):
            replace(self.settings, owner_telegram_id="")
