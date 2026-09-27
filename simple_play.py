#!/usr/bin/env python3
"""Simple game automation without complex error handling."""

import subprocess
import json
import sys
import os
os.chdir('C:/ninja_samurai/cardboard')

GAME = 21
TOKENS = {
    0: '9e34738f',
    1: '9b994212',
    2: 'd9cbd5f5',
    3: '34181a52',
    'referee': '228998ef'
}

def cmd(args):
    """Run command and return parsed JSON."""
    full = f"py -3 simulations/engine/sim.py {args}"
    r = subprocess.run(full, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR: {r.stderr}", file=sys.stderr)
        return None
    try:
        return json.loads(r.stdout.strip()) if r.stdout else None
    except:
        print(f"PARSE ERROR: {r.stdout[:200]}", file=sys.stderr)
        return None

def submit_plan(seat):
    """Get view and submit a minimal plan with discard-to-limit."""
    view = cmd(f"view --game {GAME} --seat {seat} --token {TOKENS[seat]}")
    if not view:
        return False

    hand = view['view']['you']['hand']
    excess = view['view']['you']['hand_limit_excess']

    plan_file = f"simulations/games/inbox/g{GAME}_s{seat}_auto.json"
    plan = {
        "steps": [],
        "notes": "automated pass"
    }

    if excess > 0 and len(hand) >= excess:
        plan["discard_to_limit"] = [c['uid'] for c in hand[:excess]]

    with open(plan_file, 'w') as f:
        json.dump(plan, f)

    result = cmd(f"plan --game {GAME} --seat {seat} --token {TOKENS[seat]} --file {plan_file}")
    return result and result.get('ok')

def submit_reaction(seat):
    """Get view and submit a simple reaction."""
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

# Play the game
turns = 0
max_turns = 30

while turns < max_turns:
    st = cmd(f"status --game {GAME}")
    if not st or st.get('over'):
        break

    phase = st.get('phase')
    turn = st.get('turn')
    seat = st.get('seat')

    print(f"Turn {turn} Phase {phase} Seat {seat}", file=sys.stderr)

    if phase == 'plan':
        if submit_plan(seat):
            print(f"  ✓", file=sys.stderr)
        else:
            print(f"  ✗ PLAN FAILED, SKIPPING", file=sys.stderr)
            turns += 1
    elif phase == 'react':
        for s in st.get('reactors', []):
            if submit_reaction(s):
                print(f"  ✓ seat {s}", file=sys.stderr)
            else:
                print(f"  ✗ seat {s}", file=sys.stderr)
        turns += 1
    elif phase == 'resolve':
        # skip resolve - we don't have a referee agent
        turns += 1

    turns += 1

# Get final status
final = cmd(f"status --game {GAME}")
print("\n" + "="*60, file=sys.stderr)
print(f"GAME SUMMARY", file=sys.stderr)
print("="*60, file=sys.stderr)

if final:
    print(f"Final status: {json.dumps(final, indent=2)}")
else:
    print("ERROR: Could not get final status")
