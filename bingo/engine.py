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
HOUSE_CUT_PERCENT = 20
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
            else:
                game = self._game(db)
                if game["phase"] == "registration" and not self._entries(db, game) and game["funds_mode"] != settings.funds_mode:
                    game["funds_mode"] = settings.funds_mode
                    self._save(db, game)

    def _transaction(self):
        return self.store.transaction()

    def ping(self):
        with self._transaction() as db:
            db.execute("SELECT 1").fetchone()

    def _new_round(self, db, now):
        rules = self._room_settings(db)["settings"]
        game = {"id": uuid.uuid4().hex, "phase": "registration", "called": [],
                "pool": 0, "winners": [], "reason": None, "deck": [],
                "deadline": now + rules["registration_seconds"],
                "entry_credits": rules["entry_credits"],
                "call_interval": rules["call_interval_seconds"],
                "registration_seconds": rules["registration_seconds"],
                "result_seconds": rules["result_seconds"],
                "seat_limit": rules["seat_limit"], "min_players": rules["min_players"],
                "draw_mode": rules["draw_mode"], "draw_pool_size": 75 if rules["draw_mode"] == "full_75" else 0,
                "funds_mode": self.settings.funds_mode,
                "house_cut_percent": HOUSE_CUT_PERCENT, "house_fee_charged": "0",
                "waiting_for_players": True}
        db.execute("INSERT INTO rounds VALUES (?,?,?)", (game["id"], now, json.dumps(game)))
        return game

    def _game(self, db):
        game = json.loads(db.execute("SELECT data FROM rounds ORDER BY created DESC, id DESC LIMIT 1").fetchone()[0])
        legacy = "seat_limit" not in game
        missing_fee = "house_cut_percent" not in game
        # Preserve the rules of rounds created before room settings were added.
        game.setdefault("seat_limit", 600)
        game.setdefault("min_players", 1)
        game.setdefault("waiting_for_players", False)
        game.setdefault("draw_mode", "full_75")
        game.setdefault("draw_pool_size", 75)
        game.setdefault("funds_mode", "practice")
        game.setdefault("house_cut_percent", 0)
        game.setdefault("house_fee_charged", "0")
        if legacy and game["phase"] == "registration" and not self._entries(db, game):
            rules = self._room_settings(db)["settings"]
            game.update(seat_limit=rules["seat_limit"], min_players=rules["min_players"],
                        call_interval=rules["call_interval_seconds"], registration_seconds=rules["registration_seconds"],
                        result_seconds=rules["result_seconds"], entry_credits=rules["entry_credits"],
                        draw_mode=rules["draw_mode"], waiting_for_players=True)
            self._save(db, game)
        if missing_fee and game["phase"] == "registration" and not self._entries(db, game):
            game["house_cut_percent"] = HOUSE_CUT_PERCENT
            self._save(db, game)
        return game

    def _room_settings(self, db):
        row = db.execute("SELECT value FROM metadata WHERE key='room_settings'").fetchone()
        if row:
            return json.loads(row[0])
        return {"version": 0, "settings": {
            "seat_limit": self.settings.seat_limit, "min_players": self.settings.min_players,
            "registration_seconds": self.settings.registration_seconds,
            "call_interval_seconds": self.settings.call_interval_seconds,
            "result_seconds": self.settings.result_seconds,
            "entry_credits": self.settings.entry_credits, "draw_mode": "full_75"}}

    def _require_admin(self, uid):
        if not self.is_admin(uid):
            raise GameError("Administrator access is required.", "forbidden")

    def _is_admin(self, db, uid):
        uid = str(uid)
        if self.settings.owner_telegram_id and uid == self.settings.owner_telegram_id:
            return True
        if db.execute("SELECT 1 FROM admin_revocations WHERE user_id=?", (uid,)).fetchone():
            return False
        return (uid in self.settings.admin_telegram_ids or
                bool(db.execute("SELECT 1 FROM admin_members WHERE user_id=?", (uid,)).fetchone()))

    def _require_owner(self, uid):
        if not self.settings.owner_telegram_id or str(uid) != self.settings.owner_telegram_id:
            raise GameError("Only the bot owner can change this.", "forbidden")

    def is_admin(self, uid):
        with self._transaction() as db:
            return self._is_admin(db, uid)

    def admin_settings(self, uid):
        with self._transaction() as db:
            if not self._is_admin(db, uid):
                raise GameError("Administrator access is required.", "forbidden")
            return self._admin_snapshot(db, owner=str(uid) == self.settings.owner_telegram_id)

    def _admin_snapshot(self, db, owner=False):
        game = self._game(db)
        data = {**self._room_settings(db), "can_edit_price": owner, "current_round": {
            "id": game["id"], "phase": game["phase"],
            "reserved_cards": len(self._entries(db, game)),
            "seat_limit": game["seat_limit"], "min_players": game["min_players"],
            "registration_seconds": game["registration_seconds"],
            "call_interval_seconds": game["call_interval"],
            "result_seconds": game["result_seconds"],
            "entry_credits": game["entry_credits"], "draw_mode": game["draw_mode"],
            "house_cut_percent": game["house_cut_percent"]}}
        if not owner:
            data["settings"] = {key: value for key, value in data["settings"].items() if key != "entry_credits"}
            data["current_round"].pop("house_cut_percent")
        return data

    def update_room_settings(self, uid, version, values, now=None):
        self._require_admin(uid)
        expected = {"seat_limit", "min_players", "registration_seconds", "call_interval_seconds", "result_seconds", "entry_credits", "draw_mode"}
        bounds = {"seat_limit": (2, 600), "min_players": (1, 600),
                  "registration_seconds": (10, 300), "call_interval_seconds": (2, 30),
                  "result_seconds": (5, 60), "entry_credits": (1, 100000)}
        if (type(version) is not int or not expected - {"entry_credits"} <= set(values) <= expected):
            raise GameError("Invalid room settings.", "invalid_settings")
        now = time.time() if now is None else now
        with self._transaction() as db:
            if not self._is_admin(db, uid):
                raise GameError("Administrator access is required.", "forbidden")
            current = self._room_settings(db)
            if current["version"] != version:
                raise GameError("Settings changed. Reload them before saving.", "stale_settings")
            owner = str(uid) == self.settings.owner_telegram_id
            if not owner and "entry_credits" in values and values["entry_credits"] != current["settings"]["entry_credits"]:
                raise GameError("Only the owner can change the card price.", "forbidden")
            values = {**values, "entry_credits": values.get("entry_credits", current["settings"]["entry_credits"])}
            if (any(type(values[key]) is not int or not low <= values[key] <= high for key, (low, high) in bounds.items()) or
                    values["min_players"] > values["seat_limit"] or values["draw_mode"] not in ("full_75", "selected_cards")):
                raise GameError("Invalid room settings.", "invalid_settings")
            record = {"version": version + 1, "settings": values}
            db.execute("INSERT INTO metadata(key,value) VALUES ('room_settings',?) "
                       "ON CONFLICT (key) DO UPDATE SET value=excluded.value", (json.dumps(record),))
            db.execute("INSERT INTO admin_events(user_id,created,settings,version) VALUES (?,?,?,?)",
                       (str(uid), now, json.dumps(values), record["version"]))
            game = self._game(db)
            immediate = game["phase"] == "registration" and not self._entries(db, game)
            if immediate:
                game.update(seat_limit=values["seat_limit"], min_players=values["min_players"],
                            registration_seconds=values["registration_seconds"],
                            call_interval=values["call_interval_seconds"], result_seconds=values["result_seconds"],
                            entry_credits=values["entry_credits"], draw_mode=values["draw_mode"],
                            draw_pool_size=75 if values["draw_mode"] == "full_75" else 0,
                            deadline=now + values["registration_seconds"], waiting_for_players=True)
                self._save(db, game)
            return {**self._admin_snapshot(db, owner=owner), "applies": "current_round" if immediate else "next_round"}

    def _sync_registration(self, db, game, now):
        if game["phase"] != "registration":
            return
        players = len({entry["user_id"] for entry in self._entries(db, game)})
        waiting = players < game["min_players"]
        if waiting != game["waiting_for_players"]:
            game["waiting_for_players"] = waiting
            # Begin a full countdown when enough distinct players have joined.
            # Dropping below the minimum cancels that countdown.
            game["deadline"] = now + game["registration_seconds"]
            self._save(db, game)

    def _save(self, db, game):
        db.execute("UPDATE rounds SET data=? WHERE id=?", (json.dumps(game), game["id"]))

    def _credit(self, db, uid, amount, reason, round_id, now, funds_mode="practice"):
        if funds_mode == "manual":
            from .wallet import change_balance
            return change_balance(db, uid, amount, reason, now, round_id=round_id)
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
                # Explicitly set the default for databases created with the old schema too.
                db.execute("INSERT INTO users(id,name,balance,automatic) VALUES (?,?,?,1)", (uid, name[:80], "0"))
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
        if game["phase"] == "finished":
            raise GameError("This round has already been settled.", "round_settled")
        game.update(phase="finished", deadline=now + game["result_seconds"], reason=reason)
        if winners:
            gross = Fraction(game["pool"])
            fee = gross * Fraction(game["house_cut_percent"], 100)
            prize_pool = gross - fee
            share = prize_pool / len(winners)
            game["house_fee_charged"] = str(fee)
            db.execute("INSERT INTO house_ledger(round_id,funds_mode,gross,fee,prize_pool,created) VALUES (?,?,?,?,?,?)",
                       (game["id"], game["funds_mode"], str(gross), str(fee), str(prize_pool), now))
            for uid, data in winners.items():
                self._credit(db, uid, share, "prize", game["id"], now, game["funds_mode"])
                game["winners"].append({"user_id": uid, "name": data["name"],
                                        "card_ids": data["cards"], "share": str(share)})
        else:
            for entry in self._entries(db, game):
                self._credit(db, entry["user_id"], game["entry_credits"], "refund", game["id"], now, game["funds_mode"])

    def cancel_round(self, uid, round_id, note, now=None):
        self._require_owner(uid)
        if not isinstance(note, str) or not 3 <= len(note.strip()) <= 500:
            raise GameError("Give a reason for cancelling the round.")
        now = time.time() if now is None else now
        with self._transaction() as db:
            game = self._game(db)
            if game["id"] != round_id:
                raise GameError("A new round has started. Reload before cancelling.", "stale_round")
            if game["phase"] == "finished":
                raise GameError("This round has already been settled.", "round_settled")
            self._finish(db, game, {}, now, "owner_cancelled")
            game["cancellation_note"] = note.strip()
            self._save(db, game)
            db.execute("INSERT INTO owner_events(user_id,action,target,created) VALUES (?,?,?,?)",
                       (str(uid), "cancel_round", json.dumps({"round_id": round_id, "reason": note.strip()}), now))
            return self._snapshot(db, game, str(uid), now)

    def _advance(self, db, game, now):
        if game["phase"] == "registration":
            self._sync_registration(db, game, now)
            if game["waiting_for_players"]:
                return game
        if now < game["deadline"]:
            return game
        if game["phase"] == "finished":
            return self._new_round(db, now)
        if game["phase"] == "registration":
            if not self._entries(db, game):
                # Keep an empty lobby open; never draw a round without players.
                game["deadline"] = now + game["registration_seconds"]
            else:
                game["phase"] = "playing"
                numbers = (set(range(1, 76)) if game["draw_mode"] == "full_75" else
                           {n for entry in self._entries(db, game) for n in json.loads(entry["cells"]) if n})
                game["draw_pool_size"] = len(numbers)
                game["deck"] = RNG.sample(sorted(numbers), len(numbers))
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
        fields = {"id", "phase", "called", "winners", "reason", "deadline", "entry_credits", "call_interval",
                  "registration_seconds", "result_seconds", "seat_limit", "min_players", "draw_mode",
                  "draw_pool_size", "funds_mode", "waiting_for_players", "house_cut_percent"}
        public = {key: value for key, value in game.items() if key in fields}
        gross = Fraction(game["pool"])
        refunded = game["phase"] == "finished" and game["reason"] != "bingo"
        fee = gross * Fraction(game["house_cut_percent"], 100) if not refunded else Fraction(0)
        public["pool"] = str(gross - fee if not refunded else Fraction(0))
        if str(uid) == self.settings.owner_telegram_id:
            public.update(gross_pool=str(gross), house_fee=str(fee), house_fee_charged=game["house_fee_charged"])
            if "cancellation_note" in game:
                public["cancellation_note"] = game["cancellation_note"]
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
        balance = user["balance"]
        if game["funds_mode"] == "manual":
            row = db.execute("SELECT balance FROM wallets WHERE user_id=?", (uid,)).fetchone()
            balance = row[0] if row else "0"
        return {"game": public, "user": {"name": user["name"], "balance": balance,
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
                    if len(self._entries(db, game)) >= game["seat_limit"]:
                        raise GameError("This round is full. Wait for a seat to open or join the next round.", "room_full")
                    if card_id > game["seat_limit"]:
                        raise GameError(f"Choose a cartela from 1 to {game['seat_limit']} for this room.", "card_outside_room")
                    entries = self._entries(db, game)
                    players_after = len({e["user_id"] for e in entries} | {uid})
                    if game["seat_limit"] - len(entries) - 1 < max(0, game["min_players"] - players_after):
                        raise GameError("Leave a seat for the players needed to start this round.", "seats_needed")
                    self._credit(db, uid, -game["entry_credits"], "entry", round_id, now, game["funds_mode"])
                    db.execute("INSERT INTO entries(round_id,card_id,user_id) VALUES (?,?,?)",
                               (round_id, card_id, uid))
                    game["pool"] += game["entry_credits"]
                else:
                    if entry and entry["user_id"] != uid:
                        raise GameError("You can only release your own card.", "not_your_card")
                    if entry:
                        db.execute("DELETE FROM entries WHERE round_id=? AND card_id=?", (round_id, card_id))
                        self._credit(db, uid, game["entry_credits"], "release", round_id, now, game["funds_mode"])
                        game["pool"] -= game["entry_credits"]
                self._save(db, game)
                self._sync_registration(db, game, now)
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
