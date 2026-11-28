import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from ppos.application.ports import NoteQuery
from ppos.application.vault import file_name, parse_markdown
from ppos.bootstrap import Container
from ppos.domain.notes import NoteKind
from ppos.shared.errors import ValidationError


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()


def test_export_is_an_obsidian_vault(container: Container) -> None:
    n = container.notes
    n.create(
        title="Hybrid retrieval: design",
        body="See \\[\\[Eval harness\\]\\] and [[Other|x]].",
        tags=["adr"],
    )
    n.create(title="Hybrid retrieval: design", body="second with same title")
    n.create(title="Idea one", body="", kind=NoteKind.IDEA)
    z = zipfile.ZipFile(io.BytesIO(container.vault.export_zip()))
    names = set(z.namelist())
    assert {
        "Notes/Hybrid retrieval design.md",
        "Notes/Hybrid retrieval design (2).md",
        "Ideas/Idea one.md",
    } <= names
    text = z.read("Notes/Hybrid retrieval design.md").decode()
    meta, body = parse_markdown(text)
    assert (
        meta["title"] == "Hybrid retrieval: design"
        and meta["kind"] == "general"
        and meta["tags"] == ["adr"]
    )
    assert body.strip() == "See [[Eval harness]] and [[Other|x]]."  # unescaped for Obsidian


def test_import_vault_roundtrip_and_dedupe(container: Container) -> None:
    v = container.vault
    data = _zip(
        {
            "My vault/Projects/Retrieval.md": (
                "---\ntags: [search, q4]\n---\n# Retrieval\nLinks to [[Eval harness]]."
            ),
            "My vault/Eval harness.md": "Runs nightly.",
            "My vault/.obsidian/workspace.md": "ignored",
            "My vault/image.png": "ignored",
        }
    )
    r = v.import_files("vault.zip", data)
    assert sorted(r.created) == ["Eval harness", "Retrieval"] and not r.errors
    by_title = {x.title: x for x in container.notes.find(NoteQuery())}
    assert by_title["Retrieval"].kind == NoteKind.PROJECT
    assert by_title["Retrieval"].tags == ["search", "q4"]
    backlinks = container.notes.connections(by_title["Eval harness"].id)["backlinks"]
    assert [b["title"] for b in backlinks] == ["Retrieval"]  # [[links]] resolve by title
    again = v.import_files("vault.zip", data)
    assert again.created == [] and sorted(again.skipped) == ["Eval harness", "Retrieval"]
    # exporting and importing into the same workspace creates nothing new
    assert v.import_files("export.zip", v.export_zip()).created == []
    with pytest.raises(ValidationError):
        v.import_files("x.pdf", b"%PDF-1.4")


def test_file_names_are_portable() -> None:
    assert file_name('a/b: c*?"<>|#^[x]') == "a b c x"
    assert file_name("   ") == "Untitled"


def test_vault_api(client: TestClient) -> None:
    r = client.post(
        "/api/notes/import?filename=Idea.md", content=b"---\nkind: idea\n---\nA thought"
    )
    assert r.status_code == 200 and r.json()["created"] == ["Idea"]
    z = client.get("/api/notes/export.zip")
    assert z.headers["content-type"] == "application/zip"
    assert "Ideas/Idea.md" in zipfile.ZipFile(io.BytesIO(z.content)).namelist()
