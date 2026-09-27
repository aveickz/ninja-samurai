"""Unit tests for sim.py.

Run with:
    py -3 -m unittest simulations/engine/test_sim.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sim  # noqa: E402
import card_rules as cr  # noqa: E402

CDB = sim.cards_db()

# A few well-known card ids used across tests (verified against
# simulations/data/cards.json — see card_rules.py's header note).
KATANA = 1
ARMOR = 5104
HORSEMAN = 58
PARRY = 48
MAGATAMA = 118
SNAKEBITE = 93
BOKKEN = 4  # complexity1 dmg0 weapon, harmless for setup attacks
SHUKO = 2          # Ushiwaka's favourite weapon: complexity1 dmg1
KANABO = 3         # complexity1 dmg3
NAGINATA = 28      # complexity_any dmg2, not thrown
SHURIKEN = 32      # ranged dmg1 (thrown)
BEAR_TRAP = 43     # trap
KILLERS_MARK = 91  # effect
STITCHES = 107     # action
SEPPUKU = 108      # action
WAKIZASHI = 8      # weapon, may modify a Katana attack only


class SimTestCase(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        os.unlink(path)  # sqlite creates it fresh
        self.db_path = path
        self.conn = sim.connect(self.db_path)

    def tearDown(self):
        self.conn.close()
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    # -- helpers -------------------------------------------------------

    def new_game(self, seed=1, players=4, max_turns=10, include_drafts=False):
        cur = self.conn.execute("INSERT INTO games (created_at, state_json) VALUES (?, ?)", (sim.now_iso(), "{}"))
        gid = cur.lastrowid
        self.conn.commit()
        state = sim.new_game_state(seed, players, max_turns, include_drafts, CDB)
        state["game_id"] = gid
        ctx = sim.Ctx(state, CDB)
        ctx.log("game_start", f"Game {gid} starts", data={"seed": seed, "players_n": players, "max_turns": max_turns})
        ctx.log("turn_start", f"Turn 1: {sim.player_label(state, 0)}", actor=0)
        sim.check_consistency(state)
        sim.save_game(self.conn, state, ctx.events, ctx.messages)
        return gid

    def strip_reactivity(self, state, seats, keep=()):
        """Remove intervention/defense-capable cards from the given seats'
        hands, for deterministic reactor pruning in tests."""
        keep = set(keep)
        for seat in seats:
            p = sim.find_player(state, seat)
            for uid in list(p["hand"]):
                if uid in keep:
                    continue
                c = sim.card_of(CDB, uid)
                if ("intervention" in c["types"] or "defense" in c["types"]
                        or "as an Intervention" in (c.get("text") or "")
                        or "{Polearm}" in (c.get("text") or "")):
                    sim.move_uid(state, uid, "discard")

    def avoid_hanzo(self, state, seat):
        """Hanzo can always block with any weapon in hand, so a 'nothing to
        defend with' test must not land on him."""
        p = sim.find_player(state, seat)
        if p["character"] == cr.HANZO_CHARACTER_ID:
            safe = CDB.get(cr.MANASE_CHARACTER_ID)
            p["character"] = safe["id"]
            p["hp"] = safe["hp"]
            p["max_hp"] = safe["hp"]

    def avoid_reactive_characters(self, state):
        """Hanzo (blocks with any weapon) and Norio (blocks with a Polearm)
        can become reactors purely from their character text; swap them out
        table-wide for a fully deterministic 'nobody can react' test."""
        for p in state["players"]:
            if p["character"] in (cr.HANZO_CHARACTER_ID, cr.NORIO_CHARACTER_ID):
                safe = CDB.get(cr.MANASE_CHARACTER_ID)
                p["character"] = safe["id"]
                p["hp"] = safe["hp"]
                p["max_hp"] = safe["hp"]

    def load(self, gid):
        return sim.load_game(self.conn, gid)

    def give(self, state, seat, card_id):
        """Force a copy of `card_id` into seat's hand, from wherever it is."""
        uid = None
        for u in state["deck"]:
            if sim.card_id_of(u) == card_id:
                uid = u
                break
        if uid is None:
            for u in state["_all_uids"]:
                if sim.card_id_of(u) == card_id:
                    uid = u
                    break
        self.assertIsNotNone(uid, f"no card with id {card_id} exists")
        sim.move_uid(state, uid, "hand", seat=seat)
        return uid

    def ctx(self, state):
        return sim.Ctx(state, CDB)

    def save(self, ctx):
        sim.check_consistency(ctx.state)
        sim.save_game(self.conn, ctx.state, ctx.events, ctx.messages)

    # -- game creation ---------------------------------------------------

    def test_new_game_deals_and_stats(self):
        gid = self.new_game(seed=1, players=4, max_turns=10)
        state = self.load(gid)
        self.assertEqual(state["players_n"], 4)
        self.assertEqual(len(state["players"]), 4)
        for p in state["players"]:
            self.assertEqual(len(p["hand"]), sim.STARTING_HAND)
            self.assertEqual(p["vp"], sim.STARTING_VP)
            char = CDB.get(p["character"])
            self.assertEqual(p["hp"], char["hp"])
            self.assertEqual(p["max_hp"], char["hp"])
        self.assertEqual(state["players"][0]["faction"], "samurai")
        self.assertEqual(state["players"][1]["faction"], "ninja")
        self.assertTrue(state["players"][0]["first"])

        deck_eligible = 0
        for c in CDB.by_id.values():
            if c["group"] in ("role", "character"):
                continue
            tags = c.get("tags") or []
            if "trash" in tags or "draft" in tags:
                continue
            deck_eligible += c["qty"]
        self.assertEqual(len(state["deck"]), deck_eligible - 4 * sim.STARTING_HAND)

    def test_same_seed_identical_deck_order(self):
        s1 = sim.new_game_state(42, 4, 10, False, CDB)
        s2 = sim.new_game_state(42, 4, 10, False, CDB)
        self.assertEqual(s1["deck"], s2["deck"])
        self.assertEqual([p["character"] for p in s1["players"]], [p["character"] for p in s2["players"]])
        self.assertEqual([p["hand"] for p in s1["players"]], [p["hand"] for p in s2["players"]])

    # -- plan validation ---------------------------------------------------

    def test_validate_rejects_card_not_in_hand(self):
        gid = self.new_game(seed=2)
        state = self.load(gid)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": "c9999-1", "target": 1}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

    def test_validate_rejects_attack_on_dead_or_self(self):
        gid = self.new_game(seed=3)
        state = self.load(gid)
        uid = self.give(state, 0, KATANA)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": uid, "target": 0}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

        state["players"][1]["alive"] = False
        plan2 = {"steps": [{"do": "attack", "mode": "main", "card": uid, "target": 1}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan2)

    def test_validate_rejects_third_attack(self):
        gid = self.new_game(seed=4)
        state = self.load(gid)
        plan = {"steps": [
            {"do": "attack", "mode": "bare", "target": 1},
            {"do": "attack", "mode": "bare", "target": 2},
            {"do": "attack", "mode": "bare", "target": 3},
        ]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

    def test_validate_rejects_complexity_mismatch(self):
        gid = self.new_game(seed=5)
        state = self.load(gid)
        uid = self.give(state, 0, KATANA)  # complexity1
        armor_uid = self.give(state, 1, ARMOR)
        state["players"][1]["effects"].append(armor_uid)
        # target complexity is now 2; Katana only handles 1
        plan = {"steps": [{"do": "attack", "mode": "main", "card": uid, "target": 1}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

    # -- full attack loop --------------------------------------------------

    def test_full_attack_loop_with_defense_and_draws(self):
        gid = self.new_game(seed=6, players=4, max_turns=10)
        state = self.load(gid)
        weapon = self.give(state, 0, KATANA)
        parry_uid = self.give(state, 1, PARRY)
        self.strip_reactivity(state, [1], keep=[parry_uid])
        self.strip_reactivity(state, [2, 3])
        hand_before = {p["seat"]: len(p["hand"]) for p in state["players"]}

        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        st = sim.build_status(ctx.state)
        self.assertEqual(st["phase"], "react")
        self.assertIn(1, st["reactors"])

        sim.apply_reaction(ctx, 1, {"action": "defend", "cards": [parry_uid], "trap": None})
        st = sim.build_status(ctx.state)
        self.assertEqual(st["phase"], "resolve")

        sim.apply_resolve(ctx, [{"op": "note", "text": "blocked"}], uses_attack=True)
        st = sim.build_status(ctx.state)
        self.assertEqual(st["phase"], "plan")
        self.assertEqual(st["seat"], 1)
        self.assertEqual(ctx.state["turn"], 2)

        p0 = sim.find_player(ctx.state, 0)
        self.assertEqual(p0["attacks_used"], 1)
        # active player (seat 0) drew 3, opposing team (seats 1, 3) drew 1 each
        self.assertEqual(len(p0["hand"]), hand_before[0] - 1 + 3)
        p1 = sim.find_player(ctx.state, 1)
        p3 = sim.find_player(ctx.state, 3)
        self.assertEqual(len(p1["hand"]), hand_before[1] - 1 + 1)  # -Parry (blocked, discarded) +1 opposing draw
        self.assertEqual(len(p3["hand"]), hand_before[3] + 1)
        self.save(ctx)

    def test_auto_take_when_defender_has_nothing(self):
        gid = self.new_game(seed=7)
        state = self.load(gid)
        weapon = self.give(state, 0, BOKKEN)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        st = sim.build_status(ctx.state)
        self.assertEqual(st["phase"], "resolve")
        self.assertEqual(ctx.state["pending"]["reactions"]["1"]["action"], "take")

    # -- death / VP ----------------------------------------------------

    def test_death_vp_transfer_to_enemy_killer(self):
        gid = self.new_game(seed=8)
        state = self.load(gid)
        state["players"][1]["hp"] = 1
        ctx = self.ctx(state)
        sim.apply_op(ctx, {"op": "damage", "seat": 1, "n": 5, "source": "attack", "by": 0})
        p0 = sim.find_player(ctx.state, 0)
        p1 = sim.find_player(ctx.state, 1)
        self.assertFalse(p1["alive"])
        self.assertEqual(p1["vp"], sim.STARTING_VP - 1)
        self.assertEqual(p0["vp"], sim.STARTING_VP + 1)

    def test_death_ally_kill_goes_to_discard(self):
        gid = self.new_game(seed=9)
        state = self.load(gid)
        state["players"][1]["hp"] = 1
        ctx = self.ctx(state)
        # seat 3 is on the same faction as seat 1 (ninja) with 4 players (0,2 samurai / 1,3 ninja)
        sim.apply_op(ctx, {"op": "damage", "seat": 1, "n": 5, "source": "attack", "by": 3})
        p1 = sim.find_player(ctx.state, 1)
        p3 = sim.find_player(ctx.state, 3)
        self.assertFalse(p1["alive"])
        self.assertEqual(p1["vp"], sim.STARTING_VP - 1)
        self.assertEqual(p3["vp"], sim.STARTING_VP)  # no point for an ally kill

    def test_death_by_poison_goes_to_discard(self):
        gid = self.new_game(seed=10)
        state = self.load(gid)
        state["players"][1]["hp"] = 1
        ctx = self.ctx(state)
        sim.apply_op(ctx, {"op": "damage", "seat": 1, "n": 5, "source": "poison", "by": 0})
        p0 = sim.find_player(ctx.state, 0)
        p1 = sim.find_player(ctx.state, 1)
        self.assertFalse(p1["alive"])
        self.assertTrue(p1["poison_death"])
        self.assertFalse(p1["needs_recovery"])
        self.assertEqual(p0["vp"], sim.STARTING_VP)  # poison never awards a point

    # -- poison tick / revival --------------------------------------------

    def test_poison_tick_at_end_of_turn(self):
        gid = self.new_game(seed=11)
        state = self.load(gid)
        state["players"][0]["poisoned"] = True
        state["players"][0]["hp"] = state["players"][0]["max_hp"]
        ctx = self.ctx(state)
        sim.end_of_turn(ctx)
        p0 = sim.find_player(ctx.state, 0)
        self.assertEqual(p0["hp"], p0["max_hp"] - cr.POISON_TICK_BASE)

    def test_revival_at_next_turn(self):
        gid = self.new_game(seed=12)
        state = self.load(gid)
        state["players"][1]["hp"] = 1
        ctx = self.ctx(state)
        sim.apply_op(ctx, {"op": "damage", "seat": 1, "n": 5, "source": "attack", "by": 0})
        p1 = sim.find_player(ctx.state, 1)
        self.assertFalse(p1["alive"])
        died_turn = p1["died_turn"]
        # advance turns until seat 1's died_turn < current turn and a turn boundary is crossed
        ctx.state["active"] = 0
        sim.advance_turn(ctx)  # -> seat 1 becomes active; died_turn(1) < turn(2) so they should revive
        p1 = sim.find_player(ctx.state, 1)
        self.assertTrue(p1["alive"])
        self.assertEqual(p1["hp"], p1["max_hp"])
        self.assertTrue(p1["needs_recovery"])

    # -- deck exhaustion / max turns ---------------------------------------

    def test_deck_exhaustion_sets_final_turn_and_ends_game(self):
        gid = self.new_game(seed=13, max_turns=999)
        state = self.load(gid)
        state["deck"] = state["deck"][:1]  # only one card left
        ctx = self.ctx(state)
        sim.end_of_turn(ctx)
        self.assertEqual(ctx.state["final_turn"], 1)
        self.assertEqual(ctx.state["status"], "over")
        self.assertEqual(ctx.state["result"]["reason"], "deck_empty")

    def test_max_turns_end_with_magatama_scoring(self):
        gid = self.new_game(seed=14, max_turns=1)
        state = self.load(gid)
        self.give(state, 0, MAGATAMA)
        ctx = self.ctx(state)
        sim.end_of_turn(ctx)
        self.assertEqual(ctx.state["status"], "over")
        self.assertEqual(ctx.state["result"]["reason"], "turn_cap")
        expected_samurai = sim.STARTING_VP * 2 + 1  # seats 0 and 2, +1 Magatama in seat 0's hand
        self.assertEqual(ctx.state["result"]["score"]["samurai"], expected_samurai)

    # -- reject --------------------------------------------------------

    def test_reject_returns_cards_and_leaves_attacks_used(self):
        gid = self.new_game(seed=15)
        state = self.load(gid)
        weapon = self.give(state, 0, BOKKEN)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        self.assertEqual(sim.build_status(ctx.state)["phase"], "resolve")
        sim.apply_resolve(ctx, [{"op": "reject", "reason": "misdeclared target"}])
        p0 = sim.find_player(ctx.state, 0)
        self.assertIn(weapon, p0["hand"])
        self.assertEqual(p0["attacks_used"], 0)

    # -- ops all-or-nothing --------------------------------------------

    def test_ops_all_or_nothing(self):
        gid = self.new_game(seed=16)
        state = self.load(gid)
        weapon = self.give(state, 0, BOKKEN)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        hp_before = sim.find_player(ctx.state, 1)["hp"]
        bad_ops = [
            {"op": "damage", "seat": 1, "n": 1, "source": "attack", "by": 0},
            {"op": "move", "uid": weapon, "to": "charges", "seat": 1},  # seat 1 has no aura -> raises at apply time
        ]
        with self.assertRaises(sim.ValidationError):
            sim.apply_resolve(ctx, bad_ops)
        self.assertEqual(sim.find_player(ctx.state, 1)["hp"], hp_before)
        self.assertEqual(sim.build_status(ctx.state)["phase"], "resolve")

    # -- export ----------------------------------------------------------

    def test_export_produces_valid_history_with_state_snapshots(self):
        gid = self.new_game(seed=17)
        out_dir = tempfile.mkdtemp()
        result = sim.cmd_export(self.conn, CDB, game_id=gid, out_dir=out_dir)
        self.assertTrue(result["ok"])
        path = Path(out_dir) / f"game_{gid}.json"
        self.assertTrue(path.exists())
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        self.assertIn("game", doc)
        self.assertIn("cards", doc)
        self.assertIn("events", doc)
        self.assertGreater(len(doc["events"]), 0)
        for e in doc["events"]:
            self.assertIn("state", e)
            self.assertIsInstance(e["state"], dict)
            self.assertIn("players", e["state"])

    # -- code review fixes ------------------------------------------------

    def test_replan_after_batch_discards_remaining_steps(self):
        gid = self.new_game(seed=101)
        state = self.load(gid)
        c1 = self.give(state, 0, PARRY)
        c2 = self.give(state, 0, PARRY)
        ctx = self.ctx(state)
        plan = {"steps": [
            {"do": "ability", "source": "character", "choice": "draw 2 cards", "target": None},
            {"do": "replan"},
            {"do": "trade", "discard": [c1, c2]},
        ]}
        sim.start_plan(ctx, 0, plan)
        st = sim.build_status(ctx.state)
        self.assertEqual(st["phase"], "resolve")  # the ability step's batch awaits the referee

        sim.apply_resolve(ctx, [{"op": "draw", "seat": 0, "n": 2}], uses_attack=False)
        st = sim.build_status(ctx.state)
        self.assertEqual(st["phase"], "plan")
        self.assertEqual(st["seat"], 0)
        self.assertTrue(st.get("continuing"))
        p0 = sim.find_player(ctx.state, 0)
        # the trade step (after `replan`) must never have executed
        self.assertIn(c1, p0["hand"])
        self.assertIn(c2, p0["hand"])

    def test_ketsuban_reaction_eligibility_checks_targets_stance(self):
        gid = self.new_game(seed=102)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [0, 1, 2, 3])
        # seats: 0,2 samurai; 1,3 ninja; attacker=0, target=1, target's ally=3.
        self.assertEqual(sim.eligible_interveners(CDB, state, 0, 1), [])

        # Ketsuban on the wrong holder (the ally, not the target) changes nothing.
        state["players"][3]["stance"] = "c1164-1"
        self.assertEqual(sim.eligible_interveners(CDB, state, 0, 1), [])
        state["players"][3]["stance"] = None

        # Ketsuban on the target makes their living ally eligible to share wounds.
        state["players"][1]["stance"] = "c1164-1"
        self.assertEqual(sim.eligible_interveners(CDB, state, 0, 1), [3])

    def test_reaction_enabling_auras_require_targets_team(self):
        gid = self.new_game(seed=103)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [0, 1, 2, 3])
        # attacker=0 (samurai), target=1 (ninja); seat 2 is the ATTACKER's own
        # teammate, unrelated to the target -> must not become eligible.
        state["players"][2]["aura"] = {"uid": "c1207-1", "charges": [], "in_front_of": 2}
        self.assertEqual(sim.eligible_interveners(CDB, state, 0, 1), [])
        state["players"][2]["aura"] = None

        # Oath on the TARGET's own team (seat 3, target's ally) does make them eligible.
        state["players"][3]["aura"] = {"uid": "c1207-1", "charges": [], "in_front_of": 3}
        self.assertEqual(sim.eligible_interveners(CDB, state, 0, 1), [3])

    def test_bare_hand_attack_always_costs_two_attempts(self):
        gid = self.new_game(seed=104)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "bare", "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        self.assertEqual(sim.build_status(ctx.state)["phase"], "resolve")
        sim.apply_resolve(ctx, [{"op": "note", "text": "whiff"}], result="miss", uses_attack=False)
        p0 = sim.find_player(ctx.state, 0)
        self.assertEqual(p0["attacks_used"], 2)

    def test_dust_in_the_eyes_blocks_thrown_and_high_complexity(self):
        gid = self.new_game(seed=105)
        state = self.load(gid)
        dust_uid = self.give(state, 0, cr.DUST_IN_EYES_EFFECT_ID)
        state["players"][0]["hand"].remove(dust_uid)
        state["players"][0]["effects"].append(dust_uid)

        shuriken = self.give(state, 0, SHURIKEN)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": shuriken, "target": 1}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

        # a non-thrown weapon that handles ANY complexity would otherwise be
        # legal against a complexity-2 target; Dust in the Eyes still forbids it.
        naginata = self.give(state, 0, NAGINATA)
        armor_uid = self.give(state, 1, ARMOR)
        state["players"][1]["effects"].append(armor_uid)
        plan2 = {"steps": [{"do": "attack", "mode": "main", "card": naginata, "target": 1}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan2)

    def test_smoke_veil_and_sentry_block_ranged_attacks(self):
        gid = self.new_game(seed=106)
        state = self.load(gid)
        shuriken = self.give(state, 0, SHURIKEN)

        state["players"][1]["aura"] = {"uid": "c1206-1", "charges": [], "in_front_of": 1}
        plan = {"steps": [{"do": "attack", "mode": "main", "card": shuriken, "target": 1}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)
        state["players"][1]["aura"] = None

        state["players"][0]["aura"] = {"uid": "c1209-1", "charges": [], "in_front_of": 0}
        plan2 = {"steps": [{"do": "attack", "mode": "main", "card": shuriken, "target": 1}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan2)

    def test_transaction_closed_and_end_turn_poison_events_logged(self):
        gid = self.new_game(seed=107)
        state = self.load(gid)
        weapon = self.give(state, 0, BOKKEN)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        sim.apply_resolve(ctx, [{"op": "note", "text": "whiff"}])
        kinds = [e["kind"] for e in ctx.events]
        self.assertIn("transaction_closed", kinds)

        gid2 = self.new_game(seed=108)
        state2 = self.load(gid2)
        state2["players"][0]["poisoned"] = True
        ctx2 = self.ctx(state2)
        sim.end_of_turn(ctx2)
        kinds2 = [e["kind"] for e in ctx2.events]
        self.assertIn("end_turn_poison", kinds2)
        self.assertNotIn("poison", kinds2)

    def test_second_attack_on_dead_target_is_skipped(self):
        gid = self.new_game(seed=109)
        state = self.load(gid)
        w1 = self.give(state, 0, KATANA)
        w2 = self.give(state, 0, BOKKEN)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        state["players"][1]["hp"] = 1
        ctx = self.ctx(state)
        plan = {"steps": [
            {"do": "attack", "mode": "main", "card": w1, "target": 1},
            {"do": "attack", "mode": "main", "card": w2, "target": 1},
        ]}
        sim.start_plan(ctx, 0, plan)
        self.assertEqual(sim.build_status(ctx.state)["phase"], "resolve")
        sim.apply_resolve(ctx, [{"op": "damage", "seat": 1, "n": 5, "source": "attack", "by": 0}])
        kinds = [e["kind"] for e in ctx.events]
        self.assertIn("death", kinds)     # the first attack did kill them
        self.assertIn("step_skipped", kinds)  # the second attack step was skipped, not executed
        # only ONE attack transaction ever opened (never a second one against the corpse)
        self.assertEqual(kinds.count("attack_declared"), 1)
        # no transaction left dangling
        self.assertIsNone(ctx.state.get("pending"))

    def test_undefendable_attack_offers_no_defend_reaction(self):
        gid = self.new_game(seed=110)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        state["players"][0]["character"] = cr.USHIWAKA_CHARACTER_ID
        ushiwaka = CDB.get(cr.USHIWAKA_CHARACTER_ID)
        state["players"][0]["hp"] = ushiwaka["hp"]
        state["players"][0]["max_hp"] = ushiwaka["hp"]
        shuko = self.give(state, 0, SHUKO)  # Ushiwaka's favourite weapon -> undefendable
        self.strip_reactivity(state, [1, 2, 3])
        self.give(state, 1, PARRY)          # target holds a Defense card
        self.give(state, 3, PARRY)          # target's teammate too (partial-absorption path)
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": shuko, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        self.assertEqual(ctx.state["pending"]["reactions"]["1"]["action"], "take")
        self.assertNotIn(1, ctx.state["pending"]["reactors_all"])
        self.assertNotIn(3, ctx.state["pending"]["reactors_all"])

    def test_lotus_heals_on_play(self):
        gid = self.new_game(seed=111)
        state = self.load(gid)
        state["players"][0]["max_hp"] = 10
        state["players"][0]["hp"] = 2
        lotus_uid = self.give(state, 0, sim.LOTUS_STANCE_ID)
        ctx = self.ctx(state)
        sim.start_plan(ctx, 0, {"steps": [{"do": "stance", "card": lotus_uid}]})
        p0 = sim.find_player(ctx.state, 0)
        self.assertEqual(p0["hp"], 4)

    def test_barrel_of_stench_poisons_bearer_on_play(self):
        gid = self.new_game(seed=112)
        state = self.load(gid)
        state["players"][0]["hp"] = state["players"][0]["max_hp"]
        aura_uid = self.give(state, 0, cr.BARREL_OF_STENCH_AURA_ID)
        ctx = self.ctx(state)
        sim.start_plan(ctx, 0, {"steps": [{"do": "aura", "card": aura_uid}]})
        p0 = sim.find_player(ctx.state, 0)
        self.assertTrue(p0["poisoned"])

    def test_effect_step_rejects_shadow_target(self):
        gid = self.new_game(seed=113)
        state = self.load(gid)
        shadow_uid = self.give(state, 1, cr.SHADOW_STANCE_ID)
        state["players"][1]["hand"].remove(shadow_uid)
        state["players"][1]["stance"] = shadow_uid
        killers_mark = self.give(state, 0, KILLERS_MARK)
        plan = {"steps": [{"do": "effect", "card": killers_mark, "target": 1}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

    def test_trade_rejects_two_unrelated_action_cards(self):
        gid = self.new_game(seed=114)
        state = self.load(gid)
        stitches = self.give(state, 0, STITCHES)
        seppuku = self.give(state, 0, SEPPUKU)
        plan = {"steps": [{"do": "trade", "discard": [stitches, seppuku]}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

    def test_wakizashi_modifier_requires_katana(self):
        gid = self.new_game(seed=115)
        state = self.load(gid)
        kanabo = self.give(state, 0, KANABO)
        wakizashi = self.give(state, 0, WAKIZASHI)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": kanabo, "target": 1, "modifier": wakizashi}]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

    def test_recovery_declined_when_omitted_closes_window(self):
        gid = self.new_game(seed=116)
        state = self.load(gid)
        state["players"][0]["needs_recovery"] = True
        ctx = self.ctx(state)
        sim.start_plan(ctx, 0, {"steps": []})
        p0 = sim.find_player(ctx.state, 0)
        self.assertFalse(p0["needs_recovery"])

    def test_validate_plan_rejects_duplicate_effect_in_same_plan(self):
        gid = self.new_game(seed=117)
        state = self.load(gid)
        km1 = self.give(state, 0, KILLERS_MARK)
        km2 = self.give(state, 0, KILLERS_MARK)
        plan = {"steps": [
            {"do": "effect", "card": km1, "target": 1},
            {"do": "effect", "card": km2, "target": 1},
        ]}
        with self.assertRaises(sim.ValidationError):
            sim.validate_plan(CDB, state, 0, plan)

    def test_move_op_onto_occupied_slot_raises_validation_error(self):
        gid = self.new_game(seed=118)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        # seat 2 already has a trap set, but is NOT this attack's target (seat 3
        # is) — so it stays an uninvolved bystander and the attack goes
        # straight to resolve, letting us hit the referee's `move` op directly.
        old_trap_uid = self.give(state, 2, BEAR_TRAP)
        state["players"][2]["hand"].remove(old_trap_uid)
        state["players"][2]["trap"] = {"uid": old_trap_uid, "face_up": False}
        new_uid = self.give(state, 2, BOKKEN)  # a harmless card, not defense/intervention
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "bare", "target": 3}]}
        sim.start_plan(ctx, 0, plan)
        self.assertEqual(sim.build_status(ctx.state)["phase"], "resolve")
        with self.assertRaises(sim.ValidationError):
            sim.apply_resolve(ctx, [{"op": "move", "uid": new_uid, "to": "trap", "seat": 2, "face_up": False}])
        # no corruption: the old trap is still intact, nothing was rolled half-way
        self.assertEqual(sim.find_player(ctx.state, 2)["trap"]["uid"], old_trap_uid)

    def test_ops_after_game_over_are_skipped(self):
        gid = self.new_game(seed=119)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        state["players"][1]["vp"] = 4
        p2 = sim.find_player(state, 2)
        p2["hp"] = max(1, p2["max_hp"] - 3)
        hp_before = p2["hp"]
        weapon = self.give(state, 0, BOKKEN)
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        sim.apply_resolve(ctx, [
            {"op": "vp", "seat": 1, "delta": -4},
            {"op": "heal", "seat": 2, "n": 3},
        ])
        self.assertEqual(ctx.state["status"], "over")
        self.assertEqual(sim.find_player(ctx.state, 2)["hp"], hp_before)

    def test_resolve_rejected_while_reactors_still_pending(self):
        gid = self.new_game(seed=124)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        weapon = self.give(state, 0, BOKKEN)
        parry_uid = self.give(state, 1, PARRY)
        self.strip_reactivity(state, [1], keep=[parry_uid])
        # do NOT strip seat 3: leave them a real, undecided intervener.
        self.give(state, 3, PARRY)
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        pend = ctx.state["pending"]
        self.assertEqual(sim.build_status(ctx.state)["phase"], "react")
        self.assertTrue(pend["reactors_pending"])  # someone still owes a reaction

        hp_before = sim.find_player(ctx.state, 1)["hp"]
        with self.assertRaises(sim.ValidationError):
            sim.apply_resolve(ctx, [{"op": "damage", "seat": 1, "n": 2, "source": "attack", "by": 0}])
        # no state change: still react phase, hp untouched, pending intact
        self.assertEqual(sim.build_status(ctx.state)["phase"], "react")
        self.assertEqual(sim.find_player(ctx.state, 1)["hp"], hp_before)

    def test_read_payload_reports_bad_input_as_validation_error(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not valid json")
            with self.assertRaises(sim.ValidationError):
                sim.read_payload(path)
        finally:
            os.unlink(path)

        missing = os.path.join(tempfile.gettempdir(), "definitely_missing_file_xyz.json")
        with self.assertRaises(sim.ValidationError):
            sim.read_payload(missing)

    def test_negative_heal_rejected(self):
        gid = self.new_game(seed=120)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [1, 2, 3])
        weapon = self.give(state, 0, BOKKEN)
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        hp_before = sim.find_player(ctx.state, 0)["hp"]
        with self.assertRaises(sim.ValidationError):
            sim.apply_resolve(ctx, [{"op": "heal", "seat": 0, "n": -50}])
        self.assertEqual(sim.find_player(ctx.state, 0)["hp"], hp_before)

    def test_set_hp_logs_correct_kind_and_clamps(self):
        gid = self.new_game(seed=121)
        state = self.load(gid)
        p1 = sim.find_player(state, 1)
        p1["hp"] = 5
        ctx = self.ctx(state)
        sim.apply_op(ctx, {"op": "set_hp", "seat": 1, "hp": 1})
        self.assertEqual(ctx.events[-1]["kind"], "damage")
        self.assertEqual(sim.find_player(ctx.state, 1)["hp"], 1)

        p2 = sim.find_player(ctx.state, 2)
        over = p2["max_hp"] + 500
        sim.apply_op(ctx, {"op": "set_hp", "seat": 2, "hp": over})
        self.assertEqual(sim.find_player(ctx.state, 2)["hp"], p2["max_hp"])

    def test_kill_op_zeroes_hp(self):
        gid = self.new_game(seed=122)
        state = self.load(gid)
        ctx = self.ctx(state)
        sim.apply_op(ctx, {"op": "kill", "seat": 1, "by": 0})
        p1 = sim.find_player(ctx.state, 1)
        self.assertFalse(p1["alive"])
        self.assertEqual(p1["hp"], 0)

    def test_dead_seat_cannot_react(self):
        gid = self.new_game(seed=123)
        state = self.load(gid)
        self.avoid_reactive_characters(state)
        self.strip_reactivity(state, [2, 3])
        weapon = self.give(state, 0, BOKKEN)
        self.give(state, 1, PARRY)
        ctx = self.ctx(state)
        plan = {"steps": [{"do": "attack", "mode": "main", "card": weapon, "target": 1}]}
        sim.start_plan(ctx, 0, plan)
        pend = ctx.state["pending"]
        self.assertIn(1, pend["reactors_pending"])
        sim.find_player(ctx.state, 1)["alive"] = False
        with self.assertRaises(sim.ValidationError):
            sim.apply_reaction(ctx, 1, {"action": "take"})


if __name__ == "__main__":
    unittest.main()
