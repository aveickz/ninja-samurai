#!/usr/bin/env python3
import subprocess, json, os

GAME, TOKENS = 8, {"0": "faeb6de1", "1": "ab49e442", "2": "b8079cc2", "3": "81322cda"}
REPO = "C:/ninja_samurai/cardboard"

def run_cmd(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO)
    try: return json.loads(r.stdout.strip())
    except: return None

def get_status():
    return run_cmd(f'py -3 simulations/engine/sim.py status --game {GAME}')

def submit_plan(seat, token):
    plan = {"discard_to_limit": [], "steps": [], "end_turn": {}, "notes": "pass"}
    inbox = f"{REPO}/simulations/games/inbox"
    os.makedirs(inbox, exist_ok=True)
    with open(f"{inbox}/g{GAME}_s{seat}_plan.json", 'w') as f:
        json.dump(plan, f)
    cmd = f'py -3 simulations/engine/sim.py plan --game {GAME} --seat {seat} --token {token} --file {inbox}/g{GAME}_s{seat}_plan.json'
    return run_cmd(cmd)

print(f"Running game {GAME}...")
for i in range(200):
    st = get_status()
    if not st: break
    phase, turn, deck = st.get('phase'), st.get('turn'), st.get('deck_n', '?')
    print(f"T{turn} Phase={phase} Deck={deck} cards", flush=True)
    if phase == 'over': break
    if phase == 'plan':
        seat, token = st.get('seat'), TOKENS.get(str(st.get('seat')))
        res = submit_plan(seat, token)
        if not (res and res.get('ok')): 
            print(f"Error: {res}")
            break

print("\nGame complete! Exporting...")
os.system(f'cd {REPO} && py -3 simulations/engine/sim.py export --game {GAME} 2>nul')

# Show result
print("\n=== FINAL RESULT ===")
os.system(f'cd {REPO} && py -3 simulations/engine/sim.py log --game {GAME} | tail -30')

