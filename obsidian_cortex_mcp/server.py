"""FastMCP server: environment validation, VaultManager init, tool registration."""
from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from .vault import VaultManager
from .tools import discovery, reading, writing


def _build_server() -> FastMCP:
    root = os.environ.get("OBSIDIAN_CORTEX_ROOT")
    if not root:
        raise RuntimeError(
            "OBSIDIAN_CORTEX_ROOT environment variable is required. "
            "Set it to the directory containing your Obsidian vaults."
        )

    root_path = Path(root)
    if not root_path.exists():
        raise RuntimeError(
            f"OBSIDIAN_CORTEX_ROOT path does not exist: {root}"
        )

    default_vault = os.environ.get("DEFAULT_VAULT", "Home")
    vm = VaultManager(root=root, default_vault=default_vault)

    mcp = FastMCP(name="obsidian-cortex")
    discovery.register(mcp, vm)
    reading.register(mcp, vm)
    writing.register(mcp, vm)

    return mcp


mcp = _build_server()
