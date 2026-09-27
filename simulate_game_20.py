#!/usr/bin/env python3
"""
Automated game runner for Samurai vs Ninja simulation.
Plays game 20 until completion (deck reaches floor or max turns).
"""
import subprocess
import json
import os
import sys
from pathlib import Path

GAME = 20
REPO = "C:/ninja_samurai/cardboard"
INBOX = f"{REPO}/simulations/games/inbox"
SIM = f"py -3 {REPO}/simulations/engine/sim.py"

os.makedirs(INBOX, exist_ok=True)

def run_cmd(cmd):
    """Run command and return JSON result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO)
    if result.returncode != 0:
        return {"error": result.stderr, "stdout": result.stdout}
    try:
        return json.loads(result.stdout.strip())
    except:
        return {"raw": result.stdout, "error": "Parse failed"}

def get_status():
    """Get current game status"""
    return run_cmd(f"{SIM} status --game {GAME}")

def get_public():
    """Get public game state"""
    return run_cmd(f"{SIM} public --game {GAME}")

def get_view(seat):
    """Get a player's view of the game"""
    return run_cmd(f"{SIM} view --game {GAME} --seat {seat}")

def get_pending():
    """Get the pending transaction for referee"""
    return run_cmd(f"{SIM} pending --game {GAME}")

def submit_plan(seat):
    """Submit a default plan (pass with minimal valid moves)"""
    view = get_view(seat)
    if not view or "error" in view:
        return None

    you = view.get("you", {})
    hand = you.get("hand", [])

    plan = {
        "discard_to_limit": [],
        "recovery": {"discard": []},
        "steps": [],
        "end_turn": {},
        "notes": "Automated simple strategy"
    }

    # Try to play a simple action: weapon attack if available
    for card in hand:
        card_id = card.get("id")
        card_uid = card.get("uid")
        card_types = card.get("types", [])

        # Simple strategy: play weapons if we can
        if "weapon" in card_types:
            reach = card.get("reach", [])
            if reach:
                plan["steps"].append({
                    "do": "attack",
                    "card": card_uid,
                    "mode": "main",
                    "target": reach[0],
                    "modifier": None,
                    "why": "Weapon attack"
                })
                break

    # Handle hand limit
    if you.get("hand_limit_excess", 0) > 0:
        excess = you.get("hand_limit_excess", 0)
        cards_to_discard = hand[-excess:] if excess <= len(hand) else hand
        plan["discard_to_limit"] = [c.get("uid") for c in cards_to_discard]

    # Handle recovery
    if you.get("needs_recovery"):
        plan["recovery"] = {"discard": []}

    plan_file = f"{INBOX}/g{GAME}_s{seat}_plan.json"
    with open(plan_file, 'w') as f:
        json.dump(plan, f)

    result = run_cmd(f"{SIM} plan --game {GAME} --seat {seat} --file {plan_file}")
    return result

def submit_react(seat, pending):
    """Submit a default reaction"""
    your_role = pending.get("your_role")

    if your_role == "defender":
        action = "take"  # Just take the attack
    else:
        action = "pass"  # Pass on intervention

    reaction = {
        "action": action,
        "notes": "Automated reaction"
    }

    react_file = f"{INBOX}/g{GAME}_s{seat}_react.json"
    with open(react_file, 'w') as f:
        json.dump(reaction, f)

    result = run_cmd(f"{SIM} react --game {GAME} --seat {seat} --file {react_file}")
    return result

def submit_resolve():
    """Submit a default resolution by referee"""
    pending = get_pending()
    if not pending or "error" in pending:
        return None

    transaction = pending.get("transaction", {})
    trans_type = transaction.get("type")

    if trans_type == "attack":
        # Default: resolve as hit
        resolution = {
            "result": "hit",
            "uses_attack": True,
            "ops": [{
                "op": "damage",
                "seat": transaction.get("target"),
                "n": transaction.get("base_power", 1),
                "source": "attack",
                "by": transaction.get("actor")
            }],
            "narrative": "Attack resolves",
            "rulings": []
        }
    else:
        # Default: resolve as-is
        resolution = {
            "result": "resolved",
            "uses_attack": False,
            "ops": [],
            "narrative": "Transaction resolved",
            "rulings": []
        }

    resolve_file = f"{INBOX}/g{GAME}_force_resolve.json"
    with open(resolve_file, 'w') as f:
        json.dump(resolution, f)

    result = run_cmd(f"{SIM} resolve --game {GAME} --file {resolve_file}")
    return result

def main():
    print(f"=== Game {GAME} Automated Runner ===\n")

    status = get_status()
    print(f"Initial state:")
    print(f"  Players: {[p.get('character') for p in status.get('players', [])]}")
    print(f"  Deck: {status.get('deck_n')} cards")
    print()

    max_iterations = 500
    iteration = 0
    last_turn = 0

    while iteration < max_iterations:
        status = get_status()

        if not status or "error" in status:
            print(f"ERROR getting status: {status}")
            break

        phase = status.get("phase")
        turn = status.get("turn")
        over = status.get("over")
        seat = status.get("seat")
        reactors = status.get("reactors", [])

        # Get deck info from public state
        public = get_public()
        deck_n = public.get("public", {}).get("deck_n", "?") if public and "error" not in public else "?"

        # Print progress every few turns
        if turn != last_turn:
            deck_str = f"{deck_n}" if isinstance(deck_n, int) else str(deck_n)
            print(f"Turn {turn:3d}, Phase: {phase:7s}, Deck: {deck_str:3s} cards, Over: {over}")
            last_turn = turn

        if over:
            print(f"\n=== GAME OVER ===")
            break

        # Handle different phases
        if phase == "plan":
            if not submit_plan(seat):
                print(f"ERROR submitting plan for seat {seat}")
                break

        elif phase == "react":
            # Get pending to understand what we're reacting to
            pending = get_pending()
            if not pending:
                break

            for reactor in reactors:
                if not submit_react(reactor, pending):
                    print(f"ERROR submitting reaction for seat {reactor}")
                    break

        elif phase == "resolve":
            if not submit_resolve():
                print(f"ERROR submitting resolution")
                break

        iteration += 1

    # Get final results
    print("\n=== Exporting game data ===")
    export_result = run_cmd(f"{SIM} export --game {GAME}")
    print(f"Export: {export_result}")

    # Get final log
    log_result = subprocess.run(
        f"cd {REPO} && {SIM} log --game {GAME}",
        shell=True, capture_output=True, text=True
    )

    # Get report
    report_result = run_cmd(f"{SIM} report --game {GAME}")

    print("\n=== FINAL STATUS ===")
    final_status = get_status()
    print(json.dumps(final_status, indent=2))

    print("\n=== GAME LOG (first 3000 chars) ===")
    if log_result.stdout:
        print(log_result.stdout[:3000])

if __name__ == "__main__":
    main()
