"""Obsidian-style [[wikilinks]] between notes: parsing, renaming, mentions.

Supported forms: ``[[Title]]``, ``[[Title|shown text]]``, ``[[Title#Heading]]``.
The editor stores Markdown and may escape brackets (``\\[\\[Title\\]\\]``), so
both spellings are recognised and preserved. Links inside code spans and fenced
code blocks are ignored, as in Obsidian.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# [[ ... ]] with optionally escaped brackets; the inner part may not span lines.
_LINK = re.compile(r"(\\?\[\\?\[)([^\[\]\n]+?)(\\?\]\\?\])")
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)
_CODE_SPAN = re.compile(r"`[^`\n]+`")
_UNESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
_ESC_PIPE = "\\|"


@dataclass(frozen=True)
class WikiLink:
    target: str  # note title as written (unescaped)
    heading: str | None
    alias: str | None
    start: int
    end: int

    @property
    def key(self) -> str:
        return title_key(self.target)


def title_key(title: str) -> str:
    """Titles match case-insensitively, ignoring repeated whitespace."""
    return " ".join(title.split()).casefold()


def _unescape(s: str) -> str:
    return _UNESCAPE.sub(r"\1", s)


def _code_ranges(body: str) -> list[tuple[int, int]]:
    ranges = [(m.start(), m.end()) for m in _FENCE.finditer(body)]
    ranges += [(m.start(), m.end()) for m in _CODE_SPAN.finditer(body)]
    return ranges


def _in(ranges: list[tuple[int, int]], pos: int) -> bool:
    return any(a <= pos < b for a, b in ranges)


def _split_inner(inner: str) -> tuple[str, str | None, str | None]:
    raw = inner.replace(_ESC_PIPE, "|")
    target, _, alias = raw.partition("|")
    target, _, heading = target.partition("#")
    return (
        _unescape(target).strip(),
        (_unescape(heading).strip() or None),
        (_unescape(alias).strip() or None),
    )


def parse_links(body: str) -> list[WikiLink]:
    code = _code_ranges(body)
    out: list[WikiLink] = []
    for m in _LINK.finditer(body):
        if _in(code, m.start()):
            continue
        target, heading, alias = _split_inner(m.group(2))
        if target:
            out.append(WikiLink(target, heading, alias, m.start(), m.end()))
    return out


def rename_links(body: str, old_title: str, new_title: str) -> tuple[str, int]:
    """Point every link to ``old_title`` at ``new_title``, keeping headings and aliases."""
    old = title_key(old_title)
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        target, heading, alias = _split_inner(m.group(2))
        if title_key(target) != old:
            return m.group(0)
        count += 1
        escaped = m.group(1).startswith("\\")
        inner = (
            new_title
            + (f"#{heading}" if heading else "")
            + ((_ESC_PIPE if escaped else "|") + alias if alias else "")
        )
        return f"{m.group(1)}{inner}{m.group(3)}"

    code = _code_ranges(body)
    parts: list[str] = []
    last = 0
    for m in _LINK.finditer(body):
        parts.append(body[last : m.start()])
        parts.append(m.group(0) if _in(code, m.start()) else repl(m))
        last = m.end()
    parts.append(body[last:])
    return "".join(parts), count


def _mention_pattern(title: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in title.split()]
    return re.compile(r"(?<![\w\[])" + r"\s+".join(words) + r"(?![\w\]])", re.IGNORECASE)


def unlinked_mentions(body: str, title: str) -> list[tuple[int, int]]:
    """Plain-text mentions of ``title`` that are not already links (nor in code)."""
    if len(title.strip()) < 3:
        return []
    blocked = _code_ranges(body) + [(lk.start, lk.end) for lk in parse_links(body)]
    return [
        (m.start(), m.end())
        for m in _mention_pattern(title).finditer(body)
        if not _in(blocked, m.start())
    ]


def link_first_mention(body: str, title: str) -> str | None:
    """Turn the first unlinked mention of ``title`` into ``[[title]]`` (alias keeps the text)."""
    spans = unlinked_mentions(body, title)
    if not spans:
        return None
    a, b = spans[0]
    shown = body[a:b]
    link = f"[[{title}]]" if shown == title else f"[[{title}|{shown}]]"
    return body[:a] + link + body[b:]


def snippet(body: str, start: int, end: int, width: int = 70) -> str:
    """A short, single-line excerpt around a match, for backlink lists."""
    a, b = max(0, start - width), min(len(body), end + width)
    text = " ".join(body[a:b].split())
    return ("…" if a > 0 else "") + text + ("…" if b < len(body) else "")


def headings(body: str) -> list[tuple[int, str]]:
    """Markdown headings (level, text) outside code blocks, for the outline."""
    code = _code_ranges(body)
    out = []
    for m in re.finditer(r"^(#{1,6})\s+(.+?)\s*#*\s*$", body, re.MULTILINE):
        if not _in(code, m.start()):
            out.append((len(m.group(1)), _unescape(m.group(2))))
    return out


TEMPLATE_VARS = ("date", "time", "weekday", "title")


def render_template(body: str, values: dict[str, str]) -> str:
    """Fill {{date}}, {{time}}, {{weekday}}, {{title}}; other braces stay as written."""
    return re.sub(
        r"\{\{\s*(\w+)\s*\}\}", lambda m: values.get(m.group(1).lower(), m.group(0)), body
    )
