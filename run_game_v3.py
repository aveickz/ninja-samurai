#!/usr/bin/env python3
import subprocess, json, os

GAME, TOKENS = 8, {"0": "faeb6de1", "1": "ab49e442", "2": "b8079cc2", "3": "81322cda"}
REPO = "C:/ninja_samurai/cardboard"

def run_cmd(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO)
    try: return json.loads(r.stdout.strip())
    except: return None

def get_view(seat, token):
    return run_cmd(f'py -3 simulations/engine/sim.py view --game {GAME} --seat {seat} --token {token}')

def submit_plan(seat, token):
    view = get_view(seat, token)
    hand_limit_excess = view.get('you', {}).get('hand_limit_excess', 0) if view else 0
    hand = view.get('you', {}).get('hand', []) if view else []
    
    plan = {"discard_to_limit": [], "steps": [], "end_turn": {}, "notes": "pass"}
    if hand_limit_excess > 0:
        plan["discard_to_limit"] = [c['uid'] for c in hand[:hand_limit_excess]]
    
    inbox = f"{REPO}/simulations/games/inbox"
    os.makedirs(inbox, exist_ok=True)
    pf = f"{inbox}/g{GAME}_s{seat}_plan.json"
    with open(pf, 'w') as f: json.dump(plan, f)
    return run_cmd(f'py -3 simulations/engine/sim.py plan --game {GAME} --seat {seat} --token {token} --file {pf}')

print(f"Running game {GAME}...")
for i in range(300):
    st = run_cmd(f'py -3 simulations/engine/sim.py status --game {GAME}')
    if not st: break
    phase, turn = st.get('phase'), st.get('turn')
    print(f"T{turn} Phase={phase}", flush=True)
    if phase == 'over': break
    if phase == 'plan':
        seat, token = st.get('seat'), TOKENS.get(str(st.get('seat')))
        res = submit_plan(seat, token)
        if not (res and res.get('ok')): 
            print(f"Error: {res}")
            break

print("Exporting...")
os.system(f'cd {REPO} && py -3 simulations/engine/sim.py export --game {GAME} 2>nul')

# Load and show result
import glob
gf = glob.glob(f'{REPO}/simulations/games/game_{GAME}.json')
if gf:
    with open(gf[0]) as f:
        d = json.load(f)
        result = d.get('game', {})
        print("\n=== GAME RESULT ===")
        print(f"Players: {result.get('players_n')}")
        print(f"Turns played: {result.get('turns_played')}")
        print(f"Result: {result.get('result')}")
        if result.get('players'):
            print("\nFinal standings:")
            for p in result['players']:
                print(f"  {p['name']} ({p['character']['name']}): {p.get('vp', '?')} VP")
