"""VaultManager: all filesystem operations for obsidian-cortex-mcp."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .frontmatter import parse, serialize


class VaultManager:
    """Filesystem interface for a multi-vault Obsidian root directory."""

    def __init__(self, root: str, default_vault: str = "Home") -> None:
        self.root = Path(root)
        self.default_vault = default_vault
        self._verify_ripgrep()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _verify_ripgrep(self) -> None:
        """Raise RuntimeError if rg is not available on PATH."""
        result = subprocess.run(["rg", "--version"], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                "ripgrep (rg) is required but not found on PATH. "
                "Install with: brew install ripgrep"
            )

    def _vault_path(self, vault: str) -> Path:
        """Return the absolute path for a vault name; raise ValueError if unknown."""
        path = self.root / vault
        if not (path / ".obsidian").is_dir():
            known = ", ".join(self.list_vault_names())
            raise ValueError(
                f"'{vault}' is not a recognized vault. Known vaults: {known}"
            )
        return path

    def _is_note(self, path: Path) -> bool:
        """True if path is a .md file outside of .obsidian directories."""
        return path.is_file() and path.suffix == ".md" and ".obsidian" not in path.parts

    # ── Discovery ────────────────────────────────────────────────────────────

    def list_vault_names(self) -> list[str]:
        """Return sorted names of all vaults detected under root."""
        names = []
        for entry in sorted(self.root.iterdir()):
            if (
                entry.is_dir()
                and not entry.name.startswith(".")
                and entry.name != "tmp"
                and (entry / ".obsidian").is_dir()
            ):
                names.append(entry.name)
        return names

    def list_vaults(self) -> list[dict]:
        """Return dicts with name, path, note_count for each detected vault."""
        result = []
        for name in self.list_vault_names():
            path = self.root / name
            count = sum(1 for p in path.rglob("*.md") if self._is_note(p))
            result.append({"name": name, "path": str(path), "note_count": count})
        return result

    def list_notes(self, vault: str, subfolder: str = "") -> list[str]:
        """Return relative paths (from vault root) of all entries in vault/subfolder."""
        vault_path = self._vault_path(vault)
        base = vault_path / subfolder if subfolder else vault_path

        if not base.exists():
            raise ValueError(
                f"Path '{subfolder}' does not exist in vault '{vault}'"
            )

        entries = []
        for path in sorted(base.rglob("*")):
            if ".obsidian" in path.parts:
                continue
            rel = str(path.relative_to(vault_path))
            entries.append(rel + ("/" if path.is_dir() else ""))

        return entries
