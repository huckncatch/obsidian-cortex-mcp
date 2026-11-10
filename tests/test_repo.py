"""Tests for the lint and git tools against a temporary vaults-root git repo."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from obsidian_cortex_mcp.tools.repo import _git_commit, _git_stage, _git_status, _lint_note
from obsidian_cortex_mcp.vault import VaultManager


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture()
def repo(vault_root: Path, tmp_path_factory, monkeypatch) -> Path:
    """The fixture vault root as a git repo with one commit, isolated from the user's git config."""
    home = tmp_path_factory.mktemp("githome")
    config = home / "gitconfig"
    config.write_text("[user]\n\tname = Test\n\temail = test@example.com\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    _git(vault_root, "init", "-q")
    _git(vault_root, "add", "-A")
    _git(vault_root, "commit", "-q", "-m", "init")
    return vault_root


def _edit(root: Path, rel: str, text: str = "Changed.\n") -> None:
    (root / rel).write_text(text, encoding="utf-8")


class TestGitStatus:
    def test_clean(self, repo: Path, vm: VaultManager):
        assert _git_status(vm, path="plain.md") == "clean"

    def test_unstaged(self, repo: Path, vm: VaultManager):
        _edit(repo, "Alpha/plain.md")
        assert _git_status(vm, path="plain.md") == " M Alpha/plain.md"

    def test_staged(self, repo: Path, vm: VaultManager):
        _edit(repo, "Alpha/plain.md")
        _git_stage(vm, path="plain.md")
        assert _git_status(vm, path="plain.md") == "M  Alpha/plain.md"

    def test_ignored(self, repo: Path, vm: VaultManager):
        (repo / ".gitignore").write_text("scratch.md\n")
        _edit(repo, "Alpha/scratch.md")
        assert _git_status(vm, path="scratch.md") == "!! Alpha/scratch.md"

    def test_outside_vault_refused(self, repo: Path, vm: VaultManager):
        for bad in ("../Beta/readme.md", "/etc/hosts", "", "."):
            with pytest.raises(ToolError):
                _git_status(vm, path=bad)


class TestGitStage:
    def test_stages_one_path(self, repo: Path, vm: VaultManager):
        _edit(repo, "Alpha/plain.md")
        _edit(repo, "Alpha/notes/hello.md")
        assert _git_stage(vm, path="plain.md") == "Staged: Alpha/plain.md"
        assert _git(repo, "diff", "--cached", "--name-only").split() == ["Alpha/plain.md"]

    def test_glob_is_literal(self, repo: Path, vm: VaultManager):
        _edit(repo, "Alpha/plain.md")
        with pytest.raises(ToolError):
            _git_stage(vm, path="*")
        assert _git(repo, "diff", "--cached", "--name-only") == ""

    def test_stages_deletion(self, repo: Path, vm: VaultManager):
        (repo / "Alpha/plain.md").unlink()
        _git_stage(vm, path="plain.md")
        assert _git_status(vm, path="plain.md") == "D  Alpha/plain.md"

    def test_outside_vault_refused(self, repo: Path, vm: VaultManager):
        with pytest.raises(ToolError):
            _git_stage(vm, path="../Beta/readme.md")


class TestGitCommit:
    def test_commits_only_named_paths(self, repo: Path, vm: VaultManager):
        _edit(repo, "Alpha/plain.md")
        _edit(repo, "Beta/readme.md")
        _git_stage(vm, path="plain.md")
        _git_stage(vm, path="readme.md", vault="Beta")  # another session's staged edit
        result = _git_commit(vm, message="Fix plain note", paths=["plain.md"])
        assert result.startswith("Committed: ") and result.endswith("Fix plain note")
        assert _git(repo, "show", "--name-only", "--format=", "HEAD").split() == ["Alpha/plain.md"]
        assert _git(repo, "diff", "--cached", "--name-only").split() == ["Beta/readme.md"]

    def test_message_used_as_given(self, repo: Path, vm: VaultManager):
        _edit(repo, "Alpha/plain.md")
        _git_stage(vm, path="plain.md")
        message = "Fix plain note\n\nCo-Authored-By: Someone <x@example.com>"
        _git_commit(vm, message=message, paths=["plain.md"])
        assert _git(repo, "log", "-1", "--format=%B").strip() == message

    def test_refuses_unstaged_path(self, repo: Path, vm: VaultManager):
        _edit(repo, "Alpha/plain.md")
        with pytest.raises(ToolError, match="Nothing staged"):
            _git_commit(vm, message="x", paths=["plain.md"])
        assert _git(repo, "rev-list", "--count", "HEAD").strip() == "1"

    def test_refuses_empty_message_and_paths(self, repo: Path, vm: VaultManager):
        _edit(repo, "Alpha/plain.md")
        _git_stage(vm, path="plain.md")
        with pytest.raises(ToolError):
            _git_commit(vm, message="  ", paths=["plain.md"])
        with pytest.raises(ToolError):
            _git_commit(vm, message="x", paths=[])

    def test_hook_block_keeps_index(self, repo: Path, vm: VaultManager):
        hooks = repo / ".git" / "test-hooks"
        hooks.mkdir()
        hook = hooks / "pre-commit"
        hook.write_text("#!/bin/sh\necho 'secret found' >&2\nexit 1\n")
        hook.chmod(0o755)
        _git(repo, "config", "core.hooksPath", str(hooks))
        _edit(repo, "Alpha/plain.md")
        _git_stage(vm, path="plain.md")
        with pytest.raises(ToolError, match="secret found"):
            _git_commit(vm, message="x", paths=["plain.md"])
        assert _git(repo, "rev-list", "--count", "HEAD").strip() == "1"
        assert _git_status(vm, path="plain.md") == "M  Alpha/plain.md"


@pytest.mark.skipif(not shutil.which("markdownlint-cli2"), reason="markdownlint-cli2 not installed")
class TestLintNote:
    def test_clean(self, vault_root: Path, vm: VaultManager):
        _edit(vault_root, "Alpha/good.md", "# Title\n\nText.\n")
        assert _lint_note(vm, path="good.md") == "clean"

    def test_violations(self, vault_root: Path, vm: VaultManager):
        _edit(vault_root, "Alpha/bad.md", "# Title\n#Bad\n")
        result = _lint_note(vm, path="bad.md").splitlines()
        assert any(line.startswith("2:1 MD018/no-missing-space-atx ") for line in result)
        assert all(not line.startswith("Alpha/") for line in result)

    def test_bracketed_name_is_literal(self, vault_root: Path, vm: VaultManager):
        _edit(vault_root, "Alpha/note [1].md", "#Bad\n")
        _edit(vault_root, "Alpha/note 1.md", "# Fine\n")
        result = _lint_note(vm, path="note [1].md")
        assert "MD018" in result

    def test_does_not_fix(self, vault_root: Path, vm: VaultManager):
        _edit(vault_root, "Alpha/bad.md", "#Bad\n")
        _lint_note(vm, path="bad.md")
        assert (vault_root / "Alpha/bad.md").read_text() == "#Bad\n"

    def test_missing_note(self, vault_root: Path, vm: VaultManager):
        with pytest.raises(ToolError):
            _lint_note(vm, path="nope.md")

    def test_outside_vault_refused(self, vault_root: Path, vm: VaultManager):
        with pytest.raises(ToolError):
            _lint_note(vm, path="../Beta/readme.md")
