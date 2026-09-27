#!/usr/bin/env python3
import subprocess
import json
import sys

GAME = 8
TOKENS = {
    "0": "faeb6de1",
    "1": "ab49e442", 
    "2": "b8079cc2",
    "3": "81322cda",
    "ref": "f213c80a"
}
REPO = "C:/ninja_samurai/cardboard"

def run_cmd(cmd):
    """Run a sim.py command and return JSON result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout)
    except:
        print(f"Failed to parse: {result.stdout}")
        return None

def get_status():
    """Get current game status"""
    cmd = f'cd {REPO} && py -3 simulations/engine/sim.py status --game {GAME}'
    return run_cmd(cmd)

def simple_plan(seat, token, view):
    """Generate a simple plan for a player"""
    hand = view.get('you', {}).get('hand', [])
    
    plan = {
        "discard_to_limit": [],
        "recovery": {"discard": []},
        "steps": [],
        "end_turn": {},
        "notes": "Greedy strategy"
    }
    
    # Simple heuristic: play weapons against weakest enemy
    for card in hand:
        if card.get('type') == 'weapon':
            reach = card.get('reach', [])
            if reach:
                target = reach[0]
                plan['steps'].append({
                    "do": "attack",
                    "card": card['uid'],
                    "mode": "main",
                    "target": target,
                    "modifier": None,
                    "why": "Attack with available weapon"
                })
                break
    
    return plan

def submit_plan(seat, token, plan):
    """Submit a player's plan"""
    import os
    inbox_path = f"{REPO}/simulations/games/inbox"
    os.makedirs(inbox_path, exist_ok=True)
    
    plan_file = f"{inbox_path}/g{GAME}_s{seat}_plan.json"
    with open(plan_file, 'w') as f:
        json.dump(plan, f)
    
    cmd = f'cd {REPO} && py -3 simulations/engine/sim.py plan --game {GAME} --seat {seat} --token {token} --file {plan_file}'
    return run_cmd(cmd)

def run_turn():
    """Run one player's turn"""
    status = get_status()
    if not status:
        return False
    
    if status.get('phase') == 'over':
        return False
    
    if status.get('phase') == 'plan':
        seat = status.get('seat')
        token = TOKENS.get(str(seat))
        
        # Get the view
        cmd = f'cd {REPO} && py -3 simulations/engine/sim.py view --game {GAME} --seat {seat} --token {token}'
        view = run_cmd(cmd)
        
        if view:
            plan = simple_plan(seat, token, view)
            result = submit_plan(seat, token, plan)
            return result and result.get('ok')
    
    return True

# Main loop
max_iterations = 1000
iteration = 0

print(f"Starting game {GAME}...")
while iteration < max_iterations:
    status = get_status()
    print(f"Turn {status.get('turn')}, Phase: {status.get('phase')}, Deck: {status.get('deck_n') if 'deck_n' in status else '?'} cards")
    
    if status.get('phase') == 'over':
        print(f"Game over!")
        break
    
    if status.get('phase') == 'plan':
        if not run_turn():
            print("Failed to submit plan")
            break
    
    iteration += 1
    if iteration > 100:
        print("Max iterations reached")
        break

# Export the game
print("\nExporting game result...")
cmd = f'cd {REPO} && py -3 simulations/engine/sim.py export --game {GAME}'
result = run_cmd(cmd)
if result:
    print(f"Game exported: {result}")
else:
    print("Export failed")

# Get final log
cmd = f'cd {REPO} && py -3 simulations/engine/sim.py log --game {GAME}'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print("\n=== FINAL GAME LOG ===")
print(result.stdout[:2000])  # First 2000 chars

