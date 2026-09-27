#!/usr/bin/env python3
"""Simple game auto-player."""
import subprocess
import json

GAME_ID = 27
TOKENS = {"0": "18233e53", "1": "08b815d8", "2": "443c8e38", "3": "489eebed", "ref": "9068f1e8"}

def cmd(args):
    r = subprocess.run(["py", "-3", "simulations/engine/sim.py"] + args,
                       capture_output=True, text=True, cwd="C:\\ninja_samurai\\cardboard")
    return json.loads(r.stdout) if r.returncode == 0 else None

def get_deck_info():
    pub = cmd(["public", "--game", str(GAME_ID), "--token", TOKENS["0"]])
    if pub:
        return pub.get("deck_n", 0), pub.get("discard_n", 0)
    return None, None

# Play the game
for i in range(150):
    stat = cmd(["status", "--game", str(GAME_ID)])
    if not stat or stat.get("over"):
        break

    phase = stat.get("phase", "?")
    turn = stat.get("turn", 0)
    deck, discard = get_deck_info()

    print(f"Turn {turn:3d} | Phase {phase:6s} | Deck {deck:3d}", end="")

    if deck is not None and deck <= 100 and i > 20:
        print(" *** TARGET ***", end="")
    print()

    if phase == "plan":
        seat = stat.get("seat", 0)
        plan = {"steps": [], "end_turn": {}, "notes": f"T{turn}"}
        r = subprocess.run(
            ["py", "-3", "simulations/engine/sim.py", "plan",
             "--game", str(GAME_ID), "--seat", str(seat),
             "--token", TOKENS[str(seat)], "--file", "-"],
            input=json.dumps(plan), capture_output=True, text=True,
            cwd="C:\\ninja_samurai\\cardboard"
        )
    elif phase == "react":
        for seat in stat.get("reactors", []):
            react = {"action": "pass"}
            r = subprocess.run(
                ["py", "-3", "simulations/engine/sim.py", "react",
                 "--game", str(GAME_ID), "--seat", str(seat),
                 "--token", TOKENS[str(seat)], "--file", "-"],
                input=json.dumps(react), capture_output=True, text=True,
                cwd="C:\\ninja_samurai\\cardboard"
            )
    elif phase == "resolve":
        res = {"result": "hit", "uses_attack": False, "ops": []}
        r = subprocess.run(
            ["py", "-3", "simulations/engine/sim.py", "resolve",
             "--game", str(GAME_ID), "--token", TOKENS["ref"], "--file", "-"],
            input=json.dumps(res), capture_output=True, text=True,
            cwd="C:\\ninja_samurai\\cardboard"
        )

# Export and show result
cmd(["export", "--game", str(GAME_ID)])
pub = cmd(["public", "--game", str(GAME_ID), "--token", TOKENS["0"]])
if pub and pub.get("result"):
    print(f"\n=== GAME OVER ===")
    print(f"Winner: {pub['result'].get('winner', '?')}")
    print(f"Score: {pub['result'].get('score', {})}")
    print(f"Reason: {pub['result'].get('reason', '?')}")
    print(f"Cards remaining: {pub.get('deck_n', 0)}")
