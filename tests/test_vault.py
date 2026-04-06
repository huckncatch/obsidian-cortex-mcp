"""Integration tests for VaultManager using fixture vault root."""
from __future__ import annotations

from pathlib import Path

import pytest
from obsidian_cortex_mcp.vault import VaultManager


class TestVaultDiscovery:
    def test_list_vault_names(self, vm: VaultManager):
        names = vm.list_vault_names()
        assert "Alpha" in names
        assert "Beta" in names
        assert "not-a-vault" not in names

    def test_list_vaults_returns_note_count(self, vm: VaultManager):
        vaults = vm.list_vaults()
        alpha = next(v for v in vaults if v["name"] == "Alpha")
        assert alpha["note_count"] == 3

    def test_list_vaults_excludes_obsidian_dir(self, vm: VaultManager):
        # .obsidian dir contains no .md notes — count must not include it
        vaults = vm.list_vaults()
        alpha = next(v for v in vaults if v["name"] == "Alpha")
        # Alpha has exactly 3 .md files (hello.md, swift.md, plain.md); .obsidian has none
        assert alpha["note_count"] == 3

    def test_unknown_vault_raises(self, vm: VaultManager):
        with pytest.raises(ValueError, match="not a recognized vault"):
            vm._vault_path("Nonexistent")


class TestListNotes:
    def test_list_all_notes(self, vm: VaultManager):
        entries = vm.list_notes("Alpha")
        # Should include notes/hello.md, notes/swift.md, plain.md
        assert any("hello.md" in e for e in entries)
        assert any("plain.md" in e for e in entries)

    def test_list_notes_subfolder(self, vm: VaultManager):
        entries = vm.list_notes("Alpha", "notes")
        assert any("hello.md" in e for e in entries)
        assert not any("plain.md" in e for e in entries)

    def test_list_notes_invalid_path_raises(self, vm: VaultManager):
        with pytest.raises(ValueError, match="does not exist"):
            vm.list_notes("Alpha", "nonexistent/folder")

    def test_obsidian_dir_excluded(self, vm: VaultManager):
        entries = vm.list_notes("Alpha")
        assert not any(".obsidian" in e for e in entries)
