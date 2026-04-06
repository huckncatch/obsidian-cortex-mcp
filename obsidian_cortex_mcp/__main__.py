"""Entry point for python -m obsidian_cortex_mcp."""
from .server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
