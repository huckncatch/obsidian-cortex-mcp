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


class TestReadNote:
    def test_read_full_note(self, vm: VaultManager):
        content = vm.read_note("Alpha", "plain.md")
        assert "No frontmatter at all." in content

    def test_read_with_line_numbers(self, vm: VaultManager):
        content = vm.read_note("Alpha", "plain.md")
        assert content.startswith("1\t")

    def test_read_with_offset_and_limit(self, vm: VaultManager):
        # notes/hello.md has 5 lines: ---, title:, tags:, ---, body
        content = vm.read_note("Alpha", "notes/hello.md", offset=0, limit=1)
        lines = content.splitlines()
        assert len(lines) == 1
        assert lines[0].startswith("1\t")

    def test_read_missing_note_raises(self, vm: VaultManager):
        with pytest.raises(FileNotFoundError, match="not found"):
            vm.read_note("Alpha", "nonexistent.md")


class TestSearch:
    def test_search_content(self, vm: VaultManager):
        results = vm.search("Swift content", ["Alpha"], search_type="content")
        assert any("swift.md" in r["path"] for r in results)

    def test_search_tags(self, vm: VaultManager):
        results = vm.search("shared", ["Alpha", "Beta"], search_type="tags")
        paths = [r["path"] for r in results]
        assert any("hello.md" in p for p in paths)
        assert any("world.md" in p for p in paths)

    def test_search_tags_case_insensitive(self, vm: VaultManager):
        results = vm.search("SHARED", ["Alpha"], search_type="tags")
        assert len(results) > 0

    def test_search_tags_substring(self, vm: VaultManager):
        # "alph" should match tag "alpha"
        results = vm.search("alph", ["Alpha"], search_type="tags")
        assert len(results) > 0

    def test_search_unknown_vault_raises(self, vm: VaultManager):
        with pytest.raises(ValueError, match="not a recognized vault"):
            vm.search("anything", ["NoSuchVault"])

    def test_search_invalid_type_raises(self, vm: VaultManager):
        with pytest.raises(ValueError, match="Unknown search_type"):
            vm.search("anything", ["Alpha"], search_type="invalid")


class TestListTags:
    def test_single_vault_tags(self, vm: VaultManager):
        tag_map = vm.list_tags(["Alpha"])
        assert "shared" in tag_map["Alpha"]
        assert "alpha" in tag_map["Alpha"]

    def test_multi_vault_tags(self, vm: VaultManager):
        tag_map = vm.list_tags(["Alpha", "Beta"])
        assert "shared" in tag_map["Alpha"]
        assert "shared" in tag_map["Beta"]

    def test_tags_sorted(self, vm: VaultManager):
        tag_map = vm.list_tags(["Alpha"])
        tags = tag_map["Alpha"]
        assert tags == sorted(tags)

    def test_note_without_frontmatter_not_included(self, vm: VaultManager):
        # plain.md has no frontmatter, so shouldn't cause errors
        tag_map = vm.list_tags(["Alpha"])
        assert isinstance(tag_map["Alpha"], list)
