"""Static, id-keyed tables for «Samurai vs Ninja» card mechanics.

This module holds ONLY numeric/structural facts that `sim.py` needs to compute
its best-effort attack baseline (§5.4) and to enforce the mechanical rules of
§5.2/§5.3. It never interprets free card text beyond simple substring checks
(e.g. "{Polearm}"); anything that depends on a card's prose is the referee's
job, not this table's.

Every id below was verified against `simulations/data/cards.json` (generated
by `export_cards.mjs` from `js/cards.js`) at the time this file was written.
If `js/cards.js` changes card ids, re-verify before trusting this file.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------

CHARACTER_IDS = {
    "Ushiwaka": 135,
    "Taranaga": 136,
    "Saigo": 137,
    "Hanzo": 138,
    "Iyo": 139,
    "Taka": 140,
    "Norio": 142,
    "Manase": 145,
    "Minamoto": 146,
}
CHARACTER_ID_TO_NAME = {v: k for k, v in CHARACTER_IDS.items()}

USHIWAKA_CHARACTER_ID = CHARACTER_IDS["Ushiwaka"]
TARANAGA_CHARACTER_ID = CHARACTER_IDS["Taranaga"]
SAIGO_CHARACTER_ID = CHARACTER_IDS["Saigo"]
HANZO_CHARACTER_ID = CHARACTER_IDS["Hanzo"]
IYO_CHARACTER_ID = CHARACTER_IDS["Iyo"]
TAKA_CHARACTER_ID = CHARACTER_IDS["Taka"]
NORIO_CHARACTER_ID = CHARACTER_IDS["Norio"]
MANASE_CHARACTER_ID = CHARACTER_IDS["Manase"]
MINAMOTO_CHARACTER_ID = CHARACTER_IDS["Minamoto"]

# Favourite weapon (weapon card id) -> character card id. Only 8 of the 9
# characters have one printed in the deck (Minamoto does not; his Poison Dart
# synergy is a flat, referee-adjudicated bonus, not a "favourite weapon").
FAVOURITE_WEAPON = {
    2: USHIWAKA_CHARACTER_ID,   # Shuko
    3: SAIGO_CHARACTER_ID,      # Kanabo
    6: MANASE_CHARACTER_ID,     # War Fan
    7: HANZO_CHARACTER_ID,      # Kusarigama
    23: TARANAGA_CHARACTER_ID,  # Nunti Bo
    24: NORIO_CHARACTER_ID,     # Bo
    26: TAKA_CHARACTER_ID,      # Kyoketsu-shoge
    38: IYO_CHARACTER_ID,       # Makibishi
}


def is_favourite_weapon(weapon_id: int, character_id) -> bool:
    return FAVOURITE_WEAPON.get(weapon_id) == character_id


# ---------------------------------------------------------------------------
# Complexity
# ---------------------------------------------------------------------------

COMPLEXITY_BASE = 1

ARMOR_EFFECT_ID = 5104          # effect on target: +1 target complexity
HORSEMAN_STANCE_ID = 58         # stance: +1 target complexity (defender) AND +1 handles (attacker)
CLOSED_RANKS_AURA_ID = 1202     # aura: +1 complexity for the whole team of the aura's owner
KAGINAWA_EFFECT_ID = 94         # effect on target: complexity forced to 1
BEAR_TRAP_EFFECT_ID = 43        # same card id, after it triggers and becomes an Effect: complexity forced to 1

# Effects that force target complexity to 1, overriding Armor/Closed Ranks/Horseman.
FORCE_COMPLEXITY_1_EFFECTS = {KAGINAWA_EFFECT_ID, BEAR_TRAP_EFFECT_ID}

LUNGE_MODIFIER_ID = 68          # modifier: attacker's weapon handles +2 complexity (also flat power, see below)
HACHIMAKI_MODIFIER_ID = 73      # modifier: attacker's weapon handles ANY complexity (also flat power, see below)
NAGINATA_WEAPON_ID = 28         # weapon: already icon complexity_any ({Polearm}) — listed for completeness only


def target_complexity(target_effect_ids, target_has_horseman, target_team_has_closed_ranks):
    """Best-effort target complexity, per §5.4. `target_effect_ids` is the set
    of effect card ids currently on the target."""
    if target_effect_ids & FORCE_COMPLEXITY_1_EFFECTS:
        return 1
    c = COMPLEXITY_BASE
    if ARMOR_EFFECT_ID in target_effect_ids:
        c += 1
    if target_has_horseman:
        c += 1
    if target_team_has_closed_ranks:
        c += 1
    return c


def weapon_handles(icon_complexity, attacker_has_horseman, has_lunge, has_hachimaki, is_favourite):
    """Returns an int, or the string "any"."""
    if has_hachimaki or is_favourite or icon_complexity == "any":
        return "any"
    handles = icon_complexity
    if attacker_has_horseman:
        handles += 1
    if has_lunge:
        handles += 2
    return handles


def handles_meets(handles, complexity) -> bool:
    if handles == "any":
        return True
    return handles >= complexity


# ---------------------------------------------------------------------------
# Flat power modifiers (modifier card id -> flat bonus added to base dmg icon)
# ---------------------------------------------------------------------------

TAMESHIGIRI_MODIFIER_ID = 65
CRITICAL_STRIKE_MODIFIER_ID = 80
VIAL_OF_POISON_MODIFIER_ID = 64
KUBITORI_MODIFIER_ID = 1083
WAKIZASHI_WEAPON_ID = 8
KATANA_WEAPON_ID = 1

FLAT_POWER_MODIFIERS = {
    TAMESHIGIRI_MODIFIER_ID: 1,       # Tameshigiri: +1
    CRITICAL_STRIKE_MODIFIER_ID: 2,   # Critical Strike: +2
    LUNGE_MODIFIER_ID: 1,             # Lunge: +1 (plus complexity handling above)
    VIAL_OF_POISON_MODIFIER_ID: 1,    # Vial of Poison: +1, and inflicts Poison
    HACHIMAKI_MODIFIER_ID: 1,         # Hachimaki: +1, attacker loses 1 life, cannot be played at death's door
    KUBITORI_MODIFIER_ID: 1,          # Kubitori: +1; on kill, attacker may take stance/aura/effects
}


def wakizashi_on_katana_bonus(modifier_id, weapon_id) -> int:
    """+2 power when Wakizashi (8) is played as the modifier on a Katana (1)
    attack — and only then."""
    if modifier_id == WAKIZASHI_WEAPON_ID and weapon_id == KATANA_WEAPON_ID:
        return 2
    return 0


# ---------------------------------------------------------------------------
# Stance / character / effect power notes (best-effort; referee corrects)
# ---------------------------------------------------------------------------

ARCHER_STANCE_ID = 1166        # +1 power on thrown attacks
MUSHIN_STANCE_ID = 1165        # {at death's door} +2 power
KILLERS_MARK_EFFECT_ID = 91    # +1 power to any attack against the effect's holder
CURSE_EFFECT_ID = 4104         # +2 to any damage against the effect's holder
ASSASSIN_STANCE_ID = 63        # attacker may poison the attack, or (discard 2, 1 for a ninja) make it undefendable — a
                                 # per-attack CHOICE, so it is NOT auto-applied here; the referee grants it from the
                                 # attacker's declared note/choice.


# ---------------------------------------------------------------------------
# Undefendable / ignores-traps sources
# ---------------------------------------------------------------------------

TRAITORS_DAGGER_WEAPON_ID = 5   # by a ninja attacker: undefendable + ignores traps
POISON_DART_WEAPON_ID = 39      # always: undefendable (ignores Defense) + ignores traps; draws a card
SHADOW_STRIKE_MODIFIER_ID = 67  # always: undefendable + ignores traps


def attack_is_undefendable(weapon_id, modifier_id, attacker_faction, attacker_character_id) -> bool:
    if weapon_id == TRAITORS_DAGGER_WEAPON_ID and attacker_faction == "ninja":
        return True
    if weapon_id == POISON_DART_WEAPON_ID:
        return True
    if modifier_id == SHADOW_STRIKE_MODIFIER_ID:
        return True
    if is_favourite_weapon(weapon_id, attacker_character_id):
        return True
    return False


def attack_ignores_traps(weapon_id, modifier_id, thrown, attacker_faction, defender_character_id) -> bool:
    if thrown:
        # Thrown weapons never trigger traps, UNLESS the defender is Iyo
        # (whose Trap "triggers on thrown attacks too").
        if defender_character_id == IYO_CHARACTER_ID:
            pass
        else:
            return True
    if weapon_id == TRAITORS_DAGGER_WEAPON_ID and attacker_faction == "ninja":
        return True
    if weapon_id == POISON_DART_WEAPON_ID:
        return True
    if modifier_id == SHADOW_STRIKE_MODIFIER_ID:
        return True
    return False


# ---------------------------------------------------------------------------
# Attack restrictions
# ---------------------------------------------------------------------------

DISARM_EFFECT_ID = 95              # holder cannot make direct weapon attacks
PUNCTURE_WOUNDS_EFFECT_ID = 1049   # same card id as the trap; once it passes to the (former) attacker as an
                                     # Effect, they can no longer use weapons for direct attacks
DUST_IN_EYES_EFFECT_ID = 97        # holder's attacks: complexity-1 targets only, no thrown weapons
SMOKE_VEIL_AURA_ID = 1206          # enemies of the aura owner's team cannot make ranged attacks
SENTRY_AURA_ID = 1209              # the Aura's bearer cannot use thrown weapons
EXHAUSTION_EFFECT_ID = 103         # holder: -1 attack attempt per turn
TEPPO_YUMI_WEAPON_ID = 1033

# Effects that block the holder from making ANY weapon attack at all (bare
# hands included — a documented judgment call; the alternative reading, that
# only weapon-in-hand attacks are blocked and bare hands remain legal, is
# plausible too, but "cannot make weapon attacks" reads more naturally as a
# blanket ban and keeps the mechanic simple to enforce).
ATTACKER_BLOCKED_EFFECTS = {DISARM_EFFECT_ID, PUNCTURE_WOUNDS_EFFECT_ID}

WEAPON_REQUIRES_MODIFIER = {TEPPO_YUMI_WEAPON_ID}   # fires only together with a Modifier
RENKEI_MODIFIER_ID = 1032                            # stands in as "modifier" on an attack; a later Intervention
                                                       # may tuck a real Modifier on top of it


def attacks_max(attacker_effect_ids, is_minamoto, minamoto_poisoned) -> int:
    base = 2
    if EXHAUSTION_EFFECT_ID in attacker_effect_ids:
        base -= 1
    if is_minamoto and minamoto_poisoned:
        base += 1
    return max(0, base)


# ---------------------------------------------------------------------------
# Draw-phase bonuses (character id -> description; computed by sim.py, which
# knows table-wide counts)
# ---------------------------------------------------------------------------

DRAW_BONUS_FLAT = {TARANAGA_CHARACTER_ID: 1}
DRAW_BONUS_PER_STANCE_ON_TABLE = {SAIGO_CHARACTER_ID: (1, 3)}      # (+1 per stance, cap 3)
DRAW_BONUS_PER_TRAP_ON_TABLE = {IYO_CHARACTER_ID: (1, 3)}          # (+1 per trap, cap 3)
DRAW_BONUS_PER_POISONED_PLAYER = {MINAMOTO_CHARACTER_ID: (1, 3)}   # (+1 per poisoned player, cap 3)


# ---------------------------------------------------------------------------
# Poison
# ---------------------------------------------------------------------------

POISON_TICK_BASE = 2
SNAKEBITE_EFFECT_ID = 93   # doubles the poison tick penalty; has NO effect on Minamoto


def poison_tick(character_id, has_snakebite) -> int:
    if character_id == MINAMOTO_CHARACTER_ID:
        return 0
    tick = POISON_TICK_BASE
    if has_snakebite:
        tick *= 2
    return tick


# ---------------------------------------------------------------------------
# Death's door
# ---------------------------------------------------------------------------

DEATH_DOOR_DEFAULT = 1
DEATH_DOOR_OVERRIDE = {USHIWAKA_CHARACTER_ID: 2}   # "Death's door for you: 1 or 2 life."


def death_door_threshold(character_id) -> int:
    return DEATH_DOOR_OVERRIDE.get(character_id, DEATH_DOOR_DEFAULT)


def at_death_door(hp, character_id) -> bool:
    return hp <= death_door_threshold(character_id)


def at_full_health(hp, max_hp) -> bool:
    return hp >= max_hp


# ---------------------------------------------------------------------------
# Charged auras — what may be tucked, and the step size / cap of the bonus.
# The bonus itself (extra wound, extra card, etc.) is applied by the referee
# via ops; `card_matches_aura_charge` is what `sim.py` uses to validate a
# `charge_aura` plan step.
# ---------------------------------------------------------------------------

MARTIAL_MASTERY_AURA_ID = 1200   # tuck: modifier          -> +1 dmg per 2 tucked, cap +3 (6 cards)
COVERED_FLANK_AURA_ID = 1201     # tuck: defense           -> -1 dmg per 2 tucked (floor 1), cap 3 (6 cards)
STRATEGIST_AURA_ID = 1205        # tuck: intervention|aoe  -> +1 card/draw per 2 tucked, cap +2 (4 cards)
HIGH_GROUND_AURA_ID = 1212       # tuck: thrown weapon     -> +1 dmg per full team-sized set, cap +3

AURA_CHARGE_KIND = {
    MARTIAL_MASTERY_AURA_ID: "modifier",
    COVERED_FLANK_AURA_ID: "defense",
    STRATEGIST_AURA_ID: "intervention_or_aoe",
    HIGH_GROUND_AURA_ID: "ranged_weapon",
}

AURA_CHARGE_STEP = {
    MARTIAL_MASTERY_AURA_ID: (2, 1, 3),   # every N cards -> +bonus, up to cap
    COVERED_FLANK_AURA_ID: (2, 1, 3),
    STRATEGIST_AURA_ID: (2, 1, 2),
    HIGH_GROUND_AURA_ID: (None, 1, 3),    # step is a full team-sized set, computed by sim.py
}


def card_matches_aura_charge(aura_id, card) -> bool:
    kind = AURA_CHARGE_KIND.get(aura_id)
    if kind is None:
        return False
    types = set(card.get("types") or [])
    if kind == "modifier":
        return "modifier" in types
    if kind == "defense":
        return "defense" in types
    if kind == "intervention_or_aoe":
        return bool(types & {"intervention", "aoe"})
    if kind == "ranged_weapon":
        return "weapon" in types and "ranged" in (card.get("icons") or [])
    return False


# ---------------------------------------------------------------------------
# Reaction-enabling table objects (§5.3)
# ---------------------------------------------------------------------------

OATH_AURA_ID = 1207           # any living ally may take a direct weapon attack aimed at another ally onto themselves
ARMORY_AURA_ID = 1210         # any ally may (with the attacker's consent) put a weapon in as an Intervention
BACK_TO_BACK_AURA_ID = 1204   # any ally may play a Defense card as an Intervention to defend another ally
KETSUBAN_STANCE_ID = 1164     # a willing ally may share the stance holder's wounds
BELL_TRAP_ID = 1050           # when triggered, any ally may play their own Trap in its place, as an Intervention
# NORIO_CHARACTER_ID / HANZO_CHARACTER_ID already defined above.

REACTION_ENABLING_AURAS = {OATH_AURA_ID, ARMORY_AURA_ID, BACK_TO_BACK_AURA_ID}
REACTION_ENABLING_STANCES = {KETSUBAN_STANCE_ID}
REACTION_ENABLING_TRAPS = {BELL_TRAP_ID}


def is_polearm(card) -> bool:
    return "{Polearm}" in (card.get("text") or "")


def hanzo_can_intervene(character_id) -> bool:
    """Hanzo may block ANY direct attack with a weapon, at the cost of one
    wound, even without holding a dedicated Defense card."""
    return character_id == HANZO_CHARACTER_ID


def norio_can_intervene(character_id, hand_cards) -> bool:
    """Norio, holding a Polearm, may block an attack as an Intervention."""
    if character_id != NORIO_CHARACTER_ID:
        return False
    return any(is_polearm(c) for c in hand_cards)


# ---------------------------------------------------------------------------
# Misc singled-out cards
# ---------------------------------------------------------------------------

SHADOW_STANCE_ID = 57   # holder counts as dead (untargetable) for the whole round, discarded at the start of their turn
BARREL_OF_STENCH_AURA_ID = 1203  # "The {Bearer} becomes Poisoned" on play (sim.py applies this immediately;
                                   # the ally-poisoned-attacks half of the text is left to the referee)


# ---------------------------------------------------------------------------
# Trade-in ("discard 2 of the same type -> draw 1")
# ---------------------------------------------------------------------------

# rules/content-en.html "Trading cards in" enumerates the qualifying icons:
# Weapon, Trap, Stance, Defense, Effect, Intervention, Modifier, group card
# (aoe). "action" is conspicuously absent and must NOT count as a shared type.
TRADE_QUALIFYING_TYPES = {
    "weapon", "trap", "stance", "defense", "effect", "intervention", "modifier", "aoe",
}

# Boomerang (36) and Uchine (318) are deliberately NOT special-cased here —
# per the task brief, the referee moves them back with an explicit `move` op.
