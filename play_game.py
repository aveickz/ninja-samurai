#!/usr/bin/env python3
"""
Game orchestrator using Claude API to drive agents.
"""
import subprocess
import json
import sys
import os
from pathlib import Path
import time

try:
    from anthropic import Anthropic
except ImportError:
    print("Installing anthropic...")
    subprocess.run([sys.executable, "-m", "pip", "install", "anthropic", "-q"], check=False)
    from anthropic import Anthropic

GAME = 14
TOKENS = {
    "0": "9f13135b",
    "1": "32246add",
    "2": "94e50bce",
    "3": "082d7e78",
    "ref": "793270c3"
}
REPO = "C:/ninja_samurai/cardboard"
CALL_LIMIT = 150
MAX_GAME_DURATION = 3600  # 1 hour timeout

client = Anthropic()

def run_cmd(cmd):
    """Run a shell command and return JSON result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO)
    if result.returncode != 0:
        err = result.stderr[:300] if result.stderr else result.stdout[:300]
        print(f"  ! Command failed: {err}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"  ! Parse error: {str(e)[:100]}")
        return None

def get_status():
    """Get current game status"""
    cmd = f'py -3 simulations/engine/sim.py status --game {GAME}'
    return run_cmd(cmd)

def get_view(seat, token):
    """Get player view"""
    cmd = f'py -3 simulations/engine/sim.py view --game {GAME} --seat {seat} --token {token}'
    return run_cmd(cmd)

def get_pending(token):
    """Get pending transaction (for referee)"""
    cmd = f'py -3 simulations/engine/sim.py pending --game {GAME} --token {token}'
    return run_cmd(cmd)

def get_rules():
    """Get rules digest"""
    cmd = f'py -3 simulations/engine/sim.py rules'
    return run_cmd(cmd)

def call_player_plan(seat):
    """Have Claude play a plan for the active player"""
    token = TOKENS[str(seat)]
    view = get_view(seat, token)
    if not view:
        return None

    # Read the prompt template
    try:
        with open(f"{REPO}/simulations/prompts/player-plan.md", encoding='utf-8') as f:
            prompt_template = f.read()
    except:
        print(f"  ! Failed to read prompt template")
        return None

    # Build the message with the view
    view_str = json.dumps(view, indent=2)
    user_message = f"{prompt_template}\n\n## Your game view:\n```json\n{view_str}\n```"

    print(f"  + Player {seat} planning...")

    # Call Claude
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=2000,
        messages=[{"role": "user", "content": user_message}]
    )

    response_text = response.content[0].text

    # Extract JSON from response (it should be in a code block)
    plan = None
    for line in response_text.split('\n'):
        if line.startswith('{'):
            try:
                plan = json.loads(line + ('}' if not line.endswith('}') else ''))
                break
            except:
                pass

    if not plan:
        # Try to parse the whole response as JSON
        try:
            if '```' in response_text:
                plan = json.loads(response_text.split('```')[1].strip())
        except:
            pass

    if not plan:
        print(f"  ! Failed to parse plan from Claude response")
        return None

    # Submit the plan
    plan_json = json.dumps(plan)
    cmd = f'py -3 simulations/engine/sim.py plan --game {GAME} --seat {seat} --token {token} --file -'

    result = subprocess.run(cmd, input=plan_json, shell=True, capture_output=True, text=True, cwd=REPO)
    if result.returncode != 0:
        print(f"  ! Plan submission failed")
        return None

    try:
        return json.loads(result.stdout)
    except:
        print(f"  ! Failed to parse plan response")
        return None

def call_player_react(seat, pending):
    """Have Claude react to an attack or group card"""
    token = TOKENS[str(seat)]
    view = get_view(seat, token)
    if not view:
        return None

    try:
        with open(f"{REPO}/simulations/prompts/player-react.md", encoding='utf-8') as f:
            prompt_template = f.read()
    except:
        print(f"  ! Failed to read react prompt")
        return None

    view_str = json.dumps(view, indent=2)
    pending_str = json.dumps(pending, indent=2)
    user_message = f"{prompt_template}\n\n## Your game view:\n```json\n{view_str}\n```\n\n## Current transaction:\n```json\n{pending_str}\n```"

    print(f"  + Player {seat} reacting...")

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=1000,
        messages=[{"role": "user", "content": user_message}]
    )

    response_text = response.content[0].text

    # Extract JSON
    reaction = None
    for line in response_text.split('\n'):
        if line.startswith('{'):
            try:
                reaction = json.loads(line + ('}' if not line.endswith('}') else ''))
                break
            except:
                pass

    if not reaction:
        try:
            if '```' in response_text:
                reaction = json.loads(response_text.split('```')[1].strip())
        except:
            pass

    if not reaction:
        print(f"  ! Failed to parse reaction")
        return None

    # Submit reaction
    reaction_json = json.dumps(reaction)
    cmd = f'py -3 simulations/engine/sim.py react --game {GAME} --seat {seat} --token {token} --file -'

    result = subprocess.run(cmd, input=reaction_json, shell=True, capture_output=True, text=True, cwd=REPO)
    if result.returncode != 0:
        print(f"  ! React submission failed")
        return None

    try:
        return json.loads(result.stdout)
    except:
        print(f"  ! Failed to parse react response")
        return None

def call_referee(pending):
    """Have Claude referee a transaction"""
    token = TOKENS['ref']

    try:
        with open(f"{REPO}/simulations/prompts/referee.md", encoding='utf-8') as f:
            prompt_template = f.read()
    except:
        print(f"  ! Failed to read referee prompt")
        return None

    pending_str = json.dumps(pending, indent=2)
    user_message = f"{prompt_template}\n\n## Transaction to resolve:\n```json\n{pending_str}\n```"

    print(f"  + Referee resolving...")

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        messages=[{"role": "user", "content": user_message}]
    )

    response_text = response.content[0].text

    # Extract JSON
    resolution = None
    for line in response_text.split('\n'):
        if line.startswith('{'):
            try:
                resolution = json.loads(line + ('}' if not line.endswith('}') else ''))
                break
            except:
                pass

    if not resolution:
        try:
            if '```' in response_text:
                resolution = json.loads(response_text.split('```')[1].strip())
        except:
            pass

    if not resolution:
        print(f"  ! Failed to parse resolution")
        return None

    # Submit resolution
    resolution_json = json.dumps(resolution)
    cmd = f'py -3 simulations/engine/sim.py resolve --game {GAME} --token {token} --file -'

    result = subprocess.run(cmd, input=resolution_json, shell=True, capture_output=True, text=True, cwd=REPO)
    if result.returncode != 0:
        print(f"  ! Resolve submission failed")
        return None

    try:
        return json.loads(result.stdout)
    except:
        print(f"  ! Failed to parse resolve response")
        return None

def main():
    print(f"[START] Game orchestration...")
    print(f"[GAME] {GAME}")
    print(f"[DECK] ~236 cards")
    print(f"[PLAYERS] P0 (Norio, Samurai), P1 (Ushiwaka, Ninja), P2 (Taka, Samurai), P3 (Hanzo, Ninja)")
    print()

    call_count = 0
    start_time = time.time()

    while call_count < CALL_LIMIT:
        elapsed = time.time() - start_time
        if elapsed > MAX_GAME_DURATION:
            print(f"\n[ERROR] Game exceeded time limit ({MAX_GAME_DURATION}s)")
            return False

        status = get_status()
        if not status:
            print("Failed to get status")
            return False

        deck_n = status.get('deck', [])
        print(f"[T{status['turn']:2d}] {status['phase']:7s} | Deck: {len(deck_n):3d} | ", end='', flush=True)

        if status['phase'] == 'over':
            print("[OK] GAME OVER")
            print()

            # Get final result
            status_final = get_status()
            print(f"Final status: {json.dumps(status_final, indent=2)}")

            # Export the game
            export_cmd = f'py -3 simulations/engine/sim.py export --game {GAME}'
            export_result = run_cmd(export_cmd)
            if export_result:
                print(f"\n[OK] Game exported to simulations/games/game_{GAME}.json")

                # Show summary
                game_file = Path(REPO) / "simulations" / "games" / f"game_{GAME}.json"
                if game_file.exists():
                    with open(game_file) as f:
                        exported = json.load(f)
                        result = exported.get('game', {}).get('result', {})
                        print(f"\n[RESULT]:")
                        print(f"   Winner: {result.get('winner', '?')}")
                        print(f"   Score: {result.get('score', {})}")
                        print(f"   Reason: {result.get('reason', '?')}")
                        print(f"   Turns played: {exported.get('game', {}).get('turns_played', '?')}")

            return True

        elif status['phase'] == 'plan':
            seat = status['seat']
            print(f"P{seat} planning...")
            result = call_player_plan(seat)
            if not result:
                return False

        elif status['phase'] == 'react':
            reactors = status.get('reactors', [])
            if reactors:
                pending = get_pending(TOKENS['ref'])
                print(f"Reactors: {reactors}")
                for reactor_seat in reactors:
                    result = call_player_react(reactor_seat, pending)
                    if not result:
                        return False
            else:
                print(f"No reactors")
                call_count += 1
                continue

        elif status['phase'] == 'resolve':
            pending = get_pending(TOKENS['ref'])
            print(f"Referee resolving...")
            result = call_referee(pending)
            if not result:
                return False

        else:
            print(f"Unknown phase: {status['phase']}")
            return False

        call_count += 1

    print(f"\n[ERROR] Reached call limit ({CALL_LIMIT}) without finishing")
    return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
