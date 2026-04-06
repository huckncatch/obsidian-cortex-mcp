"""Pytest fixtures providing a temporary multi-vault Obsidian environment."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def _make_vault(root: Path, name: str, notes: dict[str, str]) -> Path:
    """Create a minimal vault directory with .obsidian and notes."""
    vault = root / name
    (vault / ".obsidian").mkdir(parents=True)
    for rel_path, content in notes.items():
        note = vault / rel_path
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(content, encoding="utf-8")
    return vault


@pytest.fixture()
def vault_root(tmp_path: Path) -> Path:
    """A temporary vault root with two fixture vaults: Alpha and Beta."""
    _make_vault(root=tmp_path, name="Alpha", notes={
        "notes/hello.md": "---\ntitle: Hello\ntags: [shared, alpha]\n---\nHello world.",
        "notes/swift.md": "---\ntitle: Swift Note\ntags: [swift, alpha]\n---\nSwift content here.",
        "plain.md": "No frontmatter at all.",
    })
    _make_vault(root=tmp_path, name="Beta", notes={
        "notes/world.md": "---\ntitle: World\ntags: [shared, beta]\n---\nWorld content.",
        "readme.md": "---\ntitle: Readme\ntags: [beta]\n---\nBeta readme.",
    })
    # Also create a non-vault directory to verify it's ignored
    (tmp_path / "not-a-vault").mkdir()
    (tmp_path / "not-a-vault" / "somefile.txt").write_text("ignore me")
    return tmp_path


@pytest.fixture()
def vm(vault_root: Path):
    """A VaultManager instance pointing at the fixture vault root."""
    from obsidian_cortex_mcp.vault import VaultManager
    return VaultManager(root=str(vault_root), default_vault="Alpha")
