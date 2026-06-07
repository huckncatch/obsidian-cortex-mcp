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
| `move_note` | Move a note cross-vault (intra-vault: use Obsidian app) |

## Requirements

- Python 3.11+
- [ripgrep](https://github.com/BurntSushi/ripgrep) (`brew install ripgrep`)

## Setup

```bash
cd /Users/soob/.config/claude/mcp-servers/obsidian-cortex-mcp
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

Add to `/Users/soob/.config/claude/settings.json`:

```json
"obsidian-cortex": {
  "command": "/Users/soob/.config/claude/mcp-servers/obsidian-cortex-mcp/.venv/bin/python",
  "args": ["-m", "obsidian_cortex_mcp"],
  "env": {
    "OBSIDIAN_CORTEX_ROOT": "/Users/soob/Dropbox/Apps/Obsidian",
    "DEFAULT_VAULT": "Home"
  }
}
```

### Claude Desktop

Add the same block to `~/Library/Application Support/Claude/claude_desktop_config.json`
under `mcpServers`.

### VS Code (Claude Code for VS Code v2.1.87+)

Add to your user `settings.json` under `mcp.servers`.

## Architecture

```text
server.py       FastMCP app, env validation, tool registration
vault.py        VaultManager: all filesystem I/O and ripgrep
frontmatter.py  Pure YAML parse/serialize — no I/O
tools/
  discovery.py  list_vaults, list_notes
  reading.py    read_note, search, list_tags
  writing.py    create_note, write_note, edit_note, update_frontmatter, move_note
```

## Testing

```bash
.venv/bin/pytest -v
```
