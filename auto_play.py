#!/usr/bin/env python3
"""Automatically play game 16 until 100 cards remain."""

import subprocess
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
GAME_ID = 17
TARGET_DECK = 100

def run_sim(cmd):
    """Run a sim.py command and return the JSON result."""
    result = subprocess.run(
        ["py", "-3", str(REPO_ROOT / "simulations/engine/sim.py")] + cmd,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT)
    )
    try:
        return json.loads(result.stdout)
    except:
        if result.returncode != 0:
            print(f"Error: {result.stderr[:200]}", file=sys.stderr)
        return {"ok": False}

def simple_plan(view):
    """Create a simple passing turn with minimal action."""
    plan = {
        "discard_to_limit": [],
        "steps": [],
        "end_turn": {},
        "notes": "Pass turn"
    }

    # Handle hand limit
    excess = view.get("you", {}).get("hand_limit_excess", 0)
    if excess > 0:
        hand = view.get("you", {}).get("hand", [])
        # Discard the first N cards to reduce hand size
        plan["discard_to_limit"] = [c["uid"] for c in hand[:excess]]

    # Only include recovery if needed
    if view.get("you", {}).get("needs_recovery", False):
        plan["recovery"] = {"discard": []}

    return plan

def submit_plan(seat, plan):
    """Submit a plan."""
    inbox_dir = REPO_ROOT / "simulations/games/inbox"
    inbox_dir.mkdir(exist_ok=True)
    plan_path = inbox_dir / f"g{GAME_ID}_s{seat}_plan.json"

    with open(plan_path, "w") as f:
        json.dump(plan, f)

    return run_sim([
        "plan", "--game", str(GAME_ID), "--seat", str(seat),
        "--file", str(plan_path)
    ])

def main():
    turn_num = 0
    max_total_turns = 200  # safety limit

    while turn_num < max_total_turns:
        # Get status
        status = run_sim(["status", "--game", str(GAME_ID)])

        if not status.get("ok"):
            print(f"Status failed: {status}", file=sys.stderr)
            break

        if status.get("over"):
            print(f"Game over at turn {status.get('turn')}", file=sys.stderr)
            break

        deck_n = status.get("deck_n", 999)
        print(f"T{status.get('turn')} Deck:{deck_n} Phase:{status.get('phase')} Seat:{status.get('seat')}", file=sys.stderr)

        if deck_n <= TARGET_DECK:
            print(f"Target reached: {deck_n} <= {TARGET_DECK}", file=sys.stderr)
            break

        phase = status.get("phase")

        if phase == "plan":
            seat = status.get("seat")

            # Get view
            view_resp = run_sim(["view", "--game", str(GAME_ID), "--seat", str(seat)])
            if not view_resp.get("ok"):
                print(f"View failed for seat {seat}", file=sys.stderr)
                break

            view = view_resp.get("view", {})

            # Make plan
            plan = simple_plan(view)

            # Submit plan
            result = submit_plan(seat, plan)
            if not result.get("ok"):
                print(f"Plan failed: {result.get('errors')}", file=sys.stderr)
                # Try empty plan
                plan = {"discard_to_limit": [], "steps": [], "end_turn": {}, "notes": "fallback"}
                result = submit_plan(seat, plan)
                if not result.get("ok"):
                    print(f"Fallback also failed", file=sys.stderr)
                    break

        elif phase == "react":
            # Skip reactions for now
            print("In react phase - advancing", file=sys.stderr)
            break

        elif phase == "resolve":
            # This phase needs the referee agent
            print("In resolve phase - would need referee", file=sys.stderr)
            break

        turn_num += 1

    print(f"Finished after {turn_num} iterations", file=sys.stderr)

    # Final status
    final_status = run_sim(["status", "--game", str(GAME_ID)])
    print(json.dumps({"final_status": final_status, "iterations": turn_num}, indent=2))

if __name__ == "__main__":
    main()
