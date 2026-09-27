#!/usr/bin/env python3
"""sim.py — the bookkeeper for «Samurai vs Ninja» LLM playtests.

Owns all game state (SQLite), validates and executes player plans and
reactions, applies referee ops, builds per-player views, and exports
history/reports. See ../../simulation.md for the full contract (this file
implements §3-§6 and §9-§12).

Stdlib only. Run with: py -3 simulations/engine/sim.py <command> ...
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import os
import random
import re
import sqlite3
import sys
import time
import traceback
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_DB = REPO_ROOT / "simulations" / "games" / "sim.sqlite"
CARDS_JSON_PATH = REPO_ROOT / "simulations" / "data" / "cards.json"
RULES_HTML_PATH = REPO_ROOT / "rules" / "content-en.html"

sys.path.insert(0, str(SCRIPT_DIR))
import card_rules as cr  # noqa: E402

# ===========================================================================
# Assumptions (see simulation.md §8) — kept as constants so a design change
# is a one-line edit.
# ===========================================================================

REVIVE_HP = "full"          # A1
ONE_REACTION_ROUND = True   # A2 (informational only; enforced by the react/resolve flow)
MAX_HAND_BEFORE_LIMIT = 9
STARTING_HAND = 7
STARTING_VP = 4
DRAW_PHASE_ACTIVE_BASE = 3
DRAW_PHASE_OPPOSING = 1
MAGATAMA_ID = 118
LOTUS_STANCE_ID = 59


class SimError(Exception):
    """Unexpected internal error -> exit code 2."""


class ValidationError(Exception):
    """Structural validation failure -> exit code 1, {"ok": false, "errors": [...]}"""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


# ===========================================================================
# Card DB
# ===========================================================================

class CardDB:
    def __init__(self, path=CARDS_JSON_PATH):
        with open(path, "r", encoding="utf-8") as f:
            cards = json.load(f)
        self.by_id = {c["id"]: c for c in cards}

    def get(self, card_id):
        c = self.by_id.get(card_id)
        if c is None:
            raise SimError(f"unknown card id {card_id}")
        return c

    def has(self, card_id):
        return card_id in self.by_id


_CARDS_CACHE = None


def cards_db():
    global _CARDS_CACHE
    if _CARDS_CACHE is None:
        _CARDS_CACHE = CardDB()
    return _CARDS_CACHE


UID_RE = re.compile(r"^c(\d+)-(\d+)$")


def parse_uid(uid):
    m = UID_RE.match(uid)
    if not m:
        raise SimError(f"malformed uid {uid!r}")
    return int(m.group(1)), int(m.group(2))


def card_id_of(uid):
    return parse_uid(uid)[0]


def card_of(cdb, uid):
    return cdb.get(card_id_of(uid))


# ===========================================================================
# RNG (state persisted in the game's JSON so a fresh CLI process can resume it
# bit-for-bit).
# ===========================================================================

def _tupleize(x):
    if isinstance(x, list):
        return tuple(_tupleize(i) for i in x)
    return x


def rng_load(state):
    r = random.Random()
    rs = state.get("rng_state")
    if rs is not None:
        r.setstate(_tupleize(rs))
    else:
        r.seed(state["seed"])
    return r


def rng_save(state, r):
    state["rng_state"] = list(r.getstate())


# ===========================================================================
# DB layer
# ===========================================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  state_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game_id INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  turn INTEGER,
  active INTEGER,
  kind TEXT NOT NULL,
  actor INTEGER,
  target INTEGER,
  card TEXT,
  card_id INTEGER,
  text TEXT,
  data_json TEXT,
  notes TEXT,
  state_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game_id INTEGER NOT NULL,
  seq INTEGER,
  kind TEXT NOT NULL,
  seat INTEGER,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def connect(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_game(conn, game_id):
    row = conn.execute("SELECT state_json FROM games WHERE id = ?", (game_id,)).fetchone()
    if row is None:
        raise ValidationError([f"no such game: {game_id}"])
    return json.loads(row[0])


def require_token(state, role, token):
    """Lane check: a game created with --tokens only accepts commands carrying the token of `role`.

    `role` is a seat number (str or int) or "referee". Games without tokens (scratch, tests) skip the check.
    """
    tokens = state.get("tokens") or {}
    if not tokens:
        return
    key = str(role)
    expected = tokens.get(key)
    if expected is None:
        raise ValidationError([f"no token defined for role {key}"])
    if not token:
        raise ValidationError([f"--token required: this game enforces lanes (role {key})"])
    if str(token) != str(expected):
        raise ValidationError([f"token does not match role {key}: you may act only for your own seat/role"])


def save_game(conn, state, events, messages):
    """Persist a mutated state plus any new events/messages, atomically."""
    with conn:
        conn.execute(
            "UPDATE games SET state_json = ? WHERE id = ?",
            (json.dumps(state), state["game_id"]),
        )
        for e in events:
            conn.execute(
                "INSERT INTO events (game_id, seq, turn, active, kind, actor, target, card, "
                "card_id, text, data_json, notes, state_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    state["game_id"], e["seq"], e.get("turn"), e.get("active"), e["kind"],
                    e.get("actor"), e.get("target"), e.get("card"), e.get("card_id"),
                    e.get("text", ""), json.dumps(e.get("data") or {}), e.get("notes"),
                    json.dumps(e.get("state") or {}), now_iso(),
                ),
            )
        for m in messages:
            conn.execute(
                "INSERT INTO messages (game_id, seq, kind, seat, payload_json, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (state["game_id"], m.get("seq"), m["kind"], m.get("seat"),
                 json.dumps(m["payload"]), now_iso()),
            )


# ===========================================================================
# State helpers
# ===========================================================================

def new_game_state(seed, players_n, max_turns, include_drafts, cdb):
    if players_n < 2 or players_n > 9:
        raise ValidationError(["players_n must be between 2 and 9"])
    r = random.Random(seed)

    deck = []
    for c in cdb.by_id.values():
        if c["group"] in ("role", "character"):
            continue
        tags = c.get("tags") or []
        if "trash" in tags:
            continue
        if "draft" in tags and not include_drafts:
            continue
        for n in range(1, c["qty"] + 1):
            deck.append(f"c{c['id']}-{n}")
    r.shuffle(deck)

    characters = [c for c in cdb.by_id.values() if c["group"] == "character"]
    characters = sorted(characters, key=lambda c: c["id"])  # deterministic pre-shuffle order
    if players_n > len(characters):
        raise ValidationError([f"players_n {players_n} exceeds the {len(characters)} available characters"])
    r.shuffle(characters)
    chosen = characters[:players_n]

    players = []
    for seat in range(players_n):
        char = chosen[seat]
        faction = "samurai" if seat % 2 == 0 else "ninja"
        players.append({
            "seat": seat,
            "name": f"P{seat}",
            "faction": faction,
            "first": seat == 0,
            "character": char["id"],
            "hp": char["hp"],
            "max_hp": char["hp"],
            "vp": STARTING_VP,
            "poisoned": False,
            "alive": True,
            "died_turn": None,
            "poison_death": False,
            "needs_recovery": False,
            "hand": [],
            "stance": None,
            "trap": None,
            "aura": None,
            "effects": [],
            "attacks_used": 0,
            "stance_played": False,
            "trap_set": False,
            "aura_played": False,
            "flags": {},
        })

    for p in players:
        p["hand"] = [deck.pop(0) for _ in range(STARTING_HAND)]

    all_uids = set()
    for c in cdb.by_id.values():
        if c["group"] in ("role", "character"):
            continue
        tags = c.get("tags") or []
        if "trash" in tags:
            continue
        if "draft" in tags and not include_drafts:
            continue
        for n in range(1, c["qty"] + 1):
            all_uids.add(f"c{c['id']}-{n}")

    state = {
        "game_id": None,
        "seed": seed,
        "players_n": players_n,
        "max_turns": max_turns,
        "include_drafts": include_drafts,
        "turn": 1,
        "active": 0,
        "phase": "plan",
        "final_turn": None,
        "status": "running",
        "result": None,
        "deck": deck,
        "discard": [],
        "removed": [],
        "transit": [],
        "players": players,
        "plan": None,
        "pending": None,
        "seq": 0,
        "next_pending_id": 1,
        "_all_uids": sorted(all_uids),
    }
    rng_save(state, r)
    return state


# --- zone lookups -----------------------------------------------------------

def find_player(state, seat):
    for p in state["players"]:
        if p["seat"] == seat:
            return p
    raise SimError(f"no such seat {seat}")


def team_of(state, seat):
    return find_player(state, seat)["faction"]


def opposing_faction(faction):
    return "ninja" if faction == "samurai" else "samurai"


def teammates(state, seat, include_self=False):
    f = team_of(state, seat)
    return [p["seat"] for p in state["players"] if p["faction"] == f and (include_self or p["seat"] != seat)]


def enemies_of(state, seat):
    f = team_of(state, seat)
    return [p["seat"] for p in state["players"] if p["faction"] != f]


def living_seats(state):
    return [p["seat"] for p in state["players"] if p["alive"]]


def locate_uid(state, uid):
    """Returns (zone, seat) for a uid: zone in
    deck/discard/removed/hand/stance/trap/aura/charges/effects/played/none."""
    if uid in state["deck"]:
        return "deck", None
    if uid in state["discard"]:
        return "discard", None
    if uid in state["removed"]:
        return "removed", None
    for e in state.get("transit", []):
        if e["uid"] == uid:
            return "played", e["seat"]
    for p in state["players"]:
        if uid in p["hand"]:
            return "hand", p["seat"]
        if p["stance"] == uid:
            return "stance", p["seat"]
        if p["trap"] and p["trap"]["uid"] == uid:
            return "trap", p["seat"]
        if p["aura"]:
            if p["aura"]["uid"] == uid:
                return "aura", p["seat"]
            if uid in p["aura"].get("charges", []):
                return "charges", p["seat"]
        if uid in p["effects"]:
            return "effects", p["seat"]
    return None, None


def remove_uid(state, uid):
    """Low-level: strip uid out of wherever it currently lives. Returns the
    (zone, seat) it was removed from, or (None, None)."""
    zone, seat = locate_uid(state, uid)
    if zone == "deck":
        state["deck"].remove(uid)
    elif zone == "discard":
        state["discard"].remove(uid)
    elif zone == "removed":
        state["removed"].remove(uid)
    elif zone == "played":
        state["transit"] = [e for e in state["transit"] if e["uid"] != uid]
    elif zone in ("hand", "stance", "trap", "aura", "charges", "effects"):
        p = find_player(state, seat)
        if zone == "hand":
            p["hand"].remove(uid)
        elif zone == "stance":
            p["stance"] = None
        elif zone == "trap":
            p["trap"] = None
        elif zone == "aura":
            p["aura"] = None
        elif zone == "charges":
            p["aura"]["charges"].remove(uid)
        elif zone == "effects":
            p["effects"].remove(uid)
    return zone, seat


def move_uid(state, uid, to, seat=None, face_up=False):
    """Generic zone move (also used by the referee `move` op). `seat` is the
    new owner for hand/stance/trap/aura/charges/effects."""
    remove_uid(state, uid)
    if to == "deck":
        state["deck"].append(uid)
    elif to == "discard":
        state["discard"].append(uid)
    elif to == "removed":
        state["removed"].append(uid)
    elif to == "hand":
        find_player(state, seat)["hand"].append(uid)
    elif to == "stance":
        p = find_player(state, seat)
        if p["stance"] is not None and p["stance"] != uid:
            raise SimError(f"seat {seat} already has a stance ({p['stance']}); move it away first")
        p["stance"] = uid
    elif to == "trap":
        p = find_player(state, seat)
        if p["trap"] is not None and p["trap"]["uid"] != uid:
            raise SimError(f"seat {seat} already has a trap ({p['trap']['uid']}); move it away first")
        p["trap"] = {"uid": uid, "face_up": bool(face_up)}
    elif to == "aura":
        p = find_player(state, seat)
        if p["aura"] is not None and p["aura"]["uid"] != uid:
            raise SimError(f"seat {seat} already has an aura ({p['aura']['uid']}); move it away first")
        p["aura"] = {"uid": uid, "charges": [], "in_front_of": seat}
    elif to == "charges":
        p = find_player(state, seat)
        if not p["aura"]:
            raise SimError(f"seat {seat} has no aura to charge")
        p["aura"]["charges"].append(uid)
    elif to == "effects":
        find_player(state, seat)["effects"].append(uid)
    elif to == "played":
        if seat is None:
            raise SimError("move to 'played' requires an owning seat")
        state.setdefault("transit", []).append({"uid": uid, "seat": seat})
    else:
        raise SimError(f"unknown zone {to!r}")


# --- table-state queries used by the baseline / validator -------------------

def player_effect_ids(cdb, state, seat):
    p = find_player(state, seat)
    return {card_id_of(u) for u in p["effects"]}


def player_stance_id(state, seat):
    p = find_player(state, seat)
    return card_id_of(p["stance"]) if p["stance"] else None


def player_aura_id(state, seat):
    p = find_player(state, seat)
    return card_id_of(p["aura"]["uid"]) if p["aura"] else None


def team_has_aura(state, seat, aura_id):
    for s in teammates(state, seat, include_self=True):
        if player_aura_id(state, s) == aura_id:
            return True
    return False


def is_untargetable(state, seat):
    """Shadow stance: counts as dead to other players for the round."""
    return player_stance_id(state, seat) == cr.SHADOW_STANCE_ID


def target_complexity(cdb, state, target_seat):
    effect_ids = player_effect_ids(cdb, state, target_seat)
    has_horseman = player_stance_id(state, target_seat) == cr.HORSEMAN_STANCE_ID
    team_closed_ranks = team_has_aura(state, target_seat, cr.CLOSED_RANKS_AURA_ID)
    return cr.target_complexity(effect_ids, has_horseman, team_closed_ranks)


def compute_baseline(cdb, state, attacker_seat, target_seat, weapon_uid, mode, modifier_uid):
    """Best-effort attack baseline, per §5.4. Returns a dict with handles,
    complexity, power, notes[], and flags."""
    attacker = find_player(state, attacker_seat)
    target = find_player(state, target_seat)
    weapon = card_of(cdb, weapon_uid)
    weapon_id = weapon["id"]
    modifier = card_of(cdb, modifier_uid) if modifier_uid else None
    modifier_id = modifier["id"] if modifier else None

    icons = weapon["icons_or"] if mode == "or" else weapon["icons"]
    icon_complexity = None
    dmg = 0
    thrown = False
    for icon in icons or []:
        if icon == "complexity1":
            icon_complexity = 1
        elif icon == "complexity2":
            icon_complexity = 2
        elif icon == "complexity_any":
            icon_complexity = "any"
        elif icon == "ranged":
            icon_complexity = "any"
            thrown = True
        elif icon.startswith("dmg"):
            dmg = int(icon[3:])
        elif icon == "poison":
            pass  # handled via poisoned flag below

    notes = []
    attacker_has_horseman = player_stance_id(state, attacker_seat) == cr.HORSEMAN_STANCE_ID
    has_lunge = modifier_id == cr.LUNGE_MODIFIER_ID
    has_hachimaki = modifier_id == cr.HACHIMAKI_MODIFIER_ID
    is_favourite = cr.is_favourite_weapon(weapon_id, attacker["character"])
    handles = cr.weapon_handles(icon_complexity, attacker_has_horseman, has_lunge, has_hachimaki, is_favourite)
    if attacker_has_horseman and icon_complexity != "any":
        notes.append("Horseman: weapon handles +1 complexity")
    if has_lunge:
        notes.append("Lunge: weapon handles +2 complexity")
    if has_hachimaki:
        notes.append("Hachimaki: weapon handles any complexity")
    if is_favourite:
        notes.append("favourite weapon: handles any complexity, undefendable")

    complexity = target_complexity(cdb, state, target_seat)
    if complexity > cr.COMPLEXITY_BASE:
        notes.append(f"target complexity {complexity}")

    power = dmg
    notes.append(f"base power {dmg}")
    flat = cr.FLAT_POWER_MODIFIERS.get(modifier_id, 0)
    if flat:
        power += flat
        notes.append(f"modifier {modifier['name']}: +{flat}")
    power += cr.wakizashi_on_katana_bonus(modifier_id, weapon_id)
    if modifier_id == cr.WAKIZASHI_WEAPON_ID and weapon_id == cr.KATANA_WEAPON_ID:
        notes.append("Wakizashi on Katana: +2")

    if weapon_id == cr.KATANA_WEAPON_ID and player_stance_id(state, attacker_seat):
        power += 1
        notes.append("Katana + Stance: +1")
    if attacker_has_horseman and complexity == 1:
        power += 1
        notes.append("Horseman vs complexity 1: +1")
    if thrown and player_stance_id(state, attacker_seat) == cr.ARCHER_STANCE_ID:
        power += 1
        notes.append("Archer, thrown: +1")
    if player_stance_id(state, attacker_seat) == cr.MUSHIN_STANCE_ID and cr.at_death_door(attacker["hp"], attacker["character"]):
        power += 2
        notes.append("Mushin at death's door: +2")
    if cr.KILLERS_MARK_EFFECT_ID in player_effect_ids(cdb, state, target_seat):
        power += 1
        notes.append("Killer's Mark on target: +1")
    if cr.CURSE_EFFECT_ID in player_effect_ids(cdb, state, target_seat):
        power += 2
        notes.append("Curse on target: +2")

    poisoned = modifier_id == cr.VIAL_OF_POISON_MODIFIER_ID or "poison" in (icons or [])
    if poisoned and target["poisoned"]:
        power += 1
        notes.append("poisoned attack vs poisoned target: +1")

    undefendable = cr.attack_is_undefendable(weapon_id, modifier_id, attacker["faction"], attacker["character"])
    # Rules, «Defense»: a defender under a defenceless Effect cannot defend, and then their allies
    # cannot defend them either — so the whole attack counts as undefendable (Defenseless, id 101).
    if any(card_id_of(u) == 101 for u in target.get("effects", [])):
        undefendable = True
        notes.append("target is Defenseless: nobody may defend this attack")
    ignores_traps = cr.attack_ignores_traps(weapon_id, modifier_id, thrown, attacker["faction"], target["character"])
    trap_may_fire = bool(target["trap"]) and not ignores_traps

    return {
        "weapon": weapon_uid, "weapon_id": weapon_id, "mode": mode,
        "modifier": modifier_uid, "modifier_id": modifier_id,
        "handles": handles, "complexity": complexity,
        "power": power, "dmg_base": dmg, "thrown": thrown, "poisoned": poisoned,
        "undefendable": undefendable, "ignores_traps": ignores_traps,
        "trap_may_fire": trap_may_fire, "notes": notes,
    }


def player_attacks_max(cdb, state, seat):
    p = find_player(state, seat)
    effect_ids = player_effect_ids(cdb, state, seat)
    is_minamoto = p["character"] == cr.MINAMOTO_CHARACTER_ID
    return cr.attacks_max(effect_ids, is_minamoto, p["poisoned"])


# ===========================================================================
# Consistency check
# ===========================================================================

def check_consistency(state):
    seen = []

    def add(uid):
        seen.append(uid)

    for uid in state["deck"]:
        add(uid)
    for uid in state["discard"]:
        add(uid)
    for uid in state["removed"]:
        add(uid)
    for e in state.get("transit", []):
        add(e["uid"])
    for p in state["players"]:
        for uid in p["hand"]:
            add(uid)
        if p["stance"]:
            add(p["stance"])
        if p["trap"]:
            add(p["trap"]["uid"])
        if p["aura"]:
            add(p["aura"]["uid"])
            for uid in p["aura"].get("charges", []):
                add(uid)
        for uid in p["effects"]:
            add(uid)

    expected = set(state["_all_uids"])
    got = set(seen)
    dupes = sorted({u for u in seen if seen.count(u) > 1})
    missing = sorted(expected - got)
    extra = sorted(got - expected)
    if dupes or missing or extra:
        problems = []
        if dupes:
            problems.append(f"duplicated uids: {dupes}")
        if missing:
            problems.append(f"missing uids: {missing}")
        if extra:
            problems.append(f"unknown uids: {extra}")
        raise SimError("consistency check failed: " + "; ".join(problems))


# ===========================================================================
# Event logging
# ===========================================================================

# move events that inherit the acting player's `why` (see Ctx.step_why)
STEP_EVENT_KINDS = {"stance_set", "trap_set", "aura_set", "aura_charged", "trade", "attack_declared",
                    "effect_placed", "card_played", "ability_used", "reaction", "step_skipped"}


class Ctx:
    """Carries the mutable state plus the events/messages accumulated during
    one command, so they can be persisted atomically at the very end."""

    def __init__(self, state, cdb):
        self.state = state
        self.cdb = cdb
        self.events = []
        self.messages = []
        self.executed_texts = []
        # the short "why" of the step being executed right now (plan step `why` / reaction `notes`);
        # log() attaches it to that step's move events so the history carries the player's thinking
        self.step_why = None

    def log(self, kind, text, actor=None, target=None, card=None, data=None, notes=None):
        s = self.state
        s["seq"] += 1
        e = {
            "seq": s["seq"], "turn": s["turn"], "active": s["active"], "kind": kind,
            "actor": actor, "target": target, "card": card,
            "card_id": card_id_of(card) if card else None,
            "text": text, "data": data or {},
            "notes": notes if notes is not None else (self.step_why if kind in STEP_EVENT_KINDS else None),
            "state": public_snapshot(self.cdb, s),
        }
        self.events.append(e)
        self.executed_texts.append(text)
        return e

    def message(self, kind, seat, payload):
        self.state["seq"] += 1
        self.messages.append({"seq": self.state["seq"], "kind": kind, "seat": seat, "payload": payload})


def card_label(cdb, uid):
    c = card_of(cdb, uid)
    return f"{c['name']} ({uid})"


def player_label(state, seat):
    p = find_player(state, seat)
    char = cards_db().get(p["character"])
    return f"P{seat} ({char['name']})"


# ===========================================================================
# Death / VP / poison
# ===========================================================================

def handle_death(ctx, seat, source=None, by=None):
    state = ctx.state
    p = find_player(state, seat)
    if not p["alive"]:
        return
    p["alive"] = False
    p["died_turn"] = state["turn"]
    p["vp"] -= 1
    poison_death = source == "poison"
    p["poison_death"] = poison_death
    p["needs_recovery"] = not poison_death
    p["poisoned"] = False
    p["attacks_used"] = 0

    for uid in [p["stance"]]:
        if uid:
            move_uid(state, uid, "discard")
    p["stance"] = None
    if p["trap"]:
        move_uid(state, p["trap"]["uid"], "discard")
        p["trap"] = None
    if p["aura"]:
        for cuid in list(p["aura"].get("charges", [])):
            move_uid(state, cuid, "discard")
        move_uid(state, p["aura"]["uid"], "discard")
        p["aura"] = None
    for uid in list(p["effects"]):
        move_uid(state, uid, "discard")
    p["effects"] = []

    killer_gain = False
    if by is not None and not poison_death:
        killer = find_player(state, by)
        if killer["alive"] and killer["faction"] != p["faction"]:
            killer["vp"] += 1
            killer_gain = True

    char = cards_db().get(p["character"])
    ctx.log(
        "death", f"{player_label(state, seat)} dies" + (" (poison)" if poison_death else ""),
        actor=by, target=seat,
        data={
            "source": source, "by": by, "vp_to_killer": killer_gain,
            "death_text": char["text"],
        },
    )
    check_vp_zero(ctx)


def check_vp_zero(ctx):
    state = ctx.state
    if state["status"] == "over":
        return
    for p in state["players"]:
        if p["vp"] <= 0:
            finish_game(ctx, "vp_zero")
            return


def team_score(state, faction):
    total = sum(p["vp"] for p in state["players"] if p["faction"] == faction)
    for p in state["players"]:
        if p["faction"] == faction:
            total += sum(1 for uid in p["hand"] if card_id_of(uid) == MAGATAMA_ID)
    return total


def finish_game(ctx, reason):
    state = ctx.state
    if state["status"] == "over":
        return
    samurai = team_score(state, "samurai")
    ninja = team_score(state, "ninja")
    if samurai > ninja:
        winner = "samurai"
    elif ninja > samurai:
        winner = "ninja"
    else:
        winner = "tie"
    state["status"] = "over"
    state["phase"] = "over"
    state["result"] = {"reason": reason, "winner": winner, "score": {"samurai": samurai, "ninja": ninja}}
    ctx.log("game_over", f"Game over ({reason}): {winner} wins {samurai}-{ninja}" if winner != "tie"
             else f"Game over ({reason}): tie {samurai}-{ninja}",
             data=state["result"])


# ===========================================================================
# Draw / recovery / discard helpers
# ===========================================================================

def draw_cards(ctx, seat, n):
    state = ctx.state
    p = find_player(state, seat)
    drawn = []
    for _ in range(n):
        if not state["deck"]:
            if state["final_turn"] is None:
                state["final_turn"] = state["turn"]
                ctx.log("deck_empty", "The deck is empty; this is the final turn.")
            break
        uid = state["deck"].pop(0)
        p["hand"].append(uid)
        drawn.append(uid)
    return drawn


def draw_phase_bonus(cdb, state, seat):
    p = find_player(state, seat)
    char_id = p["character"]
    bonus = 0
    notes = []
    if char_id in cr.DRAW_BONUS_FLAT:
        bonus += cr.DRAW_BONUS_FLAT[char_id]
        notes.append("Taranaga +1")
    if char_id in cr.DRAW_BONUS_PER_STANCE_ON_TABLE:
        per, cap = cr.DRAW_BONUS_PER_STANCE_ON_TABLE[char_id]
        n = sum(1 for q in state["players"] if q["stance"])
        add = min(n, cap) * per
        if add:
            bonus += add
            notes.append(f"Saigo +{add} (stances on table)")
    if char_id in cr.DRAW_BONUS_PER_TRAP_ON_TABLE:
        per, cap = cr.DRAW_BONUS_PER_TRAP_ON_TABLE[char_id]
        n = sum(1 for q in state["players"] if q["trap"])
        add = min(n, cap) * per
        if add:
            bonus += add
            notes.append(f"Iyo +{add} (traps on table)")
    if char_id in cr.DRAW_BONUS_PER_POISONED_PLAYER:
        per, cap = cr.DRAW_BONUS_PER_POISONED_PLAYER[char_id]
        n = sum(1 for q in state["players"] if q["poisoned"])
        add = min(n, cap) * per
        if add:
            bonus += add
            notes.append(f"Minamoto +{add} (poisoned players)")
    return bonus, notes


def end_of_turn(ctx):
    """§5.1 end-of-turn sequence: end_turn choice already applied by the
    caller; here: poison tick, draw phase, end conditions, turn advance."""
    state = ctx.state
    cdb = ctx.cdb
    active = state["active"]
    p = find_player(state, active)

    if p["alive"] and p["poisoned"]:
        has_snakebite = cr.SNAKEBITE_EFFECT_ID in player_effect_ids(cdb, state, active)
        tick = cr.poison_tick(p["character"], has_snakebite)
        if tick > 0:
            new_hp = p["hp"] - tick
            ctx.log("end_turn_poison", f"{player_label(state, active)} takes {tick} poison damage",
                    actor=active, target=active, data={"n": tick})
            if new_hp <= 0:
                p["hp"] = 0
                handle_death(ctx, active, source="poison", by=None)
            else:
                p["hp"] = new_hp

    if state["status"] == "over":
        return

    if p["alive"]:
        drawn = draw_cards(ctx, active, DRAW_PHASE_ACTIVE_BASE)
        bonus, notes = draw_phase_bonus(cdb, state, active)
        if bonus:
            drawn += draw_cards(ctx, active, bonus)
        ctx.log("draw_phase", f"{player_label(state, active)} draws {len(drawn)}" +
                (" (" + "; ".join(notes) + ")" if notes else ""),
                actor=active, data={"n": len(drawn), "notes": notes})
        for seat in enemies_of(state, active):
            q = find_player(state, seat)
            if q["alive"]:
                d = draw_cards(ctx, seat, DRAW_PHASE_OPPOSING)
                ctx.log("draw_phase", f"{player_label(state, seat)} draws {len(d)} (opposing team)",
                        actor=seat, data={"n": len(d)})

    if state["turn"] == state["max_turns"]:
        finish_game(ctx, "turn_cap")
        return
    if state["final_turn"] is not None and state["turn"] == state["final_turn"]:
        finish_game(ctx, "deck_empty")
        return
    # optional experiment cap: the turn in which the deck fell to `deck_floor` cards is the last one
    floor = state.get("deck_floor")
    if floor is not None and len(state["deck"]) <= floor:
        finish_game(ctx, "deck_floor")
        return

    advance_turn(ctx)


def advance_turn(ctx):
    state = ctx.state
    next_seat = (state["active"] + 1) % state["players_n"]
    state["active"] = next_seat
    state["turn"] += 1
    state["plan"] = None
    state["phase"] = "plan"

    for p in state["players"]:
        if not p["alive"] and p["died_turn"] is not None and p["died_turn"] < state["turn"]:
            p["alive"] = True
            p["hp"] = p["max_hp"]
            revived_needs_recovery = not p["poison_death"]
            p["died_turn"] = None
            p["poison_death"] = False
            p["needs_recovery"] = revived_needs_recovery
            ctx.log("revive", f"{player_label(state, p['seat'])} revives", actor=p["seat"])

    active = find_player(state, next_seat)
    active["attacks_used"] = 0
    active["stance_played"] = False
    active["trap_set"] = False
    active["aura_played"] = False
    if active["stance"] and card_id_of(active["stance"]) == cr.SHADOW_STANCE_ID:
        move_uid(state, active["stance"], "discard")
        active["stance"] = None
        ctx.log("trap_set", f"{player_label(state, next_seat)} discards Shadow", actor=next_seat)

    ctx.log("turn_start", f"Turn {state['turn']}: {player_label(state, next_seat)}", actor=next_seat)


# ===========================================================================
# Views: public snapshot (compact, used inside every event's "state" field)
# ===========================================================================

def public_snapshot(cdb, state):
    players = []
    for p in state["players"]:
        players.append({
            "seat": p["seat"], "hp": p["hp"], "vp": p["vp"], "poisoned": p["poisoned"],
            "alive": p["alive"], "hand_n": len(p["hand"]),
            "stance": p["stance"], "trap": ({"uid": p["trap"]["uid"], "face_up": p["trap"]["face_up"]} if p["trap"] else None),
            "aura": ({"uid": p["aura"]["uid"], "charges_n": len(p["aura"]["charges"])} if p["aura"] else None),
            "effects": list(p["effects"]),
        })
    # cards currently in play (weapon, modifier, defense, intervention cards of the open transaction)
    # each entry carries the seat that played it, so the viewer can lay it at that player's slot
    in_play = [{"uid": e["uid"], "seat": e.get("seat")} for e in (state.get("transit") or [])
               if isinstance(e, dict) and "uid" in e]
    # Replay data, never shown to agents: every hand at this moment, so the viewer can show
    # what a player held when they decided (the log/text views stay public-only).
    hands = {str(p["seat"]): list(p["hand"]) for p in state["players"]}
    return {"deck_n": len(state["deck"]), "discard_n": len(state["discard"]),
            "discard_top": (state["discard"][-1] if state["discard"] else None),
            "in_play": in_play, "hands": hands, "players": players}


# ===========================================================================
# Card-object helpers for views (embed full text, per §7's "view" description)
# ===========================================================================

def card_obj(cdb, uid):
    c = card_of(cdb, uid)
    return {
        "uid": uid, "id": c["id"], "name": c["name"], "types": c["types"],
        "icons": c["icons"], "icons_or": c["icons_or"], "text": c["text"],
    }


def weapon_reach(cdb, state, seat, uid):
    c = card_of(cdb, uid)
    if "weapon" not in c["types"]:
        return None

    def reach_for(icons, mode):
        if not icons:
            return None
        icon_complexity = None
        for icon in icons:
            if icon == "complexity1":
                icon_complexity = 1
            elif icon == "complexity2":
                icon_complexity = 2
            elif icon in ("complexity_any", "ranged"):
                icon_complexity = "any"
        if icon_complexity is None:
            return None
        attacker_has_horseman = player_stance_id(state, seat) == cr.HORSEMAN_STANCE_ID
        is_favourite = cr.is_favourite_weapon(c["id"], find_player(state, seat)["character"])
        handles = cr.weapon_handles(icon_complexity, attacker_has_horseman, False, False, is_favourite)
        legal = []
        for other in state["players"]:
            if other["seat"] == seat or not other["alive"] or is_untargetable(state, other["seat"]):
                continue
            comp = target_complexity(cdb, state, other["seat"])
            if cr.handles_meets(handles, comp):
                legal.append(other["seat"])
        return legal

    return {"main": reach_for(c["icons"], "main"), "or": reach_for(c["icons_or"], "or")}


def hand_view(cdb, state, seat):
    out = []
    for uid in find_player(state, seat)["hand"]:
        obj = card_obj(cdb, uid)
        reach = weapon_reach(cdb, state, seat, uid)
        if reach is not None:
            obj["reach"] = reach
        out.append(obj)
    return out


def table_view(cdb, state, seat):
    p = find_player(state, seat)
    return {
        "stance": card_obj(cdb, p["stance"]) if p["stance"] else None,
        "trap": ({"present": True, "face_up": p["trap"]["face_up"],
                   "card": card_obj(cdb, p["trap"]["uid"]) if p["trap"]["face_up"] else None}
                  if p["trap"] else {"present": False}),
        "aura": ({"card": card_obj(cdb, p["aura"]["uid"]), "charges_n": len(p["aura"]["charges"]),
                   "in_front_of": p["aura"]["in_front_of"]} if p["aura"] else None),
        "effects": [card_obj(cdb, u) for u in p["effects"]],
    }


def opponent_table_view(cdb, state, viewer_seat, other_seat):
    p = find_player(state, other_seat)
    return {
        "stance": card_obj(cdb, p["stance"]) if p["stance"] else None,
        "trap": {
            "present": bool(p["trap"]),
            "face_up": bool(p["trap"] and p["trap"]["face_up"]),
            "card": (card_obj(cdb, p["trap"]["uid"])
                     if p["trap"] and p["trap"]["face_up"] else None),
        },
        "aura": ({"card": card_obj(cdb, p["aura"]["uid"]), "charges_n": len(p["aura"]["charges"]),
                   "in_front_of": p["aura"]["in_front_of"]} if p["aura"] else None),
        "effects": [card_obj(cdb, u) for u in p["effects"]],
        "complexity_to_attack": target_complexity(cdb, state, other_seat),
    }


def character_view(cdb, char_id):
    c = cdb.get(char_id)
    return {"id": c["id"], "name": c["name"], "text": c["text"], "hp": c["hp"]}


def log_lines_for_turn(state, turn, tail=None):
    return [], []  # placeholder filled in by DB-backed helpers (see cmd_view)


def build_player_view(cdb, state, events_this_turn, events_recent, seat):
    p = find_player(state, seat)
    you = {
        "seat": seat, "faction": p["faction"], "character": character_view(cdb, p["character"]),
        "hp": p["hp"], "max_hp": p["max_hp"], "vp": p["vp"], "poisoned": p["poisoned"],
        "alive": p["alive"], "attacks_left": max(0, player_attacks_max(cdb, state, seat) - p["attacks_used"]),
        "needs_recovery": p["needs_recovery"],
        "hand_limit_excess": max(0, len(p["hand"]) - MAX_HAND_BEFORE_LIMIT),
        "hand": hand_view(cdb, state, seat),
        "table": table_view(cdb, state, seat),
    }
    players = []
    for other in state["players"]:
        team = "you" if other["seat"] == seat else ("ally" if other["faction"] == p["faction"] else "enemy")
        entry = {
            "seat": other["seat"], "name": other["name"], "faction": other["faction"], "team": team,
            "character": {"name": cdb.get(other["character"])["name"], "text": cdb.get(other["character"])["text"]},
            "hp": other["hp"], "max_hp": other["max_hp"], "vp": other["vp"], "poisoned": other["poisoned"],
            "alive": other["alive"], "hand_n": len(other["hand"]),
        }
        if other["seat"] != seat:
            entry.update(opponent_table_view(cdb, state, seat, other["seat"]))
        players.append(entry)

    view = {
        "game": state["game_id"], "turn": state["turn"], "phase": state["phase"],
        "you": you, "players": players,
        "deck_n": len(state["deck"]), "discard_n": len(state["discard"]),
        "discard_recent": [cdb.get(card_id_of(u))["name"] for u in state["discard"][-8:]],
        "log_this_turn": events_this_turn, "log_recent": events_recent[-15:],
    }

    pend = state.get("pending")
    if state["phase"] == "react" and pend and seat in pend.get("reactors_pending", []):
        view["pending"] = build_reactor_pending_view(cdb, state, seat)
    return view


def build_reactor_pending_view(cdb, state, seat):
    pend = state["pending"]
    role = "other"
    out = {"kind": pend["kind"], "actor": pend["actor"]}
    if pend["kind"] == "attack":
        step = pend["step"]
        target = step["target"]
        role = "defender" if seat == target else "other"
        b = pend["baseline"]
        weapon_text = cdb.get(b["weapon_id"])["text"] if b["weapon_id"] else "Bare hands: no card text."
        out["attack"] = {
            "card_text": weapon_text, "mode": b["mode"],
            "modifier_text": cdb.get(b["modifier_id"])["text"] if b["modifier_id"] else None,
            "target": target, "baseline": b, "thrown": b["thrown"],
            "undefendable": b["undefendable"], "ignores_traps": b["ignores_traps"],
            "trap_may_fire": b["trap_may_fire"],
        }
    else:
        step = pend.get("step") or {}
        card_uid = step.get("card")
        out["card_text"] = cdb.get(card_id_of(card_uid))["text"] if card_uid else None
        out["ask"] = step.get("ask")
    out["your_role"] = role
    return out


# ===========================================================================
# Pending (referee) view
# ===========================================================================

def build_pending_view(cdb, state):
    pend = state.get("pending")
    if not pend:
        return None
    out = {
        "id": pend["id"], "kind": pend["kind"], "actor": pend["actor"],
        "phase": pend["phase"],
        "reactors_all": pend["reactors_all"], "reactors_pending": pend["reactors_pending"],
        "reactions": pend["reactions"],
        "played": [card_obj(cdb, e["uid"]) for e in state.get("transit", [])],
    }
    if pend["kind"] == "attack":
        step = pend["step"]
        b = pend["baseline"]
        attacker = find_player(state, pend["actor"])
        target = find_player(state, step["target"])
        out["attack"] = dict(b)
        out["attack"]["weapon_text"] = cdb.get(b["weapon_id"])["text"] if b["weapon_id"] else "Bare hands: no card text."
        out["attack"]["modifier_text"] = cdb.get(b["modifier_id"])["text"] if b["modifier_id"] else None
        out["attack"]["note"] = step.get("note")
        out["what_happens_if_undefended"] = {
            "target": step["target"], "damage": b["power"],
            "resulting_hp": max(0, target["hp"] - b["power"]),
            "lethal": target["hp"] - b["power"] <= 0,
        }
        out["attacker"] = {
            "seat": attacker["seat"], "character": character_view(cdb, attacker["character"]),
            "hand": [card_obj(cdb, u) for u in attacker["hand"]],
        }
        out["defender"] = {
            "seat": target["seat"], "character": character_view(cdb, target["character"]),
            "hand": [card_obj(cdb, u) for u in target["hand"]],
            "trap": card_obj(cdb, target["trap"]["uid"]) if target["trap"] else None,
        }
        # Plain-language reminders of the rules the referee most often slips on. They restate the
        # rules text; the referee still writes every op itself.
        r = pend["reactions"].get(str(step["target"])) or {}
        undefendable = bool(b.get("undefendable"))
        defended = (r.get("action") == "defend") and bool(r.get("cards")) and not undefendable
        hints = []
        if undefendable:
            hints.append("This attack cannot be defended: Defense cards of the defender and of teammates have no effect; treat any 'defend' as 'take'.")
        if b.get("trap_may_fire"):
            if not defended:
                hints.append("MANDATORY: the defender did not defend against a non-thrown attack, so their Trap FIRES regardless of the 'trap' field in the reaction (rules, Traps). Reveal it; if the card under the figurine is not a Trap the defender dies at once (op kill, by = attacker).")
            elif r.get("trap") == "trigger":
                hints.append("The defender defends AND chose to trigger the Trap: resolve the Defense first, then the Trap.")
            else:
                hints.append("The defender defends and holds the Trap: it stays face down.")
        elif target.get("trap"):
            hints.append("The defender has a Trap but it cannot fire against this attack (thrown, or the attack ignores Traps).")
        if defended:
            hints.append("Defended: no wounds and none of the attacker's additional effects; Defense-card effects that punish the attacker do apply.")
        for seat_key, rr in pend["reactions"].items():
            if rr.get("action") == "intervene":
                hints.append(f"Seat {seat_key} intervenes with {rr.get('cards')} (when={rr.get('when')}, target={rr.get('target')}): apply per card text, key player's most favourable order.")
        out["referee_hints"] = hints
    elif pend["kind"] == "card":
        step = pend["step"]
        out["card"] = card_obj(cdb, step["card"])
        out["ask"] = step.get("ask")
        out["step"] = step
    else:  # batch
        out["batch"] = []
        for s in pend["batch"]:
            entry = dict(s)
            if s.get("card"):
                entry["card_text"] = cdb.get(card_id_of(s["card"]))["text"]
            out["batch"].append(entry)

    def side_table(seat):
        p = find_player(state, seat)
        return {
            "seat": seat, "character": character_view(cdb, p["character"]),
            "stance": card_obj(cdb, p["stance"]) if p["stance"] else None,
            "trap": ({"present": True, "face_up": p["trap"]["face_up"],
                       "card": card_obj(cdb, p["trap"]["uid"])} if p["trap"] else {"present": False}),
            "aura": ({"card": card_obj(cdb, p["aura"]["uid"]),
                       "charges": [card_obj(cdb, u) for u in p["aura"]["charges"]]} if p["aura"] else None),
            "effects": [card_obj(cdb, u) for u in p["effects"]],
        }

    out["tables"] = [side_table(p["seat"]) for p in state["players"]]
    return out


def build_public_view(cdb, state, all_=False):
    players = []
    for p in state["players"]:
        entry = {
            "seat": p["seat"], "name": p["name"], "faction": p["faction"], "first": p["first"],
            "character": character_view(cdb, p["character"]),
            "hp": p["hp"], "max_hp": p["max_hp"], "vp": p["vp"], "poisoned": p["poisoned"],
            "alive": p["alive"], "hand_n": len(p["hand"]),
            "stance": card_obj(cdb, p["stance"]) if p["stance"] else None,
            "trap": ({"present": True, "face_up": p["trap"]["face_up"],
                       "card": card_obj(cdb, p["trap"]["uid"]) if (p["trap"]["face_up"] or all_) else None}
                      if p["trap"] else {"present": False}),
            "aura": ({"card": card_obj(cdb, p["aura"]["uid"]), "charges_n": len(p["aura"]["charges"])}
                      if p["aura"] else None),
            "effects": [card_obj(cdb, u) for u in p["effects"]],
        }
        if all_:
            entry["hand"] = [card_obj(cdb, u) for u in p["hand"]]
        players.append(entry)
    out = {
        "game": state["game_id"], "turn": state["turn"], "active": state["active"], "phase": state["phase"],
        "players": players, "deck_n": len(state["deck"]), "discard_n": len(state["discard"]),
        "discard_recent": [cdb.get(card_id_of(u))["name"] for u in state["discard"][-8:]],
        "status": state["status"], "result": state["result"],
    }
    return out


# ===========================================================================
# Status
# ===========================================================================

def build_status(state):
    out = {"game": state["game_id"], "turn": state["turn"], "phase": state["phase"], "over": state["status"] == "over"}
    if state["phase"] == "plan":
        out["seat"] = state["active"]
        if state.get("_continuing"):
            out["continuing"] = True
    elif state["phase"] in ("react", "resolve"):
        pend = state["pending"]
        out["pending_id"] = pend["id"]
        out["reactors"] = pend["reactors_pending"]
        out["seat"] = pend["actor"]
    if state["status"] == "over":
        out["result"] = state["result"]
    return out


# ===========================================================================
# Reactor pruning (§5.3)
# ===========================================================================

def can_defend(cdb, state, seat):
    """Would this player be offered a real 'defend' choice? True if they hold
    any defense-capable card, a trap, or a character defense option (Hanzo)."""
    p = find_player(state, seat)
    if p["trap"]:
        return True
    if cr.hanzo_can_intervene(p["character"]):
        return True
    for uid in p["hand"]:
        c = card_of(cdb, uid)
        if "defense" in c["types"] or "defense" in (c.get("icons") or []):
            return True
    return False


def eligible_interveners(cdb, state, attacker_seat, target_seat, undefendable=False):
    # Oath / Armory / Back to Back all read "any {ally}" of the player being
    # attacked — i.e. the aura must sit on the TARGET's team, not merely on
    # the candidate reactor's own team in isolation.
    target_team_has_reaction_aura = any(
        player_aura_id(state, s) in cr.REACTION_ENABLING_AURAS
        for s in teammates(state, target_seat, include_self=True)
    )
    # Ketsuban ("you may choose a willing ally to share those wounds with
    # you") only matters when it sits on the TARGET (the one taking the
    # wounds), and only their own ally can be offered to share them.
    target_has_ketsuban = player_stance_id(state, target_seat) in cr.REACTION_ENABLING_STANCES

    out = []
    for p in state["players"]:
        seat = p["seat"]
        if seat in (attacker_seat, target_seat) or not p["alive"]:
            continue
        same_team_as_target = team_of(state, seat) == team_of(state, target_seat)
        eligible = False
        for uid in p["hand"]:
            c = card_of(cdb, uid)
            if "intervention" in c["types"]:
                eligible = True
                break
            if "as an Intervention" in (c.get("text") or ""):
                eligible = True
                break
            if "defense" in c["types"] and same_team_as_target and not undefendable:
                eligible = True  # partial-absorption teammate defense
                break
        if not eligible and same_team_as_target and target_team_has_reaction_aura:
            eligible = True
        if not eligible and same_team_as_target and target_has_ketsuban:
            eligible = True
        if not eligible:
            target_trap_id = card_id_of(find_player(state, target_seat)["trap"]["uid"]) if find_player(state, target_seat)["trap"] else None
            if target_trap_id in cr.REACTION_ENABLING_TRAPS and same_team_as_target:
                eligible = True
        if not eligible and cr.norio_can_intervene(p["character"], [card_of(cdb, u) for u in p["hand"]]):
            eligible = True
        if eligible:
            out.append(seat)
    return out


def attack_reactors(cdb, state, attacker_seat, target_seat, undefendable=False):
    """Returns (reactors_all, reactions_prefilled) — §5.3 pruning."""
    reactions = {}
    reactors_all = []
    if not undefendable and can_defend(cdb, state, target_seat):
        reactors_all.append(target_seat)
    else:
        reactions[str(target_seat)] = {"action": "take", "cards": [], "trap": None, "auto": True}
    for seat in eligible_interveners(cdb, state, attacker_seat, target_seat, undefendable=undefendable):
        reactors_all.append(seat)
    return reactors_all, reactions


# ===========================================================================
# Validator
# ===========================================================================

class PlanSim:
    """A lightweight forward-simulation of a plan's mechanical (non-referee)
    steps, used to validate structure before anything executes for real. It
    intentionally stops tracking precisely once a transaction-opening step
    (attack / play-with-reactors) is reached, since later steps' true
    legality can depend on referee ops we cannot foresee (documented in
    `decisions`)."""

    def __init__(self, cdb, state, seat):
        self.cdb = cdb
        self.state = state
        self.seat = seat
        p = find_player(state, seat)
        self.hand = list(p["hand"])
        self.stance = p["stance"]
        self.trap = p["trap"]
        self.aura = copy.deepcopy(p["aura"])
        self.attacks_max = player_attacks_max(cdb, state, seat)
        self.attacks_nominal = 0
        self.stance_played = p["stance_played"]
        self.trap_set = p["trap_set"]
        self.aura_played = p["aura_played"]
        self.opened_transaction = False
        # target seat -> set of effect ids already simulated onto them within
        # THIS plan (lazily seeded from the real state on first touch, so two
        # `effect` steps in the same plan can't place the same id twice).
        self.effects_on = {}

    def has(self, uid):
        return uid in self.hand

    def take(self, uid):
        if uid not in self.hand:
            raise ValidationError([f"card {uid} is not in seat {self.seat}'s hand"])
        self.hand.remove(uid)


def validate_plan(cdb, state, seat, plan):
    errors = []
    if state["phase"] != "plan":
        errors.append(f"game is in phase {state['phase']!r}, not plan")
    elif state["active"] != seat:
        errors.append(f"seat {seat} is not the active player (active is {state['active']})")
    if errors:
        raise ValidationError(errors)

    p = find_player(state, seat)
    if not isinstance(plan, dict):
        raise ValidationError(["plan must be a JSON object"])
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        raise ValidationError(["plan.steps must be a list"])

    sim = PlanSim(cdb, state, seat)

    dtl = plan.get("discard_to_limit")
    if dtl is not None:
        if not isinstance(dtl, list):
            errors.append("discard_to_limit must be a list of uids")
        else:
            for uid in dtl:
                if uid not in sim.hand:
                    errors.append(f"discard_to_limit: {uid} not in hand")
                else:
                    sim.hand.remove(uid)
    hand_after_dtl = len(p["hand"]) - len(dtl or [])
    if len(p["hand"]) > MAX_HAND_BEFORE_LIMIT and hand_after_dtl > MAX_HAND_BEFORE_LIMIT:
        errors.append(f"hand has {len(p['hand'])} cards (> {MAX_HAND_BEFORE_LIMIT}); discard_to_limit does not bring it down")

    recovery = plan.get("recovery")
    if recovery is not None:
        if not p["needs_recovery"]:
            errors.append("recovery submitted but this player does not need recovery")
        else:
            rd = recovery.get("discard", []) if isinstance(recovery, dict) else None
            if rd is None:
                errors.append("recovery.discard must be a list")
            else:
                for uid in rd:
                    if uid not in sim.hand:
                        errors.append(f"recovery.discard: {uid} not in hand")
                    else:
                        sim.hand.remove(uid)

    for i, step in enumerate(steps):
        if not isinstance(step, dict) or "do" not in step:
            errors.append(f"step {i}: missing 'do'")
            continue
        do = step["do"]
        try:
            _validate_step(cdb, state, sim, i, step, errors)
        except ValidationError as ve:
            errors.extend(f"step {i}: {m}" for m in ve.errors)

    end_turn = plan.get("end_turn")
    if end_turn:
        lotus = end_turn.get("lotus")
        if lotus not in (None, "heal", "draw"):
            errors.append("end_turn.lotus must be 'heal' or 'draw'")
        if lotus and sim.stance and card_id_of(sim.stance) != LOTUS_STANCE_ID:
            errors.append("end_turn.lotus requires the Lotus stance to be active")
        if lotus and not sim.stance:
            errors.append("end_turn.lotus requires the Lotus stance to be active")
        if lotus == "heal" and end_turn.get("target") is None:
            errors.append("end_turn.lotus heal requires a target")

    if errors:
        raise ValidationError(errors)
    return True


def _validate_step(cdb, state, sim, i, step, errors):
    do = step["do"]
    seat = sim.seat
    p = find_player(state, seat)

    if do == "stance":
        if sim.stance_played:
            errors.append(f"step {i}: stance already played this turn")
            return
        uid = step.get("card")
        if not uid or not sim.has(uid):
            errors.append(f"step {i}: stance card {uid} not in hand")
            return
        c = card_of(cdb, uid)
        if "stance" not in c["types"]:
            errors.append(f"step {i}: {uid} is not a stance card")
            return
        sim.take(uid)
        if sim.stance:
            sim.hand.append(sim.stance)
        sim.stance = uid
        sim.stance_played = True

    elif do == "trap":
        if sim.trap_set:
            errors.append(f"step {i}: trap already set this turn")
            return
        uid = step.get("card")
        if not uid or not sim.has(uid):
            errors.append(f"step {i}: trap card {uid} not in hand")
            return
        sim.take(uid)
        if sim.trap:
            sim.hand.append(sim.trap["uid"])
        sim.trap = {"uid": uid, "face_up": False}
        sim.trap_set = True

    elif do == "aura":
        if sim.aura_played:
            errors.append(f"step {i}: aura already played this turn")
            return
        uid = step.get("card")
        if not uid or not sim.has(uid):
            errors.append(f"step {i}: aura card {uid} not in hand")
            return
        c = card_of(cdb, uid)
        if "aura" not in c["types"]:
            errors.append(f"step {i}: {uid} is not an aura card")
            return
        in_front_of = step.get("in_front_of")
        if in_front_of is not None and in_front_of != seat and p["character"] != cr.TARANAGA_CHARACTER_ID:
            errors.append(f"step {i}: only Taranaga may set an aura's in_front_of")
        sim.take(uid)
        if sim.aura:
            sim.hand.append(sim.aura["uid"])
        sim.aura = {"uid": uid, "charges": [], "in_front_of": in_front_of if in_front_of is not None else seat}
        sim.aura_played = True

    elif do == "charge_aura":
        uid = step.get("card")
        aura_owner = step.get("aura_owner")
        if not uid or not sim.has(uid):
            errors.append(f"step {i}: charge card {uid} not in hand")
            return
        if aura_owner is None:
            errors.append(f"step {i}: charge_aura needs aura_owner")
            return
        owner = find_player(state, aura_owner)
        if owner["faction"] != p["faction"]:
            errors.append(f"step {i}: {aura_owner} is not on your team")
            return
        aura_uid = sim.aura["uid"] if aura_owner == seat and sim.aura else (owner["aura"]["uid"] if owner["aura"] else None)
        if not aura_uid:
            errors.append(f"step {i}: seat {aura_owner} has no aura to charge")
            return
        aura_id = card_id_of(aura_uid)
        c = card_of(cdb, uid)
        if not cr.card_matches_aura_charge(aura_id, c):
            errors.append(f"step {i}: {uid} cannot be tucked under aura {aura_id}")
            return
        sim.take(uid)
        if aura_owner == seat and sim.aura:
            sim.aura["charges"].append(uid)

    elif do == "trade":
        discard = step.get("discard", [])
        if not isinstance(discard, list) or len(discard) != 2:
            errors.append(f"step {i}: trade needs exactly 2 uids")
            return
        for uid in discard:
            if not sim.has(uid):
                errors.append(f"step {i}: trade card {uid} not in hand")
                return
        c1, c2 = (card_of(cdb, u) for u in discard)
        same_id = c1["id"] == c2["id"]
        same_type = bool(set(c1["types"]) & set(c2["types"]) & cr.TRADE_QUALIFYING_TYPES)
        if not same_id and not same_type:
            errors.append(f"step {i}: traded cards share neither an id nor a qualifying type")
            return
        for uid in discard:
            sim.take(uid)

    elif do == "attack":
        sim.opened_transaction = True
        mode = step.get("mode", "main")
        target = step.get("target")
        if target is None:
            errors.append(f"step {i}: attack needs a target")
            return
        if target == seat:
            errors.append(f"step {i}: cannot attack yourself")
            return
        tgt = None
        for q in state["players"]:
            if q["seat"] == target:
                tgt = q
        if tgt is None:
            errors.append(f"step {i}: no such seat {target}")
            return
        if not tgt["alive"]:
            errors.append(f"step {i}: target {target} is dead")
            return
        if is_untargetable(state, target):
            errors.append(f"step {i}: target {target} is untargetable (Shadow)")
            return

        cost = 2 if mode == "bare" else 1
        if sim.attacks_nominal + cost > sim.attacks_max:
            errors.append(f"step {i}: not enough attack attempts left "
                           f"(used {sim.attacks_nominal}, max {sim.attacks_max}, this costs {cost})")
            return
        sim.attacks_nominal += cost

        actor_effect_ids = {card_id_of(u) for u in p["effects"]}
        if actor_effect_ids & cr.ATTACKER_BLOCKED_EFFECTS:
            errors.append(f"step {i}: an effect on you blocks weapon attacks")
            return

        thrown = False
        if mode == "bare":
            handles = 1
        else:
            uid = step.get("card")
            if not uid or not sim.has(uid):
                errors.append(f"step {i}: weapon {uid} not in hand")
                return
            c = card_of(cdb, uid)
            if "weapon" not in c["types"]:
                errors.append(f"step {i}: {uid} is not a weapon")
                return
            icons = c["icons_or"] if mode == "or" else c["icons"]
            if mode == "or" and not c.get("icons_or"):
                errors.append(f"step {i}: weapon {uid} has no 'or' mode")
                return
            if c["id"] in cr.WEAPON_REQUIRES_MODIFIER and not step.get("modifier"):
                errors.append(f"step {i}: {uid} fires only together with a Modifier")
                return
            modifier_uid = step.get("modifier")
            if modifier_uid:
                if not sim.has(modifier_uid) and modifier_uid != uid:
                    errors.append(f"step {i}: modifier {modifier_uid} not in hand")
                    return
                mc = card_of(cdb, modifier_uid)
                is_wakizashi_case = mc["id"] == cr.WAKIZASHI_WEAPON_ID
                is_renkei = mc["id"] == cr.RENKEI_MODIFIER_ID
                if "modifier" not in mc["types"] and not is_wakizashi_case and not is_renkei:
                    errors.append(f"step {i}: {modifier_uid} is not a modifier")
                    return
                if is_wakizashi_case and c["id"] != cr.KATANA_WEAPON_ID:
                    errors.append(f"step {i}: Wakizashi may only modify a Katana attack")
                    return
            icon_complexity = None
            thrown = False
            for icon in icons or []:
                if icon == "complexity1":
                    icon_complexity = 1
                elif icon == "complexity2":
                    icon_complexity = 2
                elif icon == "complexity_any":
                    icon_complexity = "any"
                elif icon == "ranged":
                    icon_complexity = "any"
                    thrown = True
            attacker_has_horseman = sim.stance and card_id_of(sim.stance) == cr.HORSEMAN_STANCE_ID
            has_lunge = modifier_uid and card_id_of(modifier_uid) == cr.LUNGE_MODIFIER_ID
            has_hachimaki = modifier_uid and card_id_of(modifier_uid) == cr.HACHIMAKI_MODIFIER_ID
            is_favourite = cr.is_favourite_weapon(c["id"], p["character"])
            handles = cr.weapon_handles(icon_complexity, attacker_has_horseman, has_lunge, has_hachimaki, is_favourite)
            if has_hachimaki and cr.at_death_door(p["hp"], p["character"]):
                errors.append(f"step {i}: Hachimaki cannot be played at death's door")
                return

        complexity = target_complexity(cdb, state, target)
        if not cr.handles_meets(handles, complexity):
            errors.append(f"step {i}: weapon handles {handles} but target complexity is {complexity}")
            return

        if cr.DUST_IN_EYES_EFFECT_ID in actor_effect_ids:
            if complexity != 1:
                errors.append(f"step {i}: Dust in the Eyes restricts you to complexity-1 targets")
                return
            if thrown:
                errors.append(f"step {i}: Dust in the Eyes forbids thrown weapons")
                return

        if thrown:
            smoke_veil_team = None
            for q in state["players"]:
                if player_aura_id(state, q["seat"]) == cr.SMOKE_VEIL_AURA_ID:
                    smoke_veil_team = q["faction"]
                    break
            if smoke_veil_team is not None and p["faction"] != smoke_veil_team:
                errors.append(f"step {i}: Smoke Veil forbids ranged attacks by the aura owner's enemies")
                return
            if player_aura_id(state, seat) == cr.SENTRY_AURA_ID:
                errors.append(f"step {i}: Sentry forbids its bearer from using thrown weapons")
                return

        if mode != "bare":
            sim.take(step["card"])
            if step.get("modifier") and step["modifier"] != step.get("card"):
                if sim.has(step["modifier"]):
                    sim.take(step["modifier"])

    elif do == "effect":
        uid = step.get("card")
        target = step.get("target")
        if not uid or not sim.has(uid):
            errors.append(f"step {i}: effect card {uid} not in hand")
            return
        c = card_of(cdb, uid)
        if "effect" not in c["types"]:
            errors.append(f"step {i}: {uid} is not an effect")
            return
        if target is None:
            errors.append(f"step {i}: effect needs a target")
            return
        tgt = None
        for q in state["players"]:
            if q["seat"] == target:
                tgt = q
        if tgt is None or not tgt["alive"]:
            errors.append(f"step {i}: target {target} is not alive")
            return
        if is_untargetable(state, target):
            errors.append(f"step {i}: target {target} is untargetable (Shadow)")
            return
        if c["id"] in sim.effects_on.setdefault(target, {card_id_of(u) for u in tgt["effects"]}):
            errors.append(f"step {i}: target already has effect {c['id']}")
            return
        sim.take(uid)
        sim.effects_on[target].add(c["id"])

    elif do == "play":
        uid = step.get("card")
        if not uid or not sim.has(uid):
            errors.append(f"step {i}: card {uid} not in hand")
            return
        c = card_of(cdb, uid)
        if not (set(c["types"]) & {"action", "aoe", "intervention"}):
            errors.append(f"step {i}: {uid} is not action/aoe/intervention")
            return
        reactors = step.get("reactors")
        if reactors is None:
            reactors = "others" if "aoe" in c["types"] else []
        if reactors not in ("others", "enemies", "allies") and not isinstance(reactors, list):
            errors.append(f"step {i}: reactors must be 'others'/'enemies'/'allies' or a list of seats")
            return
        if reactors:
            sim.opened_transaction = True
        sim.take(uid)

    elif do == "ability":
        source = step.get("source")
        if source not in ("character",) and not (isinstance(source, str) and (source.startswith("stance:") or source.startswith("aura:"))):
            errors.append(f"step {i}: invalid ability source {source!r}")
            return
        if source != "character":
            kind, _, uid = source.partition(":")
            owner_uid = sim.stance if kind == "stance" else (sim.aura["uid"] if sim.aura else None)
            if owner_uid != uid:
                errors.append(f"step {i}: {uid} is not on your table")
                return
        if not step.get("choice"):
            errors.append(f"step {i}: ability needs a 'choice'")
            return

    elif do == "replan":
        pass

    else:
        errors.append(f"step {i}: unknown do={do!r}")


def validate_reaction(cdb, state, seat, reaction):
    errors = []
    if state["phase"] != "react":
        errors.append("game is not awaiting reactions")
    pend = state.get("pending")
    if pend is None or seat not in pend.get("reactors_pending", []):
        errors.append(f"seat {seat} is not an expected reactor")
    elif not find_player(state, seat)["alive"]:
        errors.append(f"seat {seat} is dead and cannot react")
    if errors:
        raise ValidationError(errors)
    action = reaction.get("action")
    if action not in ("take", "defend", "pass", "intervene", "respond"):
        raise ValidationError([f"invalid action {action!r}"])
    p = find_player(state, seat)
    for uid in reaction.get("cards", []) or []:
        if uid == "trap":
            if not p["trap"]:
                raise ValidationError(["no trap to name"])
            continue
        if uid not in p["hand"]:
            raise ValidationError([f"card {uid} not in seat {seat}'s hand"])
    return True


def validate_ops(cdb, state, ops):
    errors = []
    if not isinstance(ops, list):
        return ["ops must be a list"]
    if any(o.get("op") == "reject" for o in ops) and len(ops) != 1:
        errors.append("'reject' must be the only op in the list")
        return errors
    for i, op in enumerate(ops):
        kind = op.get("op")
        if kind in ("damage", "heal", "poison", "draw", "discard_random", "kill", "set_hp"):
            seat = op.get("seat")
            if seat is None or not any(p["seat"] == seat for p in state["players"]):
                errors.append(f"op {i}: bad seat {seat}")
            elif kind in ("damage", "heal", "poison", "set_hp", "draw", "discard_random") and not find_player(state, seat)["alive"]:
                errors.append(f"op {i}: seat {seat} is not alive")
        if kind in ("damage", "heal") and isinstance(op.get("n"), int) and op["n"] < 0:
            errors.append(f"op {i}: {kind}.n must not be negative")
        if kind in ("draw", "discard_random") and isinstance(op.get("n"), int) and op["n"] < 1:
            errors.append(f"op {i}: {kind}.n must be at least 1")
        if kind == "transfer_random" and "n" in op and isinstance(op.get("n"), int) and op["n"] < 1:
            errors.append(f"op {i}: transfer_random.n must be at least 1")
        if kind == "set_hp" and isinstance(op.get("hp"), int) and op["hp"] < 0:
            errors.append(f"op {i}: set_hp.hp must not be negative")
        if kind == "discard":
            for uid in op.get("uids", []):
                zone, s = locate_uid(state, uid)
                if zone != "hand" or s != op.get("seat"):
                    errors.append(f"op {i}: {uid} is not in seat {op.get('seat')}'s hand")
        if kind in ("transfer",):
            uid = op.get("uid")
            if uid:
                zone, s = locate_uid(state, uid)
                if zone != "hand" or s != op.get("from"):
                    errors.append(f"op {i}: {uid} is not in seat {op.get('from')}'s hand")
        if kind == "move":
            uid = op.get("uid")
            if uid is None:
                errors.append(f"op {i}: move needs uid")
            else:
                zone, _ = locate_uid(state, uid)
                if zone is None:
                    errors.append(f"op {i}: unknown uid {uid}")
            to = op.get("to")
            if to not in ("hand", "discard", "removed", "stance", "trap", "aura", "effects", "charges"):
                errors.append(f"op {i}: bad move target {to!r}")
        if kind not in ("damage", "heal", "set_hp", "poison", "draw", "discard", "discard_random",
                         "transfer", "transfer_random", "move", "reveal", "vp", "kill", "flag",
                         "note", "reject"):
            errors.append(f"op {i}: unknown op {kind!r}")
    return errors


# ===========================================================================
# Executor — plan
# ===========================================================================

def start_plan(ctx, seat, plan):
    state = ctx.state
    validate_plan(ctx.cdb, state, seat, plan)
    p = find_player(state, seat)

    for uid in plan.get("discard_to_limit") or []:
        move_uid(state, uid, "discard")
    if plan.get("discard_to_limit"):
        ctx.log("discard_to_limit", f"{player_label(state, seat)} discards to hand limit",
                actor=seat, data={"uids": plan["discard_to_limit"]})

    recovery = plan.get("recovery")
    if recovery:
        for uid in recovery.get("discard", []):
            move_uid(state, uid, "discard")
        n = STARTING_HAND - len(p["hand"])
        drawn = draw_cards(ctx, seat, max(0, n)) if n > 0 else []
        p["needs_recovery"] = False
        ctx.log("recovery", f"{player_label(state, seat)} recovers ({len(recovery.get('discard', []))} discarded, {len(drawn)} drawn)",
                actor=seat)
    elif p["needs_recovery"]:
        # §5.1: recovery "is done before your next turn starts" — it is a
        # one-time window, not something that can be deferred indefinitely.
        # Omitting `recovery` on the turn where it is offered means "change
        # nothing" (one of the two documented choices), and closes it.
        p["needs_recovery"] = False
        ctx.log("recovery", f"{player_label(state, seat)} recovers (changes nothing)", actor=seat)

    state["plan"] = {"seat": seat, "steps": plan.get("steps", []), "cursor": 0,
                      "end_turn": plan.get("end_turn") or {}, "notes": plan.get("notes")}
    state["_continuing"] = False
    if plan.get("notes"):
        ctx.log("plan", f"{player_label(state, seat)} plans: {plan['notes']}", actor=seat, notes=plan["notes"])
    else:
        ctx.log("plan", f"{player_label(state, seat)} submits a plan", actor=seat)

    run_executor(ctx)


def _step_still_legal(cdb, state, seat, step):
    """Re-check a plan step's legality against the CURRENT state, right
    before it executes (§5.2: "steps that are no longer legal when their
    turn comes ... are skipped with an event step_skipped"). Only re-checks
    what can actually change between plan submission and execution: a card
    leaving the hand (moved by an earlier referee ruling in the same plan),
    or a target dying / becoming untargetable. Returns (True, None) or
    (False, reason)."""
    do = step["do"]
    p = find_player(state, seat)

    def has_card(uid):
        return uid in p["hand"]

    def alive_target(target):
        for q in state["players"]:
            if q["seat"] == target:
                return q["alive"]
        return False

    if do in ("stance", "trap", "aura", "charge_aura"):
        uid = step.get("card")
        if uid and not has_card(uid):
            return False, f"card {uid} is no longer in hand"
    elif do == "trade":
        for uid in step.get("discard", []) or []:
            if not has_card(uid):
                return False, f"card {uid} is no longer in hand"
    elif do == "attack":
        target = step.get("target")
        if not alive_target(target):
            return False, f"target {target} is dead"
        if is_untargetable(state, target):
            return False, f"target {target} is untargetable"
        if step.get("mode") != "bare":
            uid = step.get("card")
            if uid and not has_card(uid):
                return False, f"weapon {uid} is no longer in hand"
            modifier_uid = step.get("modifier")
            if modifier_uid and modifier_uid != uid and not has_card(modifier_uid):
                return False, f"modifier {modifier_uid} is no longer in hand"
    elif do == "effect":
        uid = step.get("card")
        target = step.get("target")
        if uid and not has_card(uid):
            return False, f"card {uid} is no longer in hand"
        if not alive_target(target):
            return False, f"target {target} is dead"
        if is_untargetable(state, target):
            return False, f"target {target} is untargetable"
        if uid:
            cid = card_id_of(uid)
            tgt = find_player(state, target)
            if cid in {card_id_of(u) for u in tgt["effects"]}:
                return False, f"target already has effect {cid}"
    elif do == "play":
        uid = step.get("card")
        if uid and not has_card(uid):
            return False, f"card {uid} is no longer in hand"
    return True, None


def _why_of(obj):
    """A step's / reaction's short reasoning phrase, trimmed; None when absent."""
    if not isinstance(obj, dict):
        return None
    w = obj.get("why") or obj.get("note") or obj.get("notes")
    if not isinstance(w, str):
        return None
    w = " ".join(w.split())
    return w[:200] if w else None


def run_executor(ctx):
    """Advances state['plan'] from its cursor until it needs to stop (a
    transaction opened, or the turn ended, or the game is over)."""
    state = ctx.state
    if state["status"] == "over":
        return
    plan = state["plan"]
    if plan is None:
        return
    steps = plan["steps"]
    batch = []

    def flush_batch(resume_index):
        if not batch:
            return False
        pid = state["next_pending_id"]
        state["next_pending_id"] += 1
        state["pending"] = {
            "id": pid, "kind": "batch", "actor": plan["seat"], "step": None,
            "batch": list(batch), "resume_index": resume_index,
            "reactors_all": [], "reactors_pending": [], "reactions": {}, "played": [],
            "phase": "resolve",
        }
        state["phase"] = "resolve"
        ctx.log("card_played", f"{player_label(state, plan['seat'])}'s actions await the referee",
                actor=plan["seat"], data={"batch": batch})
        return True

    i = plan["cursor"]
    while i < len(steps):
        step = steps[i]
        do = step["do"]
        ctx.step_why = _why_of(step)

        if do != "replan":
            legal, reason = _step_still_legal(ctx.cdb, state, plan["seat"], step)
            if not legal:
                ctx.log("step_skipped", f"step {i} ({do}) skipped: {reason}",
                        actor=plan["seat"], data={"step": step, "reason": reason})
                i += 1
                continue

        if do in ("stance", "trap", "aura", "charge_aura", "trade"):
            _exec_mechanical(ctx, plan["seat"], step)
            i += 1
            continue

        if do == "attack":
            if flush_batch(i):
                plan["cursor"] = i
                ctx.step_why = None
                return
            _open_attack(ctx, plan["seat"], step, i)
            plan["cursor"] = i + 1
            ctx.step_why = None
            return

        if do == "play":
            c = card_of(ctx.cdb, step["card"])
            reactors_spec = step.get("reactors")
            if reactors_spec is None:
                reactors_spec = "others" if "aoe" in c["types"] else []
            reactor_seats = _resolve_reactor_spec(ctx.cdb, state, plan["seat"], reactors_spec)
            if reactor_seats:
                if flush_batch(i):
                    plan["cursor"] = i
                    ctx.step_why = None
                    return
                _open_card(ctx, plan["seat"], step, i, reactor_seats)
                plan["cursor"] = i + 1
                ctx.step_why = None
                return
            else:
                move_uid(state, step["card"], "played", seat=plan["seat"])
                ctx.log("card_played", f"{player_label(state, plan['seat'])} plays {card_label(ctx.cdb, step['card'])}",
                        actor=plan["seat"], card=step["card"])
                batch.append(step)
                i += 1
                continue

        if do == "effect":
            target = step["target"]
            move_uid(state, step["card"], "effects", seat=target)
            ctx.log("effect_placed", f"{player_label(state, plan['seat'])} places {card_label(ctx.cdb, step['card'])} on {player_label(state, target)}",
                    actor=plan["seat"], target=target, card=step["card"])
            batch.append(step)
            i += 1
            continue

        if do == "ability":
            ctx.log("ability_used", f"{player_label(state, plan['seat'])} uses an ability: {step.get('choice')}",
                    actor=plan["seat"], target=step.get("target"), notes=step.get("choice"))
            batch.append(step)
            i += 1
            continue

        if do == "replan":
            opened = flush_batch(i + 1)
            ctx.log("plan", f"{player_label(state, plan['seat'])} asks to replan", actor=plan["seat"])
            if opened:
                # The batch still needs the referee, but `replan` means the
                # REST of this plan (everything after it) is discarded, not
                # merely paused — so mark the pending transaction to end the
                # plan (continuing:true) once it closes, instead of letting
                # `_close_pending_and_resume` resume the cursor into the
                # steps `replan` was supposed to cut off (see §5.2 / the
                # `replan` step in plan.schema.json).
                state["pending"]["resume_index"] = None
                state["pending"]["discard_plan_after"] = True
                plan["cursor"] = i + 1
                ctx.step_why = None
                return
            state["plan"] = None
            state["phase"] = "plan"
            state["_continuing"] = True
            ctx.step_why = None
            return

        # unknown step at execution time (should have been caught at validation)
        ctx.log("step_skipped", f"step {i} skipped (unrecognised)", actor=plan["seat"])
        i += 1

    # end of steps
    if flush_batch(len(steps)):
        plan["cursor"] = len(steps)
        ctx.step_why = None
        return
    _finish_plan(ctx)


def _resolve_reactor_spec(cdb, state, seat, spec):
    if isinstance(spec, list):
        return list(spec)
    if spec == "others":
        return [p["seat"] for p in state["players"] if p["seat"] != seat and p["alive"]]
    if spec == "enemies":
        return [s for s in enemies_of(state, seat) if find_player(state, s)["alive"]]
    if spec == "allies":
        return [s for s in teammates(state, seat) if find_player(state, s)["alive"]]
    return []


def _exec_mechanical(ctx, seat, step):
    state = ctx.state
    cdb = ctx.cdb
    p = find_player(state, seat)
    do = step["do"]

    if do == "stance":
        uid = step["card"]
        old = p["stance"]
        if old:
            move_uid(state, old, "hand", seat=seat)
        move_uid(state, uid, "stance", seat=seat)
        p["stance_played"] = True
        ctx.log("stance_set", f"{player_label(state, seat)} sets stance {card_label(cdb, uid)}", actor=seat, card=uid)
        if card_id_of(uid) == LOTUS_STANCE_ID:
            healed = min(2, p["max_hp"] - p["hp"])
            if healed > 0:
                p["hp"] += healed
            ctx.log("heal", f"{player_label(state, seat)} (Lotus) restores 2 life on play",
                    actor=seat, target=seat, data={"n": 2})

    elif do == "trap":
        uid = step["card"]
        old = p["trap"]["uid"] if p["trap"] else None
        if old:
            move_uid(state, old, "hand", seat=seat)
        move_uid(state, uid, "trap", seat=seat, face_up=False)
        p["trap_set"] = True
        ctx.log("trap_set", f"{player_label(state, seat)} sets a trap face down", actor=seat, card=uid)

    elif do == "aura":
        uid = step["card"]
        old = p["aura"]
        in_front_of = step.get("in_front_of")
        owner_seat = in_front_of if in_front_of is not None else seat
        if old:
            for cuid in list(old.get("charges", [])):
                move_uid(state, cuid, "discard")
            move_uid(state, old["uid"], "hand", seat=seat)
        move_uid(state, uid, "aura", seat=owner_seat)
        p["aura_played"] = True
        ctx.log("aura_set", f"{player_label(state, seat)} plays aura {card_label(cdb, uid)}", actor=seat, card=uid,
                target=owner_seat)
        if card_id_of(uid) == cr.BARREL_OF_STENCH_AURA_ID:
            bearer = find_player(state, owner_seat)
            bearer["poisoned"] = True
            ctx.log("poison", f"{player_label(state, owner_seat)} (Barrel of Stench) becomes poisoned",
                    target=owner_seat, data={"value": True})

    elif do == "charge_aura":
        uid = step["card"]
        aura_owner = step["aura_owner"]
        move_uid(state, uid, "charges", seat=aura_owner)
        ctx.log("aura_charged", f"{player_label(state, seat)} tucks {card_label(cdb, uid)} under {player_label(state, aura_owner)}'s aura",
                actor=seat, target=aura_owner, card=uid)

    elif do == "trade":
        discard = step["discard"]
        c1, c2 = (card_of(cdb, u) for u in discard)
        same_id = c1["id"] == c2["id"]
        for uid in discard:
            move_uid(state, uid, "discard")
        n = 2 if same_id else 1
        drawn = draw_cards(ctx, seat, n)
        ctx.log("trade", f"{player_label(state, seat)} trades {discard} for {len(drawn)} card(s)",
                actor=seat, data={"discarded": discard, "drawn": drawn})


def _open_attack(ctx, seat, step, step_index):
    state = ctx.state
    cdb = ctx.cdb
    p = find_player(state, seat)
    target = step["target"]
    mode = step.get("mode", "main")

    if mode == "bare":
        weapon_uid = None
        baseline = {
            "weapon": None, "weapon_id": None, "mode": "bare", "modifier": None, "modifier_id": None,
            "handles": 1, "complexity": target_complexity(cdb, state, target),
            "power": 2 if p["character"] == cr.SAIGO_CHARACTER_ID else 1,
            "dmg_base": 2 if p["character"] == cr.SAIGO_CHARACTER_ID else 1,
            "thrown": False, "poisoned": False,
            "undefendable": any(card_id_of(u) == 101 for u in find_player(state, target).get("effects", [])),
            "ignores_traps": False,
            "trap_may_fire": bool(find_player(state, target)["trap"]),
            "notes": ["bare hands"],
        }
    else:
        weapon_uid = step["card"]
        modifier_uid = step.get("modifier")
        baseline = compute_baseline(cdb, state, seat, target, weapon_uid, mode, modifier_uid)
        move_uid(state, weapon_uid, "played", seat=seat)
        if modifier_uid and modifier_uid != weapon_uid:
            move_uid(state, modifier_uid, "played", seat=seat)

    pid = state["next_pending_id"]
    state["next_pending_id"] += 1
    reactors_all, reactions = attack_reactors(cdb, state, seat, target, undefendable=baseline["undefendable"])
    pending = {
        "id": pid, "kind": "attack", "actor": seat, "step": {**step, "step_index": step_index},
        "batch": [], "resume_index": step_index + 1,
        "reactors_all": reactors_all, "reactors_pending": [s for s in reactors_all if str(s) not in reactions],
        "reactions": reactions, "baseline": baseline,
        "phase": None,
    }
    pending["phase"] = "react" if pending["reactors_pending"] else "resolve"
    state["pending"] = pending
    state["phase"] = pending["phase"]

    ctx.log("attack_declared",
            f"{player_label(state, seat)} attacks {player_label(state, target)} with "
            f"{'bare hands' if mode == 'bare' else card_label(cdb, weapon_uid)}",
            actor=seat, target=target, card=weapon_uid,
            data={"mode": mode, "modifier": step.get("modifier"), "baseline": baseline,
                  "reactors": list(reactors_all)})

    for s_str, r in reactions.items():
        ctx.log("reaction_auto", f"{player_label(state, int(s_str))} auto-{r['action']}s (nothing to react with)",
                actor=int(s_str), data=r)


def _open_card(ctx, seat, step, step_index, reactor_seats):
    state = ctx.state
    cdb = ctx.cdb
    move_uid(state, step["card"], "played", seat=seat)
    pid = state["next_pending_id"]
    state["next_pending_id"] += 1
    pending = {
        "id": pid, "kind": "card", "actor": seat, "step": {**step, "step_index": step_index},
        "batch": [], "resume_index": step_index + 1,
        "reactors_all": list(reactor_seats), "reactors_pending": list(reactor_seats),
        "reactions": {}, "phase": "react",
    }
    state["pending"] = pending
    state["phase"] = "react"
    ctx.log("card_played", f"{player_label(state, seat)} plays {card_label(cdb, step['card'])}",
            actor=seat, card=step["card"], data={"reactors": reactor_seats, "ask": step.get("ask")})


def _finish_plan(ctx):
    state = ctx.state
    plan = state["plan"]
    seat = plan["seat"]
    p = find_player(state, seat)
    end_turn = plan.get("end_turn") or {}
    lotus = end_turn.get("lotus")
    if lotus and p["stance"] and card_id_of(p["stance"]) == LOTUS_STANCE_ID:
        if lotus == "heal":
            tgt = find_player(state, end_turn["target"])
            tgt["hp"] = min(tgt["max_hp"], tgt["hp"] + 1)
            ctx.log("heal", f"{player_label(state, seat)} (Lotus) heals {player_label(state, tgt['seat'])} 1",
                    actor=seat, target=tgt["seat"], data={"n": 1})
        elif lotus == "draw":
            drawn = draw_cards(ctx, seat, 1)
            ctx.log("draw", f"{player_label(state, seat)} (Lotus) draws a card", actor=seat, data={"n": len(drawn)})

    end_of_turn(ctx)


# ===========================================================================
# Reactions
# ===========================================================================

def apply_reaction(ctx, seat, reaction):
    state = ctx.state
    validate_reaction(ctx.cdb, state, seat, reaction)
    pend = state["pending"]
    for uid in reaction.get("cards", []) or []:
        if uid == "trap":
            continue
        move_uid(state, uid, "played", seat=seat)
    pend["reactions"][str(seat)] = reaction
    pend["reactors_pending"].remove(seat)
    ctx.log("reaction", f"{player_label(state, seat)} reacts: {reaction.get('action')}", actor=seat,
            data=reaction, notes=_why_of(reaction))

    if not pend["reactors_pending"]:
        pend["phase"] = "resolve"
        state["phase"] = "resolve"


# ===========================================================================
# Resolve (referee ops)
# ===========================================================================

def _pending_attack_weapon_uid(state):
    """The weapon uid of the currently open attack transaction, if any — used
    to attribute `damage` ops to a card for the report (§11)."""
    pend = state.get("pending")
    if pend and pend.get("kind") == "attack":
        return pend["baseline"].get("weapon")
    return None


def apply_op(ctx, op):
    state = ctx.state
    kind = op["op"]
    if kind == "damage":
        seat = op["seat"]
        p = find_player(state, seat)
        n = op["n"]
        weapon_uid = _pending_attack_weapon_uid(state) if op.get("source") == "attack" else None
        new_hp = p["hp"] - n
        if new_hp <= 0:
            p["hp"] = 0
            ctx.log("damage", f"{player_label(state, seat)} takes {n} damage ({op.get('source')})",
                    actor=op.get("by"), target=seat, card=weapon_uid, data=op)
            handle_death(ctx, seat, source=op.get("source"), by=op.get("by"))
        else:
            p["hp"] = new_hp
            ctx.log("damage", f"{player_label(state, seat)} takes {n} damage ({op.get('source')})",
                    card=weapon_uid,
                    actor=op.get("by"), target=seat, data=op)
    elif kind == "heal":
        seat = op["seat"]
        p = find_player(state, seat)
        cap = p["max_hp"] + op.get("over_max", 0)
        p["hp"] = min(cap, p["hp"] + op["n"])
        ctx.log("heal", f"{player_label(state, seat)} heals {op['n']}", target=seat, data=op)
    elif kind == "set_hp":
        seat = op["seat"]
        p = find_player(state, seat)
        old_hp = p["hp"]
        new_hp = max(0, min(op["hp"], p["max_hp"]))
        p["hp"] = new_hp
        ctx.log("damage" if new_hp < old_hp else "heal", f"{player_label(state, seat)} hp set to {new_hp}",
                target=seat, data=op)
        if new_hp <= 0:
            handle_death(ctx, seat, source="other", by=None)
    elif kind == "poison":
        seat = op["seat"]
        p = find_player(state, seat)
        p["poisoned"] = bool(op["value"])
        ctx.log("poison", f"{player_label(state, seat)} poison set to {p['poisoned']}", target=seat, data=op)
    elif kind == "draw":
        seat = op["seat"]
        drawn = draw_cards(ctx, seat, op["n"])
        ctx.log("draw", f"{player_label(state, seat)} draws {len(drawn)}", target=seat, data={"n": len(drawn)})
    elif kind == "discard":
        seat = op["seat"]
        for uid in op["uids"]:
            move_uid(state, uid, "discard")
        ctx.log("discard", f"{player_label(state, seat)} discards {op['uids']}", target=seat, data=op)
    elif kind == "discard_random":
        seat = op["seat"]
        p = find_player(state, seat)
        r = rng_load(state)
        uids = []
        for _ in range(min(op["n"], len(p["hand"]))):
            uid = r.choice(p["hand"])
            move_uid(state, uid, "discard")
            uids.append(uid)
        rng_save(state, r)
        ctx.log("discard", f"{player_label(state, seat)} discards {len(uids)} random card(s)", target=seat,
                data={"uids": uids})
    elif kind == "transfer":
        move_uid(state, op["uid"], "hand", seat=op["to"])
        ctx.log("transfer", f"card {op['uid']} moves {op['from']} -> {op['to']}", actor=op["from"], target=op["to"],
                card=op["uid"])
    elif kind == "transfer_random":
        r = rng_load(state)
        src = find_player(state, op["from"])
        n = min(op.get("n", 1), len(src["hand"]))
        moved = []
        for _ in range(n):
            uid = r.choice(src["hand"])
            move_uid(state, uid, "hand", seat=op["to"])
            moved.append(uid)
        rng_save(state, r)
        ctx.log("transfer", f"{len(moved)} card(s) move {op['from']} -> {op['to']}", actor=op["from"], target=op["to"],
                data={"uids": moved})
    elif kind == "move":
        move_uid(state, op["uid"], op["to"], seat=op.get("seat"), face_up=op.get("face_up", False))
        ctx.log("move", f"card {op['uid']} moves to {op['to']}" + (f" (seat {op['seat']})" if op.get("seat") is not None else ""),
                target=op.get("seat"), card=op["uid"], data=op)
    elif kind == "reveal":
        seat = op["seat"]
        p = find_player(state, seat)
        if op["what"] == "trap" and p["trap"]:
            p["trap"]["face_up"] = True
        ctx.log("reveal", f"{player_label(state, seat)}'s {op['what']} is revealed", target=seat, data=op)
    elif kind == "vp":
        seat = op["seat"]
        p = find_player(state, seat)
        p["vp"] += op["delta"]
        ctx.log("vp", f"{player_label(state, seat)} VP {'+' if op['delta'] >= 0 else ''}{op['delta']}", target=seat,
                data=op)
        check_vp_zero(ctx)
    elif kind == "kill":
        find_player(state, op["seat"])["hp"] = 0
        handle_death(ctx, op["seat"], source="other", by=op.get("by"))
    elif kind == "flag":
        p = find_player(state, op["seat"])
        p["flags"][op["key"]] = op["value"]
        ctx.log("flag", f"{player_label(state, op['seat'])} flag {op['key']}={op['value']}", target=op["seat"], data=op)
    elif kind == "note":
        ctx.log("ruling", op["text"], notes=op["text"])
    else:
        raise SimError(f"unhandled op {kind!r}")


def apply_resolve(ctx, ops, result=None, uses_attack=True, narrative=None, rulings=None, flags=None):
    state = ctx.state
    pend = state["pending"]
    if pend is None or "id" not in pend:
        raise ValidationError(["no open transaction to resolve"])
    if pend.get("reactors_pending"):
        raise ValidationError(
            [f"transaction {pend['id']} still awaiting reactions from {pend['reactors_pending']}"]
        )

    errors = validate_ops(ctx.cdb, state, ops)
    if errors:
        raise ValidationError(errors)

    if len(ops) == 1 and ops[0].get("op") == "reject":
        _reject_pending(ctx)
        ctx.log("rejected", f"transaction {pend['id']} rejected: {ops[0].get('reason')}",
                data={"reason": ops[0].get("reason")})
        _close_pending_and_resume(ctx)
        return

    working = copy.deepcopy(state)
    events_before = len(ctx.events)
    texts_before = len(ctx.executed_texts)
    try:
        for op in ops:
            if ctx.state["status"] == "over":
                # A game-ending op (vp reaching 0) already ran; the game is
                # finalised (score frozen) and no further op in this same
                # list should be applied against it (§5.1 end conditions).
                ctx.log("ruling", "remaining op(s) skipped: game already over", data={"skipped_op": op})
                continue
            apply_op(ctx, op)
    except Exception as e:
        ctx.state = working
        ctx.events = ctx.events[:events_before]
        ctx.executed_texts = ctx.executed_texts[:texts_before]
        raise ValidationError([f"op application failed: {e}"])

    state = ctx.state
    if narrative:
        ctx.log("ruling", narrative, notes=narrative)
    for rul in (rulings or []):
        ctx.log("ruling", f"ruling on {rul.get('card')}: {rul.get('question')} -> {rul.get('ruling')}",
                data=rul, notes=rul.get("ruling"))

    pend = state.get("pending")
    if pend and pend["kind"] == "attack":
        is_bare = pend["step"].get("mode") == "bare"
        if is_bare or uses_attack:
            p = find_player(state, pend["actor"])
            p["attacks_used"] += 2 if is_bare else 1

    for entry in list(state.get("transit", [])):
        move_uid(state, entry["uid"], "discard")

    _close_pending_and_resume(ctx)


def _reject_pending(ctx):
    state = ctx.state
    pend = state["pending"]
    for entry in list(state.get("transit", [])):
        move_uid(state, entry["uid"], "hand", seat=entry["seat"])
    if pend["kind"] == "batch":
        for step in pend["batch"]:
            if step["do"] == "effect":
                zone, s = locate_uid(state, step["card"])
                if zone == "effects":
                    move_uid(state, step["card"], "hand", seat=pend["actor"])


def _close_pending_and_resume(ctx):
    state = ctx.state
    pend = state["pending"]
    resume_index = pend.get("resume_index")
    discard_plan_after = pend.get("discard_plan_after", False)
    ctx.log("transaction_closed", f"transaction {pend['id']} ({pend['kind']}) closes", data={"id": pend["id"], "kind": pend["kind"]})
    state["pending"] = None
    check_consistency(state)
    if state["status"] == "over":
        return
    if discard_plan_after:
        state["plan"] = None
        state["phase"] = "plan"
        state["_continuing"] = True
        return
    plan = state.get("plan")
    if plan is not None and resume_index is not None:
        actor = find_player(state, plan["seat"])
        if not actor["alive"]:
            # the acting player died inside their own turn (a trap, a counter-blow): the rest of
            # the plan is void — a dead player does nothing — and the turn ends right away
            remaining = len(plan["steps"]) - resume_index
            if remaining > 0:
                ctx.log("step_skipped", f"{player_label(state, plan['seat'])} is dead: {remaining} remaining step(s) dropped",
                        actor=plan["seat"], data={"reason": "actor dead", "dropped": remaining})
            plan["cursor"] = len(plan["steps"])
        else:
            plan["cursor"] = resume_index
        run_executor(ctx)
    else:
        state["phase"] = "plan"


# ===========================================================================
# Export (§9)
# ===========================================================================

def cmd_export(conn, cdb, game_id=None, all_=False, out_dir=None):
    out_dir = Path(out_dir) if out_dir else (REPO_ROOT / "simulations" / "games")
    out_dir.mkdir(parents=True, exist_ok=True)
    game_ids = []
    if all_:
        rows = conn.execute("SELECT id FROM games ORDER BY id").fetchall()
        game_ids = [r[0] for r in rows]
    else:
        game_ids = [game_id]

    written = []
    for gid in game_ids:
        state = load_game(conn, gid)
        events = conn.execute(
            "SELECT seq, turn, active, kind, actor, target, card, card_id, text, data_json, notes, state_json "
            "FROM events WHERE game_id = ? ORDER BY seq", (gid,)
        ).fetchall()
        ev_out = []
        for (seq, turn, active, kind, actor, target, card, card_id, text, data_json, notes, state_json) in events:
            ev_out.append({
                "seq": seq, "turn": turn, "active": active, "kind": kind, "actor": actor, "target": target,
                "card": card, "card_id": card_id, "text": text, "data": json.loads(data_json or "{}"),
                "notes": notes, "state": json.loads(state_json or "{}"),
            })
        players_out = []
        for p in state["players"]:
            char = cdb.get(p["character"])
            players_out.append({
                "seat": p["seat"], "name": p["name"], "faction": p["faction"], "first": p["first"],
                "character": {"id": char["id"], "name": char["name"], "hp": char["hp"], "text": char["text"]},
            })
        doc = {
            "game": {
                "id": gid, "seed": state["seed"], "players_n": state["players_n"], "max_turns": state["max_turns"],
                "turns_played": state["turn"] - (0 if state["status"] == "over" else 1),
                "players": players_out, "result": state["result"],
                "assumptions": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10"],
            },
            "cards": {str(cid): {
                "id": c["id"], "name": c["name"], "types": c["types"], "icons": c["icons"],
                "icons_or": c["icons_or"], "text": c["text"],
            } for cid, c in cdb.by_id.items()},
            "events": ev_out,
        }
        path = out_dir / f"game_{gid}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        written.append({"game": gid, "path": str(path)})

    index = []
    rows = conn.execute("SELECT id FROM games ORDER BY id").fetchall()
    for (gid,) in rows:
        p = out_dir / f"game_{gid}.json"
        if p.exists():
            st = load_game(conn, gid)
            index.append({"game": gid, "status": st["status"], "result": st["result"], "path": p.name})
    with open(out_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    return {"ok": True, "written": written, "index": str(out_dir / "index.json")}


# ===========================================================================
# Report (§11)
# ===========================================================================

def cmd_report(conn, cdb, game_ids=None, out_path=None):
    """Aggregate markdown report over games (§11).

    Every event row carries the table snapshot after it (hands included), so a card copy
    can be followed from the moment it enters a hand to the moment it leaves: how long it
    was held, whether it was played and in which role, or discarded unplayed, or stolen.
    """
    if game_ids is None:
        rows = conn.execute("SELECT id FROM games ORDER BY id").fetchall()
        game_ids = [r[0] for r in rows]

    ROLE_OF_KIND = {"attack_declared": "attack", "stance_set": "stance", "trap_set": "trap", "aura_set": "aura",
                    "aura_charged": "charge", "effect_placed": "effect", "card_played": "action"}
    UNPLAYED_KINDS = {"discard_to_limit": "hand limit", "trade": "traded in", "recovery": "recovery",
                      "discard": "discarded", "discard_random": "discarded", "transfer": "taken"}

    per_card = {}
    per_character = {}
    per_faction = {"samurai": {"games": 0, "wins": 0, "vp_sum": 0}, "ninja": {"games": 0, "wins": 0, "vp_sum": 0}}
    per_game = []
    rulings = []
    lengths = []

    def card_stat(cid):
        return per_card.setdefault(cid, {
            "plays": 0, "by_role": {}, "hits": 0, "no_damage": 0, "wounds_dealt": 0, "kills": 0,
            "unplayed": {}, "held_never_played": 0, "turns_held_played": [], "turns_held_unplayed": [],
            "rejected": 0, "why": [],
        })

    for gid in game_ids:
        state = load_game(conn, gid)
        rows = conn.execute(
            "SELECT turn, kind, actor, target, card, card_id, text, data_json, notes, state_json "
            "FROM events WHERE game_id = ? ORDER BY seq", (gid,)).fetchall()
        seat_char = {p["seat"]: p["character"] for p in state["players"]}
        gstat = {"game": gid, "turns": state["turn"], "attacks": 0, "defended": 0, "interventions": 0,
                 "kills": 0, "deaths": 0, "poisonings": 0, "rulings": 0,
                 "result": state.get("result"), "status": state["status"]}
        entered = {}            # uid -> turn it entered the current hand
        prev_hands = {}
        last_attack_card = {}   # actor seat -> weapon card id of their open attack
        open_attack = None      # (card_id, damaged) for the attack transaction in progress

        for (turn, kind, actor, target, card, card_id, text, data_json, notes, state_json) in rows:
            data = json.loads(data_json or "{}")
            snap = json.loads(state_json or "{}")
            hands = snap.get("hands") or {}

            # ── card copies entering / leaving hands ──
            for seat_key, hand in hands.items():
                prev = prev_hands.get(seat_key, [])
                for uid in hand:
                    if uid not in prev and uid not in entered:
                        entered[uid] = turn
                for uid in prev:
                    if uid in hand:
                        continue
                    t0 = entered.pop(uid, turn)
                    held = max(0, turn - t0)
                    try:
                        cid = card_id_of(uid)
                    except SimError:
                        continue
                    st = card_stat(cid)
                    role = None
                    if kind in ROLE_OF_KIND:
                        role = ROLE_OF_KIND[kind]
                        if kind == "attack_declared" and card != uid:
                            role = "modifier"
                    elif kind in ("reaction", "reaction_auto"):
                        act = data.get("action")
                        role = {"defend": "defense", "intervene": "intervention", "respond": "response"}.get(act, "reaction")
                    if role:
                        st["plays"] += 1
                        st["by_role"][role] = st["by_role"].get(role, 0) + 1
                        st["turns_held_played"].append(held)
                        if notes and len(st["why"]) < 3:
                            st["why"].append(notes)
                    else:
                        label = UNPLAYED_KINDS.get(kind, "left hand")
                        st["unplayed"][label] = st["unplayed"].get(label, 0) + 1
                        st["turns_held_unplayed"].append(held)
            prev_hands = {k: list(v) for k, v in hands.items()}

            # ── attacks, wounds, kills ──
            if kind == "attack_declared":
                gstat["attacks"] += 1
                open_attack = {"card_id": card_id, "damaged": False}
            if kind == "reaction" and data.get("action") == "defend":
                gstat["defended"] += 1
            if kind == "reaction" and data.get("action") == "intervene":
                gstat["interventions"] += 1
            if kind == "damage":
                n = int(data.get("n") or 0)
                src = data.get("source")
                by = data.get("by")
                if src == "attack" and open_attack is not None:
                    open_attack["damaged"] = True
                    if open_attack["card_id"]:
                        cs = card_stat(open_attack["card_id"])
                        cs["hits"] += 1
                        cs["wounds_dealt"] += n
                if target is not None and target in seat_char:
                    ch = per_character.setdefault(seat_char[target], {"games": 0, "wins": 0, "wounds_taken": 0,
                                                                        "wounds_dealt": 0, "kills": 0, "deaths": 0})
                    ch["wounds_taken"] += n
                if by is not None and by in seat_char and src in ("attack", "thrust", "trap", "other"):
                    ch2 = per_character.setdefault(seat_char[by], {"games": 0, "wins": 0, "wounds_taken": 0,
                                                                     "wounds_dealt": 0, "kills": 0, "deaths": 0})
                    ch2["wounds_dealt"] += n
            if kind == "transaction_closed":
                if open_attack is not None and not open_attack["damaged"] and open_attack["card_id"]:
                    card_stat(open_attack["card_id"])["no_damage"] += 1
                open_attack = None
            if kind == "death":
                gstat["deaths"] += 1
                by = data.get("by")
                if target in seat_char:
                    per_character.setdefault(seat_char[target], {"games": 0, "wins": 0, "wounds_taken": 0,
                                                                  "wounds_dealt": 0, "kills": 0, "deaths": 0})["deaths"] += 1
                if by is not None and by in seat_char and data.get("source") != "poison":
                    gstat["kills"] += 1
                    per_character.setdefault(seat_char[by], {"games": 0, "wins": 0, "wounds_taken": 0,
                                                              "wounds_dealt": 0, "kills": 0, "deaths": 0})["kills"] += 1
                    if open_attack is not None and open_attack["card_id"]:
                        card_stat(open_attack["card_id"])["kills"] += 1
            if kind == "poison" and data.get("value") is True:
                gstat["poisonings"] += 1
            if kind == "rejected":
                if card_id:
                    card_stat(card_id)["rejected"] += 1
            if kind == "ruling" and notes:
                gstat["rulings"] += 1
                rulings.append({"game": gid, "turn": turn, "text": notes})

        # cards still in hand at the end: held and never played
        final_turn = state["turn"]
        for uid, t0 in entered.items():
            try:
                cid = card_id_of(uid)
            except SimError:
                continue
            st = card_stat(cid)
            st["held_never_played"] += 1
            st["turns_held_unplayed"].append(max(0, final_turn - t0))

        per_game.append(gstat)
        if state["status"] == "over" and state.get("result"):
            res = state["result"]
            lengths.append(state["turn"])
            for fac in ("samurai", "ninja"):
                per_faction[fac]["games"] += 1
                per_faction[fac]["vp_sum"] += res["score"].get(fac, 0)
                if res["winner"] == fac:
                    per_faction[fac]["wins"] += 1
        for p in state["players"]:
            char = cdb.get(p["character"])
            cs = per_character.setdefault(char["id"], {"games": 0, "wins": 0, "wounds_taken": 0,
                                                          "wounds_dealt": 0, "kills": 0, "deaths": 0})
            cs["name"] = char["name"]
            cs["games"] += 1
            if state.get("result") and state["result"]["winner"] == p["faction"]:
                cs["wins"] += 1

    def avg(xs):
        return (sum(xs) / len(xs)) if xs else None

    def fmt_avg(xs):
        v = avg(xs)
        return "—" if v is None else f"{v:.1f}"

    lines = ["# Simulation report", ""]
    lines.append(f"Games: {len(game_ids)}  ")
    if lengths:
        lines.append(f"Average game length: {avg(lengths):.1f} turns  ")
    lines.append("")
    lines.append("## Games")
    lines.append("")
    lines.append("| game | turns | result | attacks | defended | interventions | kills | poisonings | rulings |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for g in per_game:
        r = g["result"]
        res = (f"{r['winner']} {r['score']['samurai']}–{r['score']['ninja']} ({r['reason']})" if r else g["status"])
        lines.append(f"| {g['game']} | {g['turns']} | {res} | {g['attacks']} | {g['defended']} | {g['interventions']} | "
                     f"{g['kills']} | {g['poisonings']} | {g['rulings']} |")
    lines.append("")
    lines.append("## By faction")
    lines.append("")
    lines.append("| faction | games | wins | avg VP |")
    lines.append("|---|---|---|---|")
    for fac, d in per_faction.items():
        a_ = d["vp_sum"] / d["games"] if d["games"] else 0
        lines.append(f"| {fac} | {d['games']} | {d['wins']} | {a_:.1f} |")
    lines.append("")
    lines.append("## By character")
    lines.append("")
    lines.append("| character | games | wins | wounds dealt | wounds taken | kills | deaths |")
    lines.append("|---|---|---|---|---|---|---|")
    for cid, d in sorted(per_character.items(), key=lambda kv: kv[1].get("name", "")):
        lines.append(f"| {d.get('name', cid)} | {d['games']} | {d['wins']} | {d['wounds_dealt']} | {d['wounds_taken']} | "
                     f"{d['kills']} | {d['deaths']} |")
    lines.append("")
    lines.append("## By card")
    lines.append("")
    lines.append("Plays are card copies leaving a hand into the game (attack, modifier, defense, intervention, "
                 "action, effect, stance, trap, aura, charge, response). *Unplayed* copies left the hand another "
                 "way (hand limit, trade-in, recovery, stolen) or were still held when the game ended. "
                 "*Held* = average turns a copy sat in a hand before being played / before leaving unplayed.")
    lines.append("")
    lines.append("| card | plays | roles | hits / no dmg | wounds | kills | unplayed | never played | held (played / unplayed) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")

    def roles_str(d):
        return ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda kv: -kv[1])) or "—"

    def unplayed_str(d):
        return ", ".join(f"{k} {v}" for k, v in sorted(d.items(), key=lambda kv: -kv[1])) or "—"

    for cid, d in sorted(per_card.items(), key=lambda kv: (-kv[1]["plays"], kv[0])):
        name = cdb.get(cid)["name"]
        hits = f"{d['hits']} / {d['no_damage']}" if (d["hits"] or d["no_damage"]) else "—"
        lines.append(f"| {name} | {d['plays']} | {roles_str(d['by_role'])} | {hits} | {d['wounds_dealt'] or '—'} | "
                     f"{d['kills'] or '—'} | {unplayed_str(d['unplayed'])} | {d['held_never_played'] or '—'} | "
                     f"{fmt_avg(d['turns_held_played'])} / {fmt_avg(d['turns_held_unplayed'])} |")
    lines.append("")
    lines.append("### Never played")
    lines.append("")
    lines.append("Cards that entered a hand at least once and were never played in any game (sorted by copies seen).")
    lines.append("")
    dead = [(cid, d) for cid, d in per_card.items() if d["plays"] == 0]
    for cid, d in sorted(dead, key=lambda kv: -(kv[1]["held_never_played"] + sum(kv[1]["unplayed"].values()))):
        seen = d["held_never_played"] + sum(d["unplayed"].values())
        lines.append(f"- {cdb.get(cid)['name']}: {seen} copies seen — {unplayed_str(d['unplayed'])}"
                     f"{', still in hand at the end ' + str(d['held_never_played']) if d['held_never_played'] else ''}")
    if not dead:
        lines.append("- none")
    lines.append("")
    lines.append("### Why cards were played (players' own words, up to three per card)")
    lines.append("")
    for cid, d in sorted(per_card.items(), key=lambda kv: (-kv[1]["plays"], kv[0])):
        if d["why"]:
            lines.append(f"- **{cdb.get(cid)['name']}**: " + " · ".join(f"«{w}»" for w in d["why"]))
    lines.append("")
    lines.append("## Referee rulings")
    lines.append("")
    for r in rulings:
        lines.append(f"- game {r['game']} turn {r['turn']}: {r['text']}")

    text = "\n".join(lines) + "\n"
    out_path = Path(out_path) if out_path else (REPO_ROOT / "simulations" / "reports" / "report.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"ok": True, "path": str(out_path), "games": len(game_ids)}


# ===========================================================================
# rules / card / log text commands
# ===========================================================================

def strip_html_to_text(html_text):
    text = re.sub(r"(?s)<!--.*?-->", "", html_text)
    text = re.sub(r"(?is)<h2[^>]*>(.*?)</h2>", lambda m: "\n\n## " + re.sub("<[^>]+>", "", m.group(1)) + "\n", text)
    text = re.sub(r"(?is)<h4[^>]*>(.*?)</h4>", lambda m: "\n### " + re.sub("<[^>]+>", "", m.group(1)) + "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"(?is)</li>", "\n", text)
    text = re.sub(r"(?is)</tr>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    out = []
    for ln in lines:
        if ln.strip() == "" and out and out[-1] == "":
            continue
        out.append(ln)
    return "\n".join(out).strip() + "\n"


def cmd_log(conn, game_id, tail=None, as_json=False):
    rows = conn.execute(
        "SELECT seq, turn, active, kind, actor, target, text, notes FROM events WHERE game_id = ? ORDER BY seq",
        (game_id,),
    ).fetchall()
    if tail:
        rows = rows[-tail:]
    if as_json:
        out = [{"seq": r[0], "turn": r[1], "active": r[2], "kind": r[3], "actor": r[4], "target": r[5],
                "text": r[6], "notes": r[7]} for r in rows]
        print(json.dumps(out, indent=2))
        return
    for (seq, turn, active, kind, actor, target, text, notes) in rows:
        print(f"[{seq:>4}] T{turn} {kind}: {text}")
        if notes:
            print(f"        note: {notes}")


# ===========================================================================
# CLI
# ===========================================================================

def read_payload(file_arg):
    """Reads and parses a --file argument's JSON. Both "the file doesn't
    exist" and "the JSON is malformed" are agent mistakes, not internal
    engine failures — they raise ValidationError (exit 1, {"ok": false,
    "errors": [...]}) so an LLM agent can tell "fix and resubmit" apart from
    a genuine SimError/traceback (exit 2)."""
    try:
        if file_arg == "-":
            raw = sys.stdin.read()
        else:
            with open(file_arg, "r", encoding="utf-8") as f:
                raw = f.read()
    except OSError as e:
        raise ValidationError([f"could not read {file_arg!r}: {e}"])
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError([f"invalid JSON in {file_arg!r}: {e}"])


def make_ctx(conn, game_id):
    state = load_game(conn, game_id)
    return Ctx(state, cards_db())


def commit(conn, ctx):
    check_consistency(ctx.state)
    save_game(conn, ctx.state, ctx.events, ctx.messages)


def cmd_new(args):
    conn = connect(args.db)
    cdb = cards_db()
    with conn:
        cur = conn.execute("INSERT INTO games (created_at, state_json) VALUES (?, ?)", (now_iso(), "{}"))
        game_id = cur.lastrowid
    state = new_game_state(args.seed, args.players, args.max_turns, args.include_drafts, cdb)
    state["game_id"] = game_id
    if getattr(args, "deck_floor", None) is not None:
        state["deck_floor"] = int(args.deck_floor)
    if getattr(args, "tokens", None):
        toks = [t.strip() for t in str(args.tokens).split(",") if t.strip()]
        if len(toks) != args.players + 1:
            raise ValidationError([f"--tokens needs {args.players + 1} comma-separated values: one per seat plus the referee"])
        state["tokens"] = {**{str(i): toks[i] for i in range(args.players)}, "referee": toks[args.players]}
    ctx = Ctx(state, cdb)
    ctx.log("game_start", f"Game {game_id} starts: seed={args.seed} players={args.players} max_turns={args.max_turns}"
            + (f" deck_floor={state['deck_floor']}" if state.get("deck_floor") is not None else ""),
            data={"seed": args.seed, "players_n": args.players, "max_turns": args.max_turns,
                  "deck_floor": state.get("deck_floor")})
    ctx.log("turn_start", f"Turn 1: {player_label(state, 0)}", actor=0)
    check_consistency(state)
    save_game(conn, state, ctx.events, ctx.messages)
    players_out = []
    for p in state["players"]:
        char = cdb.get(p["character"])
        players_out.append({"seat": p["seat"], "faction": p["faction"], "character": char["name"], "first": p["first"]})
    return {"ok": True, "game": game_id, "players": players_out, "deck_n": len(state["deck"]), "lanes": bool(state.get("tokens"))}


def cmd_list(args):
    conn = connect(args.db)
    rows = conn.execute("SELECT id, state_json FROM games ORDER BY id").fetchall()
    out = []
    for gid, sj in rows:
        st = json.loads(sj)
        out.append({"game": gid, "status": st["status"], "turn": st["turn"], "phase": st["phase"], "result": st["result"]})
    return {"ok": True, "games": out}


def cmd_status(args):
    conn = connect(args.db)
    state = load_game(conn, args.game)
    return {"ok": True, **build_status(state)}


def cmd_view(args):
    conn = connect(args.db)
    cdb = cards_db()
    state = load_game(conn, args.game)
    require_token(state, args.seat, getattr(args, "token", None))
    rows = conn.execute(
        "SELECT turn, text, notes FROM events WHERE game_id = ? ORDER BY seq", (args.game,)
    ).fetchall()
    this_turn = [r[1] for r in rows if r[0] == state["turn"]]
    recent = [r[1] for r in rows]
    view = build_player_view(cdb, state, this_turn, recent, args.seat)
    return {"ok": True, "view": view}


def cmd_pending(args):
    conn = connect(args.db)
    cdb = cards_db()
    state = load_game(conn, args.game)
    require_token(state, "referee", getattr(args, "token", None))
    pv = build_pending_view(cdb, state)
    if pv is None:
        raise ValidationError(["no open transaction"])
    return {"ok": True, "pending": pv}


def cmd_public(args):
    conn = connect(args.db)
    cdb = cards_db()
    state = load_game(conn, args.game)
    if args.all:
        require_token(state, "referee", getattr(args, "token", None))
    return {"ok": True, "public": build_public_view(cdb, state, all_=args.all)}


def cmd_plan(args):
    conn = connect(args.db)
    payload = read_payload(args.file)
    ctx = make_ctx(conn, args.game)
    require_token(ctx.state, args.seat, getattr(args, "token", None))
    ctx.message("plan", args.seat, payload)
    start_plan(ctx, args.seat, payload)
    commit(conn, ctx)
    return {"ok": True, "executed": ctx.executed_texts, "status": build_status(ctx.state)}


def cmd_react(args):
    conn = connect(args.db)
    payload = read_payload(args.file)
    ctx = make_ctx(conn, args.game)
    require_token(ctx.state, args.seat, getattr(args, "token", None))
    ctx.message("react", args.seat, payload)
    apply_reaction(ctx, args.seat, payload)
    commit(conn, ctx)
    return {"ok": True, "status": build_status(ctx.state)}


def cmd_resolve(args):
    conn = connect(args.db)
    payload = read_payload(args.file)
    ctx = make_ctx(conn, args.game)
    require_token(ctx.state, "referee", getattr(args, "token", None))
    ctx.message("resolve", None, payload)
    apply_resolve(
        ctx, payload.get("ops", []), result=payload.get("result"),
        uses_attack=payload.get("uses_attack", True), narrative=payload.get("narrative"),
        rulings=payload.get("rulings"), flags=payload.get("flags"),
    )
    commit(conn, ctx)
    return {"ok": True, "applied": ctx.executed_texts, "status": build_status(ctx.state)}


def cmd_log_cli(args):
    conn = connect(args.db)
    if args.as_json:
        # the JSON log carries event snapshots (hands included) — referee/analyst only
        require_token(load_game(conn, args.game), "referee", getattr(args, "token", None))
    return cmd_log(conn, args.game, args.tail, args.as_json)


def cmd_rules(args):
    with open(RULES_HTML_PATH, "r", encoding="utf-8") as f:
        html_text = f.read()
    print(strip_html_to_text(html_text), end="")


def cmd_card(args):
    cdb = cards_db()
    try:
        cid = int(args.ident)
        c = cdb.get(cid)
    except ValueError:
        cid = card_id_of(args.ident)
        c = cdb.get(cid)
    print(json.dumps(c, indent=2))


def cmd_export_cli(args):
    conn = connect(args.db)
    cdb = cards_db()
    return cmd_export(conn, cdb, game_id=args.game, all_=args.all)


def cmd_report_cli(args):
    conn = connect(args.db)
    cdb = cards_db()
    games = [int(x) for x in args.games.split(",")] if args.games else None
    return cmd_report(conn, cdb, game_ids=games, out_path=args.out)


def build_parser():
    ap = argparse.ArgumentParser(prog="sim.py", description="Bookkeeper CLI for Samurai vs Ninja LLM playtests.")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="path to the SQLite database")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("new", help="create a new game")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--players", type=int, default=4)
    p.add_argument("--max-turns", type=int, default=10)
    p.add_argument("--deck-floor", type=int, default=None,
                   help="end the game after the turn in which the deck falls to this many cards")
    p.add_argument("--include-drafts", action="store_true")
    p.add_argument("--tokens", default=None,
                   help="comma-separated lane tokens: one per seat plus the referee (enables --token checks)")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("list", help="list games")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("status", help="print status for a game")
    p.add_argument("--game", type=int, required=True)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("view", help="print a player's private view")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--seat", type=int, required=True)
    p.add_argument("--token", default=None, help="lane token of this seat / the referee (required when the game was created with --tokens)")
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("pending", help="print the open transaction for the referee")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--token", default=None, help="lane token of this seat / the referee (required when the game was created with --tokens)")
    p.set_defaults(func=cmd_pending)

    p = sub.add_parser("public", help="print public state")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--all", action="store_true")
    p.add_argument("--token", default=None, help="lane token of this seat / the referee (required when the game was created with --tokens)")
    p.set_defaults(func=cmd_public)

    p = sub.add_parser("plan", help="submit a plan")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--seat", type=int, required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--token", default=None, help="lane token of this seat / the referee (required when the game was created with --tokens)")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("react", help="submit a reaction")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--seat", type=int, required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--token", default=None, help="lane token of this seat / the referee (required when the game was created with --tokens)")
    p.set_defaults(func=cmd_react)

    p = sub.add_parser("resolve", help="submit referee ops for the open transaction")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--token", default=None, help="lane token of this seat / the referee (required when the game was created with --tokens)")
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser("rules", help="print the English rules as plain text")
    p.set_defaults(func=cmd_rules)

    p = sub.add_parser("card", help="print one card's JSON, by id or uid")
    p.add_argument("ident")
    p.set_defaults(func=cmd_card)

    p = sub.add_parser("log", help="print the human-readable event log")
    p.add_argument("--game", type=int, required=True)
    p.add_argument("--tail", type=int, default=None)
    p.add_argument("--json", action="store_true", dest="as_json")
    p.add_argument("--token", default=None, help="referee token (needed for --json when the game enforces lanes)")
    p.set_defaults(func=cmd_log_cli)

    p = sub.add_parser("export", help="export game history JSON for the viewer")
    p.add_argument("--game", type=int, default=None)
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_export_cli)

    p = sub.add_parser("report", help="write the aggregate markdown report")
    p.add_argument("--games", default=None, help="comma-separated game ids (default: all)")
    p.add_argument("--out", default=None)
    p.set_defaults(func=cmd_report_cli)

    return ap


TEXT_COMMANDS = {"rules", "log", "card"}


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = build_parser()
    args = ap.parse_args(argv)
    try:
        if args.command in TEXT_COMMANDS:
            args.func(args)
            return 0
        result = args.func(args)
        print(json.dumps(result))
        return 0
    except ValidationError as ve:
        print(json.dumps({"ok": False, "errors": ve.errors}))
        return 1
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
