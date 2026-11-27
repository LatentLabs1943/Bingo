"""Manual funding. Receipts never credit money without a verified admin decision.

Real balances have a separate ledger from all historical practice balances.
Withdrawal requests reserve money once; the bank transfer remains manual.
"""
import base64
from fractions import Fraction
import json
import re
import time
import uuid

from .engine import GameError

PUBLIC_FIELDS = "id,user_id,kind,status,amount,reference,account,created,reviewed,reviewer,note,payment_reference"


def amount_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,7}(\.[0-9]{1,2})?", value):
        raise GameError("Use a positive amount with at most two decimal places.", "invalid_amount")
    amount = Fraction(value)
    if not 0 < amount <= 1000000:
        raise GameError("Amount must be between 0.01 and 1,000,000 birr.", "invalid_amount")
    return amount


def change_balance(db, uid, amount, reason, now, *, round_id=None, request_id=None):
    db.execute("INSERT INTO wallets(user_id,balance) VALUES (?,'0') ON CONFLICT (user_id) DO NOTHING", (uid,))
    old = Fraction(db.execute("SELECT balance FROM wallets WHERE user_id=?", (uid,)).fetchone()[0])
    if old + amount < 0:
        raise GameError("Your available credit balance is too low.", "insufficient_balance")
    db.execute("UPDATE wallets SET balance=? WHERE user_id=?", (str(old + amount), uid))
    db.execute("INSERT INTO wallet_ledger(user_id,round_id,request_id,amount,reason,created) VALUES (?,?,?,?,?,?)",
               (uid, round_id, request_id, str(amount), reason, now))


class Wallet:
    def __init__(self, engine):
        self.engine = engine
        self.settings = engine.settings

    def _enabled(self):
        if self.settings.funds_mode != "manual":
            raise GameError("Manual funding is not enabled.", "funding_disabled")

    def _admin(self, db, uid):
        if not self.engine._is_admin(db, uid):
            raise GameError("Administrator access is required.", "forbidden")

    def _owner(self, uid):
        if not self.settings.owner_telegram_id or str(uid) != self.settings.owner_telegram_id:
            raise GameError("Only the bot owner can change this.", "forbidden")

    def _instructions(self, db):
        row = db.execute("SELECT value FROM metadata WHERE key='deposit_instructions'").fetchone()
        return row[0] if row else self.settings.deposit_instructions

    def members(self, uid):
        self._owner(uid)
        with self.engine._transaction() as db:
            added = {row["user_id"]: row for row in db.execute("SELECT * FROM admin_members").fetchall()}
            revoked = {row["user_id"]: row for row in db.execute("SELECT * FROM admin_revocations").fetchall()}
            ids = (set(self.settings.admin_telegram_ids) | set(added) | set(revoked)) - {self.settings.owner_telegram_id}
            members = []
            for member in sorted(ids):
                row = db.execute("SELECT name FROM users WHERE id=?", (member,)).fetchone()
                members.append({"id": member, "name": row[0] if row else None,
                                "active": self.engine._is_admin(db, member),
                                "source": "environment" if member in self.settings.admin_telegram_ids else "owner_added"})
            income = {mode: {"gross": Fraction(0), "fee": Fraction(0), "prize_pool": Fraction(0), "rounds": 0}
                      for mode in ("manual", "practice")}
            for row in db.execute("SELECT funds_mode,gross,fee,prize_pool FROM house_ledger").fetchall():
                total = income[row["funds_mode"]]
                for key in ("gross", "fee", "prize_pool"):
                    total[key] += Fraction(row[key])
                total["rounds"] += 1
            return {"admins": [member["id"] for member in members if member["active"]], "members": members,
                    "owner": self.settings.owner_telegram_id, "instructions": self._instructions(db),
                    "house": {mode: {key: value if key == "rounds" else str(value) for key, value in totals.items()}
                              for mode, totals in income.items()},
                    "house_rounds": [dict(row) for row in db.execute("SELECT * FROM house_ledger ORDER BY created DESC,round_id DESC LIMIT 20").fetchall()],
                    "users_count": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                    "current_round": self.engine._admin_snapshot(db, owner=True)["current_round"],
                    "activity": [dict(row) for row in db.execute("SELECT * FROM owner_events ORDER BY id DESC LIMIT 20").fetchall()]}

    def update_members(self, uid, member=None, remove=False, instructions=None):
        self._owner(uid)
        if member is not None and (not re.fullmatch(r"[1-9][0-9]{0,19}", member) or member == self.settings.owner_telegram_id):
            raise GameError("Enter another administrator's numeric Telegram user ID.")
        if instructions is not None and (not isinstance(instructions, str) or not 10 <= len(instructions.strip()) <= 2000):
            raise GameError("Enter receiving account instructions between 10 and 2000 characters.")
        with self.engine._transaction() as db:
            if member is not None:
                if remove:
                    db.execute("DELETE FROM admin_members WHERE user_id=?", (member,))
                    db.execute("INSERT INTO admin_revocations(user_id,revoked_by,created) VALUES (?,?,?) "
                               "ON CONFLICT (user_id) DO UPDATE SET revoked_by=excluded.revoked_by,created=excluded.created",
                               (member, str(uid), time.time()))
                else:
                    db.execute("DELETE FROM admin_revocations WHERE user_id=?", (member,))
                    db.execute("INSERT INTO admin_members(user_id,added_by,created) VALUES (?,?,?) ON CONFLICT (user_id) DO NOTHING",
                               (member, str(uid), time.time()))
            if instructions is not None:
                db.execute("INSERT INTO metadata(key,value) VALUES ('deposit_instructions',?) "
                           "ON CONFLICT (key) DO UPDATE SET value=excluded.value", (instructions.strip(),))
            if member is not None or instructions is not None:
                db.execute("INSERT INTO owner_events(user_id,action,target,created) VALUES (?,?,?,?)",
                           (str(uid), "remove_admin" if member and remove else "add_admin" if member else "receiving_account",
                            member or instructions.strip(), time.time()))
        return self.members(uid)

    def funding_history(self, uid, before=None, status=None):
        self._owner(uid)
        with self.engine._transaction() as db:
            conditions, values = [], []
            if status is not None:
                if status not in ("pending", "processing", "approved", "paid", "rejected"):
                    raise GameError("Invalid request status.")
                conditions.append("status=?")
                values.append(status)
            if before:
                row = db.execute("SELECT created FROM money_requests WHERE id=?", (before,)).fetchone()
                if not row:
                    raise GameError("Invalid history cursor.")
                conditions.append("(created<? OR (created=? AND id<?))")
                values.extend((row[0], row[0], before))
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            rows = db.execute(f"SELECT {PUBLIC_FIELDS} FROM money_requests" + where + " ORDER BY created DESC,id DESC LIMIT 51", values).fetchall()
            return {"requests": [self._public(row) for row in rows[:50]],
                    "next_cursor": rows[49]["id"] if len(rows) > 50 else None}

    def _public(self, row):
        return {key: row[key] for key in PUBLIC_FIELDS.split(",")}

    def state(self, uid):
        self._enabled()
        with self.engine._transaction() as db:
            row = db.execute("SELECT balance FROM wallets WHERE user_id=?", (uid,)).fetchone()
            balance = row[0] if row else "0"
            exact = Fraction(balance)
            withdrawable = Fraction((exact * 100).numerator // (exact * 100).denominator, 100)
            payout = db.execute("SELECT account FROM money_requests WHERE user_id=? AND kind='deposit' AND status='approved' "
                                "ORDER BY reviewed DESC,id DESC LIMIT 1", (uid,)).fetchone()
            requests = db.execute(f"SELECT {PUBLIC_FIELDS} FROM money_requests WHERE user_id=? ORDER BY created DESC,id DESC LIMIT 30", (uid,)).fetchall()
            held = sum((Fraction(r[0]) for r in db.execute("SELECT amount FROM money_requests WHERE user_id=? AND kind='withdrawal' AND status IN ('pending','processing')", (uid,)).fetchall()), Fraction(0))
            ledger = db.execute("SELECT amount,reason,created FROM wallet_ledger WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,)).fetchall()
            return {"balance": balance, "withdrawable": str(withdrawable), "held": str(held), "payout_account": payout[0] if payout else None,
                    "instructions": self._instructions(db), "requests": [self._public(r) for r in requests],
                    "ledger": [dict(r) for r in ledger]}

    def create(self, uid, kind, amount, key, *, reference=None, account=None, receipt=None):
        self._enabled()
        value = amount_value(amount)
        if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9-]{16,64}", key):
            raise GameError("Invalid request key.")
        if kind not in ("deposit", "withdrawal"):
            raise GameError("Unknown funding request.")
        if kind == "deposit":
            if not reference or not re.fullmatch(r"[a-zA-Z0-9 /_.-]{4,100}", reference):
                raise GameError("Enter the bank transaction reference.", "invalid_reference")
            reference = re.sub(r"\s+", "", reference).upper()
            if not account or not 5 <= len(account.strip()) <= 300:
                raise GameError("Enter the sender's name, bank and account for verified withdrawals.")
            if not isinstance(receipt, str) or len(receipt) > 1400000:
                raise GameError("Use a PNG or JPEG receipt up to 1 MB.", "invalid_receipt")
            try:
                prefix, encoded = receipt.split(",", 1)
                image = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError):
                raise GameError("Use a PNG or JPEG receipt up to 1 MB.", "invalid_receipt") from None
            if (len(image) > 1048576 or
                    not ((prefix == "data:image/png;base64" and image.startswith(b"\x89PNG\r\n\x1a\n")) or
                         (prefix == "data:image/jpeg;base64" and image.startswith(b"\xff\xd8\xff")))):
                raise GameError("Use a PNG or JPEG receipt up to 1 MB.", "invalid_receipt")
        now, request_id = time.time(), uuid.uuid4().hex
        with self.engine._transaction() as db:
            if not db.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
                raise GameError("Open the app again to sign in.", "unauthorized")
            old = db.execute("SELECT * FROM money_requests WHERE idempotency_key=?", (f"{uid}:{kind}:{key}",)).fetchone()
            if old:
                if Fraction(old["amount"]) != value or (kind == "deposit" and (old["reference"] != reference or old["account"] != account.strip() or old["receipt"] != receipt)):
                    raise GameError("This request key has already been used for another request.")
                return self._public(old)
            if kind == "deposit":
                if not self._instructions(db).strip():
                    raise GameError("The owner has not configured a receiving account yet.")
                if db.execute("SELECT 1 FROM money_requests WHERE reference=?", (reference,)).fetchone():
                    raise GameError("This transfer reference has already been submitted.", "duplicate_transfer")
                account = account.strip()
            else:
                payout = db.execute("SELECT account FROM money_requests WHERE user_id=? AND kind='deposit' AND status='approved' "
                                    "ORDER BY reviewed DESC,id DESC LIMIT 1", (uid,)).fetchone()
                if not payout:
                    raise GameError("An approved deposit is needed to verify your payout account.", "unverified_account")
                account, reference, receipt = payout[0], None, None
                change_balance(db, uid, -value, "withdrawal_hold", now, request_id=request_id)
            pending = db.execute("SELECT COUNT(*) FROM money_requests WHERE user_id=? AND status IN ('pending','processing')", (uid,)).fetchone()[0]
            if pending >= 5:
                raise GameError("Wait for your pending requests to be reviewed before submitting more.")
            db.execute("INSERT INTO money_requests(id,user_id,kind,status,amount,reference,account,receipt,created,idempotency_key) "
                       "VALUES (?,?,?,'pending',?,?,?,?,?,?)",
                       (request_id, uid, kind, str(value), reference, account, receipt, now, f"{uid}:{kind}:{key}"))
            return self._public(db.execute("SELECT * FROM money_requests WHERE id=?", (request_id,)).fetchone())

    def queue(self, uid):
        self._enabled()
        with self.engine._transaction() as db:
            self._admin(db, uid)
            if str(uid) == self.settings.owner_telegram_id:
                query = f"SELECT {PUBLIC_FIELDS} FROM money_requests WHERE status IN ('pending','processing') ORDER BY created,id LIMIT 100"
                rows = db.execute(query).fetchall()
            else:
                query = f"SELECT {PUBLIC_FIELDS} FROM money_requests WHERE status='pending' OR (status='processing' AND reviewer=?) ORDER BY created,id LIMIT 100"
                rows = db.execute(query, (str(uid),)).fetchall()
            return {"requests": [self._public(row) for row in rows]}

    def claim(self, uid, request_id, takeover=False):
        self._enabled()
        if takeover:
            self._owner(uid)
        with self.engine._transaction() as db:
            self._admin(db, uid)
            row = db.execute("SELECT * FROM money_requests WHERE id=?", (request_id,)).fetchone()
            if not row or row["kind"] != "withdrawal":
                raise GameError("Withdrawal request not found.")
            if row["status"] == "processing" and row["reviewer"] == str(uid):
                return self._public(row)
            if row["status"] != "pending" and not (takeover and row["status"] == "processing"):
                raise GameError("This withdrawal has already been claimed or reviewed.", "already_claimed")
            db.execute("UPDATE money_requests SET status='processing',reviewer=?,reviewed=? WHERE id=?",
                       (str(uid), time.time(), request_id))
            if takeover:
                db.execute("INSERT INTO owner_events(user_id,action,target,created) VALUES (?,?,?,?)",
                           (str(uid), "takeover_withdrawal", json.dumps({"request_id": request_id, "previous_admin": row["reviewer"]}), time.time()))
            return self._public(db.execute("SELECT * FROM money_requests WHERE id=?", (request_id,)).fetchone())

    def receipt(self, uid, request_id):
        self._enabled()
        with self.engine._transaction() as db:
            self._admin(db, uid)
            row = db.execute("SELECT receipt,status FROM money_requests WHERE id=? AND kind='deposit'", (request_id,)).fetchone()
            if not row:
                raise GameError("Receipt not found.")
            if str(uid) != self.settings.owner_telegram_id and row["status"] != "pending":
                raise GameError("Only the owner can view archived receipts.", "forbidden")
            return {"data_url": row[0]}

    def review(self, uid, request_id, decision, *, verified=False, note="", payment_reference=None):
        self._enabled()
        if decision not in ("approve", "reject", "paid") or len(note) > 500:
            raise GameError("Invalid review decision.")
        if decision == "reject" and not note.strip():
            raise GameError("Give the player a reason for rejecting this request.")
        if decision == "paid" and (not payment_reference or not re.fullmatch(r"[a-zA-Z0-9 /_.-]{4,100}", payment_reference)):
            raise GameError("Enter the actual payout transaction reference.", "invalid_reference")
        if payment_reference:
            payment_reference = re.sub(r"\s+", "", payment_reference).upper()
        now = time.time()
        with self.engine._transaction() as db:
            self._admin(db, uid)
            row = db.execute("SELECT * FROM money_requests WHERE id=?", (request_id,)).fetchone()
            if not row:
                raise GameError("Request not found.")
            target = {"approve": "approved", "reject": "rejected", "paid": "paid"}[decision]
            if row["status"] not in ("pending", "processing"):
                if str(uid) != self.settings.owner_telegram_id and row["reviewer"] != str(uid):
                    raise GameError("Only the owner can view other administrators' completed reviews.", "forbidden")
                if row["status"] == target:
                    return self._public(row)
                raise GameError("This request has already been reviewed.", "already_reviewed")
            if row["kind"] == "withdrawal":
                if decision == "paid" and row["status"] != "processing":
                    raise GameError("Claim this withdrawal before making the bank transfer.", "claim_required")
                if row["status"] == "processing" and row["reviewer"] != str(uid) and str(uid) != self.settings.owner_telegram_id:
                    raise GameError("Another administrator is handling this withdrawal.", "already_claimed")
            if (row["kind"] == "deposit" and decision == "paid") or (row["kind"] == "withdrawal" and decision == "approve"):
                raise GameError("Invalid decision for this request.")
            if decision in ("approve", "paid") and verified is not True:
                raise GameError("Confirm the bank transaction before completing this request.", "verification_required")
            if decision == "paid" and db.execute("SELECT 1 FROM money_requests WHERE payment_reference=?", (payment_reference,)).fetchone():
                raise GameError("This payout reference has already been used.", "duplicate_transfer")
            if row["kind"] == "deposit" and decision == "approve":
                change_balance(db, row["user_id"], Fraction(row["amount"]), "deposit", now, request_id=request_id)
            if row["kind"] == "withdrawal" and decision == "reject":
                change_balance(db, row["user_id"], Fraction(row["amount"]), "withdrawal_release", now, request_id=request_id)
            db.execute("UPDATE money_requests SET status=?,reviewed=?,reviewer=?,note=?,payment_reference=? WHERE id=?",
                       (target, now, str(uid), note.strip(), payment_reference if decision == "paid" else None, request_id))
            return self._public(db.execute("SELECT * FROM money_requests WHERE id=?", (request_id,)).fetchone())
