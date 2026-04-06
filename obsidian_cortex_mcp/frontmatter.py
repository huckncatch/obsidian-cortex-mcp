"""Pure YAML frontmatter parsing and serialization. No I/O."""
from __future__ import annotations

import yaml


def parse(content: str) -> tuple[dict, str]:
    """Split note content into (frontmatter_dict, body_str).

    Returns ({}, content) if no valid frontmatter block is present.
    """
    if not content.startswith("---\n"):
        return {}, content

    # Handle the edge case: "---\n---\n..." (empty frontmatter)
    if content.startswith("---\n---\n"):
        body = content[8:]  # skip "---\n---\n"
        return {}, body

    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content

    yaml_text = content[4:end]
    body = content[end + 5:]  # skip the "\n---\n" separator

    try:
        data = yaml.safe_load(yaml_text) or {}
    except yaml.YAMLError:
        return {}, content

    if not isinstance(data, dict):
        return {}, content

    return data, body


def serialize(frontmatter: dict, body: str) -> str:
    """Combine a frontmatter dict and body into a note string."""
    if not frontmatter:
        return body

    yaml_text = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
    ).rstrip()
    return f"---\n{yaml_text}\n---\n{body}"
