"""Tool handlers for reading and searching notes."""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..vault import VaultManager


def _read_note(
    vm: VaultManager,
    path: str,
    vault: str | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> str:
    vault = vault or vm.default_vault
    try:
        return vm.read_note(vault, path, offset=offset, limit=limit)
    except (ValueError, FileNotFoundError) as e:
        raise ToolError(str(e))


def _search(
    vm: VaultManager,
    query: str,
    vaults: list[str] | None = None,
    search_type: str = "content",
) -> str:
    vaults = vaults or [vm.default_vault]
    try:
        results = vm.search(query, vaults, search_type)
    except ValueError as e:
        raise ToolError(str(e))

    if not results:
        return f"No matches for '{query}' in {', '.join(vaults)}."

    lines = []
    for r in results:
        if search_type == "tags":
            lines.append(
                f"[{r['vault']}] {r['path']} — tags: {', '.join(r['matching_tags'])}"
            )
        else:
            lines.append(f"[{r['vault']}] {r['path']}:{r['line_number']}: {r['snippet']}")
    return "\n".join(lines)


def _list_tags(vm: VaultManager, vaults: list[str] | None = None) -> str:
    vaults = vaults or [vm.default_vault]
    try:
        tag_map = vm.list_tags(vaults)
    except ValueError as e:
        raise ToolError(str(e))

    if len(vaults) == 1:
        vault_name = vaults[0]
        tags = tag_map.get(vault_name, [])
        if not tags:
            return f"No tags found in '{vault_name}'."
        return f"{vault_name}: " + ", ".join(f"#{t}" for t in tags)

    # Multi-vault: show all tags per vault; Shared section calls out overlap
    all_sets = {v: set(tag_map.get(v, [])) for v in vaults}
    shared = set.intersection(*all_sets.values()) if all_sets else set()

    lines = []
    for vault_name in vaults:
        # Show ALL tags for this vault (including shared ones)
        all_vault_tags = sorted(all_sets[vault_name])
        tag_str = ", ".join(f"#{t}" for t in all_vault_tags) if all_vault_tags else "(none)"
        lines.append(f"{vault_name}: {tag_str}")

    lines.append("─" * 38)
    shared_str = ", ".join(f"#{t}" for t in sorted(shared)) if shared else "(none)"
    lines.append(f"Shared: {shared_str}")
    return "\n".join(lines)


def register(mcp: FastMCP, vm: VaultManager) -> None:
    """Register reading tools with the FastMCP server."""

    @mcp.tool
    def read_note(
        path: str,
        vault: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> str:
        """Read note content with line numbers. Supports paging for large notes.

        Args:
            path: Relative path to the note within the vault.
            vault: Vault name. Defaults to DEFAULT_VAULT.
            offset: Start line, 0-indexed. Default: 0.
            limit: Number of lines to return. Default: all.
        """
        return _read_note(vm, path=path, vault=vault, offset=offset, limit=limit)

    @mcp.tool
    def search(
        query: str,
        vaults: list[str] | None = None,
        search_type: str = "content",
    ) -> str:
        """Search notes by content or tags.

        Args:
            query: Search string.
            vaults: Vault names to search. Defaults to [DEFAULT_VAULT].
            search_type: 'content' (default) or 'tags'.
                         'tags' uses frontmatter parsing, not ripgrep.
        """
        return _search(vm, query=query, vaults=vaults, search_type=search_type)

    @mcp.tool
    def list_tags(vaults: list[str] | None = None) -> str:
        """Aggregate frontmatter tags across one or more vaults.

        Args:
            vaults: Vault names. Defaults to [DEFAULT_VAULT].
                    Multi-vault output groups tags per vault with a Shared section.
        """
        return _list_tags(vm, vaults=vaults)
