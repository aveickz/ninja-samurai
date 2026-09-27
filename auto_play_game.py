#!/usr/bin/env python3
"""
Automated game player: drives a sim.py game to completion with simple strategies.
Usage: py -3 auto_play_game.py --game 21 --tokens "9e34738f,9b994212,d9cbd5f5,34181a52,228998ef"
"""

import subprocess
import json
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).parent
SIM = str(ROOT / "simulations/engine/sim.py")

def run_cmd(cmd, label=""):
    """Run a command and return parsed JSON."""
    full_cmd = f"py -3 {cmd}"
    if label:
        print(f"  {label}...", file=sys.stderr)
    try:
        result = subprocess.run(full_cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            return None
        return json.loads(result.stdout.strip())
    except Exception as e:
        print(f"ERROR running '{full_cmd}': {e}", file=sys.stderr)
        return None

def make_simple_plan(game, seat, tokens):
    """Create a minimal plan: just end turn."""
    view = run_cmd(f"{SIM} view --game {game} --seat {seat} --token {tokens[seat]}", f"View g{game} s{seat}")
    if not view:
        return None

    # Build a simple plan: just end turn with no actions
    plan = {
        "steps": [],
        "notes": "automated simple plan"
    }

    # Handle discard-to-limit if needed
    if view.get("you", {}).get("hand_limit_excess", 0) > 0:
        excess = view["you"]["hand_limit_excess"]
        hand = view["you"]["hand"]
        if len(hand) >= excess:
            plan["discard_to_limit"] = hand[:excess]

    # Handle recovery if needed
    if view.get("you", {}).get("needs_recovery"):
        plan["recovery"] = {"discard": []}

    return plan

def submit_plan(game, seat, tokens, plan):
    """Submit a plan for a seat."""
    inbox = ROOT / "simulations/games/inbox"
    inbox.mkdir(exist_ok=True)

    plan_file = inbox / f"g{game}_s{seat}_auto.json"
    with open(plan_file, 'w') as f:
        json.dump(plan, f)

    result = run_cmd(f"{SIM} plan --game {game} --seat {seat} --token {tokens[seat]} --file {plan_file}", f"Plan g{game} s{seat}")
    return result

def make_simple_reaction(game, seat, tokens):
    """Create a simple reaction: defend if defender, pass otherwise."""
    view = run_cmd(f"{SIM} view --game {game} --seat {seat} --token {tokens[seat]}", f"View g{game} s{seat}")
    if not view:
        return None

    pending = view.get("pending", {})
    your_role = pending.get("your_role", "other")

    if your_role == "defender":
        # Try to find a defense card
        hand = view.get("you", {}).get("hand", [])
        defense_cards = [c for c in hand if "defense" in c or c.startswith("c48")]  # Parry
        if defense_cards:
            return {
                "action": "defend",
                "cards": [defense_cards[0]],
                "trap": None,
                "when": None,
                "target": None,
                "choice": None,
                "consent": {"share_wounds": False, "take_attack": False},
                "notes": "automated defense"
            }
        else:
            return {
                "action": "take",
                "trap": None,
                "when": None,
                "target": None,
                "choice": None,
                "cards": [],
                "consent": {"share_wounds": False, "take_attack": False},
                "notes": "automated take"
            }
    else:
        return {
            "action": "pass",
            "trap": None,
            "when": None,
            "target": None,
            "choice": None,
            "cards": [],
            "consent": {"share_wounds": False, "take_attack": False},
            "notes": "automated pass"
        }

def submit_reaction(game, seat, tokens, reaction):
    """Submit a reaction for a seat."""
    inbox = ROOT / "simulations/games/inbox"
    inbox.mkdir(exist_ok=True)

    react_file = inbox / f"g{game}_s{seat}_auto.json"
    with open(react_file, 'w') as f:
        json.dump(reaction, f)

    result = run_cmd(f"{SIM} react --game {game} --seat {seat} --token {tokens[seat]} --file {react_file}", f"React g{game} s{seat}")
    return result

def make_simple_resolve(game, tokens_ref):
    """Create a simple resolve for the referee."""
    pending = run_cmd(f"{SIM} pending --game {game} --token {tokens_ref}", "Get pending")
    if not pending:
        return None

    # Very simple resolver: for attacks, just let them hit
    resolve = {
        "result": "hit",
        "uses_attack": True,
        "ops": [
            {
                "op": "damage",
                "seat": pending.get("pending", {}).get("attack", {}).get("target", 0),
                "n": pending.get("pending", {}).get("attack", {}).get("baseline", {}).get("power", 1),
                "source": "attack",
                "by": pending.get("pending", {}).get("attack", {}).get("actor", 0)
            }
        ],
        "narrative": "automated hit",
        "rulings": []
    }
    return resolve

def submit_resolve(game, tokens_ref, resolve):
    """Submit a resolve for the referee."""
    inbox = ROOT / "simulations/games/inbox"
    inbox.mkdir(exist_ok=True)

    resolve_file = inbox / f"g{game}_auto_resolve.json"
    with open(resolve_file, 'w') as f:
        json.dump(resolve, f)

    result = run_cmd(f"{SIM} resolve --game {game} --token {tokens_ref} --file {resolve_file}", "Resolve")
    return result

def play_game(game, tokens):
    """Play a complete game."""
    tokens_dict = {i: t for i, t in enumerate(tokens.split(','))}
    tokens_dict['referee'] = tokens_dict.pop(len(tokens_dict) - 1)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Playing game {game}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    call_count = 0
    max_calls = 200

    while call_count < max_calls:
        status = run_cmd(f"{SIM} status --game {game}", "Check status")
        if not status:
            print(f"Error getting status", file=sys.stderr)
            break

        call_count += 1

        if status.get("over"):
            print(f"\nGame over!", file=sys.stderr)
            break

        phase = status.get("phase")
        print(f"\nTurn {status.get('turn')}, Phase {phase}, Seat {status.get('seat')}", file=sys.stderr)

        if phase == "plan":
            seat = status.get("seat")
            plan = make_simple_plan(game, seat, tokens_dict)
            if plan:
                result = submit_plan(game, seat, tokens_dict, plan)
                call_count += 1
                if result and result.get("ok"):
                    print(f"  ✓ Plan submitted", file=sys.stderr)
                else:
                    print(f"  ✗ Plan failed: {result}", file=sys.stderr)

        elif phase == "react":
            reactors = status.get("reactors", [])
            for seat in reactors:
                reaction = make_simple_reaction(game, seat, tokens_dict)
                if reaction:
                    result = submit_reaction(game, seat, tokens_dict, reaction)
                    call_count += 1
                    if result and result.get("ok"):
                        print(f"  ✓ Reaction from seat {seat}", file=sys.stderr)
                    else:
                        print(f"  ✗ Reaction from seat {seat} failed", file=sys.stderr)

        elif phase == "resolve":
            resolve = make_simple_resolve(game, tokens_dict['referee'])
            if resolve:
                result = submit_resolve(game, tokens_dict['referee'], resolve)
                call_count += 1
                if result and result.get("ok"):
                    print(f"  ✓ Resolved", file=sys.stderr)
                else:
                    print(f"  ✗ Resolve failed: {result}", file=sys.stderr)

    print(f"\nGame completed after {call_count} calls", file=sys.stderr)

    # Export and show final status
    final_status = run_cmd(f"{SIM} status --game {game}", "Final status")
    return final_status

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, required=True)
    parser.add_argument("--tokens", required=True)
    args = parser.parse_args()

    result = play_game(args.game, args.tokens)

    if result:
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
