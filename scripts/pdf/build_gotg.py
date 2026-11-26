"""Turn the OCR'd Glory of the Giants into compendium records.

The book has no text layer, so everything here starts from OCR (see pdf2md.py).
Feats, backgrounds and the subclass are written out from the page text; magic
items are sliced mechanically and their stat line is parsed into `data`.

    python scripts/pdf/build_gotg.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import despace  # noqa: E402
import polish  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.normalize import canonical as compendium_format  # noqa: E402

COMPENDIUM = ROOT / "content" / "compendium" / "gotg"
LOGS = ROOT / "logs"
SOURCE = "gotg"
URL = "https://www.dndbeyond.com/sources/dnd/bgg"
LICENSE = "proprietary"
PAGE_OFFSET = 4  # PDF page = printed page + 4


# --- feats ---------------------------------------------------------------

FEATS = [
    {
        "name": "Ember of the Fire Giant",
        "prerequisite": "4th level, Strike of the Giants (Fire Strike) feat",
        "page": 17,
        "text": """You've manifested the fiery combat emblematic of fire giants, granting you the following benefits:

**Ability Score Increase.** Increase your Strength, Constitution, or Wisdom score by 1, to a maximum of 20.

**Born of Flame.** You have resistance to fire damage.

**Searing Ignition.** When you take the Attack action on your turn, you can replace a single attack with a magical burst of flame. Each creature of your choice in a 15-foot-radius sphere centered on you must make a Dexterity saving throw (DC equals 8 + your proficiency bonus + the modifier of the ability increased by this feat). On a failed save, a creature takes fire damage equal to 1d8 + your proficiency bonus, and it has the blinded condition until the start of your next turn. On a successful save, the creature takes half as much damage only.

You can use your Searing Ignition a number of times equal to your proficiency bonus (but no more than once per turn), and you regain all expended uses when you finish a long rest.""",
    },
    {
        "name": "Fury of the Frost Giant",
        "prerequisite": "4th level, Strike of the Giants (Frost Strike) feat",
        "page": 17,
        "text": """You've manifested the icy might emblematic of frost giants, granting you the following benefits:

**Ability Score Increase.** Increase your Strength, Constitution, or Wisdom score by 1, to a maximum of 20.

**Born of Ice.** You have resistance to cold damage.

**Frigid Retaliation.** Immediately after a creature you can see within 30 feet of you hits you with an attack roll and deals damage, you can use your reaction to retaliate with a conjured blast of ice. The creature must make a Constitution saving throw (DC equals 8 + your proficiency bonus + the modifier of the ability increased by this feat). On a failed save, the creature takes cold damage equal to 1d8 + your proficiency bonus, and its speed is reduced to 0 until the end of its next turn.

You can use this reaction a number of times equal to your proficiency bonus, and you regain all expended uses when you finish a long rest.""",
    },
    {
        "name": "Guile of the Cloud Giant",
        "prerequisite": "4th level, Strike of the Giants (Cloud Strike) feat",
        "page": 18,
        "text": """You've manifested the confounding magic emblematic of cloud giants, granting you the following benefits:

**Ability Score Increase.** Increase your Strength, Constitution, or Charisma score by 1, to a maximum of 20.

**Cloudy Escape.** When a creature you can see hits you with an attack roll, you can use your reaction to give yourself resistance to that attack's damage. You then teleport to an unoccupied space that you can see within 30 feet of yourself.

You can use this reaction a number of times equal to your proficiency bonus, and you regain all expended uses when you finish a long rest.""",
    },
    {
        "name": "Keenness of the Stone Giant",
        "prerequisite": "4th level, Strike of the Giants (Stone Strike) feat",
        "page": 18,
        "text": """You've manifested the physical talents emblematic of stone giants, granting you the following benefits:

**Ability Score Increase.** Increase your Strength, Constitution, or Wisdom score by 1, to a maximum of 20.

**Cavernous Sight.** You gain darkvision with a range of 60 feet. If you already have darkvision from another source, its range increases by 60 feet.

**Stone Throw.** As a bonus action, you can take a rock and make a magical attack with it. The attack is a ranged spell attack with a range of 60 feet that uses the ability score you increased with this feat as the spellcasting ability. On a hit, the rock deals 1d10 force damage, and the target must succeed on a Strength saving throw (DC equals 8 + your proficiency bonus + the spellcasting ability modifier) or have the prone condition.

You can use this bonus action a number of times equal to your proficiency bonus, and you regain all expended uses when you finish a long rest.""",
    },
    {
        "name": "Rune Shaper",
        "prerequisite": "Spellcasting feature or Rune Carver background",
        "page": 18,
        "text": """You've studied the magic of Giant runes, granting you the following benefits:

**Comprehend Languages.** You learn the *comprehend languages* spell. You can cast this spell without expending a spell slot, and you must finish a long rest before you can cast it in this way again. You can also cast this spell using any spell slots you have.

**Rune Magic.** You know a number of runes equal to half your proficiency bonus (rounded down), chosen from the Rune Spells table. Whenever you finish a long rest, you can inscribe each rune you know onto one nonmagical weapon, armor, piece of clothing, or other object you touch. You temporarily learn the 1st-level spells that correspond to the runes you inscribed, as specified on the Rune Spells table, and you know those spells until you finish a long rest, when the runes fade. While you are wearing or carrying any rune-marked object, you can cast the spells associated with those runes using any spell slots you have.

You can also invoke a rune inscribed on an object you are wearing or carrying and cast its associated spell without expending a spell slot or using material components. Once you cast the spell in this way, you can't do so again until you finish a long rest. Your spellcasting ability for this feat is Intelligence, Wisdom, or Charisma (choose when you select this feat).

Each time you gain a level, you can replace one of the runes you know with another one from the Rune Spells table.""",
    },
    {
        "name": "Soul of the Storm Giant",
        "prerequisite": "4th level, Strike of the Giants (Storm Strike) feat",
        "page": 19,
        "text": """You've manifested the tempest magic emblematic of storm giants, granting you the following benefits:

**Ability Score Increase.** Increase your Strength, Wisdom, or Charisma score by 1, to a maximum of 20.

**Maelstrom Aura.** As a bonus action, you surround yourself with an aura of magical wind and lightning that extends 10 feet from you in every direction but not through total cover. The aura lasts until the start of your next turn or until you are incapacitated. While the aura is active, you have resistance to lightning and thunder damage. In addition, attack rolls against you have disadvantage, and whenever another creature starts its turn within the aura, you can force the creature to make a Strength saving throw (DC equals 8 + your proficiency bonus + the ability modifier of the score increased by this feat). On a failed save, the creature's speed is halved until the start of its next turn.

You can use this bonus action a number of times equal to your proficiency bonus, and you regain all expended uses when you finish a long rest.""",
    },
    {
        "name": "Strike of the Giants",
        "prerequisite": "Martial Weapon Proficiency or Giant Foundling background",
        "page": 19,
        "text": """You have absorbed primeval magic that gives you an echo of the might of giants. When you take this feat, choose one of the benefits listed below. Once per turn, when you hit a target with a melee weapon attack or a ranged weapon attack using a thrown weapon, you can imbue the attack with an additional effect depending on the benefit you chose:

**Cloud Strike.** The target takes an extra 1d4 thunder damage. If the target is a creature, it must succeed on a Wisdom saving throw, or you become invisible to it until the start of your next turn or until immediately after you make an attack roll or cast a spell.

**Fire Strike.** The target takes an extra 1d10 fire damage.

**Frost Strike.** The target takes an extra 1d6 cold damage. If the target is a creature, it must succeed on a Constitution saving throw, or its speed is reduced to 0 until the start of your next turn.

**Hill Strike.** The target takes an extra 1d6 damage of the weapon's type. If the target is a creature, it must succeed on a Strength saving throw or have the prone condition.

**Stone Strike.** The target takes an extra 1d6 force damage. If the target is a creature, it must succeed on a Strength saving throw or be pushed 10 feet from you in a straight line.

**Storm Strike.** The target takes an extra 1d6 lightning damage. If the target is a creature, it must succeed on a Constitution saving throw, or it has disadvantage on attack rolls until the start of your next turn.

The saving throw DC for these effects equals 8 + your proficiency bonus + your Strength or Constitution modifier.

You can use this feat a number of times equal to your proficiency bonus, and you regain all expended uses when you finish a long rest.""",
    },
    {
        "name": "Vigor of the Hill Giant",
        "prerequisite": "4th level, Strike of the Giants (Hill Strike) feat",
        "page": 19,
        "text": """You've manifested the resilience emblematic of hill giants, granting you the following benefits:

**Ability Score Increase.** Increase your Strength, Constitution, or Wisdom score by 1, to a maximum of 20.

**Bulwark.** When you are subjected to an effect that would move you at least 5 feet or give you the prone condition, you can use your reaction to steady yourself. You aren't moved and don't have the prone condition.

**Iron Stomach.** Whenever you eat food as part of a short rest and spend one or more Hit Dice to regain hit points, you regain additional hit points equal to your Constitution modifier + your proficiency bonus.""",
    },
]


# --- backgrounds ---------------------------------------------------------

BACKGROUNDS = [
    {
        "name": "Giant Foundling",
        "feature": "Strike of the Giants",
        "page": 12,
        "text": """Though you aren't a Giant, you grew up among giants. Maybe you were an orphan taken in by a sympathetic family of stone giants who raised you as one of their own. Or perhaps you lived in a lost prehistoric pocket of the world, surrounded by giants and fearsome behemoths or hulking dinosaurs. Something about your environment—perhaps the food or water that sustained you, elemental magic inherent in the site of your home, or some verdant blessing of growth placed on you—caused you to grow to a remarkable size for your kind. With the aid of this magic, you have learned how to embody the might of giants.

You are used to moving through a world much bigger than you, and that is reflected in your skills, attitude, and perspective on life.

- **Skill Proficiencies:** Intimidation, Survival
- **Languages:** Giant and one other language of your choice
- **Equipment:** A backpack, a set of traveler's clothes, a small stone or sprig that reminds you of home, and a pouch containing 10 gp

## Origin Stories

How you came to live among colossal creatures is up to you to determine, but the Foundling Origin table suggests a variety of possibilities.

| d6 | Origin |
| --- | --- |
| 1 | You were found as a baby by a family of nomadic giants who raised you as one of their own. |
| 2 | A family of stone giants rescued you when you fell into a mountain chasm, and you have lived with them underground ever since. |
| 3 | You were lost or abandoned as a child in a jungle that teemed with ravenous dinosaurs. There, you found an equally lost frost giant; together, you survived. |
| 4 | Your farm was crushed and your family killed in a battle between warring groups of giants. Racked with guilt over the destruction, a sympathetic giant soldier promised to care for you. |
| 5 | After you had a series of strange dreams as a child, your superstitious parents sent you to study with a powerful but aloof storm giant oracle. |
| 6 | While playing hide-and-seek with your friends, you stumbled into the castle of a cloud giant, who immediately adopted you. |

## Feature: Strike of the Giants

You gain the Strike of the Giants feat (described later in this chapter).

## Building a Giant Foundling Character

Your life among giants has given you a unique perspective. Though you are unusually large for your kind, you're no larger than a giant child, so you might be very mindful of your size.

**Suggested Characteristics.** The Giant Foundling Personality Traits table suggests a variety of traits you might adopt for your character.

| d6 | Personality Trait |
| --- | --- |
| 1 | What I lack in stature compared to giants, I make up for with sheer spite. |
| 2 | I insist on being taken seriously as a full-grown adult. Nobody talks down to me! |
| 3 | Crowded spaces make me uncomfortable. I'd much rather be in an open field than a bustling tavern. |
| 4 | I embrace my shorter stature. It helps me stay unnoticed—and underestimated. |
| 5 | Every avalanche begins as a single pebble. |
| 6 | The world always feels too big, and I'm afraid I'll never find my place in it. |""",
    },
    {
        "name": "Rune Carver",
        "feature": "Rune Shaper",
        "page": 14,
        "text": """You've dedicated your life to studying runecraft. Whether you were taught by a master rune carver or learned by poring over ancient engravings, you can tap into the supernatural power held within runes. The art of runecraft was initially created by giants, but over time, the practice has been adopted by many peoples. As such, though Giant runes are the most commonly used, many rune carvers incorporate symbols from their native languages into the craft.

- **Skill Proficiencies:** History, Perception
- **Tool Proficiencies:** One set of artisan's tools
- **Languages:** Giant
- **Equipment:** A set of artisan's tools (one of your choice), a small knife, a whetstone, a set of common clothes, and a pouch containing 10 gp

## Rune Styles

Each rune carver has a unique style and preferred medium. To determine how you make your runes, you can roll on the Rune Style table.

| d6 | Style |
| --- | --- |
| 1 | You inscribe runes in wax or clay with a fine metal needle. |
| 2 | You whittle pieces of wood into small figurines you mark with runes. |
| 3 | You engrave runes onto glass beads and thread them onto necklaces and bracelets. |
| 4 | You stitch runes into the hems of clothing. |
| 5 | You carve runes on a set of animal bones you can throw in different formations. |
| 6 | You draw runes into candles, melting the wax to smooth over the engravings. |

## Feature: Rune Shaper

You gain the Rune Shaper feat (described later in this chapter).

## Building a Rune Carver Character

Scholarly pursuits, ancient mysteries, or a fateful encounter might inspire a character to pursue the secrets of a rune carver.

**Suggested Characteristics.** The Rune Carver Personality Traits table suggests a variety of traits you might adopt for your character.

| d6 | Personality Trait |
| --- | --- |
| 1 | Is it practical to learn an ancient language that is rarely spoken? No. But is it fun? Very. |
| 2 | I learned one of my ancestors was a lauded rune carver whose story was lost to time. I seek to rekindle that legacy. |
| 3 | The old, traditional markings of runecraft look so boring. Why not give my runes some flair? |
| 4 | In my studies of runes, I strive to understand how great civilizations of the past fell, so I can prevent it from happening to societies of the present. |
| 5 | Life may be a whirlwind of chaos, but whenever I create my runes, I feel at peace. |
| 6 | My brain struggles to process words written in ink, but the feeling of carved runes makes my mind sing. |""",
    },
]


# --- subclass ------------------------------------------------------------

SUBCLASS = {
    "name": "Path of the Giant",
    "page": 11,
    "data": {"class": "barbarian", "level": 3},
    "text": """Barbarians who walk the Path of the Giant draw strength from the same primal forces as giants. As they rage, these barbarians surge with elemental power and grow in size, taking on forms that evoke the glory of giants. Some barbarians look like oversized versions of themselves, perhaps with a hint of elemental energy flaring in their eyes and around their weapons. Others transform more dramatically, taking on the appearance of an actual giant or a form similar to an Elemental, wreathed in fire, frost, or lightning.

## Giant's Power

*3rd-level Path of the Giant feature*

When you choose this path, you learn to speak, read, and write Giant or one other language of your choice if you already know Giant. Additionally, you learn a cantrip of your choice: either *druidcraft* or *thaumaturgy*. Wisdom is your spellcasting ability for this spell.

## Giant's Havoc

*3rd-level Path of the Giant feature*

Your rages pull strength from the primal might of giants, transforming you into a hulking force of destruction. While raging, you gain the following benefits:

**Crushing Throw.** When you make a successful ranged attack with a thrown weapon using Strength, you can add your Rage Damage bonus to the attack's damage roll.

**Giant Stature.** Your reach increases by 5 feet, and if you are smaller than Large, you become Large, along with anything you are wearing. If there isn't enough room for you to increase your size, your size doesn't change.

## Elemental Cleaver

*6th-level Path of the Giant feature*

Your bond with the elemental might of giants grows, and you learn to infuse weapons with primordial energy.

When you enter your rage, you can choose one weapon that you are holding and infuse it with one of the following damage types: acid, cold, fire, thunder, or lightning. While you wield the infused weapon during your rage, the weapon's damage type changes to the chosen type, it deals an extra 1d6 damage of the chosen type when it hits, and it gains the thrown property, with a normal range of 20 feet and a long range of 60 feet. If you throw the weapon, it reappears in your hand the instant after it hits or misses a target. The infused weapon's benefits are suppressed while a creature other than you wields it.

While raging and holding the infused weapon, you can use a bonus action to change the infused weapon's current damage type to another one from the damage type options above.

## Mighty Impel

*10th-level Path of the Giant feature*

Your connection to giant strength allows you to hurl both allies and enemies on the battlefield. As a bonus action while raging, you can choose one Medium or smaller creature within your reach and move it to an unoccupied space you can see within 30 feet of yourself. An unwilling creature must succeed on a Strength saving throw (DC equals 8 + your proficiency bonus + your Strength modifier) to avoid the effect.

If, at the end of this movement, the thrown creature isn't on a surface or liquid that can support it, the creature falls, taking damage as normal and landing prone.

## Demiurgic Colossus

*14th-level Path of the Giant feature*

The primordial power of your rage intensifies. When you rage, your reach increases by 10 feet, your size can increase to Large or Huge (your choice), and you can use your Mighty Impel to move creatures that are Large or smaller. In addition, the extra damage dealt by your Elemental Cleaver feature increases to 2d6.""",
}


# --- rules ---------------------------------------------------------------

RULES = [
    {
        "slug": "character-creation",
        "name": "Chapter 1: Character Creation",
        "page": 11,
        "text": """Most adventurers have heard tales of giants and their ilk. But for some adventurers, their connection to giants runs deeper than fanciful stories.

This chapter is for any D&D character who aspires to forge a link to the mighty giants. From sources of havoc-wreaking power to the artful study of rune magic, from boons that imbue an individual with giant-like might to fantastic tales that can shape an adventurer's entire life—giants can make both big and small impacts on a character's story.

The following sections present a variety of options for creating characters with ties to giants:

- **Subclass Option** allows barbarians to explore ties to the nature of giants.
- **Backgrounds** presents two new backgrounds: the giant foundling and the rune carver. These backgrounds represent formative years spent studying and living among giants, and they grant access to feats that represent that experience.
- **Big Heroes, Big Stories** includes inspiration for narratively connecting characters to giants, regardless of their class or background.
- **Feats** provides options for players who wish to link their characters to giants and primordial magic.""",
    },
    {
        "slug": "bonus-feats",
        "name": "Bonus Feats",
        "page": 12,
        "text": """If the DM decides to allow the Giant Foundling and Rune Carver backgrounds, all characters in the campaign gain access to a bonus feat. If you select one of those backgrounds, you gain the bonus feat specified in that background. If the background you choose doesn't provide a feat, you gain a bonus feat of your choice from the following list (these feats appear in the Player's Handbook):

- Skilled
- Tough""",
    },
    {
        "slug": "rune-spells",
        "name": "Rune Spells",
        "page": 19,
        "text": """The Rune Shaper feat refers to this table. A rune carver learns the 1st-level spells that correspond to the runes they inscribe.

| Rune | Spell |
| --- | --- |
| Cloud | *Fog cloud* |
| Death | *Inflict wounds* |
| Dragon | *Chromatic orb* |
| Enemy | *Disguise self* |
| Fire | *Burning hands* |
| Friend | *Speak with animals* |
| Frost | *Armor of Agathys* |
| Hill | *Goodberry* |
| Journey | *Longstrider* |
| King | *Command* |
| Mountain | *Entangle* |
| Stone | *Sanctuary* |
| Storm | *Thunderwave* |""",
    },
    {
        "slug": "magic-items",
        "name": "Magic Items (Giants)",
        "page": 110,
        "text": """Giants have perfected numerous forms of magical crafting. This section presents new magic items associated with the might of giants.

## A Note About Size

As described in the Dungeon Master's Guide, magic items meant to be worn can fit a creature regardless of size or build. If your campaign features a lot of magic items made by giants, you might decide to tweak this rule. Consider these two options:

**Everything Fits.** Perhaps the ancient giants of your world lived among creatures of varying statures, and as such, they took great care to ensure their magic items would resize to comfortably suit their users. With this option, any magic item created by giants (even one that is not worn, such as a wand or a weapon) magically resizes to suit any creature between Small and Huge size. The creature must spend 10 uninterrupted minutes touching the item and must attune to it if it requires attunement.

**Nothing Resizes.** Perhaps ancient giants made magic items to be used exclusively by giants. In this case, giant-made items don't resize. Smaller creatures might be able to adapt these items in various ways. A giant-made ring can be worn as a bracelet, a giant-made bracelet could serve as a headband, and so on. Some items can't be comfortably wielded by smaller creatures, but magical techniques might exist that allow skilled artisans to reshape and resize magic items with a few days of work.

Some of the magic items described in this chapter have special properties that allow them to fit creatures of any size.""",
    },
    {
        "slug": "giant-crafted-items",
        "name": "Giant-Crafted Items",
        "page": 111,
        "text": """Beyond its size, a giant-crafted version of a magic item might look different from its traditional appearance. For example, runes and rune carving are central to the magic traditions of the giants, so a *rod of rulership* created by a giant artisan might be inscribed with the king rune, while a giant-crafted *periapt of wound closure* might bear the life rune. Also, a magic item might absorb some of the latent elemental power of its giant users or creators. A +1 longsword forged by a fire giant, for example, could glow faintly like embers in the dark, while the *sentinel shield* once carried by a frost giant could be perpetually cold to the touch.

None of these cosmetic effects alter a magic item's capabilities. They merely provide a narrative link to giants' realms that characters might explore.""",
    },
]


# --- items ---------------------------------------------------------------

STAT_RE = re.compile(
    r"(?P<kind>Weapon \([^)]*\)|Armor \([^)]*\)|Wondrous Item|Ring|Rod|Staff|Wand|Potion|Scroll|Shield|Tome)"
    r"\s*,\s*(?P<rarity>Common|Uncommon|Rare|Very Rare|Legendary|Artifact|Var\w+)"
    r"(?P<rest>\s*\([^)]*\))?",
    re.IGNORECASE,
)
# Any stat line at all: used to stop an entry where the next one begins.
NEXT_STAT_RE = re.compile(
    r"(?:\b(?:Weapon|Armor)\s*\([^)]*\)|\bWondrous Item|\bRing|\bRod|\bStaff|\bWand|\bShield)"
    r"\s*,\s*(?:Common|Uncommon|Rare|Very Rare|Legendary|Artifact|Varies)",
    re.IGNORECASE,
)
ATTR_RE = re.compile(r"requires attunement", re.IGNORECASE)

# Residual OCR damage seen in the scanned pages, fixed by hand after review.
OCR_FIXES = [
    (r"\bVarics\b", "Varies"),
    # Art captions and page furniture that sit inside an entry.
    (r"\s*Heim of Perrect Porenriar\s*", " "),
    (r"\s*<Z\b\s*\.?\s*", " "),
    (r"\s+STAFF OF THE ROOTED HILLs\s*$", ""),
    (r"\bspeedand\b", "speed and"),
    (r"\bharpto\b", "harp to"),
    (r"\blallanis\b", "Iallanis"),
    (r"\bOna\b", "On a"),
    (r"mountain rune, The glove", "mountain rune. The glove"),
    (r"\s+Pre his to ric Figurines Of Wondrous.*$", ""),
    (r"\basthe\b", "as the"),
    (r"\bofthe\b", "of the"),
    (r"\bthantypical\b", "than typical"),
    (r"\battuncs\b", "attunes"),
    (r"\brunehas\b", "rune has"),
    (r"\bbracelethas\b", "bracelet has"),
    (r"\bspec tral\b", "spectral"),
    (r"\s*Chapter 5 ?I ?Giant ?Treasures\s*", " "),
    (r"\s+en\. graved\b", " engraved"),
    (r"\s+figu rines\b", " figurines"),
    # Running heads and footer furniture of the scanned pages.
    (r"(?i)CHAPTER\s*\d+\s*[|lI1]\s*[A-Z'’ ]{4,}", " "),
    (r"(?i)\b(?:isabel\s*)?(?:sabel|gibney)\b\.?", " "),
    (r"(?i)il ee at all", " "),
    (r"[^A-Za-z0-9\s']{3,}", " "),
    # Stray glyphs from the scan's decorative area, e.g. `' " '. ~' " ` between
    # two sentences. Only runs of three or more marks, and never right after a
    # letter, so ordinary quotation punctuation survives.
    (r"(?<![A-Za-z])(?:[^\w\s]\s*){3,}(?=[A-Z])", " "),
    (r"[-:·~�]{2,}", " "),
    # Display headings that leaked in from the next entry.
    (r"\s+[A-Z][A-Z'’]{1,}(?:\s+[A-Z][A-Z'’]{1,}){1,4}\s*$", ""),
    (r"\s+\d{2,3}\s*$", ""),
    # OCR letter damage seen on the low-quality page.
    (r"\bSpellicasting\b", "Spellcasting"),
    (r"elemental! weapon", "elemental weapon"),
    (r"\bSeethe\b", "See the"),
    (r"\bMonster Manualfor\b", "Monster Manual for"),
    (r"\btoits\b", "to its"),
    (r"\btoan\b", "to an"),
    (r"\bitas\b", "it as"),
    (r"\bmove carth\b", "move earth"),
    (r"\bap\. propriate\b", "appropriate"),
    (r"(?<=[a-z])\.(?=[A-Z])", ". "),
    # Random-property bullet lists print as ".2minor beneficial properties".
    (r"Guide:\.?\s*", "Guide: "),
    (r"\.\s*(\d)\s*(minor|major)\b", r"; \1 \2"),
    (r"(\d)\s*(minor|major)\b", r"\1 \2"),
    # Підпис до ілюстрації зі статуетками розпізнано як «PRENISTORIC».
    (r"\bPrenistoric\b", "Prehistoric"),
]


def normalise_chars(text: str) -> str:
    """The reference scan encodes some quotes as U+FFFD; keep the prose readable."""
    table = {
        "\ufffd": "'",
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00ad": "",
    }
    for bad, good in table.items():
        text = text.replace(bad, good)
    return text


def apply_ocr_fixes(text: str) -> str:
    text = normalise_chars(text)
    for pattern, replacement in OCR_FIXES:
        text = re.sub(pattern, replacement, text)
    # Removing running heads and captions can leave an orphaned full stop, so the
    # punctuation tidy-up has to run last.
    text = re.sub(r"\.\s*\.", ".", text)
    text = re.sub(
        r"poisoned\.\s*When you take the Attack action on your turn, "
        r"you can replace one of your attacks with a shield bash",
        "poisoned. Shield Bash. When you take the Attack action on your turn, "
        "you can replace one of your attacks with a shield bash",
        text,
    )
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text)


def squash(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def parse_item(entry: dict, ref_fallback: str | None = None) -> dict:
    name = entry["name"]
    body = polish.polish(entry["text"])
    if ref_fallback:
        # Our layout analysis interleaved the columns on this page; the second
        # OCR of the same page reads linearly, so prefer it and re-clean it.
        body = clean_reference(ref_fallback)

    # Everything before the stat line is the OCR'd display heading.
    match = STAT_RE.search(body)
    data: dict = {"item_type": None, "rarity": None, "attunement": False, "magical": True}
    if match:
        data["item_type"] = re.sub(r"\s+", " ", match.group("kind")).lower()
        rarity = match.group("rarity").title().lower()
        data["rarity"] = "varies" if rarity.startswith("var") else rarity
        data["attunement"] = bool(ATTR_RE.search(body[match.start():match.start() + 120]))
        body = body[match.start():]
        # A later entry's stat line means this body ran into the next item.
        following = NEXT_STAT_RE.search(body, 120)
        if following:
            body = body[: following.start()]
    # Sidebars that sit inside the item columns are separate records.
    for marker in SIDEBAR_CUTS:
        hit = body.find(marker)
        if 80 < hit < len(body) - 1:
            body = body[:hit]
    return {"name": name, "data": data, "text": re.sub(r"\s+", " ", apply_ocr_fixes(body)).strip()}


SIDEBAR_CUTS = ("Giant-Crafted Items", "Magic Item Descriptions", "A Note About Size")


def clean_reference(text: str) -> str:
    """Tidy a slice of the reference OCR into readable prose."""
    text = re.sub(r"(?<=[A-Za-z])- (?=[a-z])", "", text)  # "pig- ments" -> "pigments"
    text = re.sub(r"\s+", " ", text)
    return polish.polish(despace.fix(text))


def reference_items() -> dict[str, str]:
    """Reference-OCR text per item, keyed by the item name."""
    path = LOGS / "gotg_ref_items.json"
    if not path.exists():
        return {}
    entries = json.loads(path.read_text(encoding="utf-8"))
    known = [line.strip() for line in (LOGS / "gotg_items_names.txt").read_text(encoding="utf-8").splitlines()]
    mapping: dict[str, str] = {}
    heads = [squash(entry["head"]) for entry in entries]
    for name in known:
        target = squash(name)
        best = max(range(len(entries)), key=lambda index: 1.0 if heads[index].endswith(target) else 0.0)
        if heads[best].endswith(target):
            mapping[name] = entries[best]["text"]
    return mapping


def load_items() -> list[dict]:
    raw = json.loads((LOGS / "gotg_items.json").read_text(encoding="utf-8"))
    refs = reference_items()
    entries = [
        parse_item(entry, ref_fallback=refs.get(entry["name"])) for entry in raw["entries"]
    ]
    # Items whose own OCR came out unusable are transcribed by hand below.
    by_name = {item["name"]: item for item in entries}
    for name, override in MANUAL_ITEMS.items():
        if name in by_name:
            by_name[name].update(override)
        else:
            entries.append({"name": name, **override})
    order = [entry["name"] for entry in raw["entries"]]
    return sorted(entries, key=lambda item: order.index(item["name"]) if item["name"] in order else 99)


MANUAL_ITEMS = {
    "Ring of Amity": {
        "data": {"item_type": "ring", "rarity": "very rare", "attunement": True, "magical": True},
        "text": (
            "Ring, Very Rare (Requires Attunement) This ring is carved from hematite and bears an engraving of "
            "the friend rune. When you first attune to this ring, you can touch one willing creature and form a "
            "magical bond between the two of you. While this bond lasts, whenever you are subjected to a spell or "
            "magical effect that restores hit points, the bonded creature also receives the benefits of the spell "
            "or effect. You can bond with a different creature whenever you finish a long rest, provided that you "
            "can touch the creature and the creature is willing. A creature can benefit from only one ring of "
            "amity's bond at a time. The bond ends if either you or the creature travels to a different plane of "
            "existence, if you bond with a different creature at the end of a long rest, or if you sever the bond "
            "as a bonus action. Invoking the Rune. When the bonded creature hits a target with an attack roll, "
            "you can use your reaction to invoke the ring's rune if you are within 60 feet of the bonded "
            "creature. The bonded creature's attack is then turned into a critical hit. Once the rune has been "
            "invoked, it can't be invoked again until the next dawn."
        ),
    },
    "Thunderbuss": {
        "data": {"item_type": "weapon (pistol)", "rarity": "very rare", "attunement": False, "magical": True},
        "text": (
            "Weapon (Pistol), Very Rare This magic ranged weapon is a flared pistol with the storm rune "
            "engraved along the barrel. You gain a +1 bonus to attack and damage rolls made with it. It requires "
            "no ammunition, its damage is thunder instead of piercing, and it doesn't have the loading property. "
            "Invoking the Rune. As a bonus action, you can invoke the weapon's rune to launch a ball of energy to "
            "a point you can see within 30 feet of yourself. The energy then detonates into a 10-foot-radius "
            "sphere of turbulent wind and thunder centered on that point, and each creature in that sphere must "
            "make a DC 14 Constitution saving throw. On a failed save, a creature takes 3d6 thunder damage, and it "
            "can't take reactions until the end of your next turn. On a successful save, a creature takes half as "
            "much damage only. Once the rune has been invoked, it can't be invoked again until the next dawn."
        ),
    },
    "Lucent Destroyer": {
        "data": {"item_type": "weapon (musket)", "rarity": "very rare", "attunement": True, "magical": True},
        "text": (
            "Weapon (Musket), Very Rare (Requires Attunement) This magic weapon is a triple-barreled bronze "
            "musket. You gain a +1 bonus to attack and damage rolls made with it. It requires no ammunition, "
            "its damage is radiant instead of piercing, and it doesn't have the loading property. The base of "
            "the weapon is emblazoned with the light rune. Additionally, while attuned to the weapon, you can "
            "cast dancing lights from the musket at will. Invoking the Rune. As an action, you can invoke the "
            "weapon's rune to cast the sunbeam spell (save DC 17) with it. Once the rune has been invoked, it "
            "can't be invoked again until the next dawn."
        ),
    },
    "Mistral Mantle": {
        "data": {"item_type": "wondrous item", "rarity": "very rare", "attunement": True, "magical": True},
        "text": (
            "Wondrous Item, Very Rare (Requires Attunement) This thick, fur-lined cloak has the ice rune "
            "stitched on the hem in silvery blue thread. Frigid wind swirls around the cloak, regardless of the "
            "weather. While wearing this cloak, you have resistance to cold damage. Additionally, when you move "
            "within 5 feet of a creature, you can cause the cloak's cold wind to buffet the creature. The "
            "creature must succeed on a DC 14 Dexterity saving throw or take 1d6 cold damage and have the prone "
            "condition. A creature can be affected by the mantle only once during a turn. Invoking the Rune. As "
            "an action, you can invoke the mantle's rune to cast the sleet storm spell (save DC 14) with it. "
            "When you use the mantle to cast the spell, the area of the spell isn't difficult terrain for you, "
            "and you can see through the storm, ignoring the normal penalties of a heavily obscured area. Once "
            "the rune has been invoked, it can't be invoked again until the next dawn."
        ),
    },
}


# --- records -------------------------------------------------------------

def record(category: str, slug: str, name: str, text: str, data: dict, page: int | None, stamp: str) -> dict:
    return {
        "id": f"{SOURCE}/{category}/{slug}",
        "schema": "compendium-entry/1",
        "source_id": SOURCE,
        "category": category,
        "name_en": name,
        "name_uk": None,
        "edition": "2014",
        "license": LICENSE,
        "url": URL,
        "page": page,
        "text_en": text.strip(),
        "text_uk": None,
        "data": data,
        "status": "raw",
        "fetched_at": stamp,
        "notes": ["text reconstructed from the scanned print edition (OCR); spacing and hyphenation normalised"],
    }


def slugify(name: str) -> str:
    slug = name.lower().replace("'", "").replace("’", "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def main() -> None:
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    import polish as _polish  # noqa: F401  (keeps the import used with --check)

    records: dict[str, list[dict]] = {}
    records["subclass"] = [
        record("subclass", slugify(SUBCLASS["name"]), SUBCLASS["name"], SUBCLASS["text"], SUBCLASS["data"], SUBCLASS["page"], stamp)
    ]
    records["background"] = [
        record("background", slugify(bg["name"]), bg["name"], bg["text"], {"feature": bg["feature"]}, bg["page"], stamp)
        for bg in BACKGROUNDS
    ]
    records["feat"] = [
        record("feat", slugify(feat["name"]), feat["name"], feat["text"], {"prerequisite": feat["prerequisite"]}, feat["page"], stamp)
        for feat in FEATS
    ]
    items = []
    for item in load_items():
        items.append(
            record("item", slugify(item["name"]), item["name"], item["text"], item["data"], None, stamp)
        )
    records["item"] = items
    records["rule"] = [
        record("rule", rule["slug"], rule["name"], rule["text"], {}, rule["page"], stamp) for rule in RULES
    ]

    COMPENDIUM.mkdir(parents=True, exist_ok=True)
    for category, entries in records.items():
        target = COMPENDIUM / f"{category}.jsonl"
        with target.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"{category}: {len(entries)}")

    # Спільний формат записів: OCR-білдер не має власних уявлень про те, які
    # ключі мусять бути в data (contract/compendium-format.json).
    compendium_format.normalize_source(SOURCE, compendium_format.load_spec(), write=True)


if __name__ == "__main__":
    main()
