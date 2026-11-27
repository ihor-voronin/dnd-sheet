"""Polish OCR text before it goes into the compendium.

Applied after the page assembly, because these repairs need the whole line:
  * drop the `### ` artefacts and illustration credits that slipped into bodies;
  * rejoin words OCR split on a line break ("max imum" -> "maximum");
  * correct one-letter OCR damage ("attuncs" -> "attunes") against the corpus
    vocabulary, but only when a single candidate is one edit away;
  * tidy punctuation spacing.
"""

from __future__ import annotations

import re
import sys
from difflib import SequenceMatcher, get_close_matches

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import despace  # noqa: E402

CREDITS = {
    "kaicarpenter",
    "olivierbernard",
    "isabelcisney",
    "isabelgiehe",
    "isabelcibney",
    "daarken",
    "johngrello",
    "aprilprime",
    "shawnwood",
    "aozeopannam",
    "furyofthefrostgiant",
    "orcrunecarver",
}
HEADING_JUNK = re.compile(r"#+\s*")
SPACED_PUNCT = re.compile(r"\s+([,.;:!?])(?!\d)")
DOUBLE_PUNCT = re.compile(r"([,.;:!?])\1+")


def drop_credits(text: str) -> str:
    def handle(match: re.Match[str]) -> str:
        return "" if match.group(0).lower() in CREDITS else match.group(0)

    return re.sub(r"[A-Za-z]{5,}", handle, text)


def join_split_words(text: str, vocab: dict[str, float]) -> str:
    """`max imum` -> `maximum` when the joined form is a known word."""
    tokens = text.split(" ")
    out: list[str] = []
    i = 0
    while i < len(tokens):
        current = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        core = re.sub(r"[^A-Za-z]", "", nxt)
        if re.fullmatch(r"[A-Za-z]{2,}", current) and len(core) >= 2 and core[:1].islower():
            joined = (current + core).lower()
            if (
                joined in vocab
                and current.lower() in vocab
                and (core.lower() not in vocab or len(current) <= 3 or len(core) <= 3)
            ):
                out.append(current + nxt)
                i += 2
                continue
        out.append(current)
        i += 1
    return " ".join(out)


def correct_near_misses(text: str, vocab: dict[str, float]) -> str:
    """Fix one-edit OCR damage when exactly one corpus word is that close."""

    def handle(match: re.Match[str]) -> str:
        token = match.group(0)
        low = token.lower()
        if low in vocab or len(low) < 6 or low.isupper():
            return token
        candidates = get_close_matches(low, vocab.keys(), n=3, cutoff=0.78)
        if not candidates:
            return token
        # Accept only an unambiguous winner: with several equally close corpus
        # words ("attuness", "attunesd") a correction would be a guess.
        scored = sorted(
            ((SequenceMatcher(None, low, cand).ratio(), cand) for cand in candidates),
            reverse=True,
        )
        if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.03:
            return token
        best = scored[0][1]
        if best == low or abs(len(best) - len(low)) > 1:
            return token
        differing = sum(1 for a, b in zip(best, low) if a != b) + abs(len(best) - len(low))
        if differing > (2 if len(low) >= 7 else 1):
            return token
        return best

    return re.sub(r"[A-Za-z]{6,}", handle, text)


def polish(text: str) -> str:
    vocab = despace.build_vocab()
    text = HEADING_JUNK.sub(" ", text)
    text = drop_credits(text)
    text = join_split_words(text, vocab)
    text = re.sub(r"\s+", " ", text)
    text = SPACED_PUNCT.sub(r"\1", text)
    text = DOUBLE_PUNCT.sub(r"\1", text)
    text = correct_near_misses(text, vocab)
    return text.strip()


if __name__ == "__main__":
    print(polish(sys.argv[1]))
