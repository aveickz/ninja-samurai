# Simulation — LLM playtests of «Samurai vs Ninja»

> Симуляция партий силами LLM-агентов: скрипт-арбитр на Python + SQLite ведёт
> колоду и стол, судья-агент трактует тексты карт, игроки-агенты видят только свою
> руку и открытый стол. Весь стек — на английском: вход — `enDesc` из `js/cards.js`
> и `rules/content-en.html`. Этот файл — манифест: зачем, как устроено, протокол
> обмена JSON, как запускать и как читать результаты. Артефакты — в `simulations/`.

## 1. Purpose

The simulation exists to answer design questions about cards, not to win games:

- **Power.** Which cards swing life / victory points the most per play? Which never
  matter? (wounds dealt, wounds prevented, VP transferred, cards gained)
- **Interest.** Which cards are held in hand for many turns and never played
  («dead cards», meta-rule №6)? Which cards create reactions from other players
  (interventions, group answers) and which are played in silence?
- **Clarity.** Where does the referee have to make a ruling because the card text
  is ambiguous, or where do players misread a card (rejected actions)?
- **Faction tilt.** Who wins, by how much, and through which cards.

Inputs are deliberately minimal: the card texts (English) and the current English
rules. Art, icons as pictures and the Russian originals are out of scope. When the
English text is wrong, the fix goes to the Russian original first (see CLAUDE.md,
«Источники правды»).

## 2. Architecture

Three kinds of participants, communicating only through JSON messages, plus a
deterministic bookkeeper that owns the truth of the table.

```
                    ┌──────────────────────────────┐
                    │  orchestrator (Workflow)      │  decides WHO acts next,
                    │  simulations/workflow/play.js │  spawns agents, no game logic
                    └───────┬───────────┬───────────┘
                            │           │
             ┌──────────────▼──┐   ┌────▼────────────────┐
             │ player agent    │   │ referee agent        │  full rules, all hands,
             │ own hand +      │   │ resolves one          │  writes `ops`
             │ public table    │   │ transaction at a time │
             └──────┬──────────┘   └────┬────────────────┘
                    │  plan / react       │  resolve (ops)
                    ▼                     ▼
             ┌────────────────────────────────────────────┐
             │ sim.py  — the bookkeeper (Python + SQLite)  │
             │ shuffle, deal, draw, zones, HP/VP, poison,  │
             │ validation, turn/phase machine, event log,  │
             │ per-player views (information hiding),      │
             │ history export, aggregate report            │
             └────────────────────────────────────────────┘
```

- **`sim.py`** (`simulations/engine/sim.py`) is the only thing that mutates state.
  It knows the *mechanics* (zones, counters, turn order, draw phase, poison tick,
  death and victory points, end conditions) and a small static table of numeric
  card modifiers (complexity, attack power). It does **not** interpret free card
  text; everything text-dependent goes to the referee.
- **Player agents** are fresh LLM contexts. They get `sim.py view` — their own hand
  plus the public table — and answer with a JSON *plan* (their whole turn) or a
  JSON *reaction* (defense / intervention / answer to a group card). Information
  hiding is enforced by construction: the view is all they are given.
- **The referee agent** is a fresh LLM context with the full English rules, the
  open transaction with every card text involved, both sides of the table
  (including face-down traps and hands) and the bookkeeper's baseline
  calculation. It answers with a JSON list of **ops** (damage, heal, move card…)
  that `sim.py` validates and applies atomically.
- **The orchestrator** is a Workflow script. It reads `sim.py status` (returned by
  each agent) and spawns the next agent: `plan` → active player, `react` → the
  listed reactors in parallel, `resolve` → referee, `over` → stop. It holds no
  game state.

Why an LLM referee and not a rules engine: ~180 card kinds with free-text effects.
Coding them is a multi-week project; the referee gets a pilot running today, and
every ruling it makes is logged, so the ambiguous texts surface as data. When a
card family stabilises, its resolution can be moved into `card_rules.py`.

## 3. Data

### 3.1 Card export

`node simulations/engine/export_cards.mjs` evaluates `js/cards.js` and writes
`simulations/data/cards.json` — English fields only:

```json
{"id": 1, "name": "Katana", "types": ["weapon"], "group": "weapon", "qty": 2,
 "icons": ["complexity1", "dmg2"], "icons_or": null, "tags": [],
 "text": "While you hold a Stance, deal 1 extra wound.", "hp": null, "subtitle": null}
```

`text` is `enDesc` with `[NL]` → newline, `-OR-` kept as a literal separator
between two modes, `{…}` braces kept (they mark conditions and named things).

### 3.2 Deck composition

- Deck = every card whose `group` is not `role` / `character`, whose `tags` contain
  neither `trash` nor `draft` (`--include-drafts` adds drafts), repeated `qty` times.
- Characters = the 9 `character` cards without `trash`; each player draws one at
  random. Roles are virtual (faction on the player record).
- Every physical copy has a **uid** `c<id>-<n>`: `c48-3` is the third Parry.
  Uids are what messages refer to; card ids are what the report aggregates.

### 3.3 Player and seating

4 players by default, seats 0..3 clockwise, factions alternate
`samurai, ninja, samurai, ninja`. Seat 0 is the samurai with the «I» banner: the
game and every round start with them. Names are `P0..P3`; the character name is
shown next to it everywhere.

Start: character HP, 4 victory points, 7 cards each.

## 4. Game model

State lives as one JSON document per game in SQLite (`games.state_json`), with an
append-only `events` table (one row per thing that happened, with a compact public
snapshot after it) and a `messages` table (every JSON message accepted from an
agent, verbatim).

```json
{
  "game_id": 1, "seed": 1, "players_n": 4, "max_turns": 10, "include_drafts": false,
  "turn": 3, "active": 2, "phase": "plan",
  "final_turn": null, "status": "running", "result": null,
  "deck": ["c48-1", "…"], "discard": [], "removed": [],
  "players": [
    {"seat": 0, "name": "P0", "faction": "samurai", "first": true, "character": 137,
     "hp": 6, "max_hp": 6, "vp": 4, "poisoned": false, "alive": true,
     "died_turn": null, "poison_death": false, "needs_recovery": false,
     "hand": ["c1-1"], "stance": "c58-1", "trap": {"uid": "c41-1", "face_up": false},
     "aura": {"uid": "c1202-1", "charges": [], "in_front_of": 0}, "effects": ["c91-1"],
     "attacks_used": 0, "stance_played": false, "trap_set": false, "aura_played": false,
     "flags": {}}
  ],
  "plan": {"seat": 2, "steps": [], "cursor": 0, "end_turn": {}},
  "pending": null,
  "seq": 57, "rng_state": []
}
```

`pending` is the open **transaction** (§6). `plan` is the active player's submitted
turn, executed step by step by `sim.py` (§5.2).

### 4.1 Phases

| phase     | meaning                                                          | who acts          |
|-----------|------------------------------------------------------------------|-------------------|
| `plan`    | the active player must submit a plan (or a continuation)         | player `seat`     |
| `react`   | a transaction is open and waits for the listed `reactors`        | each reactor      |
| `resolve` | all reactions are in (or none were needed); the referee resolves | referee           |
| `over`    | the game has ended                                               | nobody            |

`sim.py status --game N` prints the phase and who is expected:

```json
{"game": 1, "turn": 3, "phase": "react", "seat": 2, "pending_id": 12, "reactors": [3, 1], "over": false}
```

## 5. The turn

### 5.1 What the bookkeeper does by itself

- **Turn start.** Every dead player whose `died_turn < turn` revives with **full
  life** (assumption A1, §8). A player whose `stance` is «Shadow» discards it at the
  start of their own turn. Attack counters and once-per-turn flags reset.
- **Recovery / hand limit** are decisions, so they come in the plan: `recovery`
  (if the active player died since their last turn and was not killed by poison —
  discard any number, then draw back up to 7) and `discard_to_limit` (mandatory
  when the hand exceeds 9).
- **End of turn**, in this order: `end_turn` choices from the plan (Lotus: heal 1
  or draw 1); poison tick on the active player (−2 life; ×2 under Snakebite; 0 for
  Minamoto) with death handling (point to the discard, no recovery); draw phase:
  active draws 3 + character bonuses (Taranaga +1, Saigo +1 per Stance on the
  table up to 3, Iyo +1 per Trap up to 3, Minamoto +1 per poisoned player up to 3),
  then every living player of the opposing team draws 1. Drawing from an empty deck
  gives nothing and marks `final_turn`.
- **End conditions**, checked after every op and at the end of the turn: any
  player at 0 VP → over; `final_turn` reached and the turn ended → over;
  `turn == max_turns` and the turn ended → over. Score = team VP + 1 per Magatama
  held in hand. Ties are reported as ties.
- **Death** (from any op): victim `vp −1`; if the killer (`by`) is a living player
  of the other faction and the source is not poison → killer `vp +1`, otherwise the
  point goes to the discard. Stance, Trap, Aura (with charges) and Effects go to the
  discard; poison is cleared; `alive=false`, `died_turn=turn`,
  `needs_recovery=true` (false for poison deaths). Dead players cannot be targeted.
  The character's «After your death» text is shown to the referee, who applies it
  in the same ops list.

### 5.2 The plan (player → `sim.py plan`)

The active player submits their **whole turn** in one message. `sim.py` validates
everything it can up front (cards in hand, targets alive, counters, complexity) and
rejects the whole plan with a list of errors if anything is structurally wrong —
the agent fixes and resubmits in the same session. Then it executes steps in order:

```json
{
  "discard_to_limit": ["c48-2"],
  "recovery": {"discard": ["c22-1"]},
  "steps": [
    {"do": "stance", "card": "c58-1"},
    {"do": "trap",   "card": "c41-1"},
    {"do": "aura",   "card": "c1202-1", "in_front_of": null},
    {"do": "charge_aura", "card": "c65-1", "aura_owner": 0},
    {"do": "attack", "card": "c1-2", "mode": "main", "target": 3, "modifier": "c65-1", "note": "…"},
    {"do": "attack", "mode": "bare", "target": 1},
    {"do": "effect", "card": "c91-1", "target": 3},
    {"do": "play",   "card": "c82-1", "target": null, "mode": null, "choice": "…",
                     "reactors": "others", "ask": "Discard a Defense or a Weapon, or hand me a card of your choice."},
    {"do": "ability", "source": "character", "choice": "restore 1 life", "target": 2},
    {"do": "trade",  "discard": ["c48-1", "c51-1"]},
    {"do": "replan"}
  ],
  "end_turn": {"lotus": "heal", "target": 2},
  "notes": "why this turn — one or two sentences, kept for analysis"
}
```

Every step may (and, for the LLM players, must) carry `"why": "<short phrase>"` —
the thought behind that very move. The bookkeeper copies it into the `notes` of
the events that move produces (`attack_declared`, `stance_set`, `trap_set`,
`aura_set`, `aura_charged`, `effect_placed`, `card_played`, `ability_used`,
`trade`, `step_skipped`); a reaction's `notes` lands on its `reaction` event the
same way. So the history carries, next to each move, the player's own words —
repetitive, but honest — for the viewer and for the analysis of why a card was
or was not played.

| step          | mechanical? | rules enforced by `sim.py`                                                                                                                                                                                                                                                                                                                                       |
|---------------|-------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `stance`      | yes         | once per turn; card has type `stance`; old stance returns to hand                                                                                                                                                                                                                                                                                                 |
| `trap`        | yes         | once per turn; **any** card may go face down (bluffing is legal, dying on reveal is the price); old trap returns to hand                                                                                                                                                                                                                                          |
| `aura`        | yes         | once per turn; type `aura`; old aura returns to hand, its charges go to the discard (A4); Taranaga may set `in_front_of` any living player                                                                                                                                                                                                                         |
| `charge_aura` | yes         | aura with the `charges` icon on an ally's table; card type matches the aura's named type (table in `card_rules.py`)                                                                                                                                                                                                                                              |
| `trade`       | yes         | two cards sharing a type → draw 1; two cards with the same id → draw 2                                                                                                                                                                                                                                                                                             |
| `attack`      | opens a transaction | `attacks_used < attacks_max` (2, −1 under Exhaustion, 3 for a poisoned Minamoto; `bare` costs both); card has type `weapon` (or `mode: "bare"`, power 1, Saigo 2); `mode: "or"` needs `icons_or`; `modifier` is a `modifier` card, or Wakizashi on a Katana, or Renkei; Teppo Yumi needs a modifier; target alive, not self, not under Shadow; complexity check (§5.4); Disarm / Puncture Wounds / Dust in the Eyes / Smoke Veil / Sentry restrictions |
| `effect`      | referee batch | type `effect`; target alive; no effect with the same id already on them; placed immediately, referee may `reject`                                                                                                                                                                                                                                              |
| `play`        | referee batch, or a transaction if `reactors` is non-empty | type `action`, `aoe`, `intervention` (or a dual-type card played in that role); `reactors` defaults: `aoe` → `"others"`, otherwise `[]`; may be `"others" / "enemies" / "allies"` or a list of seats                                                                                                                                                                  |
| `ability`     | referee batch | `source` is `"character"` or `"stance:<uid>"` / `"aura:<uid>"` on the actor's table; free-text `choice`                                                                                                                                                                                                                                                         |
| `replan`      | control     | execution stops here; `status` returns `plan` for the same seat with `continuing: true`; the player is asked again with the same-turn log. Use it after an attack whose outcome changes the rest of the turn                                                                                                                                                       |

Steps that are no longer legal when their turn comes (the card left the hand, the
target died) are **skipped** with an event `step_skipped` and execution continues.

**Batching.** `effect`, `play` (without reactors) and `ability` steps do not stop
execution; they accumulate in `pending.batch`. The batch is flushed to the referee
(phase `resolve`) when a step that needs reactions is reached (before its reactions
are collected, so reactors see the post-batch table), at `replan`, and at the end
of the plan. So a typical turn costs: one plan call, one referee call per attack
(after its reactions), and at most one more referee call for the rest.

### 5.3 Reactions (reactor → `sim.py react`)

When an attack or a `play` with reactors opens, `sim.py` lists **reactors**:

- the target of an attack, always — unless they have no Defense-capable card, no
  Trap and no character option (Hanzo blocks with a weapon), in which case
  `{"action": "take"}` is recorded automatically and no agent is spawned;
- every other living player who *could* react: holds an `intervention` card, a
  card whose text says «as an Intervention», a Defense card while being the
  defender's teammate (partial absorption rule), a Renkei, or has a table object
  that enables reactions (Oath / Armory / Back to Back auras, Ketsuban stance,
  Norio with a polearm, Bell trap on the defender). Others are auto-`pass`ed;
- for `play` with reactors: exactly the listed seats, no pruning.

All reactions are simultaneous (one round — A2). A reaction:

```json
{"action": "defend", "cards": ["c48-2"], "trap": "trigger", "when": null,
 "target": null, "choice": null,
 "consent": {"share_wounds": false, "take_attack": false},
 "notes": "Parry a 3-wound Kanabo; the Bear Trap punishes him on top"}
```

| field     | values                                                                                                   |
|-----------|----------------------------------------------------------------------------------------------------------|
| `action`  | `take` (defender takes the blow), `defend` (defender plays Defense card(s)), `pass`, `intervene` (any other player: intervention / defense-as-intervention / «as an Intervention» card), `respond` (answer to a group card) |
| `cards`   | uids from the reactor's hand; also `"trap"` to name their own table trap (Bell, Iyo swaps)               |
| `trap`    | defender only: `trigger` / `hold` / `null`; ignored when the attack is thrown or the trap cannot fire      |
| `when`    | conditional interventions: `null` (always), `defended`, `undefended`, `lethal`                             |
| `target`  | seat, for interventions that need one (Dragon Strike, Ginger, Block for whom)                            |
| `choice`  | free text for group cards («I discard the Parry», «I hand him my Tanto»)                                 |
| `consent` | willingness flags read by the referee when the key player wants help (Ketsuban, Oath, Feat of Valor)      |

Cards named in a reaction leave the hand into `pending.played` at once. When the
transaction closes, whatever is still in `played` goes to the discard; ops may move
cards elsewhere first (Boomerang home, Seize into the defender's hand, Bear Trap
onto the attacker as an Effect).

### 5.4 The bookkeeper's baseline (attacks)

`sim.py` computes and shows to everyone:

- **target complexity** = 1, +1 per Armor effect, +1 Horseman stance, +1 Closed
  Ranks aura on the target's team; forced to 1 by Kaginawa or the Bear Trap effect.
- **weapon handles** = icon (`complexity1` 1, `complexity2` 2, `complexity_any` /
  `ranged` any); +1 Horseman on the attacker, +2 Lunge, any with Hachimaki, any for
  a favourite weapon in its owner's hands. An attack is legal iff handles ≥ target
  complexity. Dust in the Eyes: only complexity-1 targets and nothing thrown.
- **power** = dmg icon of the chosen mode (bare 1 / Saigo 2), + flat modifiers
  (Tameshigiri +1, Critical Strike +2, Lunge +1, Vial of Poison +1 and poison,
  Hachimaki +1, Kubitori +1, Wakizashi-on-Katana +2), + known stance / character
  / effect bonuses that are unconditional or whose condition the script can see
  (Katana with a stance, Horseman vs complexity 1, Archer on thrown, Mushin at
  death's door, Killer's Mark on the target, Curse on the target, +1 on a poisoned
  attack against a poisoned target). Each contribution is listed in
  `baseline.notes`; the referee corrects anything text-dependent.
- flags: `thrown`, `poisoned`, `undefendable` (favourite weapon, Traitor's Dagger
  by a ninja, Poison Dart, Shadow Strike, Assassin's discard option once chosen),
  `ignores_traps` (thrown unless the defender is Iyo; Traitor's Dagger by a ninja;
  Poison Dart; Shadow Strike), `trap_may_fire`.

### 5.5 Resolution (referee → `sim.py resolve`)

```json
{"result": "hit", "uses_attack": true,
 "ops": [
   {"op": "damage", "seat": 3, "n": 2, "source": "attack", "by": 2},
   {"op": "draw", "seat": 2, "n": 1},
   {"op": "move", "uid": "c36-1", "to": "hand", "seat": 2}
 ],
 "narrative": "P2 (Taka) swings the Kanabo at P3 (Hanzo) …",
 "rulings": [{"card": 3, "question": "does a blocked Kanabo still discard?", "ruling": "no — a successful block cancels attacker effects"}],
 "flags": {"ambiguous": false}}
```

| op                | fields                                                        | effect                                                                                     |
|-------------------|---------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| `damage`          | `seat, n, source (attack/thrust/trap/poison/other), by`       | −n life; death handling per §5.1 if it reaches 0                                            |
| `heal`            | `seat, n, over_max` (default 0)                               | +n life, capped at `max_hp + over_max` (Manase)                                            |
| `set_hp`          | `seat, hp`                                                    | swaps / equalisations; death handling if 0                                                 |
| `poison`          | `seat, value`                                                 | set / clear poison                                                                          |
| `draw`            | `seat, n`                                                     | from the deck (empty deck → nothing, `final_turn` set)                                     |
| `discard`         | `seat, uids`                                                  | from hand                                                                                   |
| `discard_random`  | `seat, n`                                                     | script's RNG                                                                                |
| `transfer`        | `from, to, uid` — or `transfer_random` with `n`               | hand → hand                                                                                 |
| `move`            | `uid, to (hand/discard/removed/stance/trap/aura/effects/charges), seat, face_up` | any zone move; `seat` is the new owner (for `charges`: the aura's owner)      |
| `reveal`          | `seat, what (hand/trap)`                                      | logs the contents publicly; trap becomes `face_up`                                          |
| `vp`              | `seat, delta`                                                 | victory points (Betrayal, Seppuku)                                                          |
| `kill`            | `seat, by`                                                    | immediate death (Kamikaze, a non-Trap under the figurine)                                   |
| `flag`            | `seat, key, value`                                            | per-player flag: `attacks_bonus`, `attacks_used`, `defenseless_until`, `untargetable_until`… |
| `note`            | `text`                                                        | ruling text into the log                                                                    |
| `reject`          | `reason`                                                      | the action is void: cards return to hand, the attempt is not used                            |

Ops are validated (seats, uids, zones) and applied **all or nothing**; on error
the referee gets the list and resubmits. On success the transaction closes:
cards still in `played` go to the discard, `attacks_used` grows if `uses_attack`,
and `sim.py` **continues executing the plan** until the next transaction or the
end of the turn, then prints `status`.

## 6. Transactions

`pending` has one of three kinds:

| kind     | opened by                              | reactors            | phases            |
|----------|----------------------------------------|---------------------|-------------------|
| `attack` | an `attack` step                       | §5.3 pruning        | `react` → `resolve` (straight to `resolve` when every reactor is automatic) |
| `card`   | a `play` step with non-empty reactors  | exactly as listed   | `react` → `resolve` |
| `batch`  | flush of queued `effect`/`play`/`ability` steps | none        | `resolve`          |

`sim.py pending --game N` prints the transaction for the referee: the steps, the
attack with baseline, every card text involved (weapon, modifier, defense and
intervention cards, the defender's trap face up, effects, stances, auras of both
sides, both characters with their death texts), every reaction (recorded and
automatic), both players' hands, and `what_happens_if_undefended` — the script's
own arithmetic — so the referee mostly confirms and adds the text effects.

## 7. Agents

Prompt templates live in `simulations/prompts/`:

- `rules-digest.md` — the rules condensed to ~1.5k tokens for players. The referee
  gets the full rules from `sim.py rules` (the HTML of `rules/content-en.html`
  stripped to text), so a rules edit is picked up on the next game.
- `player-plan.md`, `player-react.md`, `referee.md` — instructions plus the exact
  CLI calls. Agents write their JSON to `simulations/games/inbox/` (git-ignored)
  and pass it with `--file`, or pipe it through stdin with `--file -`.

**Lanes.** A game is created with one token per seat plus one for the referee
(`sim.py new --tokens s0,s1,s2,s3,ref`). `view`, `plan` and `react` demand the
token of the seat they name; `pending`, `public --all` and `resolve` demand the
referee's. The orchestrator hands each agent only its own token, so a player
agent physically cannot read another hand, act for another seat or resolve a
transaction — and the prompts say so in a «Your lane» section. This is not
security, it is discipline: on 20.09.2026 the first pilot was «played» in four
minutes by two Haiku reaction agents that, finding an open CLI, submitted plans
for all four seats and refereed themselves (see `games/obsolete/`). `status`,
`log`, `export` and `report` stay open. Games created without tokens (scratch,
tests) skip the check.

Every agent returns a small structured object to the orchestrator: the `status`
JSON it got from the last CLI call, plus `notes`. Player notes («why») and referee
`rulings` are stored in `events` and shown in the viewer — they are the
qualitative half of the data.

Models — fixed policy, set explicitly on every `agent()` call in `play.js`:
**players (plan / react) run on Haiku**, **the referee runs on Sonnet**. Nothing
in the simulation ever inherits the session's main model. The same cap applies
to the agents that build and review this stack: Sonnet at most.

## 8. Simplifications and assumptions

Everything here is a deliberate deviation or an open question in the rules; each
is tagged so it can be revisited.

- **A1 — revival life.** The rules do not say with how much life a dead player
  returns. The sim revives at **full life** (as in Samurai Sword). To change:
  `REVIVE_HP` in `sim.py`.
- **A2 — one reaction round.** The intervention transaction is modelled as one
  simultaneous round; conditional declarations (`when`) replace the back-and-forth
  («if he defends, I break the shield»). The key player's «most favourable order»
  is applied by the referee.
- **A3 — interventions outside transactions.** «Playable at any moment» is
  narrowed to: inside a transaction, or as a `play` step on your own turn.
- **A4 — a replaced Aura** returns to hand, its charges go to the discard.
- **A5 — once-per-turn Aura** (the rules only say «on their turn»).
- **A6 — consent** (Ketsuban, Oath, Feat of Valor, Helping Hand) is expressed as
  willingness flags in the reaction; the referee pairs them with the key player's
  wish. No negotiation.
- **A7 — plans are commitments.** A player's later steps run without re-asking
  unless they put `replan` in. Steps made illegal by earlier results are skipped.
- **A8 — Shogun's Wrath** («may be made even against a player at death's door»)
  refers to a rule the current text does not have; treated as a no-op modifier
  and reported as a ruling.
- **A9 — turn cap.** `max_turns` (default 10 player-turns) ends the game with a
  VP count; the report separates cap endings from natural ones.
- **A10 — drafts** (`tags: draft`) are out of the deck unless `--include-drafts`.

Confirmed rulings (decided by the designer, not assumptions):

- **R1 — the victory point follows the source of the damage** (20.09.2026). Whoever
  owns the thing that dealt the killing wound is the killer: the attacker for a
  weapon, the trap's owner for a trap, the player of a thrust or intervention
  card, the aura's bearer for aura damage, the defender for a Defense card that
  wounds the attacker. The usual rule then applies: a living player of the other
  faction gets the point, an ally or poison sends it to the discard. Hence the
  referee's `by` on every `damage` / `kill` op is the *source*, never «the player
  whose turn it is».

## 9. History export (viewer input)

`sim.py export --game N` writes `simulations/games/game_<N>.json` and refreshes
`simulations/games/index.json`:

```json
{
  "game": {"id": 1, "seed": 1, "players_n": 4, "max_turns": 10, "turns_played": 10,
           "players": [{"seat": 0, "name": "P0", "faction": "samurai", "first": true,
                        "character": {"id": 137, "name": "Saigo", "hp": 6, "text": "…"}}],
           "result": {"reason": "turn_cap", "winner": "ninja", "score": {"samurai": 7, "ninja": 9}},
           "assumptions": ["A1", "A2", "…"]},
  "cards": {"1": {"id": 1, "name": "Katana", "types": ["weapon"], "icons": ["complexity1", "dmg2"], "icons_or": null, "text": "…"}},
  "events": [
    {"seq": 12, "turn": 2, "active": 1, "kind": "attack_declared", "actor": 1, "target": 2,
     "card": "c1-2", "card_id": 1, "text": "P1 (Hanzo) attacks P2 (Saigo) with Katana (2)",
     "data": {"mode": "main", "modifier": null, "baseline": {}},
     "notes": "player's reasoning, if any",
     "state": {"deck_n": 88, "discard_n": 9,
               "players": [{"hp": 6, "vp": 4, "poisoned": false, "alive": true, "hand_n": 7,
                            "stance": "c58-1", "trap": {"uid": "c41-1", "face_up": false},
                            "aura": null, "effects": ["c91-1"]}]}}
  ]
}
```

Event kinds: `game_start, turn_start, revive, recovery, discard_to_limit,
plan, step_skipped, stance_set, trap_set, aura_set, aura_charged, trade,
attack_declared, card_played, effect_placed, ability_used, reaction, reaction_auto,
ruling, damage, heal, poison, draw, discard, transfer, move, reveal, vp, death,
transaction_closed, rejected, end_turn_poison, draw_phase, deck_empty, game_over`.
`state` is the snapshot **after** the event, so the viewer never re-simulates.
Besides the public fields it carries replay-only data that no agent ever sees:
`discard_top` (uid on top of the discard), `in_play` (uids of the cards lying in
the open transaction) and `hands` (every seat's hand as uids). The last one is
what lets the viewer show **what a player held when they decided** — the plan
or reaction event, the hand face up next to it, and the player's `notes` — so a
bot's decision can be judged against its options.

`simulations/viewer.html` opens by double click: load a game JSON with the file
picker (or `?src=games/game_1.json` when served), then step through events with
← / → (or autoplay), jump by turn, see the photographed table (seats around it
with the character and role cards, glossy life hearts and VP coins, poison /
trap figurines, stance / aura / effect cards, the open hand face up over the
player, the cards in play on the action spot), attack arrows and the log with
player notes and referee rulings. Hover a hand to zoom it to 150 %, a card in
it to 200 %; a seat's 📌 pins its hand in the decision panel below the table.

The replay is **live**: with GSAP (`simulations/vendor/gsap.min.js`, CDN as a
fallback) every step is animated from the previous one — the deal and draws fly
from the deck as backs, played cards move from the hand to the action spot,
stance / trap / aura / effects to their places, discards fall onto the pile,
the attack arrow draws itself (dashes crawl while reactions are pending, then
it takes the ruling's colour), wounds shake the hearts with a floating −N and
an impact flash, healing, tokens, poison, death and revival each have their
beat. A step's `why` (or a reaction's note) is spoken in a bubble at the
player's shoulder, listed in the log and shown above the decision panel. The
«live» box in the footer turns the animation off; `#e=<i>` links to an event,
`#e=<i>&p=<0..1>` freezes the transition into it at that progress (a still).

## 10. Running a batch

```bash
# 1. refresh the card export (whenever js/cards.js changed)
node simulations/engine/export_cards.mjs

# 2. create games — one seed each, five fresh tokens per game (seats 0–3 + referee)
for s in 1 2 3 4 5 6 7 8 9 10; do
  py -3 simulations/engine/sim.py new --seed $s --players 4 --max-turns 10 --tokens "$(py -3 -c 'import secrets;print(",".join(secrets.token_hex(4) for _ in range(5)))')"
done

# 3. play them — the orchestrator drives the agents (from Claude Code); tokens go in args, one object per game
#    Workflow({scriptPath: "simulations/workflow/play.js",
#              args: {games: [{id: 1, tokens: {"0": "…", "1": "…", "2": "…", "3": "…", "referee": "…"}}, …]}})

# 4. export histories and the report
py -3 simulations/engine/sim.py export --all
py -3 simulations/engine/sim.py report --out simulations/reports/report.md
```

Cost model per player-turn: ~1 plan call + ~1.5 attacks × (≈1.5 reactor calls +
1 referee call) + ≤1 referee flush ≈ 5–6 agent calls. A 10-turn game is ~60 calls;
`play.js` caps a game at 120 calls as a runaway guard and logs what it dropped.

## 11. Reading the results

- **Viewer** — one game, event by event (`simulations/viewer.html`).
- **Report** (`sim.py report`) — across games: per card *plays, plays by role
  (attack / defense / intervention / action), hits vs blocks, wounds dealt and
  prevented, VP swings, turns held in hand before being played, times held and
  never played, times rejected by the referee*; per character *games, win rate,
  wounds taken / dealt*; per faction *wins, average VP, average game length*;
  the list of referee rulings grouped by card.
- **Summary on request** — the assistant reads `sim.py log --game N` (a
  human-readable event log with notes) and answers «what happened», «why did P2
  never play the Magatama», «which card decided game 7».

## 12. Layout

```
simulation.md                 this manifest
simulations/
  engine/export_cards.mjs     js/cards.js → data/cards.json
  engine/sim.py               the bookkeeper CLI (state, SQLite, validation, views, export, report)
  engine/card_rules.py        static tables: complexity / power modifiers, draw bonuses, reaction eligibility
  engine/test_sim.py          unit tests (py -3 -m unittest simulations/engine/test_sim.py)
  schema/*.schema.json        JSON Schemas: plan, reaction, resolve, status, history
  prompts/                    rules-digest.md, player-plan.md, player-react.md, referee.md
  workflow/play.js            orchestrator (Workflow script)
  data/cards.json             exported card texts
  games/sim.sqlite            all games (state, events, messages)
  games/game_<N>.json         exported histories; index.json — the list for the viewer
  games/inbox/                agents' JSON messages in flight (git-ignored)
  reports/                    generated reports
  viewer.html                 history viewer (live replay)
  vendor/gsap.min.js          GSAP 3.13 for the viewer's animations (local copy; CDN fallback)
  media/cards/<id>.png        card renders for the viewer (tools/render_card_pngs.py); backs, fig/ figurines
  media/table-bg.webp         the table photo under the scene; table-layout.json — measured seat anchors
```
