# obsidian-cortex-mcp

> **obsidian-cortex-mcp** is the high-level orchestration layer sitting on top of individual
> Obsidian vaults — the cerebral cortex of your second brain.

A Python + FastMCP server that provides cross-vault operations for multiple Obsidian vaults
living under a common root directory. Each vault is an independent Obsidian universe; this
server is the shim layer that unifies them.

## Tools

| Tool | Description |
| ---- | ----------- |
| `list_vaults` | Detect all child vaults under the root |
| `list_notes` | Browse vault directory tree |
| `read_note` | Read note content (supports paging via offset/limit) |
| `search` | Search content or tags across vaults |
| `list_tags` | Aggregate frontmatter tags with per-vault + shared output |
| `create_note` | Create a new note with optional frontmatter and body |
| `write_note` | Replace note body, preserving frontmatter |
| `edit_note` | Exact string replacement (old_string → new_string) |
| `update_frontmatter` | Add/update/remove frontmatter fields |
| `move_note` | Move a note within or across vaults (see below) |
| `lint_note` | Lint one note with `markdownlint-cli2` (never fixes) |
| `git_status` | `git status --porcelain` for one path |
| `git_stage` | `git add` one path |
| `git_commit` | Commit named staged paths only (no push) |

Same-vault moves go through the Obsidian CLI, which rewrites wikilinks and needs
Obsidian running; cross-vault moves use the filesystem.

Every tool refuses an absolute path, a path that resolves outside its vault,
and a vault name that is not a folder directly under `OBSIDIAN_CORTEX_ROOT`.

The lint and git tools run in `OBSIDIAN_CORTEX_ROOT`, which must be the root
of a git repo for the git tools. Their paths are literal (no globs).
`git_commit` commits only the paths it is given, each of
which must have a staged change, so paths that other sessions staged stay
staged. It never passes `--no-verify`: when a pre-commit hook blocks the
commit, the tool returns the hook output and leaves the index as it was.
`/opt/homebrew/bin` and `/usr/local/bin` are added to `PATH` for these
commands, so `markdownlint-cli2` and hooks that need Homebrew tools work when
a client starts the server with a minimal `PATH`.

## Requirements

- Python 3.11+
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`brew install ripgrep`)
- git, and [markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2)
  (`brew install markdownlint-cli2`) for `lint_note`

## Setup

```bash
cd ~/Developer/obsidian-cortex-mcp
python3.11 -m venv .venv
.venv/bin/pip install -e .
```

## Environment Variables

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `OBSIDIAN_CORTEX_ROOT` | Yes | — | Absolute path to the directory containing all vaults |
| `DEFAULT_VAULT` | No | `Home` | Vault used when no vault is specified in a tool call |

## Client Registration

### Claude Code

```bash
claude mcp add --scope user obsidian-cortex \
  -e OBSIDIAN_CORTEX_ROOT=/path/to/vaults -e DEFAULT_VAULT=Home \
  -- /path/to/obsidian-cortex-mcp/.venv/bin/python -m obsidian_cortex_mcp
```

### Claude Desktop

Add under `mcpServers` in
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
"obsidian-cortex": {
  "command": "/path/to/obsidian-cortex-mcp/.venv/bin/python",
  "args": ["-m", "obsidian_cortex_mcp"],
  "env": { "OBSIDIAN_CORTEX_ROOT": "/path/to/vaults", "DEFAULT_VAULT": "Home" }
}
```

### VS Code (Claude Code for VS Code v2.1.87+)

Add to your user `settings.json` under `mcp.servers`.

### On this machine

Both Claude clients launch the server through
`~/config/brain/bin/obsidian-cortex.sh`, which sets the variables from the
single vault-location definition in `~/config/home/.chezmoidata/brain.toml`.
See the obsidian-cortex section of `~/config/NOTES.md`.

## Architecture

```text
server.py       FastMCP app, env validation, tool registration
vault.py        VaultManager: all filesystem I/O, ripgrep, lint and git
frontmatter.py  Pure YAML parse/serialize — no I/O
tools/
  discovery.py  list_vaults, list_notes
  reading.py    read_note, search, list_tags
  writing.py    create_note, write_note, edit_note, update_frontmatter, move_note
  repo.py       lint_note, git_status, git_stage, git_commit
```

## Testing

```bash
.venv/bin/pytest -v
```
