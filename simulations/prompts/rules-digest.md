# Samurai vs Ninja — Rules Digest

Two teams, samurai vs ninja, seated alternately. No hidden roles: faction and
character are visible from the start.

## Setup

- Random character card's heart number = your max life. You start at max
  life, 4 VP, 7 cards in hand.
- One samurai holds the "I" banner and takes the first turn; play passes
  clockwise; every round starts with a samurai.

## Turn order

1. Discard down to 9 cards (may discard more; between turns hand is
   unlimited).
2. Recovery, only if you died since your last turn and were not killed by
   poison: discard any number, draw back up to 7.
3. Act (below).
4. End of turn: optional end-of-turn ability, poison tick, draw phase.

## What a turn allows

- Up to **2 weapon attacks**, on anyone living, ally or enemy. Bare hands
  count as a weapon: complexity 1, power 1, but use up **both** attempts.
- Change **Stance** once (new one returns old to hand).
- Set/swap **Trap** once (old one returns to hand).
- Play/replace **Aura** once (old one returns to hand; its charged cards go
  to discard).
- Any number of **Effects**, **actions**, **group/AoE cards**, and
  **Interventions** (Interventions are actually playable at any time, not
  only your turn).
- **Trade in**: two cards sharing one type icon (Weapon/Trap/Stance/
  Defense/Effect/Intervention/Modifier/group; dual-type counts as either)
  discarded → draw 1; two identical cards discarded → draw 2.

## Drawing

End of turn: you draw 3, then every living opposing player draws 1. (Uneven
team draw/VP tables exist but don't apply to an even game.)

## Complexity

Default complexity 1 for everyone (seating never matters). A weapon's
printed number is the highest complexity it handles; attack succeeds iff
weapon's handled complexity ≥ target's complexity. Thrown weapons handle any
complexity. Cards/Effects/Stances/Auras can shift either side's complexity.
Checked at the moment the attack is declared.

## Modifiers & favourite weapon

One Modifier card (red banner) may strengthen an attack. A weapon naming a
character as its favourite: in that owner's hands it handles any complexity
and cannot be defended against.

## Defense

Defender takes wounds = attack power, or plays one Defense card to block
fully (blocking cancels the attacker's extra effects). Teammates may instead
add their own Defense cards as an Intervention to reduce (not block) damage:
one card brings final wounds to 1, two bring it to 0 — but the used Defense
cards' own special effects (return damage, poison, etc.) don't fire this way.
If the defender cannot defend (defenceless Effect, or an undefendable
attack), teammates can't help either.

## Traps

One Trap, face down under the figurine. Non-thrown attack + you don't
defend → Trap always triggers; if you do defend, triggering is your choice.
Thrown weapons never trigger Traps. If reveal/steal/trigger shows the card
under the figurine isn't a Trap, that player dies instantly and the point
goes to whoever caused the reveal. A Trap still resolves even on a lethal
attack.

## Thrust

Direct-damage cards ("Thrust", spearhead icon): not an attack — unblockable
by Defense, no Trap trigger, no attack attempt used. "On taking wounds"
effects still fire. If a thrust kills, the point goes to whoever played it.

## Stances

One active Stance; new one returns old to hand. Stays until you die or a
specific effect removes it.

## Effects

Any number of Effects on a living player, never two of the same name on one
player. Last until that player dies, then all discard.

## Poison

Poisoned player marked with the poison figurine; doesn't reduce their own
attack power.
- End of a poisoned player's turn: lose 2 life. If it kills them, the VP
  goes to the discard (nobody scores it) and they get no recovery (face-up
  cards discard, hand stays as-is).
- Poisoned attack/action vs an already-poisoned target: +1 extra wound.

## Interventions

Playable at any moment, by anyone, even mid-transaction; any player may add
more Intervention-playable cards to the same open transaction, all resolving
simultaneously (no speed/order race). The **key player** (defender, or whose
life is at stake) picks the order/reading most favourable to themselves when
effects contradict.

## Auras

One Aura per player; new one replaces old (old returns to hand, its charged
cards discard). Affects the *whole table*, not just the owner's team, and
stays while the owner lives. Teammates' Auras stack (don't cancel). Charged
Auras need matching cards tucked face up under them to do anything; bonus
grows per pair or per full team-size set, and is capped. Discards with the
owner's other face-up cards on death.

## Conditions

"At death's door" = exactly 1 life. "At full health" = life at character's
max.

## Order of resolution (one line)

Stack most-permanent-first: attacker Character→Stance→Team Aura→Poison→
Effect→Weapon→Modifier; defender Character→Stance→Team Aura→Poison→Effect→
Trap→Defense. A limit set anywhere in the chain only narrows later, never
widens, except a card that explicitly cancels the opponent's bonus.

## Death

Losing your last life kills you until end of that turn. VP goes to the
killer, unless killed by poison or by an ally — then the point goes to the
discard. Your Stance/Aura/Trap/Effects discard. Your character's "After your
death" text fires immediately, like an intervention. While dead: can't be
attacked/targeted, do nothing but recovery. Everyone who died revives at the
start of the very next turn at the table — anyone's, not only yours (this
simulation: at full life, see A1) — and can be attacked right away.

## Game end and scoring

Ends when: deck runs out (that draw's turn is the last one), or any player
hits 0 VP, or (here) a turn cap is reached. Score = team VP + 1 per Magatama
still held in hand. Ties are possible and reported as such.

## Simulation conventions

- **A1** — a dead player revives at **full life**, not partial.
- **A2** — the whole intervention exchange is one simultaneous round of
  declared reactions, not a back-and-forth; `when` replaces "if he defends,
  then I...".
- **A3** — "playable at any moment" is narrowed to: inside an open
  transaction, or as your own play step on your own turn.
- **A4** — a replaced Aura returns to hand; its tucked cards discard.
- **A5** — Aura is treated as once-per-turn, like Stance and Trap.
- **A6** — consent-based effects are simple willingness flags in your
  reaction; no negotiation.
- **A7** — your submitted plan is a commitment: later steps run without
  re-asking unless you ask to replan; a step made illegal by an earlier
  result is just skipped.
- **A8** — one rules text with no matching current rule is a no-op, logged
  as a ruling.
- **A9** — this game caps at a fixed number of turns; hitting the cap ends
  and scores the game like any other end.
- **A10** — draft/unfinished cards are excluded from the deck by default.
