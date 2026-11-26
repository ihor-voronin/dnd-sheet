"""Канонічний формат записів довідника.

    from scripts.normalize import canonicalize, load_spec, write_jsonl

Специфікація — `contract/compendium-format.json` (там же блок `corpora`:
яка категорія в якому корпусі — `content/compendium` чи `content/bestiary`).
CLI — `python -m scripts.normalize --check|--write`.
"""

from __future__ import annotations

from .canonical import (
    FORMAT_FILE,
    ROOT,
    FormatSpec,
    canonicalize,
    clean_text,
    corpus_roots,
    corpus_sources,
    dump_record,
    iter_corpus,
    load_spec,
    normalize_source,
    read_jsonl,
    write_jsonl,
)

__all__ = [
    "FORMAT_FILE",
    "ROOT",
    "FormatSpec",
    "canonicalize",
    "clean_text",
    "corpus_roots",
    "corpus_sources",
    "dump_record",
    "iter_corpus",
    "load_spec",
    "normalize_source",
    "read_jsonl",
    "write_jsonl",
]
