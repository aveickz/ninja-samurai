#!/usr/bin/env python3
"""
Fast automated game runner for game 20.
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
    """Submit a minimal pass plan"""
    view = get_view(seat)
    if not view or "error" in view:
        return False

    you = view.get("view", {}).get("you", {})
    plan = {"steps": [], "notes": "pass"}

    # Only add discard_to_limit if needed
    if you.get("hand_limit_excess", 0) > 0:
        hand = you.get("hand", [])
        excess = you.get("hand_limit_excess", 0)
        to_discard = [c.get("uid") for c in hand[-excess:] if excess <= len(hand)]
        if to_discard:
            plan["discard_to_limit"] = to_discard

    # Only add recovery if needed
    if you.get("needs_recovery"):
        plan["recovery"] = {"discard": []}

    plan_file = f"{INBOX}/g{GAME}_s{seat}_plan.json"
    with open(plan_file, 'w') as f:
        json.dump(plan, f)

    result = run_cmd(f"{SIM} plan --game {GAME} --seat {seat} --file {plan_file}")
    return result and result.get("ok")

def submit_react(seat):
    """Submit default reaction"""
    pending = get_pending()
    if not pending:
        return False

    trans = pending.get("pending", {}).get("transaction", {})
    your_role = pending.get("pending", {}).get("your_role", "")
    action = "take" if your_role == "defender" else "pass"

    reaction = {"action": action, "notes": "auto"}

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

    trans = pending.get("pending", {}).get("transaction", {})
    trans_type = trans.get("type")

    if trans_type == "attack":
        resolution = {
            "result": "hit",
            "uses_attack": True,
            "ops": [{
                "op": "damage",
                "seat": trans.get("target"),
                "n": trans.get("base_power", 1),
                "source": "attack",
                "by": trans.get("actor")
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

print(f"Playing game {GAME}...\n")
max_iter = 200
last_turn = 0
failed_count = 0

for i in range(max_iter):
    status = get_status()
    if not status:
        print("ERROR: Cannot get status")
        break

    phase = status.get("phase")
    turn = status.get("turn")
    over = status.get("over")
    seat = status.get("seat")

    if turn != last_turn:
        print(f"Turn {turn:3d}, Phase: {phase:7s}")
        last_turn = turn

    if over:
        print("\nGAME OVER")
        break

    try:
        if phase == "plan":
            if not submit_plan(seat):
                failed_count += 1
                if failed_count > 3:
                    print(f"ERROR: plan failed too many times")
                    break
        elif phase == "react":
            for reactor in status.get("reactors", []):
                if not submit_react(reactor):
                    print(f"ERROR: react failed for seat {reactor}")
                    failed_count += 1
                    if failed_count > 3:
                        break
        elif phase == "resolve":
            if not submit_resolve():
                print(f"ERROR: resolve failed")
                failed_count += 1
                if failed_count > 3:
                    break
        else:
            print(f"Unknown phase: {phase}")
            break
    except Exception as e:
        print(f"Exception: {e}")
        break

# Get final status and show results
print("\n=== Final Game Status ===")
final = get_status()
print(json.dumps(final, indent=2))

# Export and get log
print("\nExporting game...")
run_cmd(f"{SIM} export --game {GAME}")

log_out = subprocess.run(f"cd {REPO} && {SIM} log --game {GAME}", shell=True, capture_output=True, text=True)
print("\n=== Game Log ===")
print(log_out.stdout if log_out.stdout else "(no log)")

print("\n=== Done ===")
