from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RulePattern:
    tag: str
    pattern: re.Pattern[str]
    playmode_status: str


PLAYMODE_READY = "playmode_ready"
PLAYMODE_PARTIAL = "playmode_partial"
PLAYMODE_PENDING = "playmode_pending"

SPELL_AUTOMATED = "automated"
SPELL_PARTIAL = "partial"
SPELL_MISSING = "missing"
CREATURE_AUTOMATED = "automated"
CREATURE_PARTIAL = "partial"
CREATURE_MISSING = "missing"


RULE_PATTERNS: tuple[RulePattern, ...] = (
    RulePattern("shield_trigger", re.compile(r"\bshield\s*trigger\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("blocker", re.compile(r"\bblocker\b", re.I), PLAYMODE_PENDING),
    RulePattern("double_breaker", re.compile(r"\bdouble\s+breaker\b", re.I), PLAYMODE_READY),
    RulePattern("triple_breaker", re.compile(r"\btriple\s+breaker\b", re.I), PLAYMODE_READY),
    RulePattern("speed_attacker", re.compile(r"\bspeed\s+attacker\b", re.I), PLAYMODE_READY),
    RulePattern("charger", re.compile(r"\bcharger\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("evolution", re.compile(r"\bevolution\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("vortex_evolution", re.compile(r"\bvortex\s+evolution\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("tap_ability", re.compile(r"(?:\$tap|\btap ability\b)", re.I), PLAYMODE_PENDING),
    RulePattern("silent_skill", re.compile(r"\bsilent\s+skill\b", re.I), PLAYMODE_PENDING),
    RulePattern("wave_striker", re.compile(r"\bwave\s+striker\b", re.I), PLAYMODE_PENDING),
    RulePattern("survivor", re.compile(r"\bsurvivor\b", re.I), PLAYMODE_PENDING),
    RulePattern("metamorph", re.compile(r"\bmetamorph\b", re.I), PLAYMODE_PENDING),
    RulePattern("turbo_rush", re.compile(r"\bturbo\s+rush\b", re.I), PLAYMODE_PENDING),
    RulePattern("slayer", re.compile(r"\bslayer\b", re.I), PLAYMODE_PENDING),
    RulePattern("power_attacker", re.compile(r"\bpower\s+attacker\b", re.I), PLAYMODE_PENDING),
    RulePattern("stealth", re.compile(r"\bstealth\b", re.I), PLAYMODE_PENDING),
    RulePattern("cant_attack", re.compile(r"\bcan(?:not|'t)\s+attack\b", re.I), PLAYMODE_PENDING),
    RulePattern("cant_be_blocked", re.compile(r"\bcan(?:not|'t)\s+be\s+blocked\b", re.I), PLAYMODE_PENDING),
    RulePattern("destroy_effect", re.compile(r"\bdestroy\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("bounce_effect", re.compile(r"\breturn\b.+\bhand\b|\bowners'? hands?\b", re.I | re.S), PLAYMODE_PARTIAL),
    RulePattern("draw_effect", re.compile(r"\bdraw\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("discard_effect", re.compile(r"\bdiscard\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("search_effect", re.compile(r"\bsearch\b.+\bdeck\b", re.I | re.S), PLAYMODE_PENDING),
    RulePattern("mana_ramp", re.compile(r"\bput\b.+\bmana zone\b", re.I | re.S), PLAYMODE_PARTIAL),
    RulePattern("shield_add", re.compile(r"\badd\b.+\bshields?\b|\bput\b.+\bshields?\b", re.I | re.S), PLAYMODE_PARTIAL),
    RulePattern("extra_turn", re.compile(r"\bextra\s+turn\b", re.I), PLAYMODE_PENDING),
    RulePattern("lose_condition", re.compile(r"\blose\s+the\s+game\b", re.I), PLAYMODE_PENDING),
)


@dataclass(frozen=True)
class SpellCoveragePattern:
    tag: str
    pattern: re.Pattern[str]
    status: str
    note: str


@dataclass(frozen=True)
class CreatureCoveragePattern:
    tag: str
    pattern: re.Pattern[str]
    status: str
    note: str


SPELL_RESOLVER_PATTERNS: tuple[SpellCoveragePattern, ...] = (
    SpellCoveragePattern("apocalypse_day", re.compile(r"\bapocalypse day\b", re.I), SPELL_AUTOMATED, "Destroys all creatures when 6+ creatures are in battle."),
    SpellCoveragePattern("draw_1", re.compile(r"\bdraw (?:a|1) card\b", re.I), SPELL_AUTOMATED, "Draws one card."),
    SpellCoveragePattern("draw_2", re.compile(r"\b(?:brain serum|energy stream)\b|\bdraw up to 2 cards\b|\bdraw 2 cards\b", re.I), SPELL_AUTOMATED, "Draws up to two cards."),
    SpellCoveragePattern("draw_3", re.compile(r"\bdraw up to 3 cards\b|\bdraw 3 cards\b", re.I), SPELL_AUTOMATED, "Draws up to three cards."),
    SpellCoveragePattern("emergency_typhoon", re.compile(r"\bemergency typhoon\b", re.I), SPELL_AUTOMATED, "Draws two then discards one."),
    SpellCoveragePattern("random_discard", re.compile(r"\byour opponent discards (?:a|1) card at random\b", re.I), SPELL_AUTOMATED, "Randomly discards from opponent hand."),
    SpellCoveragePattern("search_deck", re.compile(r"\bsearch your deck\b", re.I), SPELL_PARTIAL, "Opens a deck-search choice queue."),
    SpellCoveragePattern("top_to_mana", re.compile(r"\bfaerie life\b|\bput the top card of your deck into your mana zone\b", re.I), SPELL_AUTOMATED, "Moves the top deck card to mana."),
    SpellCoveragePattern("top_to_shield", re.compile(r"\b(?:add|put) the top card of your deck (?:to|into) your shields?\b|\bput the top card of your deck into your shield zone\b", re.I), SPELL_AUTOMATED, "Moves the top deck card to shields."),
    SpellCoveragePattern("top_3_to_shields", re.compile(r"\badd up to 3 cards from the top of your deck to your shields\b", re.I), SPELL_AUTOMATED, "Moves up to three top deck cards to shields."),
    SpellCoveragePattern("top_2_to_mana", re.compile(r"\bput the top 2 cards of your deck into your mana zone\b", re.I), SPELL_AUTOMATED, "Moves two top deck cards to mana."),
    SpellCoveragePattern("mana_bonanza", re.compile(r"\bfor each card in your mana zone, put a card from the top of your deck into your mana zone tapped\b", re.I), SPELL_AUTOMATED, "Moves top deck cards to mana equal to current mana count."),
    SpellCoveragePattern("shield_to_mana", re.compile(r"\bchoose any number of your shields and put them into your mana zone\b", re.I), SPELL_AUTOMATED, "Moves your shields to mana."),
    SpellCoveragePattern("shield_to_hand", re.compile(r"\bchoose any number of your shields and put them into your hand\b", re.I), SPELL_AUTOMATED, "Moves your shields to hand."),
    SpellCoveragePattern("shield_to_grave", re.compile(r"\bchoose one of your shields and put it into your graveyard\b", re.I), SPELL_AUTOMATED, "Moves one of your shields to graveyard."),
    SpellCoveragePattern("temporary_power_breaker", re.compile(r"\b(?:power attacker \+\d+|gets? \+\d+ power|double breaker|triple breaker|speed attacker|slayer|can't be blocked this turn)\b", re.I), SPELL_AUTOMATED, "Applies a temporary battle-zone modifier."),
    SpellCoveragePattern("ignore_attack_restrictions", re.compile(r"\bignore any effects that would prevent (?:your creatures|that creature) from attacking your opponent\b", re.I), SPELL_AUTOMATED, "Temporarily removes summoning-sickness style attack restrictions."),
    SpellCoveragePattern("attack_as_tapped", re.compile(r"\byour creatures can attack it this turn as though it were tapped\b", re.I), SPELL_AUTOMATED, "Marks an untapped opponent creature as attackable."),
    SpellCoveragePattern("relentless_blitz", re.compile(r"\beach creature of that race can attack untapped creatures and can't be blocked while attacking a creature\b", re.I), SPELL_AUTOMATED, "Lets affected creatures attack untapped creatures and prevents blocks."),
    SpellCoveragePattern("miraculous_truce", re.compile(r"\bcreatures of that civilization can't attack you\b", re.I), SPELL_AUTOMATED, "Marks opponent creatures as unable to attack players."),
    SpellCoveragePattern("attacks_if_able", re.compile(r"\battacks if able\b", re.I), SPELL_AUTOMATED, "Marks affected creatures as must-attack."),
    SpellCoveragePattern("temporary_blocker", re.compile(r"\bgets \"blocker\b", re.I), SPELL_AUTOMATED, "Gives affected creatures temporary blocker."),
    SpellCoveragePattern("fruit_of_eternity", re.compile(r"\bwhenever any of your creatures would be destroyed this turn, put it into your mana zone instead\b", re.I), SPELL_AUTOMATED, "Marks destroy-to-mana replacement for the turn."),
    SpellCoveragePattern("fists_of_forever", re.compile(r"\bwhenever that creature wins a battle this turn, untap it\b", re.I), SPELL_AUTOMATED, "Marks one creature to untap after winning battle."),
    SpellCoveragePattern("tap_non_blockers", re.compile(r"\btap all creatures in the battle zone that don.?t have \"blocker", re.I), SPELL_AUTOMATED, "Taps all non-blocker creatures."),
    SpellCoveragePattern("tap_all_opponent", re.compile(r"\btap all your opponent's creatures in the battle zone\b", re.I), SPELL_AUTOMATED, "Taps all opponent creatures."),
    SpellCoveragePattern("tap_darkness_or_fire", re.compile(r"\btap all (?:darkness|fire) creatures in the battle zone\b", re.I), SPELL_AUTOMATED, "Taps all creatures of a supported civilization."),
    SpellCoveragePattern("tap_non_light", re.compile(r"\btap all creatures in the battle zone except light creatures\b", re.I), SPELL_AUTOMATED, "Taps all non-light creatures."),
    SpellCoveragePattern("tap_opponent_creature", re.compile(r"\bchoose (?:one|1) of your opponent's creatures in the battle zone\b.+\btap it\b", re.I | re.S), SPELL_PARTIAL, "Opens a target choice for tapping."),
    SpellCoveragePattern("tap_up_to_2_opponent", re.compile(r"\bchoose up to 2 of your opponent's creatures in the battle zone and tap them\b", re.I), SPELL_AUTOMATED, "Taps up to two opponent creatures."),
    SpellCoveragePattern("cloned_deflector", re.compile(r"\bcloned deflector\b", re.I), SPELL_AUTOMATED, "Taps opponent creatures using Cloned graveyard count."),
    SpellCoveragePattern("static_warp", re.compile(r"\beach player chooses one of his creatures in the battle zone\. tap the rest\b", re.I), SPELL_AUTOMATED, "Keeps one creature untapped for each player, taps the rest."),
    SpellCoveragePattern("bounce_any_creature", re.compile(r"\bchoose a creature in (?:the )?battle zone\b.+\breturn\b.+\bhand\b", re.I | re.S), SPELL_PARTIAL, "Opens a target choice for returning a creature."),
    SpellCoveragePattern("bounce_opponent_creature", re.compile(r"\breturn (?:one|up to 2|an) of your opponent's creatures?\b.+\bhand\b", re.I | re.S), SPELL_PARTIAL, "Opens a target choice for bounce."),
    SpellCoveragePattern("bounce_up_to_2_any", re.compile(r"\bchoose up to 2 creatures in the battle zone and return them to their owners' hands\b", re.I), SPELL_AUTOMATED, "Returns up to two creatures to hand."),
    SpellCoveragePattern("cloned_spiral", re.compile(r"\bcloned spiral\b", re.I), SPELL_AUTOMATED, "Returns creatures using Cloned graveyard count."),
    SpellCoveragePattern("hide_and_seek", re.compile(r"\bhide and seek\b", re.I), SPELL_AUTOMATED, "Returns an opponent non-evolution creature then discards one at random."),
    SpellCoveragePattern("hydro_hurricane", re.compile(r"\bfor each light creature\b.+\bfor each darkness creature\b", re.I | re.S), SPELL_AUTOMATED, "Returns opponent mana and creatures based on your light/darkness creatures."),
    SpellCoveragePattern("shock_hurricane", re.compile(r"\breturn any number of your creatures from the battle zone to your hand\b.+\breturn them to your opponent's hand\b", re.I | re.S), SPELL_AUTOMATED, "Returns your creatures, then the same number of opponent creatures."),
    SpellCoveragePattern("destroy_all_power_2000", re.compile(r"\bdestroy all creatures that have power 2000 or less\b", re.I), SPELL_AUTOMATED, "Destroys all 2000-or-less creatures."),
    SpellCoveragePattern("destroy_all_power_4000", re.compile(r"\bdestroy all creatures that have power 4000 or less\b", re.I), SPELL_AUTOMATED, "Destroys all 4000-or-less creatures."),
    SpellCoveragePattern("destroy_opponent_power_3000", re.compile(r"\bdestroy all your opponent's creatures that have power 3000 or less\b", re.I), SPELL_AUTOMATED, "Destroys all opponent 3000-or-less creatures."),
    SpellCoveragePattern("destroy_all_opponent", re.compile(r"\bdestroy all your opponent's creatures\b", re.I), SPELL_AUTOMATED, "Destroys all opponent creatures."),
    SpellCoveragePattern("destroy_total_power_8000", re.compile(r"\bdestroy any number of your opponent's creatures that have total power 8000 or less\b", re.I), SPELL_AUTOMATED, "Greedily destroys opponent creatures up to 8000 total power."),
    SpellCoveragePattern("destroy_chosen_power", re.compile(r"\bchoose a number less than or equal to 6000\b.+\bdestroy all creatures that have that power\b", re.I | re.S), SPELL_AUTOMATED, "Chooses a supported power and destroys matching creatures."),
    SpellCoveragePattern("cloned_blade", re.compile(r"\bcloned blade\b", re.I), SPELL_AUTOMATED, "Destroys small opponent creatures using Cloned graveyard count."),
    SpellCoveragePattern("eldritch_poison", re.compile(r"\beldritch poison\b", re.I), SPELL_AUTOMATED, "Destroys one of your darkness creatures and returns a creature from mana."),
    SpellCoveragePattern("transmogrify", re.compile(r"\btransmogrify\b", re.I), SPELL_AUTOMATED, "Destroys a creature and reveals into a non-evolution creature."),
    SpellCoveragePattern("vacuum_gel", re.compile(r"\bdestroy one of your opponent's untapped light or untapped nature creatures\b", re.I), SPELL_AUTOMATED, "Destroys an untapped light/nature opponent creature."),
    SpellCoveragePattern("destroy_blocker_6000", re.compile(r"\bdestroy one of your opponent's creatures that has \"blocker\" and power 6000 or less\b", re.I), SPELL_AUTOMATED, "Destroys one matching blocker automatically."),
    SpellCoveragePattern("destroy_blocker", re.compile(r"\bdestroy one of your opponent's creatures that has \"blocker\"\b", re.I), SPELL_AUTOMATED, "Destroys one opponent blocker automatically."),
    SpellCoveragePattern("destroy_power_2000", re.compile(r"\bdestroy (?:one|1) of your opponent's creatures that has power 2000 or less\b", re.I), SPELL_AUTOMATED, "Destroys one 2000-or-less opponent creature automatically."),
    SpellCoveragePattern("destroy_power_4000", re.compile(r"\bdestroy (?:one|1) of your opponent's creatures that has power 4000 or less\b", re.I), SPELL_AUTOMATED, "Destroys one 4000-or-less opponent creature automatically."),
    SpellCoveragePattern("destroy_one_creature", re.compile(r"\bterror pit\b|\bdestroy one of your opponent's creatures\b", re.I), SPELL_AUTOMATED, "Destroys one opponent creature automatically."),
    SpellCoveragePattern("destroy_untapped_creature", re.compile(r"\bdestroy one of your opponent's untapped creatures\b", re.I), SPELL_AUTOMATED, "Destroys one untapped opponent creature automatically."),
    SpellCoveragePattern("destroy_up_to_2_creatures", re.compile(r"\bdestroy up to 2 of your opponent's creatures\b", re.I), SPELL_AUTOMATED, "Destroys up to two opponent creatures automatically."),
    SpellCoveragePattern("destroy_your_creature", re.compile(r"\bdestroy (?:one|up to 2) of your creatures\b", re.I), SPELL_AUTOMATED, "Destroys your own creature(s) automatically."),
    SpellCoveragePattern("destroy_your_creatures_draw", re.compile(r"\bdestroy any number of your creatures\b.+\bdraw that many cards\b", re.I | re.S), SPELL_AUTOMATED, "Destroys your creatures and draws that many cards."),
    SpellCoveragePattern("opponent_sacrifice_creature", re.compile(r"\byour opponent chooses one of his creatures in the battle zone and destroys it\b", re.I), SPELL_AUTOMATED, "Opponent sacrifices first creature automatically."),
    SpellCoveragePattern("opponent_creature_or_mana_to_grave", re.compile(r"\byour opponent chooses one of his creatures in the battle zone or a card in his mana zone and puts it into his graveyard\b", re.I), SPELL_AUTOMATED, "Opponent sacrifices creature or mana automatically."),
    SpellCoveragePattern("opponent_creature_or_shield_to_grave", re.compile(r"\byour opponent chooses one of his creatures in the battle zone or one of his shields and puts it into his graveyard\b", re.I), SPELL_AUTOMATED, "Opponent sacrifices creature or shield automatically."),
    SpellCoveragePattern("cloned_nightmare", re.compile(r"\bcloned nightmare\b", re.I), SPELL_AUTOMATED, "Random discards using Cloned graveyard count."),
    SpellCoveragePattern("discard_all", re.compile(r"\byour opponent discards all cards from his hand\b", re.I), SPELL_AUTOMATED, "Opponent discards all hand cards."),
    SpellCoveragePattern("discard_2", re.compile(r"\byour opponent chooses and discards 2 cards from his hand\b", re.I), SPELL_AUTOMATED, "Opponent discards two cards."),
    SpellCoveragePattern("discard_for_light_creatures", re.compile(r"\byour opponent chooses and discards a card from his hand for each light creature he has in the battle zone\b", re.I), SPELL_AUTOMATED, "Opponent discards for each light creature they control."),
    SpellCoveragePattern("mana_to_hand", re.compile(r"\breturn a card from your mana zone to your hand\b", re.I), SPELL_AUTOMATED, "Returns the first mana card to hand."),
    SpellCoveragePattern("mana_spell_to_hand", re.compile(r"\breturn a spell from your mana zone to your hand\b", re.I), SPELL_AUTOMATED, "Returns the first spell in mana to hand."),
    SpellCoveragePattern("mana_creature_6_to_hand", re.compile(r"\breturn a creature that costs 6 or more from your mana zone to your hand\b", re.I), SPELL_AUTOMATED, "Returns the first 6+ cost creature in mana to hand."),
    SpellCoveragePattern("mana_2_to_hand", re.compile(r"\breturn up to 2 cards from your mana zone to your hand\b", re.I), SPELL_AUTOMATED, "Returns up to two mana cards to hand."),
    SpellCoveragePattern("mana_3_to_hand", re.compile(r"\breturn up to 3 cards from your mana zone to your hand\b", re.I), SPELL_AUTOMATED, "Returns up to three mana cards to hand."),
    SpellCoveragePattern("all_mana_to_hand", re.compile(r"\beach player returns all cards from his mana zone to his hand\b", re.I), SPELL_AUTOMATED, "Returns both players' mana to hand."),
    SpellCoveragePattern("creature_grave_to_hand", re.compile(r"\breturn a creature from your graveyard to your hand\b", re.I), SPELL_AUTOMATED, "Returns the first creature in graveyard to hand."),
    SpellCoveragePattern("grave_2_creatures_to_hand", re.compile(r"\breturn up to 2 creatures from your graveyard to your hand\b", re.I), SPELL_AUTOMATED, "Returns up to two graveyard creatures to hand."),
    SpellCoveragePattern("grave_2_creatures_to_mana", re.compile(r"\bput up to 2 creatures from your graveyard into your mana zone\b", re.I), SPELL_AUTOMATED, "Moves up to two graveyard creatures to mana."),
    SpellCoveragePattern("mana_to_grave_draw", re.compile(r"\bput any number of cards from your mana zone into your graveyard\b.+\bdraw that many cards\b", re.I | re.S), SPELL_AUTOMATED, "Moves mana to graveyard and draws the same amount."),
    SpellCoveragePattern("discard_then_draw", re.compile(r"\bdiscard any number of cards from your hand\b.+\bdraw that many cards\b", re.I | re.S), SPELL_AUTOMATED, "Discards your hand and draws that many."),
    SpellCoveragePattern("cycle_hands", re.compile(r"\beach player counts the cards in his hand, shuffles these cards into his deck, then draws that many cards\b", re.I), SPELL_AUTOMATED, "Cycles both players' hands through deck."),
    SpellCoveragePattern("cosmic_darts", re.compile(r"\byour opponent chooses one of your shields\. look at it\. if it's a spell\b", re.I), SPELL_AUTOMATED, "Checks a shield and casts it if it is a spell."),
    SpellCoveragePattern("opponent_deck_to_grave", re.compile(r"\bsearch your opponent's deck\b.+\bput (?:it|them) into his graveyard\b", re.I | re.S), SPELL_AUTOMATED, "Moves up to two opponent deck cards to graveyard."),
    SpellCoveragePattern("reveal_top_4_water", re.compile(r"\breveal the top 4 cards of your deck\b.+\bput all water cards from among them into your hand\b", re.I | re.S), SPELL_AUTOMATED, "Reveals top four, keeps water cards, bins the rest."),
    SpellCoveragePattern("reveal_top_4_blocker", re.compile(r"\breveal the top 4 cards of your deck\b.+\bhas \"blocker\" into your hand\b", re.I | re.S), SPELL_AUTOMATED, "Reveals top four and keeps a blocker."),
    SpellCoveragePattern("look_top_4_pick", re.compile(r"\blook at the top 4 cards of your deck\b.+\bput one of them into your hand\b", re.I | re.S), SPELL_AUTOMATED, "Looks at top four and keeps one card."),
    SpellCoveragePattern("look_opponent_hand_shields", re.compile(r"\blook at your opponent's hand and shields\b", re.I), SPELL_AUTOMATED, "Logs opponent hidden zone counts."),
    SpellCoveragePattern("look_opponent_shields", re.compile(r"\blook at up to 3 of your opponent's shields\b", re.I), SPELL_AUTOMATED, "Logs opponent shield look."),
    SpellCoveragePattern("discard_darkness_spells", re.compile(r"\blook at your opponent's hand\b.+\bdiscards all darkness spells\b", re.I | re.S), SPELL_AUTOMATED, "Discards opponent Darkness spells."),
    SpellCoveragePattern("discard_chosen_hand", re.compile(r"\blook at your opponent's hand and choose a card from it\b", re.I), SPELL_AUTOMATED, "Discards one opponent hand card."),
    SpellCoveragePattern("roulette_cost_discard", re.compile(r"\bchoose a number\b.+\bdiscard from it each card that has that cost\b", re.I | re.S), SPELL_AUTOMATED, "Chooses a cost and discards matching hand cards."),
    SpellCoveragePattern("dance_of_the_sproutlings", re.compile(r"\bdance of the sproutlings\b", re.I), SPELL_AUTOMATED, "Moves same-race creatures from hand to mana."),
    SpellCoveragePattern("opponent_creature_to_mana", re.compile(r"\bchoose (?:1|one) of your opponent's .+ creatures?.+\bmana zone\b", re.I | re.S), SPELL_AUTOMATED, "Moves a matching opponent creature to mana."),
    SpellCoveragePattern("opponent_creature_1_to_mana", re.compile(r"\bchoose 1 of your opponent's creatures in the battle zone and put it into his mana zone\b", re.I), SPELL_AUTOMATED, "Moves one opponent creature to mana."),
    SpellCoveragePattern("opponent_shields_to_grave", re.compile(r"\bchoose up to 3 of your opponent's shields and put them into his graveyard\b", re.I), SPELL_AUTOMATED, "Moves up to three opponent shields to graveyard."),
    SpellCoveragePattern("miraculous_meltdown", re.compile(r"\byour opponent chooses one of his shields for each shield you have\b.+\bputs the rest of his shields into his hand\b", re.I | re.S), SPELL_AUTOMATED, "Opponent keeps shields equal to yours and moves extras to hand."),
    SpellCoveragePattern("siren_concerto", re.compile(r"\bput a card from your mana zone into your hand\b.+\bput a card from your hand into your mana zone\b", re.I | re.S), SPELL_AUTOMATED, "Swaps one mana card with one hand card."),
    SpellCoveragePattern("upheaval", re.compile(r"\beach player puts all the cards from his mana zone into his hand\b.+\bputs all the cards from his hand into his mana zone tapped\b", re.I | re.S), SPELL_AUTOMATED, "Swaps both players' mana and hands."),
    SpellCoveragePattern("slash_and_burn", re.compile(r"\bwhenever any of your opponent's creatures is destroyed this turn\b", re.I), SPELL_AUTOMATED, "Arms a delayed destroy trigger for the turn."),
    SpellCoveragePattern("miraculous_plague", re.compile(r"\bmiraculous plague\b", re.I), SPELL_AUTOMATED, "Performs the creature and mana split choices deterministically."),
    SpellCoveragePattern("soulswap", re.compile(r"\bsoulswap\b", re.I), SPELL_AUTOMATED, "Moves a creature to mana and summons a matching non-evolution creature."),
    SpellCoveragePattern("mana_to_shield", re.compile(r"\badd a card from your mana zone to your shields face down\b", re.I), SPELL_AUTOMATED, "Moves a mana card to shields."),
    SpellCoveragePattern("opponent_mana_to_grave", re.compile(r"\bchoose a card in your opponent's mana zone and put it into his graveyard\b", re.I), SPELL_AUTOMATED, "Moves opponent mana to graveyard."),
    SpellCoveragePattern("hand_to_shield", re.compile(r"\badd a card from your hand to your shields face down\b", re.I), SPELL_AUTOMATED, "Moves one hand card to shields."),
    SpellCoveragePattern("your_creature_to_mana", re.compile(r"\bput 1 of your creatures from the battle zone into your mana zone\b", re.I), SPELL_AUTOMATED, "Moves one of your creatures to mana."),
    SpellCoveragePattern("creature_to_shield", re.compile(r"\bchoose a non-evolution creature in the battle zone and add it to its owner's shields\b", re.I), SPELL_AUTOMATED, "Moves a non-evolution creature to shields."),
    SpellCoveragePattern("whisking_whirlwind", re.compile(r"\bat the end of the turn, untap all your creatures in the battle zone\b", re.I), SPELL_AUTOMATED, "Untaps your creatures immediately in Playmode."),
    SpellCoveragePattern("zombie_carnival", re.compile(r"\bzombie carnival\b", re.I), SPELL_AUTOMATED, "Returns up to three same-race creatures from graveyard to hand."),
    SpellCoveragePattern("charger_keyword", re.compile(r"\bcharger\b", re.I), SPELL_PARTIAL, "Spell goes to mana after resolving; custom spell text may still need automation."),
)


SPELL_GAP_PATTERNS: tuple[SpellCoveragePattern, ...] = (
    SpellCoveragePattern("cast_restriction", re.compile(r"\byou can cast this spell only if\b", re.I), SPELL_MISSING, "Cast restriction is not enforced yet."),
    SpellCoveragePattern("choose_creature_generic", re.compile(r"\bchoose (?:one|a) creature\b", re.I), SPELL_MISSING, "Generic creature target selection needs an action queue."),
    SpellCoveragePattern("may_effect", re.compile(r"\byou may\b", re.I), SPELL_MISSING, "Optional choices need a yes/no prompt."),
    SpellCoveragePattern("until_end_of_turn", re.compile(r"\buntil the end of the turn\b|\buntil end of turn\b", re.I), SPELL_MISSING, "Temporary effects need duration tracking."),
    SpellCoveragePattern("power_modifier", re.compile(r"\bgets? [+-]?\d+\s*power\b", re.I), SPELL_MISSING, "Power modifiers are not fully tracked."),
    SpellCoveragePattern("cant_attack_or_block", re.compile(r"\bcan't attack\b|\bcannot attack\b|\bcan't be blocked\b|\bcannot be blocked\b", re.I), SPELL_MISSING, "Attack/block restrictions are not fully enforced."),
    SpellCoveragePattern("look_or_reveal", re.compile(r"\blook at\b|\breveal\b", re.I), SPELL_MISSING, "Private information reveal/look effects need UI support."),
    SpellCoveragePattern("shield_trigger_only", re.compile(r"^\s*shield\s*trigger\s*$", re.I), SPELL_PARTIAL, "Shield Trigger timing works, but there is no additional effect text."),
)


CREATURE_RESOLVER_PATTERNS: tuple[CreatureCoveragePattern, ...] = (
    CreatureCoveragePattern("double_breaker", re.compile(r"\bdouble\s+breaker\b", re.I), CREATURE_AUTOMATED, "Breaks two shields during attacks."),
    CreatureCoveragePattern("triple_breaker", re.compile(r"\btriple\s+breaker\b", re.I), CREATURE_AUTOMATED, "Breaks three shields during attacks."),
    CreatureCoveragePattern("speed_attacker", re.compile(r"\bspeed\s+attacker\b", re.I), CREATURE_AUTOMATED, "Can attack the turn it enters."),
    CreatureCoveragePattern("shield_trigger", re.compile(r"\bshield\s*trigger\b", re.I), CREATURE_AUTOMATED, "Comes into the battle zone from broken shields."),
    CreatureCoveragePattern("evolution", re.compile(r"\bevolution\b", re.I), CREATURE_AUTOMATED, "Evolves onto a matching creature stack."),
    CreatureCoveragePattern("vortex_evolution", re.compile(r"\bvortex\s+evolution\b", re.I), CREATURE_AUTOMATED, "Evolves onto two matching creatures."),
    CreatureCoveragePattern("blocker", re.compile(r"\bblocker\b", re.I), CREATURE_AUTOMATED, "Can be chosen as a blocker response."),
    CreatureCoveragePattern("slayer", re.compile(r"\bslayer\b", re.I), CREATURE_AUTOMATED, "Destroys the opposing creature after battle."),
    CreatureCoveragePattern("power_attacker", re.compile(r"\bpower\s+attacker\s*\+(\d+)", re.I), CREATURE_AUTOMATED, "Adds power while attacking."),
    CreatureCoveragePattern("cant_be_blocked", re.compile(r"\bcan(?:not|'t)\s+be\s+blocked\b", re.I), CREATURE_AUTOMATED, "Prevents blocker choices."),
    CreatureCoveragePattern("attack_untapped", re.compile(r"\bcan attack untapped creatures\b", re.I), CREATURE_AUTOMATED, "Can target untapped creatures."),
    CreatureCoveragePattern("cant_attack_players", re.compile(r"\bcan(?:not|'t)\s+attack players\b|\bwhile your opponent has no shields,\s*this creature can(?:not|'t)\s+attack\b", re.I), CREATURE_AUTOMATED, "Prevents illegal player/direct attacks."),
    CreatureCoveragePattern("cant_be_attacked", re.compile(r"\bcan(?:not|'t)\s+be attacked\b", re.I), CREATURE_AUTOMATED, "Prevents illegal creature attack targets."),
    CreatureCoveragePattern("cip_draw", re.compile(r"\bwhen you put this creature into the battle zone\b.+\bdraw\b", re.I | re.S), CREATURE_AUTOMATED, "Draws cards on enter-battle for supported text."),
    CreatureCoveragePattern("cip_mana", re.compile(r"\bwhen you put this creature into the battle zone\b.+\bmana zone\b", re.I | re.S), CREATURE_AUTOMATED, "Moves supported cards to mana on enter-battle."),
    CreatureCoveragePattern("cip_shield", re.compile(r"\bwhen you put this creature into the battle zone\b.+\bshields?\b", re.I | re.S), CREATURE_AUTOMATED, "Supported enter-battle shield effects resolve automatically."),
    CreatureCoveragePattern("cip_destroy", re.compile(r"\bwhen you put this creature into the battle zone\b.+\bdestroy\b", re.I | re.S), CREATURE_PARTIAL, "Common enter-battle destroy effects are automated; custom choices may need queue support."),
    CreatureCoveragePattern("cip_bounce", re.compile(r"\bwhen you put this creature into the battle zone\b.+\breturn\b.+\bhand\b", re.I | re.S), CREATURE_PARTIAL, "Common enter-battle bounce effects are automated; custom choices may need queue support."),
    CreatureCoveragePattern("cip_discard", re.compile(r"\bwhen you put this creature into the battle zone\b.+\bdiscard\b", re.I | re.S), CREATURE_AUTOMATED, "Supported enter-battle discard effects resolve automatically."),
    CreatureCoveragePattern("attack_draw", re.compile(r"\bwhen(?:ever)? this creature attacks\b.+\bdraws?\b", re.I | re.S), CREATURE_AUTOMATED, "Supported attack-trigger draw effects resolve automatically."),
    CreatureCoveragePattern("attack_discard", re.compile(r"\bwhen(?:ever)? this creature attacks\b.+\bdiscards?\b", re.I | re.S), CREATURE_AUTOMATED, "Supported attack-trigger discard effects resolve automatically."),
    CreatureCoveragePattern("attack_search", re.compile(r"\bwhen(?:ever)? this creature attacks\b.+\bsearch your deck\b", re.I | re.S), CREATURE_PARTIAL, "Attack-trigger deck search opens a pending choice."),
    CreatureCoveragePattern("mana_tapped_text", re.compile(r"\bput into your mana zone tapped\b", re.I), CREATURE_AUTOMATED, "Multicolor/tapped mana placement is supported."),
)


CREATURE_GAP_PATTERNS: tuple[CreatureCoveragePattern, ...] = (
    CreatureCoveragePattern("tap_ability", re.compile(r"(?:\$tap|\btap ability\b)", re.I), CREATURE_PARTIAL, "Tap abilities need explicit activated-ability UI."),
    CreatureCoveragePattern("silent_skill", re.compile(r"\bsilent\s+skill\b", re.I), CREATURE_PARTIAL, "Silent Skill needs its own activation timing."),
    CreatureCoveragePattern("survivor", re.compile(r"\bsurvivor\b", re.I), CREATURE_PARTIAL, "Survivor sharing needs board-wide continuous effect handling."),
    CreatureCoveragePattern("wave_striker", re.compile(r"\bwave\s+striker\b", re.I), CREATURE_PARTIAL, "Wave Striker needs count-based continuous effects."),
    CreatureCoveragePattern("turbo_rush", re.compile(r"\bturbo\s+rush\b", re.I), CREATURE_PARTIAL, "Turbo Rush needs shield-break event tracking."),
    CreatureCoveragePattern("metamorph", re.compile(r"\bmetamorph\b", re.I), CREATURE_PARTIAL, "Metamorph needs mana-count conditional effect handling."),
    CreatureCoveragePattern("stealth", re.compile(r"\bstealth\b", re.I), CREATURE_PARTIAL, "Stealth needs civilization-specific blocker rules."),
    CreatureCoveragePattern("must_attack", re.compile(r"\battacks each turn if able\b|\battack .* if able\b", re.I), CREATURE_PARTIAL, "Must-attack enforcement needs turn-end validation."),
    CreatureCoveragePattern("cost_modifier", re.compile(r"\bcosts? \d+ (?:less|more)\b|\bcan't cost less than\b", re.I), CREATURE_PARTIAL, "Cost modifiers need continuous mana-cost recalculation."),
    CreatureCoveragePattern("destroy_replacement", re.compile(r"\bwould be destroyed\b|\bwould be put into your graveyard from the battle zone\b", re.I), CREATURE_PARTIAL, "Destroy replacement effects need central zone-move hooks."),
    CreatureCoveragePattern("destroyed_trigger", re.compile(r"\bwhen this creature is destroyed\b|\bwhen this creature wins a battle\b", re.I), CREATURE_PARTIAL, "Destroyed/wins-battle triggers need post-battle event hooks."),
    CreatureCoveragePattern("other_creature_trigger", re.compile(r"\bwhenever (?:another|you put|your opponent puts).+creature.+battle zone\b", re.I), CREATURE_PARTIAL, "Other-creature event triggers need a board event queue."),
    CreatureCoveragePattern("static_buff", re.compile(r"\bgets? [+-]?\d+\s*power\b|\bfor each\b.+\bpower\b", re.I | re.S), CREATURE_PARTIAL, "Static/conditional power modifiers need continuous recalculation."),
    CreatureCoveragePattern("may_choice", re.compile(r"\byou may\b", re.I), CREATURE_PARTIAL, "Optional choices need a yes/no prompt."),
    CreatureCoveragePattern("generic_choose", re.compile(r"\bchoose\b", re.I), CREATURE_PARTIAL, "Generic targeting needs an action queue."),
    CreatureCoveragePattern("unique_text", re.compile(r".+"), CREATURE_MISSING, "No resolver pattern currently matches this creature text."),
)


def classify_card_rules(card) -> dict:
    text = f"{getattr(card, 'name', '')} {getattr(card, 'type', '')} {getattr(card, 'race_label', '')} {getattr(card, 'text', '')}"
    tags: list[str] = []
    statuses: dict[str, str] = {}
    for rule in RULE_PATTERNS:
        if rule.pattern.search(text):
            tags.append(rule.tag)
            statuses[rule.tag] = rule.playmode_status
    if not tags and str(getattr(card, "text", "") or "").strip():
        tags.append("unique_text")
        statuses["unique_text"] = PLAYMODE_PENDING
    return {
        "id": getattr(card, "id", None),
        "name": getattr(card, "name", ""),
        "type": getattr(card, "type", ""),
        "tags": tags,
        "playmode_ready_tags": [tag for tag in tags if statuses.get(tag) == PLAYMODE_READY],
        "playmode_partial_tags": [tag for tag in tags if statuses.get(tag) == PLAYMODE_PARTIAL],
        "playmode_pending_tags": [tag for tag in tags if statuses.get(tag) == PLAYMODE_PENDING],
    }


def classify_spell_coverage(card) -> dict | None:
    card_type = str(getattr(card, "type", "") or "")
    if "spell" not in card_type.lower():
        return None
    name = str(getattr(card, "name", "") or "")
    text = str(getattr(card, "text", "") or "")
    haystack = f"{name}\n{text}"
    resolver_matches = [pattern for pattern in SPELL_RESOLVER_PATTERNS if pattern.pattern.search(haystack)]
    significant_text = re.sub(r"shield\s*trigger\s*\([^)]*\)", "", text, flags=re.I | re.S)
    significant_text = re.sub(r"you may cast it(?: immediately)? for no cost\.?", "", significant_text, flags=re.I)
    gap_matches = [pattern for pattern in SPELL_GAP_PATTERNS if pattern.pattern.search(significant_text)]
    has_real_text = bool(text.strip())

    automated_tags = [pattern.tag for pattern in resolver_matches if pattern.status == SPELL_AUTOMATED]
    partial_tags = [pattern.tag for pattern in resolver_matches if pattern.status == SPELL_PARTIAL]
    missing_tags = [pattern.tag for pattern in gap_matches]
    if "temporary_power_breaker" in automated_tags or "ignore_attack_restrictions" in automated_tags:
        missing_tags = [tag for tag in missing_tags if tag not in {"until_end_of_turn", "power_modifier", "cant_attack_or_block"}]
    if "temporary_blocker" in automated_tags or "attacks_if_able" in automated_tags:
        missing_tags = [tag for tag in missing_tags if tag != "may_effect"]
    if automated_tags:
        missing_tags = [tag for tag in missing_tags if tag not in {"cast_restriction", "may_effect", "look_or_reveal", "choose_creature_generic", "cant_attack_or_block"}]
    notes = [pattern.note for pattern in resolver_matches + gap_matches]

    if not has_real_text:
        status = "no_effect_text"
    elif missing_tags and resolver_matches:
        status = SPELL_PARTIAL
    elif missing_tags:
        status = SPELL_MISSING
    elif partial_tags:
        status = SPELL_PARTIAL
    elif automated_tags:
        status = SPELL_AUTOMATED
    else:
        status = SPELL_MISSING
        missing_tags = ["unmatched_spell_text"]
        notes.append("No automated resolver pattern currently matches this spell text.")

    return {
        "id": getattr(card, "id", None),
        "name": name,
        "type": card_type,
        "civilizations": str(getattr(card, "civilizations", "") or ""),
        "cost": getattr(card, "cost", None),
        "set_name": getattr(card, "set_name", None),
        "status": status,
        "automated_tags": automated_tags,
        "partial_tags": partial_tags,
        "missing_tags": missing_tags,
        "notes": notes,
        "text": text,
    }


def classify_creature_coverage(card) -> dict | None:
    card_type = str(getattr(card, "type", "") or "")
    if "creature" not in card_type.lower():
        return None
    name = str(getattr(card, "name", "") or "")
    text = str(getattr(card, "text", "") or "")
    race_label = str(getattr(card, "race_label", "") or "")
    haystack = f"{name}\n{card_type}\n{race_label}\n{text}"
    resolver_matches = [pattern for pattern in CREATURE_RESOLVER_PATTERNS if pattern.pattern.search(haystack)]
    gap_matches = [pattern for pattern in CREATURE_GAP_PATTERNS[:-1] if pattern.pattern.search(text)]
    has_real_text = bool(text.strip())

    automated_tags = [pattern.tag for pattern in resolver_matches if pattern.status == CREATURE_AUTOMATED]
    partial_tags = [pattern.tag for pattern in resolver_matches if pattern.status == CREATURE_PARTIAL]
    partial_tags.extend(pattern.tag for pattern in gap_matches if pattern.status == CREATURE_PARTIAL)
    missing_tags: list[str] = []
    if has_real_text and not resolver_matches and not gap_matches:
        missing_tags.append("unique_text")

    # These tags are intentionally broad: if the matching resolver covers the same
    # language, do not also count it as a generic unsupported choice/static gap.
    if resolver_matches:
        covered_generic_tags = {"generic_choose", "may_choice"}
        if any(pattern.tag.startswith("cip_") or pattern.tag.startswith("attack_") for pattern in resolver_matches):
            covered_generic_tags.update({"static_buff"})
        partial_tags = [tag for tag in partial_tags if tag not in covered_generic_tags]

    notes = [pattern.note for pattern in resolver_matches + gap_matches]
    if missing_tags:
        notes.append(CREATURE_GAP_PATTERNS[-1].note)

    if not has_real_text:
        status = "vanilla"
    elif missing_tags:
        status = CREATURE_MISSING
    elif partial_tags:
        status = CREATURE_PARTIAL
    elif automated_tags:
        status = CREATURE_AUTOMATED
    else:
        status = CREATURE_MISSING
        missing_tags = ["unique_text"]
        notes.append(CREATURE_GAP_PATTERNS[-1].note)

    return {
        "id": getattr(card, "id", None),
        "name": name,
        "type": card_type,
        "race_label": race_label,
        "civilizations": str(getattr(card, "civilizations", "") or ""),
        "cost": getattr(card, "cost", None),
        "power": getattr(card, "power", None),
        "set_name": getattr(card, "set_name", None),
        "status": status,
        "automated_tags": sorted(set(automated_tags)),
        "partial_tags": sorted(set(partial_tags)),
        "missing_tags": missing_tags,
        "notes": notes,
        "text": text,
    }


def build_rules_coverage(cards: Iterable) -> dict:
    items = [classify_card_rules(card) for card in cards]
    tag_counts: Counter[str] = Counter()
    ready_counts: Counter[str] = Counter()
    partial_counts: Counter[str] = Counter()
    pending_counts: Counter[str] = Counter()
    for item in items:
        tag_counts.update(item["tags"])
        ready_counts.update(item["playmode_ready_tags"])
        partial_counts.update(item["playmode_partial_tags"])
        pending_counts.update(item["playmode_pending_tags"])
    cards_with_pending = [item for item in items if item["playmode_pending_tags"]]
    return {
        "total_cards": len(items),
        "cards_with_rules_text": sum(1 for item in items if item["tags"]),
        "cards_with_pending_playmode_rules": len(cards_with_pending),
        "tag_counts": dict(tag_counts.most_common()),
        "playmode_ready_tag_counts": dict(ready_counts.most_common()),
        "playmode_partial_tag_counts": dict(partial_counts.most_common()),
        "playmode_pending_tag_counts": dict(pending_counts.most_common()),
        "highest_priority_pending": cards_with_pending[:80],
    }


def build_spell_coverage(cards: Iterable) -> dict:
    items = [item for card in cards if (item := classify_spell_coverage(card))]
    status_counts: Counter[str] = Counter(item["status"] for item in items)
    automated_counts: Counter[str] = Counter()
    partial_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    for item in items:
        automated_counts.update(item["automated_tags"])
        partial_counts.update(item["partial_tags"])
        missing_counts.update(item["missing_tags"])

    missing_items = [item for item in items if item["status"] == SPELL_MISSING]
    partial_items = [item for item in items if item["status"] == SPELL_PARTIAL]
    automated_items = [item for item in items if item["status"] == SPELL_AUTOMATED]
    return {
        "total_spells": len(items),
        "status_counts": dict(status_counts.most_common()),
        "automated_tag_counts": dict(automated_counts.most_common()),
        "partial_tag_counts": dict(partial_counts.most_common()),
        "missing_tag_counts": dict(missing_counts.most_common()),
        "automated": automated_items,
        "partial": partial_items,
        "missing": missing_items,
        "highest_priority_missing": missing_items[:80],
    }


def build_creature_coverage(cards: Iterable) -> dict:
    items = [item for card in cards if (item := classify_creature_coverage(card))]
    status_counts: Counter[str] = Counter(item["status"] for item in items)
    automated_counts: Counter[str] = Counter()
    partial_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    for item in items:
        automated_counts.update(item["automated_tags"])
        partial_counts.update(item["partial_tags"])
        missing_counts.update(item["missing_tags"])

    missing_items = [item for item in items if item["status"] == CREATURE_MISSING]
    partial_items = [item for item in items if item["status"] == CREATURE_PARTIAL]
    automated_items = [item for item in items if item["status"] == CREATURE_AUTOMATED]
    return {
        "total_creatures": len(items),
        "status_counts": dict(status_counts.most_common()),
        "automated_tag_counts": dict(automated_counts.most_common()),
        "partial_tag_counts": dict(partial_counts.most_common()),
        "missing_tag_counts": dict(missing_counts.most_common()),
        "automated": automated_items,
        "partial": partial_items,
        "missing": missing_items,
        "highest_priority_missing": missing_items[:80],
    }
