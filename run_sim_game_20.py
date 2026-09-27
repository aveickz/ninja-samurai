#!/usr/bin/env python3
"""
Fast automated game runner - minimal output, focuses on speed.
"""
import subprocess
import json
import os

GAME = 20
REPO = "C:/ninja_samurai/cardboard"
INBOX = f"{REPO}/simulations/games/inbox"
SIM = f"py -3 {REPO}/simulations/engine/sim.py"

os.makedirs(INBOX, exist_ok=True)

def run_cmd(cmd):
    """Run command and return JSON result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=REPO)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout.strip())
    except:
        return None

def get_status():
    return run_cmd(f"{SIM} status --game {GAME}")

def get_view(seat):
    return run_cmd(f"{SIM} view --game {GAME} --seat {seat}")

def get_pending():
    return run_cmd(f"{SIM} pending --game {GAME}")

def submit_plan(seat):
    """Submit a simple pass plan"""
    view = get_view(seat)
    if not view:
        return False

    you = view.get("you", {})

    plan = {
        "discard_to_limit": [],
        "steps": [],
        "end_turn": {},
        "notes": "Pass"
    }

    # Handle hand limit
    hand = you.get("hand", [])
    if you.get("hand_limit_excess", 0) > 0:
        excess = you.get("hand_limit_excess", 0)
        cards_to_discard = [c.get("uid") for c in hand[-excess:] if excess <= len(hand)]
        plan["discard_to_limit"] = cards_to_discard

    if you.get("needs_recovery"):
        plan["recovery"] = {"discard": []}

    plan_file = f"{INBOX}/g{GAME}_s{seat}_plan.json"
    with open(plan_file, 'w') as f:
        json.dump(plan, f)

    result = run_cmd(f"{SIM} plan --game {GAME} --seat {seat} --file {plan_file}")
    return result and result.get("ok")

def submit_react(seat, pending):
    """Submit default reaction"""
    your_role = pending.get("your_role", "")
    action = "take" if your_role == "defender" else "pass"

    reaction = {"action": action, "notes": "Auto"}

    react_file = f"{INBOX}/g{GAME}_s{seat}_react.json"
    with open(react_file, 'w') as f:
        json.dump(reaction, f)

    result = run_cmd(f"{SIM} react --game {GAME} --seat {seat} --file {react_file}")
    return result and result.get("ok")

def submit_resolve():
    """Submit default resolution"""
    pending = get_pending()
    if not pending:
        return False

    transaction = pending.get("transaction", {})
    trans_type = transaction.get("type")

    if trans_type == "attack":
        resolution = {
            "result": "hit",
            "uses_attack": True,
            "ops": [{
                "op": "damage",
                "seat": transaction.get("target"),
                "n": transaction.get("base_power", 1),
                "source": "attack",
                "by": transaction.get("actor")
            }],
            "narrative": "Hit",
            "rulings": []
        }
    else:
        resolution = {
            "result": "resolved",
            "uses_attack": False,
            "ops": [],
            "narrative": "Resolved",
            "rulings": []
        }

    resolve_file = f"{INBOX}/g{GAME}_force_resolve.json"
    with open(resolve_file, 'w') as f:
        json.dump(resolution, f)

    result = run_cmd(f"{SIM} resolve --game {GAME} --file {resolve_file}")
    return result and result.get("ok")

# Main loop
print(f"Running game {GAME}...")
max_iter = 300
last_turn = 0

for i in range(max_iter):
    status = get_status()
    if not status:
        print("ERROR: Cannot get status")
        break

    phase = status.get("phase")
    turn = status.get("turn")
    over = status.get("over")

    if turn != last_turn:
        print(f"Turn {turn:3d}, Phase: {phase}")
        last_turn = turn

    if over:
        print("GAME OVER")
        break

    if phase == "plan":
        seat = status.get("seat")
        if not submit_plan(seat):
            print(f"ERROR: plan failed for seat {seat}")
            break
    elif phase == "react":
        pending = get_pending()
        for reactor in status.get("reactors", []):
            if not submit_react(reactor, pending):
                print(f"ERROR: react failed for seat {reactor}")
                break
    elif phase == "resolve":
        if not submit_resolve():
            print(f"ERROR: resolve failed")
            break

# Get final status and export
print("\n--- Final Status ---")
status = get_status()
print(json.dumps(status, indent=2))

print("\n--- Exporting ---")
export_result = run_cmd(f"{SIM} export --game {GAME}")
print("Export completed")

# Print the game log
print("\n--- Game Log (first 2000 chars) ---")
log = subprocess.run(f"cd {REPO} && {SIM} log --game {GAME}", shell=True, capture_output=True, text=True)
print(log.stdout[:2000])

print("\n--- Done ---")
