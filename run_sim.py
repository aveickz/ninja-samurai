#!/usr/bin/env python3
"""Simple game driver to play out a simulation until 100 cards remain."""

import subprocess
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
GAME_ID = 16

def run_sim(cmd):
    """Run a sim.py command and return the JSON result."""
    result = subprocess.run(
        ["py", "-3", str(REPO_ROOT / "simulations/engine/sim.py")] + cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT)
    )
    if result.returncode != 0:
        print(f"Error running {cmd}: {result.stderr}", file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON: {result.stdout}", file=sys.stderr)
        return None

def make_simple_plan(view):
    """Create a minimal valid plan (mostly pass with basic attacks if available)."""
    plan = {
        "discard_to_limit": [],
        "recovery": {"discard": []},
        "steps": [],
        "end_turn": {},
        "notes": "Simple turn"
    }

    # Handle required discards
    if view.get("you", {}).get("hand_limit_excess", 0) > 0:
        hand = view.get("you", {}).get("hand", [])
        discard_count = view["you"]["hand_limit_excess"]
        plan["discard_to_limit"] = [c["uid"] for c in hand[:discard_count]]

    # Handle recovery
    if view.get("you", {}).get("needs_recovery", False):
        plan["recovery"]["discard"] = []

    # Very simple attack logic: if we have a weapon and can attack, try to hit an alive enemy
    hand = view.get("you", {}).get("hand", [])
    weapons = [c for c in hand if "weapon" in c.get("types", [])]
    enemies = [p for i, p in enumerate(view.get("players", []))
               if i != view.get("seat") and (view.get("you", {}).get("faction") != p.get("faction")) and p.get("alive")]

    if weapons and enemies and view.get("you", {}).get("attacks_left", 0) > 0:
        weapon = weapons[0]
        target = enemies[0]["seat"]
        reach = weapon.get("reach", [0, 1, 2, 3])
        if target in reach:
            plan["steps"].append({
                "do": "attack",
                "card": weapon["uid"],
                "mode": "main",
                "target": target,
                "modifier": None,
                "why": "attack"
            })

    return plan

def save_and_submit_plan(game_id, seat, plan):
    """Save plan to inbox and submit it."""
    inbox_dir = REPO_ROOT / "simulations/games/inbox"
    inbox_dir.mkdir(exist_ok=True)
    plan_path = inbox_dir / f"g{game_id}_s{seat}_plan.json"

    with open(plan_path, "w") as f:
        json.dump(plan, f)

    result = run_sim([
        "plan", "--game", str(game_id), "--seat", str(seat),
        "--file", str(plan_path)
    ])
    return result

def main():
    turn = 0
    max_turns = 50

    while turn < max_turns:
        # Get current status
        status = run_sim(["status", "--game", str(GAME_ID)])
        if not status or status.get("over"):
            print(f"Game ended. Status: {status}")
            break

        deck_n = status.get("deck_n", 0)
        print(f"Turn {status.get('turn', '?')}, Deck: {deck_n} cards", file=sys.stderr)

        if deck_n <= 100:
            print(f"Target reached: {deck_n} cards <= 100", file=sys.stderr)
            break

        # Check current phase
        phase = status.get("phase")
        seat = status.get("seat")

        if phase == "plan":
            # Get player view
            view = run_sim(["view", "--game", str(GAME_ID), "--seat", str(seat)])
            if not view or not view.get("ok"):
                print(f"Failed to get view for seat {seat}: {view}", file=sys.stderr)
                break

            # Make and submit plan
            plan = make_simple_plan(view)
            result = save_and_submit_plan(GAME_ID, seat, plan)
            if not result or not result.get("ok"):
                print(f"Plan rejected: {result}", file=sys.stderr)
                break
            print(f"Seat {seat} played", file=sys.stderr)

        elif phase == "react":
            # Get pending transaction
            pending = run_sim(["pending", "--game", str(GAME_ID)])
            if not pending or not pending.get("ok"):
                print(f"Failed to get pending: {pending}", file=sys.stderr)
                break

            reactors = pending.get("reactors", [])
            for reactor_seat in reactors:
                # Simple reaction: always defend or pass
                reaction = {
                    "action": "pass",
                    "notes": "auto-pass"
                }
                # Could add more logic here for smart reactions
                # For now just pass for everyone

        elif phase == "resolve":
            # Referee resolves - we would need to call referee agent here
            # For now, skip
            print("In resolve phase - would need referee agent", file=sys.stderr)
            break

        turn += 1

    # Export the game
    print("Exporting game...", file=sys.stderr)
    export = run_sim(["export", "--game", str(GAME_ID)])
    if export and export.get("ok"):
        print("Game exported", file=sys.stderr)

    # Log the game
    log = run_sim(["log", "--game", str(GAME_ID)])
    if log:
        print("Game log retrieved", file=sys.stderr)

if __name__ == "__main__":
    main()
