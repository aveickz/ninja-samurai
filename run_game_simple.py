#!/usr/bin/env python3
import subprocess
import json
import sys
import os

GAME = 8
TOKENS = {"0": "faeb6de1", "1": "ab49e442", "2": "b8079cc2", "3": "81322cda", "ref": "f213c80a"}
REPO = "C:/ninja_samurai/cardboard"

def run_cmd(cmd):
    """Run a command and return parsed JSON result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO)
    try:
        return json.loads(result.stdout.strip())
    except:
        return None

def get_status():
    """Get current game status"""
    cmd = f'py -3 simulations/engine/sim.py status --game {GAME}'
    return run_cmd(cmd)

def submit_simple_plan(seat, token):
    """Submit a simple passing plan"""
    plan = {
        "discard_to_limit": [],
        "recovery": {"discard": []},
        "steps": [],
        "end_turn": {},
        "notes": "Simple pass"
    }
    
    inbox = f"{REPO}/simulations/games/inbox"
    os.makedirs(inbox, exist_ok=True)
    plan_file = f"{inbox}/g{GAME}_s{seat}_plan.json"
    
    with open(plan_file, 'w') as f:
        json.dump(plan, f)
    
    cmd = f'py -3 simulations/engine/sim.py plan --game {GAME} --seat {seat} --token {token} --file {plan_file}'
    return run_cmd(cmd)

# Main loop
print(f"Starting game {GAME}...")
turn_count = 0
max_turns = 60

while turn_count < max_turns:
    status = get_status()
    if not status:
        break
    
    deck_n = status.get('deck_n', '?')
    phase = status.get('phase', 'unknown')
    turn = status.get('turn', 0)
    
    print(f"Turn {turn}, Phase: {phase}, Deck: {deck_n} cards", flush=True)
    
    if phase == 'over':
        print("Game finished!")
        break
    
    if phase == 'plan':
        seat = status.get('seat')
        token = TOKENS.get(str(seat))
        result = submit_simple_plan(seat, token)
        if result and result.get('ok'):
            print(f"  P{seat} submitted plan")
        else:
            print(f"  P{seat} plan failed: {result}")
            break
        turn_count += 1
    else:
        print(f"  Unexpected phase: {phase}")
        break

print("\nExporting game...")
os.system(f'cd {REPO} && py -3 simulations/engine/sim.py export --game {GAME} >nul 2>&1')

print("\nFetching game result...")
result = run_cmd(f'py -3 simulations/engine/sim.py log --game {GAME} --format json')
if result:
    print(json.dumps(result, indent=2)[:500])
else:
    os.system(f'cd {REPO} && py -3 simulations/engine/sim.py log --game {GAME} | head -100')

