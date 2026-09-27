#!/usr/bin/env py -3
"""Simple auto-player for running the simulation."""

import json
import subprocess
import sys
import random

def run_sim(cmd_args):
    """Run a sim.py command and return the JSON result."""
    cmd = ["py", "-3", "simulations/engine/sim.py"] + cmd_args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd="C:\\ninja_samurai\\cardboard")
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse: {result.stdout}", file=sys.stderr)
        return None

def make_simple_plan(view):
    """Create a simple plan based on the player's view."""
    hand = view.get("hand", [])
    complexity = view.get("attack", {}).get("baseline", {}).get("target_complexity", 1)

    plan = {
        "steps": [],
        "end_turn": {},
        "notes": "Simple auto-play"
    }

    # Try to play a weapon attack if we have one
    for card_uid in hand:
        card_info = view.get("cards", {}).get(card_uid, {})
        card_types = card_info.get("types", [])

        if "weapon" in card_types:
            # Find a valid target
            targets = view.get("table", {}).get("players", {})
            alive_enemies = [s for s in targets.keys()
                           if targets[s].get("alive") and s != str(view["seat"])]

            if alive_enemies:
                target = int(random.choice(alive_enemies))
                plan["steps"].append({
                    "do": "attack",
                    "card": card_uid,
                    "mode": "main",
                    "target": target,
                    "why": "Basic attack"
                })
                break

    return plan

def make_simple_react(pending, view):
    """Create a simple reaction."""
    # For now, just take the attack
    return {
        "action": "take",
        "notes": "Auto-take"
    }

def play_game(game_id, max_iterations=500):
    """Play through a game automatically."""
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Get current status
        status_result = run_sim(["status", "--game", str(game_id)])
        if not status_result:
            print("Failed to get status")
            break

        status = status_result.get("status", {})
        phase = status.get("phase")

        print(f"[{iteration}] Turn {status.get('turn')}, Phase: {phase}", flush=True)

        if phase == "over":
            print("Game over!")
            break

        if phase == "plan":
            # Get player view
            seat = status.get("seat")
            view = run_sim(["view", "--game", str(game_id), "--seat", str(seat)])
            if not view:
                print(f"Failed to get view for seat {seat}")
                break

            # Make a plan
            plan = make_simple_plan(view)
            print(f"Submitting plan for seat {seat}", flush=True)

            plan_result = run_sim(["plan", "--game", str(game_id), "--seat", str(seat), "--file", "-"])
            # Use stdin instead
            cmd = ["py", "-3", "simulations/engine/sim.py", "plan", "--game", str(game_id), "--seat", str(seat), "--file", "-"]
            result = subprocess.run(cmd, input=json.dumps(plan), capture_output=True, text=True, cwd="C:\\ninja_samurai\\cardboard")

            if result.returncode != 0:
                print(f"Plan submission failed: {result.stderr}", file=sys.stderr)
                break

        elif phase == "react":
            # Get pending transaction
            pending = run_sim(["pending", "--game", str(game_id)])
            if not pending:
                print("Failed to get pending")
                break

            seat = status.get("seat")
            view = run_sim(["view", "--game", str(game_id), "--seat", str(seat)])
            if not view:
                print(f"Failed to get view for reactor {seat}")
                break

            # Make a reaction
            reaction = make_simple_react(pending, view)
            print(f"Submitting reaction for seat {seat}", flush=True)

            cmd = ["py", "-3", "simulations/engine/sim.py", "react", "--game", str(game_id), "--seat", str(seat), "--file", "-"]
            result = subprocess.run(cmd, input=json.dumps(reaction), capture_output=True, text=True, cwd="C:\\ninja_samurai\\cardboard")

            if result.returncode != 0:
                print(f"React submission failed: {result.stderr}", file=sys.stderr)
                break

        elif phase == "resolve":
            # This should be handled by the referee, but in auto-play we'll skip
            print("Resolve phase - skipping in auto-play", flush=True)
            break

        else:
            print(f"Unknown phase: {phase}")
            break

    print(f"Game completed after {iteration} iterations")
    return status_result

if __name__ == "__main__":
    if len(sys.argv) > 1:
        game_id = int(sys.argv[1])
    else:
        game_id = 26

    result = play_game(game_id)
    if result:
        print(f"\nFinal status: {json.dumps(result['status'], indent=2)}")
