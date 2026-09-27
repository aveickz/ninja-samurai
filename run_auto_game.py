#!/usr/bin/env python3
"""Auto-play a simulation game with simple strategies."""

import subprocess
import json
import sys

def run_cmd(args):
    """Run a sim.py command and return the parsed JSON output."""
    cmd = ["py", "-3", "simulations/engine/sim.py"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd="C:\\ninja_samurai\\cardboard")
    if result.returncode != 0:
        print(f"Error: {' '.join(cmd)}", file=sys.stderr)
        if result.stderr:
            print(result.stderr[:500], file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        print(f"Output: {result.stdout[:200]}", file=sys.stderr)
        return None

def main():
    game_id = 27
    tokens = {
        "0": "18233e53",
        "1": "08b815d8",
        "2": "443c8e38",
        "3": "489eebed",
        "ref": "9068f1e8"
    }

    print(f"Starting game {game_id}...\n")

    max_iterations = 200
    iteration = 0
    target_reached = False

    while iteration < max_iterations:
        iteration += 1

        # Get current status
        status = run_cmd(["status", "--game", str(game_id)])
        if not status or status.get("over"):
            print(f"\n=== GAME OVER ===")
            break

        phase = status.get("phase")
        turn = status.get("turn", 0)

        # Get public view to see deck count
        player_seat = status.get("seat", 0)
        token = tokens.get(str(player_seat), tokens["0"])
        public = run_cmd(["public", "--game", str(game_id), "--token", token])

        deck_n = public.get("deck_n", 0) if public else 0
        discard_n = public.get("discard_n", 0) if public else 0

        print(f"[Turn {turn:2d}] Phase: {phase:6s} | Deck: {deck_n:3d} | Discard: {discard_n:3d}", end="")

        # Check milestone
        if deck_n <= 100 and not target_reached:
            print(" <- TARGET REACHED (100 cards or less)!", end="")
            target_reached = True

        print()

        if phase == "plan":
            seat = status.get("seat")
            token = tokens[str(seat)]

            # Submit a minimal valid plan (just end turn, no actions)
            plan = {
                "steps": [],
                "end_turn": {},
                "notes": f"Turn {turn}: Auto-player skips"
            }

            result = subprocess.run(
                ["py", "-3", "simulations/engine/sim.py", "plan", "--game", str(game_id),
                 "--seat", str(seat), "--token", token, "--file", "-"],
                input=json.dumps(plan),
                capture_output=True,
                text=True,
                cwd="C:\\ninja_samurai\\cardboard"
            )

            if result.returncode != 0:
                print(f"  Plan submission failed: {result.stderr[:200]}", file=sys.stderr)
                break

            try:
                new_status = json.loads(result.stdout)
                new_phase = new_status.get("phase", "unknown")
                print(f"  P{seat} submitted -> phase now: {new_phase}")
            except:
                print(f"  Plan accepted but couldn't parse response", file=sys.stderr)
                pass

        elif phase == "react":
            reactors = status.get("reactors", [])
            print(f"  Waiting for reactions from: {reactors}")

            for seat in reactors:
                token = tokens.get(str(seat), "invalid")

                # Auto-pass reaction
                reaction = {
                    "action": "pass",
                    "notes": f"Auto-pass"
                }

                result = subprocess.run(
                    ["py", "-3", "simulations/engine/sim.py", "react", "--game", str(game_id),
                     "--seat", str(seat), "--token", token, "--file", "-"],
                    input=json.dumps(reaction),
                    capture_output=True,
                    text=True,
                    cwd="C:\\ninja_samurai\\cardboard"
                )

                if result.returncode == 0:
                    try:
                        new_status = json.loads(result.stdout)
                        new_phase = new_status.get("phase", "?")
                        print(f"    P{seat} reacted -> phase: {new_phase}")
                    except:
                        print(f"    P{seat} reacted (parse failed)")
                        pass
                else:
                    print(f"    P{seat} react failed: {result.stderr[:100]}", file=sys.stderr)

        elif phase == "resolve":
            token = tokens["ref"]

            # Get the pending transaction to understand what needs resolving
            pending = run_cmd(["pending", "--game", str(game_id), "--token", token])

            if pending:
                pend_data = pending.get("pending", {})

                # Create a minimal resolution (just mark as hit with no damage)
                resolve = {
                    "result": "hit",
                    "uses_attack": False,
                    "ops": [],
                    "narrative": "Auto-referee: pass through"
                }

                result = subprocess.run(
                    ["py", "-3", "simulations/engine/sim.py", "resolve", "--game", str(game_id),
                     "--token", token, "--file", "-"],
                    input=json.dumps(resolve),
                    capture_output=True,
                    text=True,
                    cwd="C:\\ninja_samurai\\cardboard"
                )

                if result.returncode == 0:
                    try:
                        new_status = json.loads(result.stdout)
                        new_phase = new_status.get("phase", "?")
                        print(f"  Referee resolved -> phase: {new_phase}")
                    except:
                        print(f"  Resolution submitted")
                        pass
                else:
                    print(f"  Resolve failed: {result.stderr[:200]}", file=sys.stderr)

    print(f"\n=== Stopping after {iteration} iterations ===\n")

    # Export the game
    print("Exporting game...")
    export_result = run_cmd(["export", "--game", str(game_id)])
    if export_result and export_result.get("ok"):
        print("Game exported successfully.\n")

    # Get final status and log
    print("=== FINAL GAME STATE ===")

    # Get public view for final state
    public = run_cmd(["public", "--game", str(game_id), "--token", tokens["0"]])
    if public:
        result = public.get("result")
        if result:
            print(f"Winner: {result.get('winner', '?')}")
            print(f"Reason: {result.get('reason', '?')}")
            score = result.get('score', {})
            if score:
                print(f"Score - Samurai: {score.get('samurai', 0)}, Ninja: {score.get('ninja', 0)}")

        print(f"\nFinal deck: {public.get('deck_n', 0)} cards remaining")
        print(f"Final discard: {public.get('discard_n', 0)} cards")

    print(f"\nGame 27 can be viewed at: simulations/games/game_27.json")

if __name__ == "__main__":
    main()
