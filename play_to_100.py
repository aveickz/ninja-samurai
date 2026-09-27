#!/usr/bin/env python3
"""Play game 27 until 100 cards remain in deck."""
import subprocess, json, sys

GAME = 27
TOKENS = {"0": "18233e53", "1": "08b815d8", "2": "443c8e38", "3": "489eebed", "ref": "9068f1e8"}

def cmd(args):
    """Run sim.py command."""
    r = subprocess.run(["py", "-3", "simulations/engine/sim.py"] + args,
                       capture_output=True, text=True, cwd="C:\\ninja_samurai\\cardboard")
    try:
        return json.loads(r.stdout) if r.returncode == 0 else None
    except:
        return None

def get_deck():
    """Get current deck count."""
    pub = cmd(["public", "--game", str(GAME), "--token", TOKENS["0"]])
    return pub.get("deck_n", 0) if pub else 0

def play_auto_turn(seat, token):
    """Get player view and submit a simple plan."""
    # Get player's view
    view = cmd(["view", "--game", str(GAME), "--seat", str(seat), "--token", token])
    if not view:
        print(f"  P{seat}: Failed to get view", file=sys.stderr)
        return False

    you = view.get("you", {})
    hand = you.get("hand", [])
    excess = you.get("hand_limit_excess", 0)

    plan = {"steps": [], "end_turn": {}, "notes": f"P{seat}: auto turn"}

    # Add discard_to_limit if needed
    if excess > 0:
        cards_to_discard = [card["uid"] for card in hand[:excess]]
        plan["discard_to_limit"] = cards_to_discard

    # Submit plan
    input_json = json.dumps(plan)
    r = subprocess.run(
        ["py", "-3", "simulations/engine/sim.py", "plan",
         "--game", str(GAME), "--seat", str(seat), "--token", token, "--file", "-"],
        input=input_json, capture_output=True, text=True,
        cwd="C:\\ninja_samurai\\cardboard"
    )

    if r.returncode == 0:
        status = json.loads(r.stdout)
        print(f"  P{seat} -> phase {status.get('phase')}")
        return True
    else:
        errors = json.loads(r.stdout).get("errors", []) if r.stdout else []
        print(f"  P{seat} plan failed: {errors[0] if errors else 'unknown'}", file=sys.stderr)
        return False

def auto_react(seat, token):
    """Auto-react: pass."""
    react = {"action": "pass"}
    r = subprocess.run(
        ["py", "-3", "simulations/engine/sim.py", "react",
         "--game", str(GAME), "--seat", str(seat), "--token", token, "--file", "-"],
        input=json.dumps(react), capture_output=True, text=True,
        cwd="C:\\ninja_samurai\\cardboard"
    )
    return r.returncode == 0

def auto_resolve():
    """Auto-resolve: simple hit."""
    resolve = {"result": "hit", "uses_attack": False, "ops": []}
    r = subprocess.run(
        ["py", "-3", "simulations/engine/sim.py", "resolve",
         "--game", str(GAME), "--token", TOKENS["ref"], "--file", "-"],
        input=json.dumps(resolve), capture_output=True, text=True,
        cwd="C:\\ninja_samurai\\cardboard"
    )
    return r.returncode == 0

# Main loop
print(f"Playing game {GAME} until 100 cards remain...\n")
target_reached = False

for i in range(200):
    stat = cmd(["status", "--game", str(GAME)])
    if not stat or stat.get("over"):
        print(f"\nGame over!")
        break

    phase = stat.get("phase", "?")
    turn = stat.get("turn", 0)
    deck = get_deck()

    print(f"T{turn:2d} Phase {phase:6s} Deck {deck:3d}", end="")
    if deck <= 100:
        if not target_reached:
            print(" *** TARGET HIT ***", end="")
            target_reached = True
    print()

    if phase == "plan":
        play_auto_turn(stat.get("seat", 0), TOKENS[str(stat.get("seat", 0))])
    elif phase == "react":
        for seat in stat.get("reactors", []):
            auto_react(seat, TOKENS[str(seat)])
    elif phase == "resolve":
        auto_resolve()

# Export and show result
print("\nExporting...")
cmd(["export", "--game", str(GAME)])

# Show final result
pub = cmd(["public", "--game", str(GAME), "--token", TOKENS["0"]])
if pub and pub.get("result"):
    r = pub["result"]
    print(f"\nWINNER: {r.get('winner', '?').upper()}")
    print(f"Score: {r.get('score', {})}")
    print(f"Final deck: {pub.get('deck_n', 0)} cards")
    print(f"Turns played: {pub.get('turns_played', stat.get('turn', 0)) if pub else stat.get('turn', 0)}")
