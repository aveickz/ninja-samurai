#!/usr/bin/env python3
import subprocess
import json
import sys
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "anthropic", "-q"], check=False)
    from anthropic import Anthropic

GAME = 31
TOKENS = {"0": "ea193b9b", "1": "e0566d68", "2": "529b7c9b", "3": "a6fd2f90", "ref": "b2758ba8"}
REPO = r"C:\ninja_samurai\cardboard"
CALL_LIMIT = 250
client = Anthropic()

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except:
        return None

def get_status():
    return run_cmd(f'py -3 simulations/engine/sim.py status --game {GAME}')

def get_view(seat, token):
    return run_cmd(f'py -3 simulations/engine/sim.py view --game {GAME} --seat {seat} --token {token}')

def get_pending(token):
    return run_cmd(f'py -3 simulations/engine/sim.py pending --game {GAME} --token {token}')

def call_player_plan(seat):
    token = TOKENS[str(seat)]
    view = get_view(seat, token)
    if not view:
        return None
    
    try:
        with open(f"{REPO}/simulations/prompts/player-plan.md", encoding='utf-8') as f:
            prompt_template = f.read()
    except:
        return None
    
    user_message = f"{prompt_template}\n\n## Your game view:\n```json\n{json.dumps(view, indent=2)}\n```"
    print(f"  + Player {seat} planning...", flush=True)
    
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=2000,
        messages=[{"role": "user", "content": user_message}]
    )
    
    response_text = response.content[0].text
    plan = None
    for line in response_text.split('\n'):
        if line.startswith('{'):
            try:
                plan = json.loads(line + ('}' if not line.endswith('}') else ''))
                break
            except:
                pass
    
    if not plan and '```' in response_text:
        try:
            plan = json.loads(response_text.split('```')[1].strip())
        except:
            pass
    
    if not plan:
        return None
    
    result = subprocess.run(
        f'py -3 simulations/engine/sim.py plan --game {GAME} --seat {seat} --token {token} --file -',
        input=json.dumps(plan),
        shell=True,
        capture_output=True,
        text=True,
        cwd=REPO
    )
    
    try:
        return json.loads(result.stdout)
    except:
        return None

def call_player_react(seat, pending):
    token = TOKENS[str(seat)]
    view = get_view(seat, token)
    if not view:
        return None
    
    try:
        with open(f"{REPO}/simulations/prompts/player-react.md", encoding='utf-8') as f:
            prompt_template = f.read()
    except:
        return None
    
    user_message = f"{prompt_template}\n\n## Your game view:\n```json\n{json.dumps(view, indent=2)}\n```\n\n## Current transaction:\n```json\n{json.dumps(pending, indent=2)}\n```"
    print(f"  + Player {seat} reacting...", flush=True)
    
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=1000,
        messages=[{"role": "user", "content": user_message}]
    )
    
    response_text = response.content[0].text
    reaction = None
    for line in response_text.split('\n'):
        if line.startswith('{'):
            try:
                reaction = json.loads(line + ('}' if not line.endswith('}') else ''))
                break
            except:
                pass
    
    if not reaction and '```' in response_text:
        try:
            reaction = json.loads(response_text.split('```')[1].strip())
        except:
            pass
    
    if not reaction:
        return None
    
    result = subprocess.run(
        f'py -3 simulations/engine/sim.py react --game {GAME} --seat {seat} --token {token} --file -',
        input=json.dumps(reaction),
        shell=True,
        capture_output=True,
        text=True,
        cwd=REPO
    )
    
    try:
        return json.loads(result.stdout)
    except:
        return None

def call_referee(pending):
    token = TOKENS['ref']
    
    try:
        with open(f"{REPO}/simulations/prompts/referee.md", encoding='utf-8') as f:
            prompt_template = f.read()
    except:
        return None
    
    user_message = f"{prompt_template}\n\n## Transaction to resolve:\n```json\n{json.dumps(pending, indent=2)}\n```"
    print(f"  + Referee resolving...", flush=True)
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        messages=[{"role": "user", "content": user_message}]
    )
    
    response_text = response.content[0].text
    resolution = None
    for line in response_text.split('\n'):
        if line.startswith('{'):
            try:
                resolution = json.loads(line + ('}' if not line.endswith('}') else ''))
                break
            except:
                pass
    
    if not resolution and '```' in response_text:
        try:
            resolution = json.loads(response_text.split('```')[1].strip())
        except:
            pass
    
    if not resolution:
        return None
    
    result = subprocess.run(
        f'py -3 simulations/engine/sim.py resolve --game {GAME} --token {token} --file -',
        input=json.dumps(resolution),
        shell=True,
        capture_output=True,
        text=True,
        cwd=REPO
    )
    
    try:
        return json.loads(result.stdout)
    except:
        return None

print("\n=== SIMULATION START ===")
print(f"Game: {GAME}")
print(f"Deck: ~236 cards\n")

status_initial = get_status()
if status_initial:
    for p in status_initial.get('players', []):
        print(f"  P{p['seat']}: {p['character']} ({p['faction']})")
print()

call_count = 0
while call_count < CALL_LIMIT:
    status = get_status()
    if not status:
        print("Failed to get status")
        sys.exit(1)
    
    deck_remaining = len(status.get('deck', []))
    print(f"[T{status['turn']:2d}] Phase: {status['phase']:8s} | Deck: {deck_remaining:3d} | ", end='', flush=True)
    
    if status['phase'] == 'over':
        print("GAME OVER\n")
        
        export_cmd = f'py -3 simulations/engine/sim.py export --game {GAME}'
        export_result = run_cmd(export_cmd)
        
        if export_result:
            game_file = Path(REPO) / "simulations" / "games" / f"game_{GAME}.json"
            if game_file.exists():
                with open(game_file) as f:
                    exported = json.load(f)
                    result = exported.get('game', {}).get('result', {})
                    
                    print("=== SIMULATION RESULT ===")
                    print(f"Winner: {result.get('winner', '?')}")
                    print(f"Score: {result.get('score', {})}")
                    print(f"Reason: {result.get('reason', '?')}")
                    print(f"Turns played: {exported.get('game', {}).get('turns_played', '?')}")
                    
                    initial_deck = 236
                    deck_used = initial_deck - deck_remaining
                    print(f"Cards used from deck: {deck_used} ({deck_remaining} remaining)")
        break
    
    elif status['phase'] == 'plan':
        seat = status['seat']
        print(f"P{seat} planning")
        result = call_player_plan(seat)
        if not result:
            print("Plan failed")
            sys.exit(1)
    
    elif status['phase'] == 'react':
        reactors = status.get('reactors', [])
        if reactors:
            pending = get_pending(TOKENS['ref'])
            print(f"Reactions from {reactors}")
            for reactor_seat in reactors:
                result = call_player_react(reactor_seat, pending)
                if not result:
                    print("React failed")
                    sys.exit(1)
        else:
            print("Auto-resolve")
            call_count += 1
            continue
    
    elif status['phase'] == 'resolve':
        pending = get_pending(TOKENS['ref'])
        print("Referee resolving")
        result = call_referee(pending)
        if not result:
            print("Resolution failed")
            sys.exit(1)
    
    else:
        print(f"Unknown phase: {status['phase']}")
        sys.exit(1)
    
    call_count += 1

print("\n=== SIMULATION COMPLETE ===")