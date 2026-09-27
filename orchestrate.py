#!/usr/bin/env python3
"""
Orchestrator for Samurai vs Ninja simulation.
Drives agents through a game until completion.
"""
import subprocess
import json
import sys
import os
from pathlib import Path

GAME = 14
TOKENS = {
    "0": "9f13135b",
    "1": "32246add",
    "2": "94e50bce",
    "3": "082d7e78",
    "ref": "793270c3"
}
REPO = "C:/ninja_samurai/cardboard"
CALL_LIMIT = 120

def run_cmd(cmd):
    """Run a shell command and return JSON result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR (code {result.returncode}): {result.stderr[:500]}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON: {result.stdout[:200]}")
        return None

def get_status():
    """Get current game status"""
    cmd = f'cd {REPO} && py -3 simulations/engine/sim.py status --game {GAME}'
    return run_cmd(cmd)

def call_agent(phase, seat, token):
    """Call an LLM agent for a specific phase and seat"""
    prompt_file = {
        "plan": "player-plan.md",
        "react": "player-react.md",
        "resolve": "referee.md"
    }.get(phase)

    if not prompt_file:
        return None

    prompt_path = f"{REPO}/simulations/prompts/{prompt_file}"

    # Read the prompt
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except:
        print(f"Failed to read {prompt_path}")
        return None

    # Prepare the command with GAME, SEAT (or "ref"), and TOKEN
    if phase == "resolve":
        env_vars = f"GAME={GAME} SEAT=ref TOKEN={token}"
    else:
        env_vars = f"GAME={GAME} SEAT={seat} TOKEN={token}"

    # The prompt should contain the sim.py command to run
    # We'll execute it in the context of the prompt
    print(f"[{phase.upper()} seat {seat}] Calling agent...")

    # For simplicity, we'll just call the CLI that the prompt suggests
    # The prompt templates include comments with the exact CLI calls
    cmd = f"cd {REPO} && {env_vars} py -3 simulations/engine/sim.py {phase} --game {GAME}"
    if phase != "resolve":
        cmd += f" --seat {seat} --token {token}"
    else:
        cmd += f" --token {token}"

    result = run_cmd(cmd)
    return result

def main():
    print(f"Starting orchestration of game {GAME}...")
    print(f"Deck size: ~236 cards initially")
    print()

    call_count = 0

    while call_count < CALL_LIMIT:
        # Get current status
        status = get_status()
        if not status:
            print("Failed to get status")
            return False

        print(f"\n=== Call {call_count + 1}/{CALL_LIMIT} ===")
        print(f"Game {status['game']}, Turn {status['turn']}, Phase: {status['phase']}")

        if status['phase'] == 'over':
            print("\n✓ GAME OVER")
            # Export the result
            export_cmd = f"cd {REPO} && py -3 simulations/engine/sim.py export --game {GAME}"
            export_result = run_cmd(export_cmd)
            if export_result:
                print("✓ Game exported to simulations/games/game_{}.json".format(GAME))
            return True

        elif status['phase'] == 'plan':
            # Active player submits a plan
            seat = status['seat']
            token = TOKENS[str(seat)]
            result = call_agent('plan', seat, token)
            if not result:
                print(f"Agent call failed for seat {seat}")
                return False

        elif status['phase'] == 'react':
            # Reactors submit reactions in parallel (we'll do sequentially)
            reactors = status.get('reactors', [])
            if reactors:
                for reactor_seat in reactors:
                    token = TOKENS[str(reactor_seat)]
                    result = call_agent('react', reactor_seat, token)
                    if not result:
                        print(f"Agent call failed for reactor {reactor_seat}")
                        return False
            else:
                # No reactors, auto-resolve
                call_count += 1
                continue

        elif status['phase'] == 'resolve':
            # Referee resolves the transaction
            token = TOKENS['ref']
            result = call_agent('resolve', None, token)
            if not result:
                print("Agent call failed for referee")
                return False

        else:
            print(f"Unknown phase: {status['phase']}")
            return False

        call_count += 1

    print(f"\n✗ Reached call limit ({CALL_LIMIT}) without finishing")
    return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
