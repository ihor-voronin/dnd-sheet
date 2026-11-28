"""Портрети персонажів: малюємо SVG кодом, без чужих картинок.

Кожен портрет — погруддя у квадраті 100×100: тло з відтінком класу, одяг і
головний убір класу, голова виду, зачіска й борода. Усе задано id портрета
(`catalog.Portrait`), а дрібні відмінності варіантів (колір шкіри, волосся,
зачіска) беремо зі стабільного хешу id — той самий id завжди дає той самий
малюнок.

Стиль — пласкі кольорові форми, як фішки на столі: читаються і в 32 px на
картці, і в 220 px у виборі. Кут обрізає CSS (шестикутник `--hex-v`), тож
важливе тримаємо в центрі: голова — 20…64 по вертикалі, плечі — нижче.

Палітра сайту (theme.css): латунь #d1a654, малиновий #c2323d, темне тло #11141b.
"""

from __future__ import annotations

import math
import re
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field

from dndsheet.visuals.domain.catalog import Portrait

# ---------------------------------------------------------------------------
# дрібниці: кольори, дзеркало контуру
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[MLCQZ]|-?\d+(?:\.\d+)?")


def _mirror(d: str) -> str:
    """Контур, віддзеркалений відносно вертикалі x = 50 (лише M/L/C/Q/Z з парами чисел)."""
    out: list[str] = []
    expect_x = True
    for token in _TOKEN.findall(d):
        if token.isalpha():
            out.append(token)
            expect_x = True
            continue
        value = float(token)
        if expect_x:
            value = 100 - value
        out.append(f"{value:g}")
        expect_x = not expect_x
    return " ".join(out)


def _rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _mix(a: str, b: str, t: float) -> str:
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return "#{:02x}{:02x}{:02x}".format(
        round(ra + (rb - ra) * t),
        round(ga + (gb - ga) * t),
        round(ba + (bb - ba) * t),
    )


def _dark(color: str, k: float) -> str:
    return _mix(color, "#000000", k)


def _light(color: str, k: float) -> str:
    return _mix(color, "#ffffff", k)


def _p(d: str, fill: str = "none", extra: str = "") -> str:
    return f'<path d="{d}" fill="{fill}"{extra}/>'


def _pair(d: str, fill: str = "none", extra: str = "") -> str:
    """Контур і його дзеркало: вуха, роги, наплічники."""
    return _p(d, fill, extra) + _p(_mirror(d), fill, extra)


def _stroke(color: str, width: float, opacity: float = 1.0) -> str:
    alpha = f' stroke-opacity="{opacity:g}"' if opacity < 1 else ""
    return f' stroke="{color}" stroke-width="{width:g}" stroke-linecap="round" stroke-linejoin="round"{alpha}'


def _circle(cx: float, cy: float, r: float, fill: str, extra: str = "") -> str:
    return f'<circle cx="{cx:g}" cy="{cy:g}" r="{r:g}" fill="{fill}"{extra}/>'


def _ellipse(cx: float, cy: float, rx: float, ry: float, fill: str, extra: str = "") -> str:
    return f'<ellipse cx="{cx:g}" cy="{cy:g}" rx="{rx:g}" ry="{ry:g}" fill="{fill}"{extra}/>'


def _pick(seed: str, salt: str, options: Sequence[str]) -> str:
    return options[zlib.crc32(f"{seed}|{salt}".encode()) % len(options)]


# ---------------------------------------------------------------------------
# палітри
# ---------------------------------------------------------------------------

BRASS = "#d1a654"
INK = "#1a1512"
IVORY = "#efe6d2"
LIP = "#b25562"

HUMAN_SKIN = ("#f3d3b8", "#e8b993", "#d49a6c", "#b07548", "#8a5634", "#5f3a22")
HAIR = ("#1f1a17", "#3b2a20", "#5e3f28", "#8a5a32", "#a8552c", "#d8b26a", "#e3d6b8", "#8f8f96")


@dataclass(frozen=True, slots=True)
class Outfit:
    main: str
    second: str
    trim: str
    tint: str
    headgear: tuple[str, ...]
    gem: str = "#e04a6a"


OUTFITS: dict[str, Outfit] = {
    "artificer": Outfit("#6a4c30", "#3e4a5c", BRASS, "#3a3326", ("goggles", "none", "goggles")),
    "barbarian": Outfit("#8a6a48", "#5a3a24", "#c8b08a", "#4a2a20", ("paint", "horned", "none")),
    "bard": Outfit("#8a2a62", "#efe6d4", BRASS, "#432641", ("beret", "none", "circlet"), "#6fc7c0"),
    "cleric": Outfit("#e6dfcc", "#c9bd9a", BRASS, "#4a4128", ("none", "circlet", "coif"), "#f6e08a"),
    "druid": Outfit("#55703a", "#7a5a36", "#9cc25a", "#283d24", ("antlers", "leaves", "hood")),
    "fighter": Outfit("#9aa3b5", "#6b4a2e", BRASS, "#2e3442", ("helm", "none", "helm")),
    "monk": Outfit("#c87a2c", "#7a2a2a", "#e8c070", "#4a3220", ("headband", "none", "headband")),
    "paladin": Outfit("#b4bcca", "#b3242e", BRASS, "#463a22", ("none", "plume", "circlet"), "#8ab4ff"),
    "ranger": Outfit("#3c5f36", "#6b4a2e", "#c8a060", "#22392a", ("hood", "none", "hood")),
    "rogue": Outfit("#34302c", "#4a3f36", "#8a7a66", "#22262e", ("hood", "mask", "none")),
    "sorcerer": Outfit("#7a2440", "#2c1830", "#e0b860", "#4a1f30", ("circlet", "glow", "none")),
    "warlock": Outfit("#2e2342", "#1a1426", "#a77ce8", "#2c2142", ("hood", "none", "hood")),
    "wizard": Outfit("#2c4680", "#1d2f5a", BRASS, "#22305a", ("hat", "none", "hood"), "#8ab4ff"),
}

#: Убори, що не лізуть на звірині голови (дзьоб, морда, вуха зверху).
_SPECIAL_HEADGEAR = frozenset({"hat", "hood", "circlet", "none", "glow", "paint"})


@dataclass(frozen=True, slots=True)
class Kind:
    """Як виглядає група: голова, вуха, шкіра, волосся, особливості."""

    skin: tuple[str, ...] = HUMAN_SKIN
    hair: tuple[str, ...] = HAIR
    ears: str = "human"
    head: str = "human"  # human | dragon | cat | bird | tortle | warforged | bull | elephant
    scale: tuple[float, float, float] = (1.0, 1.0, 0.0)  # sx, sy, зсув униз
    eyes: str = "normal"  # normal | glow | slit | pale | big
    eye_color: str = INK
    hair_f: tuple[str, ...] = ("long", "bob", "bun", "braid", "wavy", "pony")
    hair_m: tuple[str, ...] = ("short", "swept", "long", "bald", "topknot", "curly")
    beards: tuple[str, ...] = ("none", "stubble", "full", "goatee", "moustache", "none")
    nose: str = "small"  # small | big | flat | none
    extras: tuple[str, ...] = ()
    body: float = 1.0


KINDS: dict[str, Kind] = {
    "human": Kind(),
    "elf": Kind(
        skin=("#f4dcc6", "#ecc7a3", "#d9a77c", "#a87150"),
        hair=("#1f1a17", "#5e3f28", "#a8552c", "#d8b26a", "#e8e0cc", "#e3d6b8"),
        ears="long",
        scale=(0.95, 1.03, 0.0),
        hair_m=("long", "swept", "long", "topknot"),
        beards=("none",),
    ),
    "drow": Kind(
        skin=("#4b4660", "#3d3a55", "#5a4f6e"),
        hair=("#eeeeea", "#dcdce8", "#c8c8d8"),
        ears="long",
        scale=(0.95, 1.03, 0.0),
        eyes="glow",
        eye_color="#e05a6a",
        hair_m=("long", "swept", "long"),
        beards=("none",),
    ),
    "half-elf": Kind(ears="pointed", beards=("none", "stubble", "goatee", "none")),
    "dwarf": Kind(
        skin=("#efc6a4", "#dba07a", "#b87d56", "#8a5a3a"),
        hair=("#1f1a17", "#5e3f28", "#a8552c", "#b0682e", "#8f8f96", "#d8b26a"),
        scale=(1.12, 0.98, 2.0),
        hair_f=("braids", "bun", "braids", "long"),
        hair_m=("short", "bald", "swept", "short"),
        beards=("dwarf",),
        nose="big",
        body=1.1,
    ),
    "duergar": Kind(
        skin=("#8a8d93", "#74777e", "#9a9a9e"),
        hair=("#cfcfd2", "#9a9aa0", "#5a5a60"),
        scale=(1.12, 0.98, 2.0),
        hair_f=("bald",),
        hair_m=("bald",),
        beards=("dwarf",),
        nose="big",
        extras=("tattoo",),
        body=1.1,
    ),
    "halfling": Kind(
        ears="small",
        scale=(1.05, 1.0, 3.0),
        hair_f=("curly", "bob", "bun", "braid"),
        hair_m=("curly", "short", "swept", "curly"),
        beards=("none", "none", "stubble"),
    ),
    "gnome": Kind(
        skin=("#f3d3b8", "#e8b993", "#c68a5e", "#9a6440"),
        hair=("#e3d6b8", "#a8552c", "#d8b26a", "#5e3f28", "#eeeeea", "#1f1a17"),
        ears="pointed",
        scale=(1.07, 1.02, 2.0),
        eyes="big",
        hair_f=("curly", "bun", "pony", "curly"),
        hair_m=("curly", "mohawk", "swept", "bald"),
        beards=("none", "goatee", "moustache", "full"),
        nose="big",
    ),
    "half-orc": Kind(
        skin=("#86a061", "#6f8f5a", "#8c9a78", "#9aa36a", "#7a8a6a"),
        hair=("#1f1a17", "#2a2420", "#3b2a20", "#5a5a5a"),
        ears="pointed",
        scale=(1.06, 1.0, 0.0),
        hair_m=("short", "mohawk", "bald", "topknot", "long"),
        beards=("none", "stubble", "none"),
        nose="flat",
        extras=("tusks", "brow"),
        body=1.06,
    ),
    "tiefling": Kind(
        skin=("#c0443e", "#a33a55", "#7c4a8e", "#c96a4a", "#8e3b3b", "#b77a6a"),
        hair=("#1f1a17", "#3a2050", "#5a1e2e", "#20243a", "#2a2a2a"),
        ears="pointed",
        eyes="glow",
        eye_color="#f2c14e",
        beards=("none", "goatee", "stubble", "none"),
        extras=("horns",),
    ),
    "aasimar": Kind(
        skin=("#f6dcc6", "#e8b993", "#c68a5e", "#8a5634"),
        hair=("#e3d6b8", "#d8b26a", "#eeeeea", "#3b2a20"),
        eyes="glow",
        eye_color="#fff1c0",
        beards=("none", "stubble", "none"),
        extras=("halo",),
    ),
    "goliath": Kind(
        skin=("#9aa0a6", "#8a8f96", "#a5a09a", "#8a8278"),
        hair=("#1f1a17", "#3b2a20"),
        scale=(1.04, 1.05, -1.0),
        hair_f=("bun", "short", "braid"),
        hair_m=("bald",),
        beards=("none",),
        extras=("marks",),
        body=1.12,
    ),
    "firbolg": Kind(
        skin=("#8aa0b8", "#9ab0a0", "#a0a8c8", "#b0a8a0"),
        hair=("#c8b8a0", "#5e3f28", "#a8552c", "#8f8f96"),
        ears="droop",
        scale=(1.04, 1.03, 0.0),
        beards=("full", "full", "dwarf"),
        nose="big",
        body=1.08,
    ),
    "genasi-fire": Kind(
        skin=("#d0603a", "#c04a30", "#a83c2c"),
        hair=("#ffb347",),
        eyes="glow",
        eye_color="#ffe08a",
        hair_f=("flame",),
        hair_m=("flame",),
        beards=("none",),
    ),
    "genasi-water": Kind(
        skin=("#3f86a8", "#2f7898", "#4a90a0"),
        hair=("#7fd4d8", "#2a5a8a", "#a8e0e8"),
        hair_f=("wavy", "long", "bob"),
        hair_m=("long", "swept", "curly"),
        beards=("none",),
        extras=("drops",),
    ),
    "genasi-air": Kind(
        skin=("#a8c4dc", "#b8d0e4", "#c4d4e0"),
        hair=("#f4f8fc", "#dfe8f2"),
        eyes="glow",
        eye_color="#ffffff",
        hair_f=("wisp",),
        hair_m=("wisp",),
        beards=("none",),
    ),
    "genasi-earth": Kind(
        skin=("#8a6a4a", "#7a6a5a", "#9a7a5a"),
        hair=("#3a2e24", "#5a4a3a", "#2a2420"),
        hair_m=("bald", "short", "mohawk"),
        beards=("none", "stubble"),
        extras=("cracks",),
        body=1.06,
    ),
    "tabaxi": Kind(
        skin=("#d9a35a", "#b07a3e", "#7a7470", "#e8d8b8", "#3a3330", "#c8884a"),
        head="cat",
        eyes="slit",
        eye_color="#9fd36a",
        extras=("stripes",),
    ),
    "leonin": Kind(skin=("#c89a52", "#b0803a", "#d8b070"), head="cat", eyes="slit", eye_color="#f2c14e"),
    "kenku": Kind(skin=("#4a4652", "#55495a", "#40464f"), head="bird", eye_color="#d8d8e0"),
    "aarakocra": Kind(skin=("#c84a2a", "#3a6aa8", "#d0a040", "#8a6a4a"), head="bird", eye_color="#f2c14e"),
    "owlin": Kind(skin=("#a08060", "#d8c8a8", "#7a6a5a"), head="bird", eye_color="#f2a53e", extras=("owl",)),
    "tortle": Kind(skin=("#6f8f4a", "#5a7a40", "#7a8a50"), head="tortle"),
    "lizardfolk": Kind(
        skin=("#5a8a5a", "#6a8a4a", "#4a7a6a"), head="dragon", eyes="slit", eye_color="#e8c040", extras=("crest",)
    ),
    "kobold": Kind(
        skin=("#a8543a", "#7a4a8a", "#4a6a8a"),
        head="dragon",
        eyes="slit",
        eye_color="#f2c14e",
        scale=(0.92, 0.95, 4.0),
        extras=("small",),
    ),
    "dragonborn": Kind(
        skin=("#b8383a", "#3a6aa8", "#3e8a4e", "#d6a84e", "#b9c2cc", "#a8743a", "#46464f", "#dfe5ec", "#b8643a"),
        head="dragon",
        eyes="slit",
        eye_color="#f2c14e",
        body=1.08,
    ),
    "warforged": Kind(skin=("#8a8f96", "#9a7a52", "#6f747c"), head="warforged", eyes="glow", eye_color="#7fe0ff"),
    "triton": Kind(
        skin=("#5a9ab0", "#4a8aa8", "#6aa8b0", "#7ab0a8"),
        hair=("#1d3a5a", "#2a6a7a", "#0f2a3a"),
        ears="fin",
        beards=("none",),
        extras=("fin",),
    ),
    "gith": Kind(
        skin=("#b8b86a", "#a8b070", "#c0b878"),
        hair=("#1f1a17", "#7a2a22", "#3b2a20"),
        ears="gith",
        scale=(0.96, 1.04, 0.0),
        hair_f=("topknot",),
        hair_m=("topknot", "bald"),
        beards=("none",),
        nose="none",
    ),
    "hobgoblin": Kind(
        skin=("#c8643a", "#b85a34", "#a85030"),
        hair=("#1f1a17", "#2a2420"),
        ears="pointed",
        hair_f=("topknot", "braid", "long"),
        hair_m=("topknot", "long", "short"),
        beards=("none",),
        nose="flat",
        extras=("fangs",),
    ),
    "bugbear": Kind(
        skin=("#8a5a34", "#6b4a2e", "#7a6a4a"),
        hair=("#4a3020", "#3a2a1c"),
        ears="bear",
        scale=(1.08, 1.03, 0.0),
        hair_m=("shaggy",),
        beards=("fur",),
        nose="big",
        extras=("fangs",),
        body=1.12,
    ),
    "goblin": Kind(
        skin=("#8aa04a", "#c8843a", "#7a9a50", "#a0a050"),
        hair=("#1f1a17", "#3b2a20"),
        ears="goblin",
        scale=(0.98, 0.94, 4.0),
        eyes="big",
        eye_color="#a8401e",
        hair_f=("pony", "bun", "bob"),
        hair_m=("bald", "mohawk", "short"),
        beards=("none",),
        nose="big",
        extras=("fangs",),
        body=0.94,
    ),
    "changeling": Kind(
        skin=("#d8dce0", "#c8ccd4", "#e0dcdc"),
        hair=("#f4f4f2", "#dcdce4"),
        eyes="pale",
        eye_color="#eef4f8",
        hair_m=("short", "swept", "long"),
        beards=("none",),
        nose="none",
    ),
    "minotaur": Kind(skin=("#5a3a28", "#3a2a22", "#8a6a4a"), head="bull", body=1.12),
    "loxodon": Kind(skin=("#8a8c90", "#9a9590", "#7a7c80"), head="elephant", body=1.12),
    "harengon": Kind(
        skin=("#e0d0b8", "#a8845a", "#efe8dc", "#8a7a6a"),
        hair=("#efe8dc", "#8a6a4a", "#3b2a20"),
        beards=("none",),
        nose="none",
        extras=("bunny",),
    ),
    "satyr": Kind(
        ears="goat",
        hair_f=("curly", "wavy", "bob"),
        hair_m=("curly", "short", "curly"),
        beards=("goatee", "full", "goatee"),
        extras=("small-horns",),
    ),
    "fairy": Kind(
        skin=("#f4dcc6", "#ecc7a3", "#d9a77c", "#b8d8c0"),
        hair=("#e88ab0", "#6fc7c0", "#d8b26a", "#b48cff", "#1f1a17"),
        ears="long",
        beards=("none",),
        extras=("wings",),
    ),
    "shifter": Kind(
        ears="pointed",
        eyes="slit",
        eye_color="#e8c040",
        hair_f=("wavy", "braid", "long"),
        hair_m=("long", "short", "swept"),
        beards=("stubble", "full", "none"),
        extras=("fangs", "sideburns"),
    ),
    "yuan-ti": Kind(
        skin=("#d4b48a", "#b8946a", "#8a6a4a", "#9ab08a"),
        hair=("#1f1a17", "#3b2a20", "#2a3a2a"),
        eyes="slit",
        eye_color="#d8c040",
        beards=("none",),
        extras=("scales",),
    ),
    "dhampir": Kind(
        skin=("#ece4e0", "#ddd2d0", "#cfc4c8"),
        hair=("#1f1a17", "#eeeeea", "#3a2030"),
        eyes="glow",
        eye_color="#d0303c",
        beards=("none", "goatee"),
        extras=("fangs",),
    ),
    "hexblood": Kind(
        skin=("#9ab08a", "#a8a0c0", "#b0a890"),
        hair=("#2a3a2a", "#5a3a5a", "#1f1a17"),
        ears="pointed",
        eyes="glow",
        eye_color="#9fe06a",
        beards=("none",),
        extras=("twigs",),
    ),
    "vedalken": Kind(
        skin=("#7a9ac8", "#6a8ab8", "#8aa4c8"),
        hair=("#1d2f5a",),
        scale=(0.96, 1.07, -1.0),
        hair_f=("bald", "bun"),
        hair_m=("bald",),
        beards=("none",),
    ),
}


# ---------------------------------------------------------------------------
# образ: що саме малюємо для цього id
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Look:
    portrait: Portrait
    kind: Kind
    outfit: Outfit
    skin: str
    hair: str
    hair_style: str
    beard: str
    headgear: str
    eyes: str
    eye_color: str
    defs: list[str] = field(default_factory=list)

    @property
    def female(self) -> bool:
        return self.portrait.gender == "f"

    @property
    def male(self) -> bool:
        return self.portrait.gender == "m"


def look_of(item: Portrait) -> Look:
    kind = KINDS[item.group]
    outfit = OUTFITS[item.class_key]
    seed = item.id
    skin = _pick(seed, "skin", kind.skin)
    hair = _pick(seed, "hair", kind.hair)
    if item.gender == "f":
        style = _pick(seed, "style", kind.hair_f)
    elif item.gender == "m":
        style = _pick(seed, "style", kind.hair_m)
    else:
        style = _pick(seed, "style", kind.hair_f + kind.hair_m)
    beard = _pick(seed, "beard", kind.beards) if item.gender == "m" else "none"
    if item.group == "bugbear":
        beard = "fur"
    # Варіанти одного класу різняться убором: зсув від групи, щоб «перший» варіант
    # у різних видів не був однаковим.
    offset = zlib.crc32(f"{item.group}{item.gender}".encode())
    headgear = outfit.headgear[(item.variant - 1 + offset) % len(outfit.headgear)]
    if kind.head != "human" and headgear not in _SPECIAL_HEADGEAR:
        headgear = "none"
    if kind.head in ("bull", "elephant") and headgear in ("hat", "hood"):
        headgear = "none"
    eyes, eye_color = kind.eyes, kind.eye_color
    if headgear == "glow" or (item.class_key == "warlock" and headgear == "hood"):
        eyes, eye_color = "glow", outfit.trim if headgear == "glow" else "#c8a8ff"
    return Look(item, kind, outfit, skin, hair, style, beard, headgear, eyes, eye_color)


# ---------------------------------------------------------------------------
# тіло й одяг
# ---------------------------------------------------------------------------

TORSO = "M 6 100 C 7 83 17 71 36 67 Q 50 70 64 67 C 83 71 93 83 94 100 Z"
NECK = "M 44.6 50 L 44.4 67 Q 50 70.5 55.6 67 L 55.4 50 Z"
V_NECK = "M 44 66.6 L 50 78 L 56 66.6 Q 50 69.8 44 66.6 Z"


def _back_items(look: Look) -> str:
    """Те, що за спиною: лютня, сагайдак, крила, панцир."""
    o, cls = look.outfit, look.portrait.class_key
    parts: list[str] = []
    if "wings" in look.kind.extras:
        wing = "M 42 72 C 26 52 8 46 6 60 C 4 72 22 80 42 74 Z"
        low = "M 42 76 C 30 80 18 90 22 98 C 28 100 38 90 43 79 Z"
        attrs = _stroke("#e8fff8", 0.8, 0.7) + ' fill-opacity=".38"'
        parts.append(_pair(wing, "#bfe8e0", attrs) + _pair(low, "#d8c8f0", attrs))
    if look.kind.head == "tortle":
        shell = "M 6 100 C 4 70 22 52 50 51 C 78 52 96 70 94 100 Z"
        parts.append(_p(shell, "#6b5a3a", _stroke("#4a3e28", 1.2)))
        parts.append(_p("M 20 72 Q 50 60 80 72 M 14 88 Q 50 76 86 88", "none", _stroke("#4a3e28", 1.1)))
    if cls == "bard":
        parts.append(_p("M 73 72 L 88 33 L 91.4 34.4 L 77.6 73.6 Z", "#8a5a32"))
        parts.append(_p("M 86.6 34 L 89.4 26.4 L 94 28.2 L 91.4 35.4 Z", "#5e3f28"))
        parts.append(_p("M 88.4 30 L 86 29 M 90 31 L 87.6 30", "none", _stroke(BRASS, 1)))
    if cls == "ranger":
        parts.append(_p("M 21 72 L 29 51 L 35 53.4 L 28.6 74 Z", o.second))
        for x, y in ((29.4, 50.6), (32.4, 51.6), (35.2, 52.8)):
            parts.append(_p(f"M {x} {y} L {x - 2.4} {y - 7} L {x + 1.6} {y - 1.2} Z", "#e8e0cc"))
    return "".join(parts)


def _torso(look: Look) -> str:
    o, skin, cls = look.outfit, look.skin, look.portrait.class_key
    sx = look.kind.body
    parts: list[str] = [_p(NECK, _dark(skin, 0.16))]
    body: list[str] = []
    if cls == "barbarian":
        body.append(_p(TORSO, skin))
        body.append(_p("M 38 82 Q 44 85 50 82.5 Q 56 85 62 82", "none", _stroke(_dark(skin, 0.25), 1)))
        if look.female:
            body.append(_p("M 32 79 Q 50 84 68 79 L 69 89 Q 50 94 31 89 Z", o.second))
        fur = (
            "M 7 96 C 8 80 18 70 36 66.5 L 39 70 L 36 73 L 38.5 76.5 L 33 77 L 33.5 81.5 L 27.5 80 "
            "L 26 85.5 L 20.5 82.5 L 17 88.5 L 12.5 85 Z"
        )
        body.append(_pair(fur, o.main, _stroke(_dark(o.main, 0.3), 0.8)))
        body.append(_p("M 33 69 L 39 67.6 L 70 100 L 62 100 Z", o.second))
        body.append(_circle(47, 80.5, 2.2, o.trim, _stroke(_dark(o.trim, 0.4), 0.6)))
    elif cls in ("fighter", "paladin"):
        steel = o.main
        body.append(_p(TORSO, _dark(steel, 0.32) if cls == "fighter" else _dark(steel, 0.18)))
        if cls == "fighter":
            rings = "".join(
                _p(f"M {12 + i * 8} {84 + (i % 2) * 2} q 4 3 8 0", "none", _stroke(_dark(steel, 0.5), 0.7, 0.6))
                for i in range(10)
            )
            body.append(rings)
            body.append(_p("M 31 70.5 L 36.5 68.6 L 70 100 L 62 100 Z", o.second))
            body.append(_p("M 47 83 h 6 v 5 h -6 Z", o.trim))
        else:
            body.append(_p("M 39.6 72 L 60.4 72 L 58.6 100 L 41.4 100 Z", o.second))
            body.append(_p("M 48.6 78 h 2.8 v 6 h 5 v 2.8 h -5 v 9 h -2.8 v -9 h -5 v -2.8 h 5 Z", o.trim))
        pauldron = "M 8.6 90 C 8.6 76 20 68 34 67.6 C 35.4 73.4 31 80.4 23 86 C 18.6 89 13.6 90.4 8.6 90 Z"
        body.append(_pair(pauldron, steel, _stroke(_dark(steel, 0.45), 0.9)))
        body.append(_pair("M 12 84 C 16 77 22 73 30 71", "none", _stroke(_light(steel, 0.45), 1, 0.8)))
        body.append(
            _p(
                "M 39.4 66.4 Q 50 72.6 60.6 66.4 L 61.4 70.4 Q 50 77 38.6 70.4 Z",
                _dark(steel, 0.08),
                _stroke(_dark(steel, 0.45), 0.7),
            )
        )
    elif cls == "rogue":
        body.append(_p(TORSO, o.main))
        body.append(_p("M 29.6 72 L 34 70.4 L 64 100 L 58.6 100 Z", o.second))
        body.append(_p(_mirror("M 29.6 72 L 34 70.4 L 64 100 L 58.6 100 Z"), _dark(o.second, 0.15)))
        body.append(_p("M 38.6 64.4 Q 50 71.4 61.4 64.4 L 62.4 70.2 Q 50 78.4 37.6 70.2 Z", o.second))
        body.append(_p("M 47.6 84 h 4.8 v 4 h -4.8 Z", o.trim))
    elif cls == "ranger":
        body.append(_p(TORSO, o.second))
        body.append(_p(V_NECK, skin))
        cloak = "M 6 100 C 7 83 17 71 36 67 L 41.4 70.4 C 31 76 24.6 87 22.6 100 Z"
        body.append(_pair(cloak, o.main, _stroke(_dark(o.main, 0.3), 0.8)))
        body.append(_p("M 58 68.4 L 63 69.6 L 35.4 100 L 29.4 100 Z", _dark(o.second, 0.3)))
        body.append(_circle(41.4, 70.6, 2, o.trim) + _circle(58.6, 70.6, 2, o.trim))
        body.append(_p("M 41.4 70.6 Q 50 74 58.6 70.6", "none", _stroke(o.trim, 0.7)))
    elif cls == "monk":
        body.append(_p(TORSO, o.main))
        body.append(_p(V_NECK, skin))
        body.append(_p("M 42.6 66 L 50 80.6 L 57.4 66", "none", _stroke(_dark(o.main, 0.35), 3.2)))
        body.append(_p("M 21 92 Q 50 97.6 79 92 L 80 100 L 20 100 Z", o.second))
        for i in range(11):
            t = i / 10
            x = 39 + 22 * t
            y = 67.6 + 9.4 * (1 - (2 * t - 1) ** 2)
            body.append(_circle(x, y, 1.15, "#5a3a24" if i != 5 else o.trim))
    elif cls == "bard":
        body.append(_p(TORSO, o.main))
        body.append(_pair("M 9 98 C 10 86 14 79 20 75 L 24 100 Z", _dark(o.main, 0.25)))
        ruff = (
            "M 37.4 66 Q 40.6 62.6 43.8 66 Q 46.9 62.6 50 66 Q 53.1 62.6 56.2 66 Q 59.4 62.6 62.6 66 "
            "Q 59.6 71.6 56.2 69.4 Q 53.1 72.4 50 69.8 Q 46.9 72.4 43.8 69.4 Q 40.4 71.6 37.4 66 Z"
        )
        body.append(_p(ruff, o.second, _stroke(_dark(o.second, 0.2), 0.6)))
        for y in (77, 83, 89, 95):
            body.append(_circle(50, y, 1.3, o.trim))
    elif cls == "artificer":
        body.append(_p(TORSO, o.second))
        body.append(_p(V_NECK, skin))
        body.append(_p("M 37 73 L 63 73 L 66.4 100 L 33.6 100 Z", o.main, _stroke(_dark(o.main, 0.35), 0.8)))
        body.append(_p("M 37.6 73 L 39.8 66.8 M 62.4 73 L 60.2 66.8", "none", _stroke(_dark(o.main, 0.25), 1.6)))
        body.append(_p("M 41 84 h 9 v 7 h -9 Z", _dark(o.main, 0.2)))
        body.append(_p("M 43.4 79 L 44.6 85.4 M 46.6 78.6 L 46.6 85.4", "none", _stroke("#9aa3b5", 1.1)))
        teeth = "".join(
            f'<rect x="58.6" y="78.6" width="2.4" height="2.4" fill="{o.trim}" transform="rotate({a} 59.8 84.2)"/>'
            for a in range(0, 360, 45)
        )
        body.append(teeth + _circle(59.8, 84.2, 3.4, o.trim) + _circle(59.8, 84.2, 1.3, _dark(o.main, 0.2)))
    elif cls == "cleric":
        body.append(_p(TORSO, o.main))
        body.append(_p(V_NECK, skin))
        body.append(_pair("M 41.6 67 L 39.2 100 L 45.2 100 L 46.2 69 Z", o.trim))
        rays = "".join(
            f'<rect x="49.4" y="78.4" width="1.2" height="2.6" fill="{o.trim}" transform="rotate({a} 50 84)"/>'
            for a in range(0, 360, 45)
        )
        body.append(rays + _circle(50, 84, 3.2, o.trim) + _circle(50, 84, 1.5, _light(o.trim, 0.4)))
        body.append(_p("M 50 74 L 50 80.6", "none", _stroke(o.trim, 0.7)))
    elif cls == "druid":
        body.append(_p(TORSO, o.main))
        body.append(_p(V_NECK, skin))
        leaves: list[str] = []
        for i in range(9):
            t = i / 8
            x = 31 + 38 * t
            y = 70.4 + 6 * (1 - (2 * t - 1) ** 2) - 2.4 * abs(2 * t - 1)
            angle = -60 + 120 * t
            color = o.trim if i % 2 else _dark(o.trim, 0.25)
            leaves.append(
                f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="2" ry="4.2" fill="{color}" '
                f'transform="rotate({angle:.0f} {x:.1f} {y:.1f})"/>'
            )
        body.append("".join(leaves))
        body.append(_circle(50, 80, 1.6, o.second))
    else:  # wizard, sorcerer, warlock — мантії
        body.append(_p(TORSO, o.main))
        body.append(_pair("M 9 98 C 10 86 14 79 20 75 L 24 100 Z", _dark(o.main, 0.25)))
        body.append(_p(V_NECK, skin))
        if cls == "wizard":
            body.append(_p("M 42.6 66 L 50 80 L 57.4 66", "none", _stroke(o.trim, 2)))
            body.append(_p("M 33 86 l 1 -2.6 l 1 2.6 l 2.6 1 l -2.6 1 l -1 2.6 l -1 -2.6 l -2.6 -1 Z", o.trim))
        else:
            collar = "M 35.6 67.4 C 34.4 60 35.4 52.6 37.4 47 C 40.6 54.6 43.6 61.6 46 67 Z"
            if cls == "warlock":
                collar = "M 33 68.4 C 31 58 32 49.6 35 43 C 39 52.6 43 60.6 46 67 Z"
            body.append(_pair(collar, o.second, _stroke(o.trim, 0.9)))
            body.append(_circle(50, 75, 2.4, o.trim) + _circle(50, 75, 1.1, o.second))
    transform = f' transform="translate(50 100) scale({sx:g} 1) translate(-50 -100)"' if sx != 1 else ""
    parts.append(f"<g{transform}>{''.join(body)}</g>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# голова людиноподібних
# ---------------------------------------------------------------------------


def _head_path(look: Look) -> str:
    jaw = 0.55 if look.female else 0.72
    if look.portrait.group in ("dwarf", "duergar", "goliath", "half-orc", "bugbear"):
        jaw += 0.12
    top, chin, w = 23.0, 57.0, 13.5
    h = chin - top
    y1 = top + 0.47 * h
    return (
        f"M 50 {top} C {50 + 0.75 * w:.2f} {top} {50 + w} {top + 0.25 * h:.2f} {50 + w} {y1:.2f} "
        f"C {50 + w} {top + 0.74 * h:.2f} {50 + jaw * w * 0.72:.2f} {chin} 50 {chin} "
        f"C {50 - jaw * w * 0.72:.2f} {chin} {50 - w} {top + 0.74 * h:.2f} {50 - w} {y1:.2f} "
        f"C {50 - w} {top + 0.25 * h:.2f} {50 - 0.75 * w:.2f} {top} 50 {top} Z"
    )


EARS = {
    "human": "M 37.2 37.8 C 34.6 37.4 33.4 40.2 33.8 42.8 C 34.2 45.6 35.6 47.6 37.6 47.2 Z",
    "small": "M 37.2 37.8 C 34.4 36.8 32.2 35.6 31.4 34.6 C 31.6 39.4 33.6 45.8 37.6 47.2 Z",
    "pointed": "M 37.4 38.4 C 34 36.6 31 34.4 28.8 32.4 C 29.4 37.4 31.6 43.2 37.2 46.8 Z",
    "long": "M 37.4 38.4 C 33 35.5 27.6 30.6 24 26.8 C 25.2 33.4 28.4 41.6 37.2 46.8 Z",
    "gith": "M 37.4 37.6 C 32.6 35 28.6 31.6 25 27.4 C 27.4 33.4 30.6 39.8 37.2 44.4 Z",
    "goblin": "M 37.5 38 C 31 35.6 22 33.6 14.6 36.2 C 19.6 41.2 28 45.6 37.4 46.6 Z",
    "droop": "M 37.4 38.2 C 32.6 37.4 26.6 39.6 22.6 45.2 C 27.4 47.6 32.6 48.4 37.4 47 Z",
    "goat": "M 37 38.5 C 32 36.2 26 35.2 21.6 36.6 C 24.8 40.6 31 43.6 37 44.8 Z",
    "fin": "M 37.4 37.8 L 26.6 32.4 L 29.6 37.2 L 25.8 39.8 L 29.8 42.4 L 27.4 46.2 L 37.4 46.8 Z",
}


def _ears(look: Look) -> str:
    kind = look.kind.ears
    skin = look.skin
    if kind == "bear":
        return _pair("M 35.6 30.6 C 31 27.6 30.6 20.6 35 18.8 C 39 17.4 42.6 20.8 42.4 25 Z", skin) + _pair(
            "M 36.2 28 C 34.2 26 34 22.4 36 21.6 C 38 21 39.8 22.8 39.8 25 Z", _dark(skin, 0.3)
        )
    d = EARS.get(kind)
    if d is None:
        return ""
    inner = _stroke(_dark(skin, 0.28), 0.8)
    fill = _dark(skin, 0.06) if kind != "fin" else _mix(skin, "#2a6a8a", 0.3)
    shade = "M 36.4 40.6 C 35.4 41.4 35.4 44 36.6 45.2"
    if kind in ("long", "pointed", "gith"):
        shade = "M 36.2 40.4 C 33 38 30.6 35.6 29 33.6 C 30.4 37.6 32.6 41.6 36.2 44.2"
    return _pair(d, fill) + _pair(shade, "none", inner)


def _eyes(look: Look) -> str:
    kind, color = look.eyes, look.eye_color
    left = (44.6, 41.6)
    parts: list[str] = []
    big = kind == "big"
    rx, ry = (2.1, 2.5) if big else (1.7, 2.0)
    for cx, cy in (left, (100 - left[0], left[1])):
        if kind == "glow":
            parts.append(_ellipse(cx, cy, 3.6, 3, color, ' fill-opacity=".28"'))
            parts.append(_ellipse(cx, cy, 2, 1.4, color))
        elif kind == "pale":
            parts.append(_ellipse(cx, cy, 2, 1.5, color, _stroke(_dark(look.skin, 0.35), 0.5)))
        elif kind == "slit":
            parts.append(_ellipse(cx, cy, 2.1, 1.6, color, _stroke(INK, 0.5)))
            parts.append(_ellipse(cx, cy, 0.5, 1.5, INK))
        else:
            parts.append(_ellipse(cx, cy, rx, ry, color if color != INK else INK))
            parts.append(_circle(cx + 0.55, cy - 0.7, 0.55 if not big else 0.7, "#ffffff", ' fill-opacity=".85"'))
    brow_color = _dark(look.hair, 0.15) if look.hair_style != "bald" or look.male else _dark(look.skin, 0.35)
    if "brow" in look.kind.extras:
        parts.append(_pair("M 40.6 38.6 Q 44.6 35.6 48.4 38.2 L 48 39.6 Q 44.4 37.6 41 39.8 Z", _dark(look.skin, 0.3)))
    if look.female:
        parts.append(_pair("M 41.8 38.4 Q 44.6 36.6 47.4 38", "none", _stroke(brow_color, 0.9)))
        parts.append(_pair("M 42.8 41 L 41.4 40", "none", _stroke(INK, 0.7)))
    else:
        parts.append(_pair("M 41.6 38.6 Q 44.6 37.2 47.6 38.4", "none", _stroke(brow_color, 1.5)))
    return "".join(parts)


def _nose_mouth(look: Look) -> str:
    skin = look.skin
    shade = _dark(skin, 0.3)
    parts: list[str] = []
    nose = look.kind.nose
    if nose == "big":
        parts.append(_ellipse(50, 47, 3.4, 2.8, _dark(skin, 0.08)))
        parts.append(_p("M 47.4 48.4 Q 50 50.4 52.6 48.4", "none", _stroke(shade, 0.8)))
    elif nose == "flat":
        parts.append(_p("M 47 47.6 Q 50 49.4 53 47.6", "none", _stroke(shade, 1.2)))
        parts.append(_circle(48.4, 47.4, 0.7, shade) + _circle(51.6, 47.4, 0.7, shade))
    elif nose == "none":
        parts.append(_p("M 49.2 46.6 L 49.4 47.6 M 50.8 46.6 L 50.6 47.6", "none", _stroke(shade, 0.7)))
    else:
        parts.append(_p("M 50.8 42.4 C 51.6 45 51.8 46.6 49.6 47.4", "none", _stroke(shade, 1.1)))
    if look.female:
        parts.append(_p("M 47 51.2 Q 50 50 53 51.2 Q 50 53.8 47 51.2 Z", _mix(skin, LIP, 0.55)))
        parts.append(_circle(42.6, 47, 2.6, "#e0707a", ' fill-opacity=".14"'))
        parts.append(_circle(57.4, 47, 2.6, "#e0707a", ' fill-opacity=".14"'))
    else:
        parts.append(_p("M 47.2 51.6 Q 50 52.6 52.8 51.6", "none", _stroke(_dark(skin, 0.4), 1.1)))
    extras = look.kind.extras
    if "tusks" in extras:
        parts.append(_pair("M 45.6 52.8 L 46 48.6 L 47.6 52.6 Z", IVORY))
    if "fangs" in extras:
        parts.append(_pair("M 47.4 51.8 L 47.9 54 L 48.5 52 Z", IVORY))
    if "bunny" in extras:
        parts.append(_p("M 48.4 46 L 51.6 46 L 50 48 Z", "#e08a96"))
        parts.append(_p("M 48.8 52 h 2.4 v 2.2 h -2.4 Z", IVORY))
        for y in (49.2, 50.6):
            parts.append(_pair(f"M 45 {y} L 38.4 {y - 0.8}", "none", _stroke(_light(skin, 0.5), 0.5, 0.8)))
    return "".join(parts)


def _marks(look: Look) -> str:
    extras, skin = look.kind.extras, look.skin
    parts: list[str] = []
    if "marks" in extras:
        parts.append(
            _p(
                "M 39 33 L 42.4 35.4 L 40.6 38.6 M 58 31 L 61.4 34 M 56.6 47 L 60.4 49.6 L 59 53",
                "none",
                _stroke(_dark(skin, 0.38), 0.9),
            )
        )
        parts.append(_circle(41, 49, 0.9, _dark(skin, 0.3)) + _circle(43, 51.4, 0.7, _dark(skin, 0.3)))
    if "cracks" in extras:
        parts.append(
            _p(
                "M 40 30 L 43 34 L 41.6 37 M 57 28 L 55.6 32.6 L 58.4 35 M 58.6 47.6 L 61 51",
                "none",
                _stroke("#f2b25a", 0.8, 0.85),
            )
        )
    if "scales" in extras:
        scale = _mix(skin, "#3e7a4e", 0.55)
        for x, y in ((40.4, 45.6), (42.6, 46.8), (40.8, 48.2), (57.4, 45.6), (59.4, 47), (50, 27.6), (52.4, 28.8)):
            parts.append(_p(f"M {x - 1.1} {y} q 1.1 -1.4 2.2 0", "none", _stroke(scale, 0.7)))
    if "tattoo" in extras:
        parts.append(_p("M 44 27 L 50 31 L 56 27 M 50 31 L 50 35", "none", _stroke(_dark(skin, 0.35), 0.9)))
    if "drops" in extras:
        parts.append(_p("M 60 46 q 1.2 2.4 0 3 q -1.2 -0.6 0 -3 Z", _light(skin, 0.5), ' fill-opacity=".7"'))
    if "sideburns" in extras:
        parts.append(_pair("M 36.4 39.6 C 35.8 46 37 50.6 39.8 52.6 L 38.6 44 Z", look.hair))
    if look.headgear == "paint":
        parts.append(_pair("M 39.4 43.8 L 46 44.8 L 45.8 46.4 L 39.8 45.8 Z", "#b3242e", ' fill-opacity=".85"'))
        parts.append(_p("M 49 30 h 2 v 5 h -2 Z", "#b3242e", ' fill-opacity=".85"'))
    if look.portrait.class_key == "sorcerer" and look.headgear == "glow":
        parts.append(
            _p("M 57.6 45.6 l 2.6 1.6 l -1 2.6 M 41.8 45.6 l -2.6 1.6", "none", _stroke(look.outfit.trim, 0.8, 0.9))
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# волосся
# ---------------------------------------------------------------------------

CAP = (
    "M 36.3 41.5 C 35.2 27.5 41.6 20.8 50 20.8 C 58.4 20.8 64.8 27.5 63.7 41.5 L 62.6 41.5 "
    "C 62.2 34.4 58.2 30.4 50 30.8 C 41.8 30.4 37.8 34.4 37.4 41.5 Z"
)
SWEPT = (
    "M 36.3 41.5 C 35 27 41 19.5 51 19.6 C 60 19.7 65.5 27 63.7 41.5 L 62.6 41.5 C 62.4 35 60.5 31.4 57.5 30 "
    "C 52 32.6 44 31 38.6 34.8 C 37.8 37 37.5 39 37.4 41.5 Z"
)
PARTED = (
    "M 36.2 42 C 35 27.5 41.5 20.8 50 20.8 C 58.5 20.8 65 27.5 63.8 42 C 62.8 34.4 60.4 30.2 55 28.4 "
    "C 50 31 43.4 33.6 37.6 42 Z"
)
MIDDLE = (
    "M 36.2 42 C 35 27.5 41.5 20.8 50 20.8 C 58.5 20.8 65 27.5 63.8 42 C 63 35 61.6 30.4 50 27.8 "
    "C 38.4 30.4 37 35 36.2 42 Z"
)
FRINGE = (
    "M 36.2 42 C 35 27.5 41.5 20.8 50 20.8 C 58.5 20.8 65 27.5 63.8 42 C 63 37.4 62.4 35 61.4 33.6 "
    "Q 50 35.4 38.6 33.6 C 37.6 35 37 37.4 36.2 42 Z"
)
HIGH = (
    "M 36.6 40.5 C 35.6 27.5 41.6 21 50 21 C 58.4 21 64.4 27.5 63.4 40.5 C 62.4 33 58.4 28.6 50 28.4 "
    "C 41.6 28.6 37.6 33 36.6 40.5 Z"
)


def _hair(look: Look) -> tuple[str, str]:
    """(за головою, на голові)."""
    style, color = look.hair_style, look.hair
    if look.headgear in ("hood", "coif") and style not in ("flame",):
        # Під каптуром видно лише чубчик.
        return "", _p(FRINGE if look.female else CAP, color)
    shine = _p("M 42.6 25 Q 50 22.4 57.4 25", "none", _stroke(_light(color, 0.45), 1.1, 0.5))
    back, front = "", ""
    if style == "short":
        front = _p(CAP, color)
    elif style == "swept":
        front = _p(SWEPT, color)
    elif style == "long":
        if look.female:
            back = _p(
                "M 36 34 C 33 46 32.5 60 30.5 74 C 36 78.6 42 76 43.6 68 L 45 60 L 55 60 L 56.4 68 "
                "C 58 76 64 78.6 69.5 74 C 67.5 60 67 46 64 34 Z",
                color,
            )
            front = _p(PARTED, color)
        else:
            back = _p(
                "M 36 34 C 34 44 34.6 54 35.6 62 C 39 64.6 42 63 43.6 60 L 56.4 60 C 58 63 61 64.6 64.4 62 "
                "C 65.4 54 66 44 64 34 Z",
                color,
            )
            front = _p(MIDDLE, color)
    elif style == "wavy":
        back = _p(
            "M 36 34 C 32 44 34 50 31 58 C 28 66 33 70 30 78 C 37 80.4 43 76 44 68 L 45 60 L 55 60 L 56 68 "
            "C 57 76 63 80.4 70 78 C 67 70 72 66 69 58 C 66 50 68 44 64 34 Z",
            color,
        )
        front = _p(MIDDLE, color)
    elif style == "bob":
        back = _p(
            "M 35.6 34 C 33.4 44 33 52 34.4 58.6 C 38 59.6 41 58.8 42 57 L 58 57 C 59 58.8 62 59.6 65.6 58.6 "
            "C 67 52 66.6 44 64.4 34 Z",
            color,
        )
        front = _p(FRINGE, color)
    elif style == "bun":
        front = (
            _p(HIGH, color)
            + _circle(50, 17.4, 6.2, color)
            + _p("M 44.6 21.6 Q 50 23.8 55.4 21.6", "none", _stroke(look.outfit.trim, 1.2))
        )
    elif style == "braid":
        back = _p("M 36 34 C 34 42 35 48 38 52 L 62 52 C 65 48 66 42 64 34 Z", color)
        links = "".join(
            _ellipse(x, y, r, r * 1.2, color, _stroke(_dark(color, 0.35), 0.6))
            for x, y, r in ((37.4, 52, 3.6), (36, 58, 3.5), (35, 64, 3.4), (34.6, 70, 3.2), (34.6, 75.6, 3))
        )
        back += links + _p("M 33 79 L 36 79 L 37 86 L 34.6 84 L 32 86 Z", color)
        back += _p("M 32.8 78.6 h 3.8", "none", _stroke(look.outfit.trim, 1.4))
        front = _p(SWEPT, color)
    elif style == "braids":
        back = _p("M 36 34 C 34 42 35 48 38 52 L 62 52 C 65 48 66 42 64 34 Z", color)
        for side in (1, -1):
            for i, y in enumerate((50, 56, 62, 68, 74)):
                x = 50 + side * (14.6 - i * 0.4)
                back += _ellipse(x, y, 3.2, 3.8, color, _stroke(_dark(color, 0.35), 0.6))
            back += _circle(50 + side * 12.8, 78.6, 1.6, look.outfit.trim)
        front = _p(MIDDLE, color)
    elif style == "pony":
        back = _p("M 54 21 C 64 14 74 22 71 36 C 69 46 70 54 72 60 C 66 56 64 46 65 38 C 66 30 62 25 56 25 Z", color)
        front = _p(HIGH, color) + _p("M 56.6 21.6 L 58.4 25", "none", _stroke(look.outfit.trim, 1.8))
    elif style == "mohawk":
        front = _p(CAP, color, ' fill-opacity=".25"') + _p(
            "M 46.2 31 C 45.6 22 47 15 50 11.6 C 53 15 54.4 22 53.8 31 Z", color
        )
    elif style == "topknot":
        front = _p(CAP if look.male else HIGH, color) + _circle(50, 17.6, 4.2, color)
        front += _p("M 48 21.4 Q 50 22.6 52 21.4", "none", _stroke(look.outfit.trim, 1.2))
        if look.portrait.group == "gith":
            front += _p("M 50 14 C 56 12 60 18 59 26 C 57 22 54 18 50 17 Z", color)
    elif style == "curly":
        puffs = ((37.4, 37), (38.2, 30), (42.4, 24.6), (48, 21.8), (54, 22), (59, 24.8), (62.2, 30.4), (63, 37))
        front = _p(CAP, color) + "".join(_circle(x, y, 4.6, color) for x, y in puffs)
        if look.female:
            back = "".join(
                _circle(x, y, 4.8, color) for x, y in ((35, 44), (34, 51), (35.4, 57), (65, 44), (66, 51), (64.6, 57))
            )
        front += _p("M 44 23 Q 48 20.6 52 21.6", "none", _stroke(_light(color, 0.4), 1, 0.5))
        return back, front
    elif style == "shaggy":
        front = _p(
            "M 35.6 42 C 34 28 40 19.6 50 19.6 C 60 19.6 66 28 64.4 42 L 61.6 36 L 60.4 40 L 58 33 L 55 36 L 52 31 "
            "L 48.6 35 L 46 31 L 43 36 L 41.4 32.6 L 39.6 40 L 38.2 35.6 Z",
            color,
        )
    elif style == "flame":
        flame = (
            "M 36 40 C 32 30 34 22 38 16 C 38.6 21 40.6 23 42 23.6 C 41 16 44 9 50 4 C 49.6 10 52 15 55 17 "
            "C 56 13 58 11 61 9.6 C 60 15 62 20 64 24 C 66 28 66 34 64 40 C 61 33 56 30 50 30.4 C 44 30 39 33 36 40 Z"
        )
        front = _p(flame, "#ff8a3d") + _p(
            "M 41 32 C 40 26 42 20 45 16 C 45.6 21 48 24 50 25 C 51 20 53 16 56 14.6 C 55.6 19 57.6 23 59.6 27 "
            "C 56 28.4 46 28.4 41 32 Z",
            "#ffd36a",
        )
        return "", front
    elif style == "wisp":
        front = _p(HIGH, color, ' fill-opacity=".9"') + _p(
            "M 38 30 C 30 24 28 14 36 10 C 34 16 38 20 42 22 M 50 21 C 48 12 54 6 60 8 C 56 10 54 14 55 20 "
            "M 62 30 C 70 26 72 18 68 14",
            "none",
            _stroke(color, 1.8, 0.85),
        )
        return "", front
    else:  # bald
        front = _p("M 43 26 Q 50 23.4 57 26", "none", _stroke(_light(look.skin, 0.4), 1.4, 0.5))
        return "", front
    return back, front + shine


def _beard(look: Look) -> str:
    style, color = look.beard, look.hair
    if style == "none" or (not look.male and style != "fur"):
        return ""
    mo = (
        "M 44.4 51.6 C 46 49.4 48.6 49.6 50 50.6 C 51.4 49.6 54 49.4 55.6 51.6 C 53.6 51.4 51.6 51.8 50 52.6 "
        "C 48.4 51.8 46.4 51.4 44.4 51.6 Z"
    )
    full = (
        "M 36.6 42 C 36.6 52 41 60.6 50 62.6 C 59 60.6 63.4 52 63.4 42 L 61.6 43 C 61 49 58.6 52.6 55.6 53.6 "
        "C 53.6 52 46.4 52 44.4 53.6 C 41.4 52.6 39 49 38.4 43 Z"
    )
    if style == "full":
        return _p(full, color) + _p(mo, _dark(color, 0.1))
    if style == "stubble":
        return _p(full, color, ' fill-opacity=".3"')
    if style == "goatee":
        return _p(
            "M 46 53.6 C 47 52.6 53 52.6 54 53.6 C 54 57.6 52.6 60 50 61 C 47.4 60 46 57.6 46 53.6 Z", color
        ) + _p(mo, color)
    if style == "moustache":
        return _p(mo, color)
    if style == "fur":
        return _p(
            "M 36 40 C 35 52 40 62 50 64.6 C 60 62 65 52 64 40 L 61.6 44 C 60 51 56 54 50 54.6 C 44 54 40 51 38.4 44 Z",
            color,
        ) + _p(
            "M 38 52 l 2 3 M 42 58 l 2 2.4 M 62 52 l -2 3 M 58 58 l -2 2.4", "none", _stroke(_dark(color, 0.3), 0.8)
        )
    # dwarf
    long = (
        "M 36.6 42 C 36 54 38 66 42 74 C 44.6 79 47.6 82 50 84 C 52.4 82 55.4 79 58 74 C 62 66 64 54 63.4 42 "
        "L 61.6 43 C 61 49 58.6 52.6 55.6 53.6 C 53.6 52 46.4 52 44.4 53.6 C 41.4 52.6 39 49 38.4 43 Z"
    )
    strands = _p(
        "M 44 60 Q 45 68 47 76 M 50 62 L 50 80 M 56 60 Q 55 68 53 76", "none", _stroke(_dark(color, 0.3), 0.8, 0.8)
    )
    rings = _p("M 46.4 72.6 h 7.2", "none", _stroke(look.outfit.trim, 1.6))
    return _p(long, color) + strands + rings + _p(mo, _dark(color, 0.1))


# ---------------------------------------------------------------------------
# убори
# ---------------------------------------------------------------------------

HOOD_BACK = (
    "M 27.6 72 C 23 52 27.6 17.6 50 15.6 C 72.4 17.6 77 52 72.4 72 C 66 69 60 67 50 67.6 C 40 67 34 69 27.6 72 Z"
)
HOOD_INNER = "M 35.4 60 C 33.4 44 36 25 50 24.2 C 64 25 66.6 44 64.6 60 Z"
HOOD_FRONT = (
    "M 34.6 43 C 35.2 26 41 20.2 50 20.2 C 59 20.2 64.8 26 65.4 43 C 63.6 33.6 58.6 28.6 50 28.6 "
    "C 41.4 28.6 36.4 33.6 34.6 43 Z"
)


def _hood_color(look: Look) -> str:
    o = look.outfit
    if look.portrait.class_key == "cleric":
        return o.main
    return o.main if look.portrait.class_key != "rogue" else o.second


def _behind_head(look: Look) -> str:
    parts: list[str] = []
    if "halo" in look.kind.extras:
        parts.append(_circle(50, 31, 19.6, "none", _stroke("#f3d98a", 5, 0.18)))
        parts.append(_circle(50, 31, 19.6, "none", _stroke("#f3d98a", 1.4, 0.9)))
    if look.headgear in ("hood", "coif"):
        color = _hood_color(look)
        parts.append(_p(HOOD_BACK, color) + _p(HOOD_INNER, _mix(color, "#07060a", 0.78)))
    if look.portrait.group == "leonin" and look.portrait.gender != "f":
        mane = []
        for i in range(36):
            angle = 2 * math.pi * i / 36
            radius = 27 if i % 2 else 21
            mane.append(f"{50 + radius * math.cos(angle):.1f} {42 + radius * math.sin(angle):.1f}")
        mane_color = _mix(look.skin, "#5a2e14", 0.55)
        parts.append(_p("M " + " L ".join(mane) + " Z", mane_color))
        parts.append(_circle(50, 42, 20, _light(mane_color, 0.12)))
    return "".join(parts)


def _headgear(look: Look) -> str:
    gear, o = look.headgear, look.outfit
    if gear in ("hood", "coif"):
        color = _hood_color(look)
        shadow = _p(HOOD_INNER, "url(#hs)")
        look.defs.append(
            '<linearGradient id="hs" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#000" stop-opacity=".55"/>'
            '<stop offset=".55" stop-color="#000" stop-opacity="0"/></linearGradient>'
        )
        folds = _pair("M 30 66 C 30 52 31 38 36 28", "none", _stroke(_dark(color, 0.3), 0.8, 0.8))
        return shadow + _p(HOOD_FRONT, _dark(color, 0.12)) + folds
    if gear == "hat":
        brim = (
            "M 25.6 30.6 C 30 26 40 24.6 50 24.6 C 60 24.6 70 26 74.4 30.6 C 70 33.4 60 33.8 50 33.4 "
            "C 40 33.8 30 33.4 25.6 30.6 Z"
        )
        cone = (
            "M 36 29.6 C 39 21 45 12 54 4.6 C 56.6 3 58.4 3.6 57 6 C 55 11 58 20 64.6 29.6 C 56 31.4 44 31.4 36 29.6 Z"
        )
        band = "M 36.6 28.2 C 45 30.2 55 30.2 64 28.2 L 63.2 25.4 C 55 27.4 45 27.4 37.6 25.4 Z"
        star = "M 52 13 l .8 -2 l .8 2 l 2 .8 l -2 .8 l -.8 2 l -.8 -2 l -2 -.8 Z"
        return _p(brim, _dark(o.main, 0.25)) + _p(cone, o.main) + _p(band, o.trim) + _p(star, o.trim)
    if gear in ("helm", "plume", "horned"):
        steel = "#9aa3b5" if look.portrait.class_key != "paladin" else "#b4bcca"
        if look.portrait.class_key == "barbarian":
            steel = "#8a8f96"
        dome = (
            "M 35.4 42 C 34.6 26 41 19 50 19 C 59 19 65.4 26 64.6 42 L 61.8 46 C 62 38 60.6 34 58.6 33.2 "
            "L 41.4 33.2 C 39.4 34 38 38 38.2 46 Z"
        )
        parts = [_p(dome, steel, _stroke(_dark(steel, 0.45), 0.7))]
        parts.append(_p("M 36 33 L 64 33 L 63.6 36 L 36.4 36 Z", _dark(steel, 0.25)))
        parts.append("".join(_circle(x, 34.5, 0.6, _light(steel, 0.5)) for x in (39, 44, 56, 61)))
        if gear != "horned":
            parts.append(_p("M 48.6 33 L 51.4 33 L 51 46.6 L 49 46.6 Z", steel, _stroke(_dark(steel, 0.45), 0.5)))
        parts.append(_p("M 42 24 Q 50 20.6 58 24", "none", _stroke(_light(steel, 0.6), 1.2, 0.6)))
        if gear == "plume":
            parts.insert(0, _p("M 47.4 20 C 46.6 13 47.6 8 50 5 C 52.4 8 53.4 13 52.6 20 Z", o.second))
        if gear == "horned":
            parts.insert(
                0, _pair("M 37.6 28 C 31 26 26 20 25 12 C 30 17 34 20 39.4 22 Z", IVORY, _stroke("#b8ac90", 0.6))
            )
        return "".join(parts)
    if gear == "circlet":
        return _p("M 37 33.6 Q 50 29.4 63 33.6", "none", _stroke(o.trim, 1.5)) + _circle(
            50, 31.4, 1.7, o.gem, _stroke(_dark(o.trim, 0.3), 0.5)
        )
    if gear == "beret":
        beret = "M 33 30 C 32 22 44 17.6 56 19 C 66 20.6 70 26 67 30 C 60 32.4 42 32.6 33 30 Z"
        feather = "M 60 22 C 68 14 76 10 82 9 C 78 14 72 20 63 25 Z"
        return (
            _p(feather, o.second, _stroke(_dark(o.second, 0.3), 0.5))
            + _p(beret, o.main)
            + _p("M 33.6 29 C 42 31.4 58 31.4 66.6 29", "none", _stroke(o.trim, 1.2))
        )
    if gear == "antlers":
        wood = "#8a6a48"
        branch = "M 39 27 C 36 20 33 15 28 11 M 34.6 18.6 C 31 18 28.6 19.6 26 22 M 31.6 14.6 C 31 10.6 32 7.6 34 5"
        return _pair(branch, "none", _stroke(wood, 2.2)) + _pair("M 40 27 L 37 24 L 41 24 Z", o.trim)
    if gear == "leaves":
        parts = []
        for i in range(7):
            t = i / 6
            x = 37 + 26 * t
            y = 30.4 - 5.4 * (1 - (2 * t - 1) ** 2)
            angle = -50 + 100 * t
            parts.append(
                f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="1.9" ry="3.8" fill="{o.trim if i % 2 else _dark(o.trim, 0.25)}" '
                f'transform="rotate({angle:.0f} {x:.1f} {y:.1f})"/>'
            )
        return "".join(parts)
    if gear == "headband":
        band = "M 36.2 33.4 Q 50 30.4 63.8 33.4 L 63.8 36.2 Q 50 33.2 36.2 36.2 Z"
        tail = "M 63.4 34 C 68 36 70 40 69 45 C 67 41 65 38 63 36.4 Z"
        return _p(tail, _dark(o.second, 0.15)) + _p(band, o.second)
    if gear == "goggles":
        strap = "M 36 31.6 Q 50 28.6 64 31.6 L 64 34 Q 50 31 36 34 Z"
        lens = "".join(
            _circle(x, 31.4, 4.2, o.trim) + _circle(x, 31.4, 2.9, "#5fb8b0") + _circle(x - 1, 30.4, 0.8, "#e8fffa")
            for x in (44.2, 55.8)
        )
        return _p(strap, "#3a2a1c") + lens
    if gear == "mask":
        mask = (
            "M 36.8 46.6 C 40 47.6 45 46.6 50 46 C 55 46.6 60 47.6 63.2 46.6 C 63 52 58.6 58.6 50 60 "
            "C 41.4 58.6 37 52 36.8 46.6 Z"
        )
        return _p(mask, o.second) + _p(
            "M 42 52 Q 50 55 58 52 M 45 56.4 Q 50 58 55 56.4", "none", _stroke(_dark(o.second, 0.35), 0.8)
        )
    return ""


def _top_extras(look: Look) -> str:
    """Роги й вуха поверх убору (тіфлінґ у каптурі — роги назовні)."""
    extras, parts = look.kind.extras, []
    if "horns" in extras:
        horn = "#2b2228"
        if _pick(look.portrait.id, "horns", ("ram", "swept")) == "ram":
            d = (
                "M 41.6 27.6 C 38 21 30.6 19.6 27.8 25 C 25.8 29.4 28.6 34 32.6 33.4 C 35 33 35.8 30.6 34.6 28.8 "
                "C 33.6 30.6 31 30.8 30.4 28.6 C 29.8 25.6 33.2 23.4 36.4 25.2 C 38 26 39.2 27.4 40 29 Z"
            )
        else:
            d = "M 42 27.4 C 40 20 37 14 33 9 C 38 12 43 18 45.8 25.8 Z"
        parts.append(_pair(d, horn, _stroke(_light(horn, 0.25), 0.6)))
    if "small-horns" in extras:
        parts.append(_pair("M 43 25 C 42 20 40 17 37.6 15.6 C 40.6 16.6 43.6 19.6 45.6 24 Z", "#6b4a2e"))
    if "twigs" in extras:
        parts.append(
            _pair("M 42 26 C 41 21 38 18 35 17 M 39.6 20.6 C 39 18 39.4 16 40.6 14.6", "none", _stroke("#5a4a3a", 1.4))
        )
    if "bunny" in extras:
        ear = "M 42.6 26 C 38.6 14 37.6 4 41.4 2 C 45.4 4 47 14 46.4 25 Z"
        inner = "M 42.8 22 C 40.6 14 40.4 7 41.8 5.4 C 43.6 7.4 44.6 14 44.6 22 Z"
        parts.append(_pair(ear, look.skin) + _pair(inner, "#e8a8b0"))
    if "fin" in extras:
        parts.append(_p("M 50 21 C 48 15 49 10 51 6 C 52 11 54 15 55.4 21.4 Z", _mix(look.skin, "#2a6a8a", 0.3)))
    return "".join(parts)


# ---------------------------------------------------------------------------
# звірині голови
# ---------------------------------------------------------------------------


def _dragon(look: Look) -> str:
    skin, small = look.skin, "small" in look.kind.extras
    dark, light = _dark(skin, 0.3), _light(skin, 0.3)
    parts: list[str] = []
    if "crest" in look.kind.extras:
        parts.append(
            _p("M 42 24 L 40 12 L 46 21 L 47 8 L 51 20 L 55 9 L 55 21 L 61 13 L 58.6 24.6 Z", _dark(skin, 0.2))
        )
    else:
        parts.append(
            _pair(
                "M 39 26 C 33 19 27 12 22 6 C 29 9 36 15 42 22 Z",
                _light(skin, 0.15) if small else IVORY,
                _stroke(dark, 0.6),
            )
        )
        parts.append(_pair("M 37 32 C 31 29 26 28 22 28 C 27 31 32 34 36.6 36 Z", dark))
    head = (
        "M 50 20 C 59 20 65.6 26 65.6 35 C 65.6 42 62 47 59 53 C 57 58 54 63 50 63 C 46 63 43 58 41 53 "
        "C 38 47 34.4 42 34.4 35 C 34.4 26 41 20 50 20 Z"
    )
    parts.append(_pair("M 35 40 L 27 45 L 33 46 L 28 51 L 38.6 50 Z", dark))
    parts.append(_p(head, skin))
    parts.append(_p("M 44 44 C 44 52 46 58 50 61 C 54 58 56 52 56 44 Z", light, ' fill-opacity=".35"'))
    parts.append(_pair("M 39 36.6 Q 44 34 47.6 37.2 L 47 38.6 Q 43.6 36.6 39.6 38.4 Z", dark))
    for cx in (43.8, 56.2):
        parts.append(_ellipse(cx, 40.6, 2.3, 1.6, look.eye_color, _stroke(INK, 0.5)))
        parts.append(_ellipse(cx, 40.6, 0.5, 1.5, INK))
    for y in (45, 49.6):
        parts.append(_p(f"M 46.6 {y} Q 50 {y - 1.6} 53.4 {y}", "none", _stroke(dark, 0.8)))
    for x, y in ((45, 27), (50, 25.4), (55, 27), (47.6, 30.4), (52.4, 30.4)):
        parts.append(_p(f"M {x - 1.4} {y} q 1.4 1.6 2.8 0", "none", _stroke(dark, 0.7)))
    parts.append(_ellipse(47.4, 58.4, 0.9, 0.6, INK) + _ellipse(52.6, 58.4, 0.9, 0.6, INK))
    parts.append(_p("M 42 53.6 Q 50 59.4 58 53.6", "none", _stroke(_dark(skin, 0.45), 0.9)))
    return "".join(parts)


def _cat(look: Look) -> str:
    fur = look.skin
    light = _light(fur, 0.55)
    dark = _dark(fur, 0.35)
    parts = [_pair("M 37 32 L 35 15 L 47 24.6 Z", fur) + _pair("M 38.2 29 L 37.2 18.6 L 44.6 24.6 Z", "#d88a90")]
    parts.append(
        _p("M 50 22 C 60 22 66 29 65.6 39 C 65 48 59 56 50 57 C 41 56 35 48 34.4 39 C 34 29 40 22 50 22 Z", fur)
    )
    if "stripes" in look.kind.extras:
        parts.append(
            _p("M 50 23 L 48.8 30 L 51.2 30 Z M 44 24.6 L 45 29 L 46.4 28.4 Z M 56 24.6 L 55 29 L 53.6 28.4 Z", dark)
        )
        parts.append(_pair("M 35 42 L 40 43.4 L 35.6 45 Z", dark))
    parts.append(
        _p(
            "M 50 45 C 55 45 58.6 48 58 51.6 C 57.6 55 54 56.8 50 56.8 C 46 56.8 42.4 55 42 51.6 "
            "C 41.4 48 45 45 50 45 Z",
            light,
        )
    )
    for cx in (44.2, 55.8):
        parts.append(
            _p(
                f"M {cx - 3.2} 40.6 Q {cx} 37.4 {cx + 3.2} 40.4 Q {cx} 43 {cx - 3.2} 40.6 Z",
                look.eye_color,
                _stroke(INK, 0.5),
            )
        )
        parts.append(_ellipse(cx, 40.4, 0.7, 2, INK))
    parts.append(_p("M 47.8 47.4 L 52.2 47.4 L 50 49.8 Z", "#c86a78"))
    parts.append(
        _p(
            "M 50 49.8 L 50 51.2 M 50 51.2 Q 48 53 46.4 51.8 M 50 51.2 Q 52 53 53.6 51.8",
            "none",
            _stroke(_dark(fur, 0.55), 0.8),
        )
    )
    parts.append(_pair("M 43 50.6 L 31 48.6 M 43 52.2 L 31.6 54", "none", _stroke("#f4ede0", 0.5, 0.8)))
    return "".join(parts)


def _bird(look: Look) -> str:
    feathers = look.skin
    dark, light = _dark(feathers, 0.35), _light(feathers, 0.25)
    owl = "owl" in look.kind.extras
    beak = "#e0a030" if look.portrait.group == "aarakocra" else ("#3a3a42" if not owl else "#d8b070")
    parts: list[str] = []
    if owl:
        parts.append(_pair("M 38 26 L 33 14 L 44 23 Z", dark))
    else:
        parts.append(_p("M 46 21 L 42 9 L 49 19 Z M 50 20 L 51 7 L 53 20 Z M 54 21 L 59 10 L 56.6 21.6 Z", dark))
    parts.append(
        _p("M 50 19 C 61 19 66 27 65.6 37 C 65 47 59 55 50 57 C 41 55 35 47 34.4 37 C 34 27 39 19 50 19 Z", feathers)
    )
    if owl:
        parts.append(_circle(43.4, 39.4, 6.6, light) + _circle(56.6, 39.4, 6.6, light))
    for cx in (43.4, 56.6):
        parts.append(_circle(cx, 39.6, 2.6 if owl else 2.2, look.eye_color, _stroke(INK, 0.5)))
        parts.append(_circle(cx, 39.6, 1.1, INK) + _circle(cx + 0.6, 38.9, 0.45, "#ffffff"))
    for x, y in ((42, 50), (58, 50), (46, 53.6), (54, 53.6), (50, 27), (45, 29), (55, 29)):
        parts.append(_p(f"M {x - 1.6} {y} q 1.6 1.8 3.2 0", "none", _stroke(dark, 0.7)))
    if owl:
        parts.append(_p("M 47.6 44 C 48.6 42.6 51.4 42.6 52.4 44 L 50.6 50 Q 50 51 49.4 50 Z", beak))
    else:
        parts.append(_p("M 45.4 43.6 C 47 41.6 53 41.6 54.6 43.6 L 50.6 60.4 Q 50 62 49.4 60.4 Z", beak))
        parts.append(_p("M 47 47.6 Q 50 49 53 47.6", "none", _stroke(_dark(beak, 0.4), 0.6)))
    return "".join(parts)


def _tortle(look: Look) -> str:
    skin = look.skin
    dark = _dark(skin, 0.35)
    head = (
        "M 50 24 C 60 24 64.6 31 64.6 40 C 64.6 49 58 56.6 50 56.6 C 42 56.6 35.4 49 35.4 40 C 35.4 31 40 24 50 24 Z"
    )
    parts = [_p(head, skin)]
    parts.append(_p("M 41 49 Q 50 54 59 49 Q 50 51.6 41 49 Z", dark))
    parts.append(_pair("M 40.4 38 Q 44 36 47.4 38.4", "none", _stroke(dark, 1.4)))
    parts.append(_ellipse(44.2, 41.2, 1.8, 1.9, INK) + _ellipse(55.8, 41.2, 1.8, 1.9, INK))
    parts.append(_circle(44.8, 40.5, 0.5, "#fff") + _circle(56.4, 40.5, 0.5, "#fff"))
    parts.append(_circle(48.6, 45.6, 0.6, dark) + _circle(51.4, 45.6, 0.6, dark))
    parts.append(_p("M 44 29 q 2 -1.6 4 0 M 52 29 q 2 -1.6 4 0", "none", _stroke(_light(skin, 0.3), 0.8)))
    return "".join(parts)


def _warforged(look: Look) -> str:
    metal = look.skin
    dark, light = _dark(metal, 0.4), _light(metal, 0.3)
    head = "M 50 21 L 61 24 L 64.6 34 L 62.6 48 L 56 57.6 L 44 57.6 L 37.4 48 L 35.4 34 L 39 24 Z"
    parts = [_p(head, metal, _stroke(dark, 0.8))]
    parts.append(
        _p(
            "M 50 21 L 50 36 M 37 34 L 46 36 M 63 34 L 54 36 M 40 48 L 46 50 M 60 48 L 54 50",
            "none",
            _stroke(dark, 0.8),
        )
    )
    parts.append(_p("M 41 39.6 L 47.6 41 L 47 43 L 41.4 42 Z", look.eye_color))
    parts.append(_p(_mirror("M 41 39.6 L 47.6 41 L 47 43 L 41.4 42 Z"), look.eye_color))
    parts.append(_ellipse(44.4, 41.4, 5, 3.4, look.eye_color, ' fill-opacity=".18"'))
    parts.append(_ellipse(55.6, 41.4, 5, 3.4, look.eye_color, ' fill-opacity=".18"'))
    parts.append(_p("M 45 52 L 55 52 M 45.6 54.4 L 54.4 54.4", "none", _stroke(dark, 1)))
    parts.append(_p("M 42 26 L 50 23.6 L 58 26", "none", _stroke(light, 1, 0.8)))
    parts.append(_circle(39.4, 46, 0.7, light) + _circle(60.6, 46, 0.7, light))
    return "".join(parts)


def _bull(look: Look) -> str:
    skin = look.skin
    dark, light = _dark(skin, 0.35), _light(skin, 0.3)
    parts = [_pair("M 39 27 C 30 26 22 22 18 13 C 26 18 32 19 40 21.6 Z", IVORY, _stroke("#b8ac90", 0.6))]
    parts.append(_pair("M 37 33 C 32 32 27 33 24 36 C 28 38 33 38.4 37 37.4 Z", dark))
    head = (
        "M 50 21 C 59 21 64 28 63.6 37 C 63 44 60 49 60 54 C 60 60 56 63 50 63 C 44 63 40 60 40 54 "
        "C 40 49 37 44 36.4 37 C 36 28 41 21 50 21 Z"
    )
    parts.append(_p(head, skin))
    parts.append(_p("M 41 50 C 41 46 59 46 59 50 C 60 58 56 62.6 50 62.6 C 44 62.6 40 58 41 50 Z", light))
    parts.append(_p("M 44 23 C 47 26 53 26 56 23 C 54 28 46 28 44 23 Z", dark))
    parts.append(_ellipse(43.6, 39.6, 1.6, 1.6, INK) + _ellipse(56.4, 39.6, 1.6, 1.6, INK))
    parts.append(_ellipse(46.4, 55, 1.2, 1.8, dark) + _ellipse(53.6, 55, 1.2, 1.8, dark))
    parts.append(_circle(50, 59.6, 2.6, "none", _stroke(BRASS, 1.1)))
    return "".join(parts)


def _elephant(look: Look) -> str:
    skin = look.skin
    dark = _dark(skin, 0.3)
    parts = [_pair("M 37 30 C 24 22 12 30 14 46 C 16 58 26 62 37 52 Z", _dark(skin, 0.1), _stroke(dark, 0.7))]
    parts.append(
        _p(
            "M 50 22 C 60 22 64 29 63.6 38 C 63 44 58 48 55 50 L 45 50 C 42 48 37 44 36.4 38 C 36 29 40 22 50 22 Z",
            skin,
        )
    )
    parts.append(_pair("M 44 52 C 40 58 38 62 35.6 63 C 39 63 43 60 46 55 Z", IVORY))
    parts.append(_p("M 45 44 C 45 56 46 66 44 76 C 47 78 50 77 51 74 C 53 66 55 56 55 44 Z", skin))
    parts.append(_p("M 46 54 h 8 M 46 60 h 7.6 M 45.6 66 h 7", "none", _stroke(dark, 0.7)))
    parts.append(_ellipse(43.4, 39, 1.3, 1.5, INK) + _ellipse(56.6, 39, 1.3, 1.5, INK))
    parts.append(_pair("M 40.6 36 Q 43.6 34.6 46.4 36", "none", _stroke(dark, 1)))
    return "".join(parts)


SPECIAL_HEADS = {
    "dragon": _dragon,
    "cat": _cat,
    "bird": _bird,
    "tortle": _tortle,
    "warforged": _warforged,
    "bull": _bull,
    "elephant": _elephant,
}


# ---------------------------------------------------------------------------
# складання
# ---------------------------------------------------------------------------


def render(item: Portrait) -> str:
    look = look_of(item)
    kind = look.kind
    sx, sy, dy = kind.scale
    head_transform = (
        f' transform="translate(50 {40 + dy:g}) scale({sx:g} {sy:g}) translate(-50 -40)"'
        if (sx, sy, dy) != (1.0, 1.0, 0.0)
        else ""
    )
    behind = _behind_head(look)
    head_layers: list[str] = []
    special = SPECIAL_HEADS.get(kind.head)
    if special is not None:
        head_layers.append(special(look))
        head_layers.append(_headgear(look) if look.headgear in ("circlet", "hat", "hood") else "")
        head_layers.append(_marks(look) if look.headgear == "paint" else "")
    else:
        back_hair, front_hair = _hair(look)
        head_layers += [back_hair, _ears(look), _p(_head_path(look), look.skin)]
        head_layers += [_eyes(look), _nose_mouth(look), _marks(look), _beard(look), front_hair]
        head_layers += [_headgear(look), _top_extras(look)]
    if special is not None and look.headgear == "hood":
        # Каптур поверх морди: його тінь і край.
        pass
    tint = look.outfit.tint
    defs = (
        '<radialGradient id="bg" cx=".5" cy=".38" r=".72">'
        f'<stop offset="0" stop-color="{_light(tint, 0.18)}"/><stop offset="1" stop-color="#0d1016"/></radialGradient>'
        '<linearGradient id="lt" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#fff6e0" stop-opacity=".12"/>'
        '<stop offset=".55" stop-color="#000" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#000" stop-opacity=".34"/></linearGradient>'
    )
    head_svg = "".join(head_layers)
    body = (
        '<rect width="100" height="100" fill="url(#bg)"/>'
        + _back_items(look)
        + f"<g{head_transform}>{behind}</g>"
        + _torso(look)
        + f"<g{head_transform}>{head_svg}</g>"
        + '<rect width="100" height="100" fill="url(#lt)"/>'
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="5 3 90 90">'
        f"<defs>{defs}{''.join(look.defs)}</defs>{body}</svg>"
    )
