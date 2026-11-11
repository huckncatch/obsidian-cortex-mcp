"""VaultManager: all filesystem operations for obsidian-cortex-mcp."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .frontmatter import parse, serialize

# Clients such as Claude Desktop start the server with a minimal PATH. markdownlint-cli2 and the
# gitleaks pre-commit hook live in Homebrew.
_EXTRA_PATH = "/opt/homebrew/bin:/usr/local/bin"


def _frontmatter_tags(fm: dict) -> list[str]:
    """Return a note's tags as strings. A bare `tags:` key parses to None."""
    raw_tags = fm.get("tags")
    if raw_tags is None:
        return []
    if not isinstance(raw_tags, list):
        raw_tags = [raw_tags]
    return [str(t) for t in raw_tags if t is not None and t != ""]


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
        if vault in ("", ".", "..") or Path(vault).name != vault or not (path / ".obsidian").is_dir():
            known = ", ".join(self.list_vault_names())
            raise ValueError(
                f"'{vault}' is not a recognized vault. Known vaults: {known}"
            )
        return path

    def _note_path(self, vault: str, note_path: str, allow_vault_root: bool = False) -> Path:
        """Return vault_path / note_path; refuse absolute paths and paths that resolve outside the vault."""
        vault_path = self._vault_path(vault)
        resolved_vault = vault_path.resolve()
        if Path(note_path).is_absolute():
            raise ValueError(f"'{note_path}' is not a relative path in vault '{vault}'")
        full = (vault_path / note_path).resolve()
        if not full.is_relative_to(resolved_vault) or (full == resolved_vault and not allow_vault_root):
            raise ValueError(f"'{note_path}' is outside vault '{vault}'")
        return vault_path / full.relative_to(resolved_vault)

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
        base = self._note_path(vault, subfolder, allow_vault_root=True)

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
        full_path = self._note_path(vault, note_path)

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
                # -e and -- keep a query that starts with "-" from being read as an rg option
                ["rg", "--json", "-g", "*.md", "-e", query, "--", str(vault_path)],
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
                matching = [
                    t for t in _frontmatter_tags(fm) if query_lower in t.lower()
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
                tags.update(_frontmatter_tags(fm))
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
        full_path = self._note_path(vault, note_path)

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
        full_path = self._note_path(vault, note_path)

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
        full_path = self._note_path(vault, note_path)

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
        full_path = self._note_path(vault, note_path)

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
        src_full = self._note_path(vault, source_path)
        dst_full = self._note_path(vault, dest_path)

        if not src_full.exists():
            raise FileNotFoundError(
                f"Note not found at '{source_path}' in vault '{vault}'"
            )
        if dst_full.exists():
            raise FileExistsError(
                f"Destination already exists at '{dest_path}' in vault '{vault}'"
            )

        dst_full.parent.mkdir(parents=True, exist_ok=True)
        output = self._run_cli(vault, "move", f"path={source_path}", f"to={dest_path}")
        if not dst_full.exists():
            raise RuntimeError(
                f"Obsidian CLI move did not create '{dest_path}' in vault '{vault}'"
                + (f": {output}" if output else "")
            )
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

        src_full = self._note_path(source_vault, source_path)
        dst_full = self._note_path(dest_vault, effective_dest)

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

    # ── Lint and git ─────────────────────────────────────────────────────────

    def _repo_path(self, vault: str, note_path: str) -> str:
        """Return '<vault>/<note_path>' relative to root; refuse paths outside the vault."""
        full = self._note_path(vault, note_path)
        # Forward slashes on every OS: git output and tool replies use them
        return full.relative_to(self.root).as_posix()

    def _run(self, *cmd: str) -> subprocess.CompletedProcess:
        """Run a command in root with Homebrew on PATH and literal git pathspecs."""
        env = dict(os.environ)
        env["PATH"] = _EXTRA_PATH + os.pathsep + env.get("PATH", "")
        env["GIT_LITERAL_PATHSPECS"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        # Resolve the full path first: on Windows, subprocess finds only .exe files, and npm
        # installs tools such as markdownlint-cli2 as .cmd shims
        exe = shutil.which(cmd[0], path=env["PATH"])
        if exe is None:
            raise RuntimeError(f"'{cmd[0]}' not found on PATH")
        try:
            return subprocess.run(
                (exe, *cmd[1:]), cwd=self.root, env=env, capture_output=True, text=True
            )
        except FileNotFoundError:
            raise RuntimeError(f"'{cmd[0]}' not found on PATH")

    def _git(self, *args: str) -> str:
        """Run git in root; raise RuntimeError with its output on failure."""
        result = self._run("git", *args)
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip()
            raise RuntimeError(f"git {args[0]} failed: {detail}")
        return result.stdout

    def lint_note(self, vault: str, note_path: str) -> list[str]:
        """Lint one note with markdownlint-cli2 from root. Return 'line[:col] rule message' lines."""
        rel = self._repo_path(vault, note_path)
        if not (self.root / rel).is_file():
            raise FileNotFoundError(f"Note not found at '{note_path}' in vault '{vault}'")
        # A leading ':' makes markdownlint-cli2 read the argument as a literal path, not a glob
        result = self._run("markdownlint-cli2", ":" + rel)
        if result.returncode > 1:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"markdownlint-cli2 failed: {detail}")
        violations = []
        prefix = rel + ":"
        for line in result.stderr.splitlines():
            if not line.startswith(prefix):
                continue
            location, _, rest = line[len(prefix):].partition(" ")
            if rest.startswith("error "):
                rest = rest[len("error "):]
            violations.append(f"{location} {rest}")
        return violations

    def git_status(self, vault: str, note_path: str) -> list[str]:
        """Return the porcelain status lines for one path; an ignored path shows '!!'."""
        rel = self._repo_path(vault, note_path)
        return self._git("status", "--porcelain", "--ignored", "--", rel).splitlines()

    def git_stage(self, vault: str, note_path: str) -> str:
        """Stage one path (a change, new file, or deletion). Return the repo-relative path."""
        rel = self._repo_path(vault, note_path)
        self._git("add", "--", rel)
        return rel

    def git_commit(self, message: str, paths: list[tuple[str, str]]) -> str:
        """Commit the given (vault, path) pairs with git commit -- <paths>.

        Each path must have a staged change. Other staged paths stay staged. The pre-commit
        hooks run. Return the new commit's short hash and subject.
        """
        if not message.strip():
            raise ValueError("A commit message is required")
        if not paths:
            raise ValueError("At least one path is required")
        rels = [self._repo_path(vault, p) for vault, p in paths]
        unstaged = [
            rel for rel in rels
            if not self._git("diff", "--cached", "--name-only", "--", rel).strip()
        ]
        if unstaged:
            raise ValueError(
                "Nothing staged for: " + ", ".join(unstaged) + ". Stage each path with git_stage first."
            )
        self._git("commit", "-m", message, "--", *rels)
        return self._git("log", "-1", "--format=%h %s").strip()
