"""Versioned prompt templates loaded from the repository's prompts/ directory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ppos.shared.errors import PposError


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    version: int
    meta: dict[str, str]
    body: str

    @property
    def ref(self) -> str:
        return f"{self.id}@v{self.version}"

    def render(self, **values: str) -> str:
        """Substitute {{name}} for provided values only (other braces untouched)."""
        return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), self.body)


def load_template(prompts_dir: Path, rel_path: str) -> PromptTemplate:
    path = prompts_dir / rel_path
    if not path.is_file():
        raise PposError(f"prompt template not found: {rel_path}")
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        raise PposError(f"prompt template {rel_path} lacks front matter")
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    if "id" not in meta or "version" not in meta:
        raise PposError(f"prompt template {rel_path} needs id and version")
    return PromptTemplate(meta["id"], int(meta["version"]), meta, m.group(2).strip())
