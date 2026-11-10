"""Tool handlers for linting notes and committing them to the vault git repo."""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..vault import VaultManager


def _lint_note(vm: VaultManager, path: str, vault: str | None = None) -> str:
    vault = vault or vm.default_vault
    try:
        violations = vm.lint_note(vault, path)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        raise ToolError(str(e))
    return "\n".join(violations) if violations else "clean"


def _git_status(vm: VaultManager, path: str, vault: str | None = None) -> str:
    vault = vault or vm.default_vault
    try:
        lines = vm.git_status(vault, path)
    except (ValueError, RuntimeError) as e:
        raise ToolError(str(e))
    return "\n".join(lines) if lines else "clean"


def _git_stage(vm: VaultManager, path: str, vault: str | None = None) -> str:
    vault = vault or vm.default_vault
    try:
        return f"Staged: {vm.git_stage(vault, path)}"
    except (ValueError, RuntimeError) as e:
        raise ToolError(str(e))


def _git_commit(
    vm: VaultManager,
    message: str,
    paths: list[str],
    vault: str | None = None,
) -> str:
    vault = vault or vm.default_vault
    try:
        return f"Committed: {vm.git_commit(message, [(vault, p) for p in paths])}"
    except (ValueError, RuntimeError) as e:
        raise ToolError(str(e))


def register(mcp: FastMCP, vm: VaultManager) -> None:
    """Register lint and git tools with the FastMCP server."""

    @mcp.tool
    def lint_note(path: str, vault: str | None = None) -> str:
        """Lint one note with markdownlint-cli2 and the vaults-root config. Never fixes.

        Args:
            path: Relative path to the note.
            vault: Vault name. Defaults to DEFAULT_VAULT.

        Returns 'clean', or one 'line[:col] rule message' line per violation.
        """
        return _lint_note(vm, path=path, vault=vault)

    @mcp.tool
    def git_status(path: str, vault: str | None = None) -> str:
        """Show the git status of one path. Run it before editing an existing note.

        Args:
            path: Relative path to the note or folder.
            vault: Vault name. Defaults to DEFAULT_VAULT.

        Returns 'clean', or the `git status --porcelain --ignored` lines ('!!' = ignored).
        """
        return _git_status(vm, path=path, vault=vault)

    @mcp.tool
    def git_stage(path: str, vault: str | None = None) -> str:
        """Stage one path with git add (a change, a new note, or a deletion).

        Stage each edit as soon as it is made. While anything is staged, the hourly
        vault-sync run skips, so the edit stays out of auto-commits.

        Args:
            path: Relative path to the note.
            vault: Vault name. Defaults to DEFAULT_VAULT.
        """
        return _git_stage(vm, path=path, vault=vault)

    @mcp.tool
    def git_commit(message: str, paths: list[str], vault: str | None = None) -> str:
        """Commit the named notes with `git commit -- <paths>`. Never pushes.

        Each path must have a staged change; other staged paths (from other sessions)
        stay staged. Any unstaged change in a named file is committed too. The
        pre-commit hooks (gitleaks) run; if one blocks the commit, its output is
        returned as an error and the index is left as it was.

        Args:
            message: Commit message, used exactly as given. Say which note changed and why.
            paths: Relative paths of the notes to commit, all in one vault.
            vault: Vault name. Defaults to DEFAULT_VAULT.
        """
        return _git_commit(vm, message=message, paths=paths, vault=vault)
