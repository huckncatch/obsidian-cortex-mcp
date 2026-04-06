"""VaultManager: all filesystem operations for obsidian-cortex-mcp."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .frontmatter import parse


class VaultManager:
    """Filesystem interface for a multi-vault Obsidian root directory."""

    def __init__(self, root: str, default_vault: str = "Home") -> None:
        self.root = Path(root)
        self.default_vault = default_vault
        self._verify_ripgrep()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _verify_ripgrep(self) -> None:
        """Raise RuntimeError if rg is not available on PATH."""
        if not shutil.which("rg"):
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

    # ── Reading ──────────────────────────────────────────────────────────────

    def read_note(
        self,
        vault: str,
        note_path: str,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> str:
        """Read note content with line numbers. offset/limit for paging."""
        vault_path = self._vault_path(vault)
        full_path = vault_path / note_path

        if not full_path.exists():
            raise FileNotFoundError(
                f"Note not found at '{note_path}' in vault '{vault}'"
            )

        lines = full_path.read_text(encoding="utf-8").splitlines(keepends=True)
        sliced = lines[offset : offset + limit] if limit is not None else lines[offset:]
        numbered = [f"{offset + i + 1}\t{line}" for i, line in enumerate(sliced)]
        return "".join(numbered)

    def search(
        self,
        query: str,
        vaults: list[str],
        search_type: str = "content",
    ) -> list[dict]:
        """Search vaults. search_type: 'content' (default) or 'tags'."""
        if search_type == "tags":
            return self._search_tags(query, vaults)
        if search_type != "content":
            raise ValueError(f"Unknown search_type '{search_type}'. Valid values: 'content', 'tags'")

        results = []
        for vault_name in vaults:
            vault_path = self._vault_path(vault_name)
            proc = subprocess.run(
                ["rg", "--json", "-g", "*.md", query, str(vault_path)],
                capture_output=True,
                text=True,
            )
            for line in proc.stdout.splitlines():
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") != "match":
                    continue
                data = obj["data"]
                try:
                    rel_path = str(
                        Path(data["path"]["text"]).relative_to(vault_path)
                    )
                    results.append({
                        "vault": vault_name,
                        "path": rel_path,
                        "line_number": data["line_number"],
                        "snippet": data["lines"]["text"].rstrip(),
                    })
                except (KeyError, ValueError):
                    continue
        return results

    def _search_tags(self, query: str, vaults: list[str]) -> list[dict]:
        """Tag search via frontmatter parsing. Case-insensitive substring."""
        query_lower = query.lower()
        results = []
        for vault_name in vaults:
            vault_path = self._vault_path(vault_name)
            for md_file in sorted(vault_path.rglob("*.md")):
                if not self._is_note(md_file):
                    continue
                content = md_file.read_text(encoding="utf-8")
                fm, _ = parse(content)
                raw_tags = fm.get("tags", [])
                if isinstance(raw_tags, str):
                    raw_tags = [raw_tags]
                matching = [
                    str(t) for t in raw_tags if query_lower in str(t).lower()
                ]
                if matching:
                    results.append({
                        "vault": vault_name,
                        "path": str(md_file.relative_to(vault_path)),
                        "matching_tags": matching,
                    })
        return results

    def list_tags(self, vaults: list[str]) -> dict[str, list[str]]:
        """Return {vault_name: sorted_tag_list} for each specified vault."""
        result: dict[str, list[str]] = {}
        for vault_name in vaults:
            vault_path = self._vault_path(vault_name)
            tags: set[str] = set()
            for md_file in vault_path.rglob("*.md"):
                if not self._is_note(md_file):
                    continue
                content = md_file.read_text(encoding="utf-8")
                fm, _ = parse(content)
                raw_tags = fm.get("tags", [])
                if isinstance(raw_tags, str):
                    raw_tags = [raw_tags]
                tags.update(str(t) for t in raw_tags if t)
            result[vault_name] = sorted(tags)
        return result
