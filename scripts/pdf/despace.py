"""Re-insert spaces the OCR dropped.

Tightly tracked small-caps text comes out of OCR glued together:
"characterstotheancientmagicof giants". The existing compendium is a large
corpus of clean English, so its word list makes a good dictionary for a
word-break pass over suspiciously long tokens.

    python scripts/pdf/despace.py "some text"          # demo
"""

from __future__ import annotations

import json
import math
import re
import sys
from functools import lru_cache
from pathlib import Path

COMPENDIUM = Path(__file__).resolve().parents[2] / "content" / "compendium"
# Статблоки лежать в окремому корпусі, але словник для de-spacing збирається з
# усього тексту, який ми розібрали: інакше після винесення монстрів змінився б
# розбір злиплих слів у GOTG.
BESTIARY = COMPENDIUM.parent / "bestiary"
TOKEN_RE = re.compile(r"[A-Za-z]+")
MIN_GLUED = 13
MAX_WORD = 18
WORD_PENALTY = 6.0
SHORT_OK = {"of", "to", "in", "on", "at", "is", "it", "as", "by", "or", "be", "an"}
FUNCTION_WORDS = {
    "the",
    "of",
    "and",
    "to",
    "in",
    "on",
    "at",
    "for",
    "with",
    "from",
    "that",
    "this",
    "is",
    "are",
    "was",
    "were",
    "a",
    "an",
    "as",
    "by",
    "or",
    "be",
    "it",
    "you",
    "your",
    "their",
    "they",
    "them",
    "its",
    "if",
    "not",
    "but",
    "can",
}

STOP_EXTRA = [
    "dnd",
    "beyond",
    "compendium",
    "bestiary",
    "statblock",
    "sorcerer",
    "warlock",
    "barbarian",
    "paladin",
    "ranger",
    "druid",
    "cleric",
    "bard",
    "monk",
    "rogue",
    "wizard",
    "artificer",
    "subclass",
    "subclasses",
    "cantrip",
    "cantrips",
    "darkvision",
    "tiefling",
    "aasimar",
    "dragonborn",
    "halfling",
    "goliath",
    "eladrin",
    "genasi",
    "tabaxi",
    "kenku",
    "firbolg",
    "githyanki",
    "githzerai",
    "shadar-kai",
    "duergar",
    "yuan-ti",
    "svirfneblin",
    "lizardfolk",
    "tortle",
    "aarakocra",
    "grung",
    "locathah",
    "kender",
    "dungeon",
    "master",
    "dungeons",
    "dragons",
    "player's",
    "handbook",
    "foundling",
    "foundlings",
    "runecraft",
    "runecarver",
    "runecarvers",
    "runes",
    "runic",
    "rune",
    "giantkind",
    "giants",
    "giant's",
    "giantkin",
    "ordning",
    "enclave",
    "enclaves",
    "scion",
    "scions",
    "firbolg",
    "firbolgs",
    "fomorian",
    "fomorians",
    "ettin",
    "ettins",
    "gargantua",
    "colossus",
    "titanothere",
    "ceratops",
    "regisaur",
    "aerosaur",
    "altisaur",
    "maw",
    "yeenoghu",
    "kostchtchie",
    "grolantor",
    "memnor",
    "skoraeus",
    "stronmaus",
    "surtur",
    "thrym",
    "annam",
    "diancastra",
    "hiatea",
    "karontor",
    "baphomet",
    "demogorgon",
    "tarrasque",
    "behir",
    "behirs",
    "wyvern",
    "wyverns",
]

_cache: dict[str, float] | None = None

# Словник збирається з корпусу, а корпус змінюється — тому після першої
# побудови він лягає у файл і далі читається звідти. Без цього повторна збірка
# тієї самої книги дає інший текст: розпізнані раніше слова змінюють те, як
# розбираються «злиплі» токени (напр. «dinosaurs» ламалося на «di nosaurs»,
# коли книга, з якої це слово прийшло, тимчасово зникала зі словника).
VOCAB_CACHE = Path(__file__).resolve().parents[2] / "logs" / "despace-vocab.json"
EXCLUDE_SOURCES: set[str] = set()


def build_vocab() -> dict[str, float]:
    """word -> log frequency: кеш із файлу, інакше з усіх записів корпусу."""
    global _cache
    if _cache is not None:
        return _cache
    if VOCAB_CACHE.exists():
        try:
            _cache = {
                word: float(weight) for word, weight in json.loads(VOCAB_CACHE.read_text(encoding="utf-8")).items()
            }
            return _cache
        except (OSError, ValueError):
            pass  # зіпсований кеш не привід падати — перебудуємо
    counts: dict[str, int] = {}
    corpus_files = [path for root in (COMPENDIUM, BESTIARY) for path in root.glob("*/*.jsonl")]
    for path in corpus_files:
        if path.parent.name in EXCLUDE_SOURCES:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            for word in TOKEN_RE.findall((record.get("text_en") or "").lower()):
                counts[word] = counts.get(word, 0) + 1
    for word in STOP_EXTRA:
        counts[word] = counts.get(word, 0) + 50
    total = sum(counts.values()) or 1
    vocab = {word: math.log(1 + count / total * 1e6) for word, count in counts.items()}
    # OCR glues inflected forms too, while the corpus mostly lists base forms;
    # making the obvious inflections resolvable lets them win over a 2-word split.
    for word, weight in list(vocab.items()):
        for suffix in ("s", "es", "ed", "ing", "ly", "d"):
            vocab.setdefault(word + suffix, weight * 0.55)
        # ...and the other way: a plural-only corpus entry should still resolve
        # its singular, or OCR splits it into two shorter words.
        if len(word) > 5 and word.endswith("s") and not word.endswith("ss"):
            vocab.setdefault(word[:-1], weight * 0.6)
    _cache = vocab
    try:
        VOCAB_CACHE.parent.mkdir(parents=True, exist_ok=True)
        VOCAB_CACHE.write_text(
            json.dumps({word: round(weight, 6) for word, weight in vocab.items()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass  # кеш — оптимізація, не обов'язок
    return _cache


def segment(token: str, vocab: dict[str, float], min_len: int = MIN_GLUED) -> list[str] | None:
    """Best word break of one token, or None if it is already fine."""
    low = token.lower()
    if low in vocab or len(low) < min_len:
        return None

    @lru_cache(maxsize=None)
    def best(start: int) -> tuple[float, tuple[str, ...]] | None:
        if start == len(low):
            return (0.0, ())
        options: tuple[float, tuple[str, ...]] | None = None
        for end in range(start + 2, min(len(low), start + MAX_WORD) + 1):
            piece = low[start:end]
            if len(piece) < 3 and piece not in SHORT_OK:
                continue
            weight = vocab.get(piece)
            if weight is None:
                continue
            rest = best(end)
            if rest is None:
                continue
            # Penalty per word: without it the splitter prefers many common short
            # words ("found li ng") over one unusual long one ("foundling").
            score = (weight - WORD_PENALTY) + rest[0]
            if options is None or score > options[0]:
                options = (score, (piece, *rest[1]))
        return options

    result = best(0)
    best.cache_clear()
    if result is None:
        return None
    words = result[1]
    if len(words) < 2:
        return None
    if sum(len(word) for word in words) != len(low):
        return None
    return list(words)


def fix(text: str) -> str:
    vocab = build_vocab()

    def handle(match: re.Match[str]) -> str:
        token = match.group(0)
        words = segment(token, vocab)
        if not words and len(token) >= 7:
            # Short glue ("thegiant", "toallow") is only split when a function
            # word takes part; otherwise ordinary long words would get mangled.
            guess = segment(token, vocab, min_len=7)
            if guess and FUNCTION_WORDS & set(guess):
                words = guess
        if not words:
            return token
        # Keep the original capitalisation of the first letter only.
        if token[:1].isupper():
            words = [words[0][:1].upper() + words[0][1:], *words[1:]]
        return " ".join(words)

    return TOKEN_RE.sub(handle, text)


if __name__ == "__main__":
    sample = (
        sys.argv[1]
        if len(sys.argv) > 1
        else (
            "characterstotheancientmagicof giants, thegiantfoundling background "
            "represents a life spent aroundtitanic creatures"
        )
    )
    print(fix(sample))
