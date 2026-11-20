"""Gameplay and credit changes are serialized in durable database transactions.

Cards and rounds survive restarts. The uncalled deck never leaves this module.
Credits are exact rational numbers: tied players receive identical shares.
"""
from fractions import Fraction
import json
import random
import secrets
import time
import uuid

from .config import Settings
from .storage import Store

RNG = random.SystemRandom()
LINES = (
    tuple(tuple(row * 5 + col for col in range(5)) for row in range(5))
    + tuple(tuple(row * 5 + col for row in range(5)) for col in range(5))
    + ((0, 6, 12, 18, 24), (4, 8, 12, 16, 20), (0, 4, 20, 24))
)


class GameError(Exception):
    def __init__(self, message: str, code: str = "invalid_action"):
        super().__init__(message)
        self.code = code


def winning_cells(marks):
    marked = set(marks) | {12}
    return sorted({cell for line in LINES if set(line) <= marked for cell in line})


def make_card():
    columns = [RNG.sample(range(col * 15 + 1, col * 15 + 16), 5) for col in range(5)]
    cells = [columns[col][row] for row in range(5) for col in range(5)]
    cells[12] = 0
    return cells


class Engine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = Store(settings)
        with self._transaction() as db:
            self.store.initialize(db)
            existing = db.execute("SELECT id,cells FROM cards").fetchall()
            ids, layouts = {row["id"] for row in existing}, {row["cells"] for row in existing}
            missing = []
            for card_id in set(range(1, 601)) - ids:
                cells = json.dumps(make_card())
                while cells in layouts:
                    cells = json.dumps(make_card())
                layouts.add(cells)
                missing.append((card_id, cells))
            if missing:
                db.executemany("INSERT INTO cards VALUES (?,?)", missing)
            if not db.execute("SELECT 1 FROM rounds LIMIT 1").fetchone():
                self._new_round(db, time.time())

    def _transaction(self):
        return self.store.transaction()

    def ping(self):
        with self._transaction() as db:
            db.execute("SELECT 1").fetchone()

    def _new_round(self, db, now):
        game = {"id": uuid.uuid4().hex, "phase": "registration", "called": [],
                "pool": 0, "winners": [], "reason": None, "deck": [],
                "deadline": now + self.settings.registration_seconds,
                "entry_credits": self.settings.entry_credits,
                "call_interval": self.settings.call_interval_seconds,
                "registration_seconds": self.settings.registration_seconds,
                "result_seconds": self.settings.result_seconds}
        db.execute("INSERT INTO rounds VALUES (?,?,?)", (game["id"], now, json.dumps(game)))
        return game

    def _game(self, db):
        return json.loads(db.execute("SELECT data FROM rounds ORDER BY created DESC, id DESC LIMIT 1").fetchone()[0])

    def _save(self, db, game):
        db.execute("UPDATE rounds SET data=? WHERE id=?", (json.dumps(game), game["id"]))

    def _credit(self, db, uid, amount, reason, round_id, now):
        row = db.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()
        balance = Fraction(row[0]) + amount
        if balance < 0:
            raise GameError("You do not have enough demo credits.", "insufficient_balance")
        db.execute("UPDATE users SET balance=? WHERE id=?", (str(balance), uid))
        db.execute("INSERT INTO ledger(user_id,round_id,amount,reason,created) VALUES (?,?,?,?,?)",
                   (uid, round_id, str(amount), reason, now))

    def register_user(self, uid, name):
        uid = str(uid)
        with self._transaction() as db:
            if not db.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
                db.execute("INSERT INTO users(id,name,balance) VALUES (?,?,?)", (uid, name[:80], "0"))
                self._credit(db, uid, self.settings.starting_credits, "welcome", None, time.time())
            else:
                db.execute("UPDATE users SET name=? WHERE id=?", (name[:80], uid))
        return uid

    def demo_signing_key(self):
        with self._transaction() as db:
            db.execute("INSERT INTO metadata VALUES ('demo_signing_key',?) ON CONFLICT (key) DO NOTHING",
                       (secrets.token_hex(32),))
            return bytes.fromhex(db.execute("SELECT value FROM metadata WHERE key='demo_signing_key'").fetchone()[0])

    def claim_update(self, update_id, now=None):
        """Lease a webhook delivery. Concurrent copies must retry, not acknowledge."""
        now = time.time() if now is None else now
        with self._transaction() as db:
            row = db.execute("SELECT * FROM telegram_updates WHERE update_id=?", (update_id,)).fetchone()
            if row and row["done"]:
                return "done"
            if row and row["lease_until"] > now:
                return "busy"
            db.execute("""INSERT INTO telegram_updates(update_id,done,lease_until) VALUES (?,0,?)
                ON CONFLICT (update_id) DO UPDATE SET lease_until=excluded.lease_until""",
                       (update_id, now + 45))
            return "claimed"

    def complete_update(self, update_id):
        with self._transaction() as db:
            db.execute("UPDATE telegram_updates SET done=1,lease_until=0 WHERE update_id=?", (update_id,))

    def release_update(self, update_id):
        with self._transaction() as db:
            db.execute("UPDATE telegram_updates SET lease_until=0 WHERE update_id=? AND done=0", (update_id,))

    def _entries(self, db, game):
        return db.execute("""SELECT e.*, c.cells, u.name, u.automatic FROM entries e
            JOIN cards c ON c.id=e.card_id JOIN users u ON u.id=e.user_id
            WHERE round_id=? ORDER BY card_id""", (game["id"],)).fetchall()

    def _auto_mark(self, db, game, only_user=None):
        if game["phase"] != "playing":
            return
        called = set(game["called"])
        for entry in self._entries(db, game):
            if entry["automatic"] and (only_user is None or entry["user_id"] == only_user):
                cells = json.loads(entry["cells"])
                marks = sorted(set(json.loads(entry["marks"])) | {12} |
                               {i for i, number in enumerate(cells) if number in called})
                db.execute("UPDATE entries SET marks=? WHERE round_id=? AND card_id=?",
                           (json.dumps(marks), game["id"], entry["card_id"]))

    def _finish(self, db, game, winners, now, reason):
        game.update(phase="finished", deadline=now + self.settings.result_seconds, reason=reason)
        if winners:
            share = Fraction(game["pool"], len(winners))
            for uid, data in winners.items():
                self._credit(db, uid, share, "prize", game["id"], now)
                game["winners"].append({"user_id": uid, "name": data["name"],
                                        "card_ids": data["cards"], "share": str(share)})
        else:
            for entry in self._entries(db, game):
                self._credit(db, entry["user_id"], game["entry_credits"], "refund", game["id"], now)

    def _advance(self, db, game, now):
        if now < game["deadline"]:
            return game
        if game["phase"] == "finished":
            return self._new_round(db, now)
        if game["phase"] == "registration":
            if not self._entries(db, game):
                # Keep an empty lobby open; never draw a round without players.
                game["deadline"] = now + self.settings.registration_seconds
            else:
                game["phase"] = "playing"
                game["deck"] = RNG.sample(range(1, 76), 75)
                game["called"].append(game["deck"].pop())
                game["deadline"] = now + game["call_interval"]
                self._auto_mark(db, game)
        else:
            winners = {}
            for entry in self._entries(db, game):
                if winning_cells(json.loads(entry["marks"])):
                    data = winners.setdefault(entry["user_id"], {"name": entry["name"], "cards": []})
                    data["cards"].append(entry["card_id"])
            if winners:
                self._finish(db, game, winners, now, "bingo")
            elif not game["deck"]:
                self._finish(db, game, {}, now, "no_marked_winner")
            else:
                game["called"].append(game["deck"].pop())
                game["deadline"] = now + game["call_interval"]
                self._auto_mark(db, game)
        # Advance at most one draw: a restart must not skip the marking interval.
        self._save(db, game)
        return game

    def tick(self, now=None):
        with self._transaction() as db:
            self._advance(db, self._game(db), time.time() if now is None else now)

    def _snapshot(self, db, game, uid, now):
        user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if user is None:
            raise GameError("Open the game again to sign in.", "unauthorized")
        entries = self._entries(db, game)
        public = {key: value for key, value in game.items() if key != "deck"}
        public["winners"] = [{**w, "is_you": w["user_id"] == uid}
                             for w in public["winners"]]
        # Telegram IDs are not needed in the public room snapshot.
        for winner in public["winners"]:
            winner.pop("user_id")
        public.update(server_time=now, players=len({e["user_id"] for e in entries}),
                      reserved=[e["card_id"] for e in entries],
                      my_cards=[{"id": e["card_id"], "cells": json.loads(e["cells"]),
                                 "marks": json.loads(e["marks"]),
                                 "winning_cells": winning_cells(json.loads(e["marks"]))}
                                for e in entries if e["user_id"] == uid])
        return {"game": public, "user": {"name": user["name"], "balance": user["balance"],
                                          "automatic": bool(user["automatic"])}}

    def state(self, uid, now=None):
        now = time.time() if now is None else now
        with self._transaction() as db:
            game = self._advance(db, self._game(db), now)
            return self._snapshot(db, game, str(uid), now)

    def card(self, card_id):
        if type(card_id) is not int or not 1 <= card_id <= 600:
            raise GameError("Choose a card from 1 to 600.")
        with self._transaction() as db:
            row = db.execute("SELECT cells FROM cards WHERE id=?", (card_id,)).fetchone()
            return {"id": card_id, "cells": json.loads(row[0])}

    def act(self, uid, round_id, action, *, card_id=None, cell=None, enabled=None, now=None):
        uid = str(uid)
        now = time.time() if now is None else now
        # Persist due transitions even when the subsequent action is rejected.
        self.tick(now)
        with self._transaction() as db:
            game = self._game(db)
            if not db.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
                raise GameError("Open the game again to sign in.", "unauthorized")
            if game["id"] != round_id:
                raise GameError("A new round has started. Refresh your board.", "stale_round")
            if action in ("select", "release"):
                if game["phase"] != "registration":
                    raise GameError("Registration is closed.", "registration_closed")
                self.card_id_valid(card_id)
                entry = db.execute("SELECT * FROM entries WHERE round_id=? AND card_id=?",
                                   (round_id, card_id)).fetchone()
                if action == "select":
                    if entry:
                        if entry["user_id"] != uid:
                            raise GameError("This card was selected by another player.", "card_taken")
                        return self._snapshot(db, game, uid, now)  # retry is idempotent
                    count = db.execute("SELECT COUNT(*) FROM entries WHERE round_id=? AND user_id=?",
                                       (round_id, uid)).fetchone()[0]
                    if count >= 2:
                        raise GameError("You can choose up to two cards.", "card_limit")
                    self._credit(db, uid, -game["entry_credits"], "entry", round_id, now)
                    db.execute("INSERT INTO entries(round_id,card_id,user_id) VALUES (?,?,?)",
                               (round_id, card_id, uid))
                    game["pool"] += game["entry_credits"]
                else:
                    if entry and entry["user_id"] != uid:
                        raise GameError("You can only release your own card.", "not_your_card")
                    if entry:
                        db.execute("DELETE FROM entries WHERE round_id=? AND card_id=?", (round_id, card_id))
                        self._credit(db, uid, game["entry_credits"], "release", round_id, now)
                        game["pool"] -= game["entry_credits"]
                self._save(db, game)
            elif action == "automatic":
                if type(enabled) is not bool:
                    raise GameError("Automatic must be on or off.")
                db.execute("UPDATE users SET automatic=? WHERE id=?", (int(enabled), uid))
                self._auto_mark(db, game, uid)
            elif action == "mark":
                if game["phase"] != "playing":
                    raise GameError("Numbers can only be marked while playing.")
                self.card_id_valid(card_id)
                if type(cell) is not int or not 0 <= cell < 25:
                    raise GameError("Invalid card cell.")
                entry = db.execute("SELECT e.*,c.cells FROM entries e JOIN cards c ON c.id=e.card_id "
                                   "WHERE round_id=? AND card_id=? AND user_id=?",
                                   (round_id, card_id, uid)).fetchone()
                if not entry:
                    raise GameError("You can only mark your own card.", "not_your_card")
                number = json.loads(entry["cells"])[cell]
                if cell != 12 and number not in game["called"]:
                    raise GameError("That number has not been called yet.", "uncalled_number")
                marks = sorted(set(json.loads(entry["marks"])) | {cell, 12})
                db.execute("UPDATE entries SET marks=? WHERE round_id=? AND card_id=?",
                           (json.dumps(marks), round_id, card_id))
            else:
                raise GameError("Unknown action.")
            return self._snapshot(db, game, uid, now)

    @staticmethod
    def card_id_valid(card_id):
        if type(card_id) is not int or not 1 <= card_id <= 600:
            raise GameError("Choose a card from 1 to 600.")
