"""Tool handlers for vault and note discovery."""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..vault import VaultManager


def _list_vaults(vm: VaultManager) -> str:
    vaults = vm.list_vaults()
    if not vaults:
        return "No vaults found."
    lines = [
        f"- {v['name']} ({v['note_count']} notes): {v['path']}"
        for v in vaults
    ]
    return "\n".join(lines)


def _list_notes(vm: VaultManager, vault: str | None = None, path: str = "") -> str:
    vault = vault or vm.default_vault
    try:
        entries = vm.list_notes(vault, path)
    except (ValueError, FileNotFoundError) as e:
        raise ToolError(str(e))
    if not entries:
        loc = f"'{vault}/{path}'" if path else f"'{vault}'"
        return f"No files found in {loc}."
    return "\n".join(entries)


def register(mcp: FastMCP, vm: VaultManager) -> None:
    """Register discovery tools with the FastMCP server."""

    @mcp.tool
    def list_vaults() -> str:
        """List all Obsidian vaults detected under the vault root."""
        return _list_vaults(vm)

    @mcp.tool
    def list_notes(vault: str | None = None, path: str = "") -> str:
        """List notes and folders in a vault directory.

        Args:
            vault: Vault name. Defaults to DEFAULT_VAULT.
            path: Optional subfolder path within the vault.
        """
        return _list_notes(vm, vault=vault, path=path)
