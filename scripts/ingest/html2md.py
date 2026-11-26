"""Перетворення HTML сторінки D&D Beyond у markdown.

Працює на stdlib (html.parser): будує легке дерево, знаходить контейнер статті,
віддає markdown із заголовками, списками й таблицями. Без зовнішніх залежностей.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

SKIP_TAGS = {
    "script", "style", "noscript", "svg", "nav", "header", "footer",
    "form", "button", "select", "iframe", "template",
}

# Класи-контейнери, у яких D&D Beyond тримає тіло статті (від найточнішого).
ARTICLE_HINTS = ("article-content", "p-article", "content-body", "source-content", "article")


class Node:
    __slots__ = ("tag", "attrs", "children", "text", "parent")

    def __init__(self, tag: str, attrs: dict[str, str] | None = None, text: str = "") -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list["Node"] = []
        self.text = text
        self.parent: "Node | None" = None

    @property
    def classes(self) -> str:
        return self.attrs.get("class", "")

    def text_content(self) -> str:
        if self.text:
            return self.text
        return "".join(child.text_content() for child in self.children)

    def iter_nodes(self):
        yield self
        for child in self.children:
            if child.text:
                continue
            yield from child.iter_nodes()


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack: list[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        node = Node(tag, {k: (v or "") for k, v in attrs})
        node.parent = self.stack[-1]
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        node = Node(tag, {k: (v or "") for k, v in attrs})
        node.parent = self.stack[-1]
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            node = Node("#text", text=data)
            node.parent = self.stack[-1]
            self.stack[-1].children.append(node)


def build_tree(html: str) -> Node:
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


def find_article(root: Node) -> Node:
    """Найбільший вузол, схожий на тіло статті; інакше <main>, інакше <body>."""
    best: Node | None = None
    best_len = 0
    for node in root.iter_nodes():
        if node.tag in ("div", "article", "section", "main"):
            classes = node.classes.lower()
            matched = any(hint in classes for hint in ARTICLE_HINTS)
            if not matched and node.tag != "article":
                continue
            length = len(node.text_content())
            if length > best_len:
                best, best_len = node, length
    if best is not None and best_len > 200:
        return best
    for node in root.iter_nodes():
        if node.tag == "main":
            return node
    for node in root.iter_nodes():
        if node.tag == "body":
            return node
    return root


def page_title(root: Node) -> str:
    for node in root.iter_nodes():
        if node.tag == "h1":
            title = _clean(node.text_content())
            if title:
                return title
    for node in root.iter_nodes():
        if node.tag == "title":
            title = _clean(node.text_content())
            if title:
                return title.split(" - ")[0].strip()
    return ""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _render_table(node: Node) -> str:
    rows: list[list[str]] = []
    for row in node.iter_nodes():
        if row.tag != "tr":
            continue
        cells = []
        for cell in row.children:
            if cell.tag in ("td", "th"):
                cells.append(_clean(cell.text_content()).replace("|", "\\|"))
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _is_inside_table(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.tag == "table":
            return True
        parent = parent.parent
    return False


def _render_ability_scores(node: Node) -> str:
    """Блок характеристик монстра -> «STR 10 (+0) · DEX 14 (+2) · ...».

    D&D Beyond тримає їх не в <table>, а в купі <div>, тому без цього окремого
    випадку шість чисел — найважливіше в статблоці — просто зникали.
    """
    parts: list[str] = []
    for stat in node.iter_nodes():
        if "scores-stat" not in stat.classes:
            continue
        heading = score = modifier = ""
        for child in stat.iter_nodes():
            if child.text:
                continue
            classes = child.classes
            if "scores-heading" in classes:
                heading = _clean(child.text_content())
            elif "scores-score" in classes:
                score = _clean(child.text_content())
            elif "scores-modifier" in classes:
                modifier = _clean(child.text_content())
        if heading and score:
            parts.append(f"{heading} {score} {modifier}".strip())
    return " · ".join(parts)


def to_markdown(root: Node, container: Node) -> str:
    blocks: list[str] = []

    def walk(node: Node) -> None:
        if node.text:
            return
        if node.tag in SKIP_TAGS:
            return
        if node.tag == "table":
            table = _render_table(node)
            if table:
                blocks.append(table)
            return

        if "stat-block-ability-scores" in node.classes and "scores-stat" not in node.classes:
            scores = _render_ability_scores(node)
            if scores:
                blocks.append(scores)
            return

        if node.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(node.tag[1])
            text = _clean(node.text_content())
            if text:
                blocks.append("#" * level + " " + text)
            return

        if node.tag in ("p", "blockquote", "dt", "dd"):
            text = _clean(node.text_content())
            if text:
                blocks.append("> " + text if node.tag == "blockquote" else text)
            return

        if node.tag == "li":
            text = _clean(node.text_content())
            if text:
                blocks.append("- " + text)
            return

        if node.tag == "br":
            blocks.append("")
            return

        for child in node.children:
            walk(child)

    for child in container.children:
        walk(child)

    text = "\n\n".join(block for block in blocks if block is not None)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def parse_page(html: str) -> tuple[str, str]:
    """Повертає (title, markdown-тіло)."""
    root = build_tree(html)
    container = find_article(root)
    return page_title(root), to_markdown(root, container)
