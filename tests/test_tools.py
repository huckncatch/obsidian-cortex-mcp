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
