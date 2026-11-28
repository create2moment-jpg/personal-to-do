"""Content-addressed store for original documents inside LOCAL_DATA_DIR."""

from __future__ import annotations

import os
from pathlib import Path


class DocumentStore:
    def __init__(self, data_dir: Path, folder: str = "documents") -> None:
        self.root = data_dir
        self.folder = folder
        self.base = data_dir / folder

    def save(self, sha256: str, ext: str, data: bytes) -> str:
        rel = Path(self.folder) / sha256[:2] / f"{sha256}{ext}"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.exists():
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(data)
            if os.name == "posix":
                tmp.chmod(0o600)
            tmp.replace(path)  # atomic
        return rel.as_posix()

    def read(self, rel: str) -> bytes:
        return self.path(rel).read_bytes()

    def path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.base.resolve()):
            raise PermissionError("path escapes the document store")
        return p

    def delete(self, rel: str) -> None:
        self.path(rel).unlink(missing_ok=True)
