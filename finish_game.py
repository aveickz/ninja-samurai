#!/usr/bin/env python3
"""Rapidly finish game 27 to reach 100 cards in deck."""
import subprocess, json

G = 27
T = {"0": "18233e53", "1": "08b815d8", "2": "443c8e38", "3": "489eebed", "ref": "9068f1e8"}

def cmd(args):
    r = subprocess.run(["py", "-3", "simulations/engine/sim.py"] + args,
                      capture_output=True, text=True, cwd="C:\\ninja_samurai\\cardboard")
    return json.loads(r.stdout) if r.returncode == 0 else None

def submit_plan(seat, token):
    v = cmd(["view", "--game", str(G), "--seat", str(seat), "--token", token])
    if not v:
        return False
    y = v.get("you", {})
    plan = {"steps": [], "end_turn": {}, "notes": "auto"}
    excess = y.get("hand_limit_excess", 0)
    if excess > 0:
        hand = y.get("hand", [])
        plan["discard_to_limit"] = [c["uid"] for c in hand[:excess]]
    r = subprocess.run(
        ["py", "-3", "simulations/engine/sim.py", "plan", "--game", str(G),
         "--seat", str(seat), "--token", token, "--file", "-"],
        input=json.dumps(plan), capture_output=True, text=True,
        cwd="C:\\ninja_samurai\\cardboard"
    )
    return r.returncode == 0

def get_deck():
    p = cmd(["public", "--game", str(G), "--token", T["0"]])
    return p.get("deck_n", 0) if p else 0

print("Finishing game 27...\n")
for i in range(300):
    s = cmd(["status", "--game", str(G)])
    if not s or s.get("over"):
        print("Game over")
        break

    phase = s.get("phase", "?")
    turn = s.get("turn", 0)
    deck = get_deck()

    if i % 20 == 0:  # Print every 20 iterations
        print(f"T{turn:3d} {phase:6s} Deck {deck:3d}", end="")
        if deck <= 100:
            print(" *** TARGET ***", end="")
        print()

    if phase == "plan":
        submit_plan(s.get("seat", 0), T[str(s.get("seat", 0))])
    elif phase == "react":
        for seat in s.get("reactors", []):
            react = {"action": "pass"}
            subprocess.run(
                ["py", "-3", "simulations/engine/sim.py", "react", "--game", str(G),
                 "--seat", str(seat), "--token", T[str(seat)], "--file", "-"],
                input=json.dumps(react), capture_output=True,
                cwd="C:\\ninja_samurai\\cardboard"
            )
    elif phase == "resolve":
        subprocess.run(
            ["py", "-3", "simulations/engine/sim.py", "resolve", "--game", str(G),
             "--token", T["ref"], "--file", "-"],
            input=json.dumps({"result": "hit", "uses_attack": False, "ops": []}),
            capture_output=True, cwd="C:\\ninja_samurai\\cardboard"
        )

cmd(["export", "--game", str(G)])
print("\nFinal result:")
pub = cmd(["public", "--game", str(G), "--token", T["0"]])
if pub:
    if pub.get("result"):
        r = pub["result"]
        print(f"Winner: {r.get('winner')}")
        print(f"Score: {r.get('score')}")
        print(f"Reason: {r.get('reason')}")
    print(f"Deck: {pub.get('deck_n')} cards remaining")
    print(f"Turns: {pub.get('turns_played', 'unknown')}")
