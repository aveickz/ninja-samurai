#!/usr/bin/env python3
import subprocess, json, sys, os
os.chdir('C:/ninja_samurai/cardboard')

GAME = 23
TOKENS = {
    0: 'd4be7df2',
    1: '41f6fd82',
    2: '3ff6c6e1',
    3: '2f7673a4',
    'referee': '4d3a1529'
}

def cmd(args):
    full = f"py -3 simulations/engine/sim.py {args}"
    r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout.strip()) if r.stdout else None
    except:
        return None

def submit_plan(seat):
    view = cmd(f"view --game {GAME} --seat {seat} --token {TOKENS[seat]}")
    if not view:
        return False

    hand = view['view']['you']['hand']
    excess = view['view']['you']['hand_limit_excess']

    plan_file = f"simulations/games/inbox/g{GAME}_s{seat}_auto.json"
    plan = {"steps": [], "notes": "automated pass"}

    if excess > 0 and len(hand) >= excess:
        plan["discard_to_limit"] = [c['uid'] for c in hand[:excess]]

    with open(plan_file, 'w') as f:
        json.dump(plan, f)

    result = cmd(f"plan --game {GAME} --seat {seat} --token {TOKENS[seat]} --file {plan_file}")
    return result and result.get('ok')

def submit_reaction(seat):
    view = cmd(f"view --game {GAME} --seat {seat} --token {TOKENS[seat]}")
    if not view:
        return False

    pending = view['view'].get('pending', {})
    your_role = pending.get('your_role', 'other')

    reaction = {
        "action": "take" if your_role == "defender" else "pass",
        "cards": [],
        "trap": None,
        "when": None,
        "target": None,
        "choice": None,
        "consent": {"share_wounds": False, "take_attack": False},
        "notes": "automated"
    }

    react_file = f"simulations/games/inbox/g{GAME}_s{seat}_auto.json"
    with open(react_file, 'w') as f:
        json.dump(reaction, f)

    result = cmd(f"react --game {GAME} --seat {seat} --token {TOKENS[seat]} --file {react_file}")
    return result and result.get('ok')

turns = 0
while turns < 300:
    st = cmd(f"status --game {GAME}")
    if not st or st.get('over'):
        break

    phase = st.get('phase')
    turn = st.get('turn')
    seat = st.get('seat')

    print(f"T{turn:2d} {phase:10s} S{seat}", file=sys.stderr, end='  ')

    if phase == 'plan':
        submit_plan(seat)
        print("✓", file=sys.stderr)
    elif phase == 'react':
        for s in st.get('reactors', []):
            submit_reaction(s)
        print("✓", file=sys.stderr)
    elif phase == 'resolve':
        print("-", file=sys.stderr)

    turns += 1

final = cmd(f"status --game {GAME}")
print("\n" + "="*70)
print(json.dumps(final, indent=2))
