"""Tool handlers for creating and modifying notes."""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..vault import VaultManager


def _create_note(
    vm: VaultManager,
    path: str,
    body: str = "",
    vault: str | None = None,
    frontmatter: dict | None = None,
) -> str:
    vault = vault or vm.default_vault
    try:
        result = vm.create_note(vault, path, body=body, frontmatter_data=frontmatter)
        return f"Created: {result}"
    except (ValueError, FileExistsError, OSError) as e:
        raise ToolError(str(e))


def _write_note(vm: VaultManager, path: str, body: str, vault: str | None = None) -> str:
    vault = vault or vm.default_vault
    try:
        result = vm.write_note(vault, path, body)
        return f"Updated: {result}"
    except (ValueError, FileNotFoundError, OSError) as e:
        raise ToolError(str(e))


def _edit_note(
    vm: VaultManager,
    path: str,
    old_string: str,
    new_string: str,
    vault: str | None = None,
) -> str:
    vault = vault or vm.default_vault
    try:
        result = vm.edit_note(vault, path, old_string, new_string)
        return f"Edited: {result}"
    except (ValueError, FileNotFoundError, OSError) as e:
        raise ToolError(str(e))


def _update_frontmatter(
    vm: VaultManager,
    path: str,
    updates: dict,
    vault: str | None = None,
) -> str:
    vault = vault or vm.default_vault
    try:
        result = vm.update_frontmatter(vault, path, updates)
        return f"Updated frontmatter: {result}"
    except (ValueError, FileNotFoundError, OSError) as e:
        raise ToolError(str(e))


def _move_note(
    vm: VaultManager,
    source_vault: str,
    dest_vault: str,
    source_path: str,
    dest_path: str | None = None,
) -> str:
    try:
        result = vm.move_note(source_vault, dest_vault, source_path, dest_path)
        return f"Moved to: {result}"
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, OSError) as e:
        raise ToolError(str(e))


def register(mcp: FastMCP, vm: VaultManager) -> None:
    """Register writing tools with the FastMCP server."""

    @mcp.tool
    def create_note(
        path: str,
        body: str = "",
        vault: str | None = None,
        frontmatter: dict | None = None,
    ) -> str:
        """Create a new note in the vault.

        Args:
            path: Relative path for the new note (e.g. 'Development/mynote.md').
            body: Markdown body content.
            vault: Vault name. Defaults to DEFAULT_VAULT.
            frontmatter: Optional dict of frontmatter key/value pairs.
        """
        return _create_note(vm, path=path, body=body, vault=vault, frontmatter=frontmatter)

    @mcp.tool
    def write_note(path: str, body: str, vault: str | None = None) -> str:
        """Replace the body of an existing note. Frontmatter is preserved.

        Args:
            path: Relative path to the note.
            body: New markdown body content.
            vault: Vault name. Defaults to DEFAULT_VAULT.
        """
        return _write_note(vm, path=path, body=body, vault=vault)

    @mcp.tool
    def edit_note(
        path: str,
        old_string: str,
        new_string: str,
        vault: str | None = None,
    ) -> str:
        """Replace an exact string within a note. old_string must match exactly once.

        Args:
            path: Relative path to the note.
            old_string: Exact text to find — must appear exactly once.
            new_string: Replacement text.
            vault: Vault name. Defaults to DEFAULT_VAULT.
        """
        return _edit_note(vm, path=path, old_string=old_string, new_string=new_string, vault=vault)

    @mcp.tool
    def update_frontmatter(path: str, updates: dict, vault: str | None = None) -> str:
        """Add, update, or remove frontmatter fields. Body is never touched.

        Args:
            path: Relative path to the note.
            updates: Key/value pairs to merge. Set value to null to remove a key.
            vault: Vault name. Defaults to DEFAULT_VAULT.
        """
        return _update_frontmatter(vm, path=path, updates=updates, vault=vault)

    @mcp.tool
    def move_note(
        source_vault: str,
        dest_vault: str,
        source_path: str,
        dest_path: str | None = None,
    ) -> str:
        """Move a note between vaults or within the same vault.

        Intra-vault moves (source_vault == dest_vault) use the Obsidian CLI and
        preserve wikilink integrity — requires Obsidian to be running.
        Cross-vault moves use the filesystem directly.

        Args:
            source_vault: Vault to move from.
            dest_vault: Vault to move to (same as source_vault for intra-vault move).
            source_path: Relative path in source vault.
            dest_path: Relative path in destination vault. Defaults to source_path.
        """
        return _move_note(vm, source_vault=source_vault, dest_vault=dest_vault,
                          source_path=source_path, dest_path=dest_path)
