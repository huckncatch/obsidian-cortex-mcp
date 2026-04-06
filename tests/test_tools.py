"""End-to-end tests for MCP tool handlers via fixture vaults."""
from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError
from obsidian_cortex_mcp.vault import VaultManager


class TestDiscoveryTools:
    def test_list_vaults_output(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.discovery import _list_vaults
        result = _list_vaults(vm)
        assert "Alpha" in result
        assert "Beta" in result
        assert "notes)" in result or "note" in result

    def test_list_notes_output(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.discovery import _list_notes
        result = _list_notes(vm, vault="Alpha")
        assert "hello.md" in result
        assert "plain.md" in result

    def test_list_notes_subfolder(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.discovery import _list_notes
        result = _list_notes(vm, vault="Alpha", path="notes")
        assert "hello.md" in result
        assert "plain.md" not in result

    def test_list_notes_bad_vault_raises_tool_error(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.discovery import _list_notes
        with pytest.raises(ToolError):
            _list_notes(vm, vault="NoSuchVault")


class TestReadingTools:
    def test_read_note_output(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.reading import _read_note
        result = _read_note(vm, path="plain.md", vault="Alpha")
        assert "1\t" in result
        assert "No frontmatter" in result

    def test_read_note_with_limit(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.reading import _read_note
        result = _read_note(vm, path="notes/hello.md", vault="Alpha", offset=0, limit=1)
        assert result.count("\n") <= 1

    def test_read_note_missing_raises_tool_error(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.reading import _read_note
        with pytest.raises(ToolError):
            _read_note(vm, path="ghost.md", vault="Alpha")

    def test_search_content_output(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.reading import _search
        result = _search(vm, query="Swift content", vaults=["Alpha"])
        assert "swift.md" in result
        assert "[Alpha]" in result

    def test_search_tags_output(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.reading import _search
        result = _search(vm, query="shared", vaults=["Alpha", "Beta"], search_type="tags")
        assert "Alpha" in result
        assert "Beta" in result

    def test_search_no_results_message(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.reading import _search
        result = _search(vm, query="XYZZY_NOT_FOUND", vaults=["Alpha"])
        assert "No matches" in result

    def test_list_tags_single_vault(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.reading import _list_tags
        result = _list_tags(vm, vaults=["Alpha"])
        assert "#alpha" in result
        assert "#shared" in result

    def test_list_tags_multi_vault_shows_shared(self, vm: VaultManager):
        from obsidian_cortex_mcp.tools.reading import _list_tags
        result = _list_tags(vm, vaults=["Alpha", "Beta"])
        # Shared tags appear in each vault's line AND in Shared: section
        assert "Alpha:" in result
        assert "Beta:" in result
        assert "Shared:" in result
        # #shared is a tag in both vaults — must appear in all three places
        lines = result.splitlines()
        alpha_line = next(l for l in lines if l.startswith("Alpha:"))
        beta_line = next(l for l in lines if l.startswith("Beta:"))
        shared_line = next(l for l in lines if l.startswith("Shared:"))
        assert "#shared" in alpha_line
        assert "#shared" in beta_line
        assert "#shared" in shared_line
