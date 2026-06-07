"""VaultManager: all filesystem operations for obsidian-cortex-mcp."""
from __future__ import annotations

import json
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

    def _run_cli(self, vault_name: str, *args: str) -> str:
        """Run an Obsidian CLI command targeting a specific vault. Requires Obsidian to be running."""
        cmd = ["obsidian", f"vault={vault_name}", *args]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            raise RuntimeError(
                "Obsidian CLI not found on PATH. "
                "Ensure Obsidian.app is installed and 'obsidian' is in PATH."
            )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"Obsidian CLI error (is Obsidian running?): {detail}"
            )
        return result.stdout.strip()

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

    # ── Writing ─────────────────────────────────────────────────────────────

    def create_note(
        self,
        vault: str,
        note_path: str,
        body: str = "",
        frontmatter_data: Optional[dict] = None,
    ) -> str:
        """Create a new note. Errors if path already exists."""
        vault_path = self._vault_path(vault)
        full_path = vault_path / note_path

        if full_path.exists():
            raise FileExistsError(
                f"Note already exists at '{note_path}' — "
                "use write_note or edit_note to modify it"
            )

        full_path.parent.mkdir(parents=True, exist_ok=True)
        content = serialize(frontmatter_data or {}, body)
        full_path.write_text(content, encoding="utf-8")
        return str(full_path)

    def write_note(self, vault: str, note_path: str, body: str) -> str:
        """Replace body of existing note; frontmatter is preserved."""
        vault_path = self._vault_path(vault)
        full_path = vault_path / note_path

        if not full_path.exists():
            raise FileNotFoundError(
                f"Note not found at '{note_path}' in vault '{vault}' — "
                "use create_note to create it"
            )

        fm, _ = parse(full_path.read_text(encoding="utf-8"))
        full_path.write_text(serialize(fm, body), encoding="utf-8")
        return str(full_path)

    def edit_note(
        self,
        vault: str,
        note_path: str,
        old_string: str,
        new_string: str,
    ) -> str:
        """Exact string replacement. old_string must match exactly once."""
        vault_path = self._vault_path(vault)
        full_path = vault_path / note_path

        if not full_path.exists():
            raise FileNotFoundError(
                f"Note not found at '{note_path}' in vault '{vault}'"
            )

        content = full_path.read_text(encoding="utf-8")
        count = content.count(old_string)

        if count == 0:
            raise ValueError("old_string not found in note")
        if count > 1:
            raise ValueError(
                f"old_string matches {count} locations — make it more specific"
            )

        full_path.write_text(content.replace(old_string, new_string, 1), encoding="utf-8")
        return str(full_path)

    def update_frontmatter(
        self,
        vault: str,
        note_path: str,
        updates: dict,
    ) -> str:
        """Merge updates into frontmatter. Set value to None to remove a key."""
        vault_path = self._vault_path(vault)
        full_path = vault_path / note_path

        if not full_path.exists():
            raise FileNotFoundError(
                f"Note not found at '{note_path}' in vault '{vault}'"
            )

        fm, body = parse(full_path.read_text(encoding="utf-8"))
        for key, value in updates.items():
            if value is None:
                fm.pop(key, None)
            else:
                fm[key] = value

        full_path.write_text(serialize(fm, body), encoding="utf-8")
        return str(full_path)

    def intra_vault_move(self, vault: str, source_path: str, dest_path: str) -> str:
        """Move a note within a vault using the Obsidian CLI (preserves wikilinks).

        Requires Obsidian to be running.
        """
        vault_path = self._vault_path(vault)
        src_full = vault_path / source_path
        dst_full = vault_path / dest_path

        if not src_full.exists():
            raise FileNotFoundError(
                f"Note not found at '{source_path}' in vault '{vault}'"
            )
        if dst_full.exists():
            raise FileExistsError(
                f"Destination already exists at '{dest_path}' in vault '{vault}'"
            )

        self._run_cli(vault, "move", f"path={source_path}", f"to={dest_path}")
        return str(dst_full)

    def move_note(
        self,
        source_vault: str,
        dest_vault: str,
        source_path: str,
        dest_path: Optional[str] = None,
    ) -> str:
        """Move a note. Intra-vault uses CLI (wikilinks preserved); cross-vault uses filesystem."""
        effective_dest = dest_path or source_path

        if source_vault == dest_vault:
            return self.intra_vault_move(source_vault, source_path, effective_dest)

        src_vault_path = self._vault_path(source_vault)
        dst_vault_path = self._vault_path(dest_vault)

        src_full = src_vault_path / source_path
        dst_full = dst_vault_path / effective_dest

        if not src_full.exists():
            raise FileNotFoundError(
                f"Note not found at '{source_path}' in vault '{source_vault}'"
            )
        if dst_full.exists():
            raise FileExistsError(
                f"Destination already exists at '{effective_dest}' in vault '{dest_vault}'"
            )

        dst_full.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_full), str(dst_full))
        return str(dst_full)
