"""Tests for frontmatter.py — pure parse/serialize, no I/O."""
import pytest
from obsidian_cortex_mcp.frontmatter import parse, serialize


class TestParse:
    def test_note_with_frontmatter(self):
        content = "---\ntitle: My Note\ntags: [swift, ios]\n---\nBody here."
        fm, body = parse(content)
        assert fm == {"title": "My Note", "tags": ["swift", "ios"]}
        assert body == "Body here."

    def test_note_without_frontmatter(self):
        content = "Just a plain note."
        fm, body = parse(content)
        assert fm == {}
        assert body == "Just a plain note."

    def test_empty_frontmatter_block(self):
        content = "---\n---\nBody."
        fm, body = parse(content)
        assert fm == {}
        assert body == "Body."

    def test_frontmatter_with_no_body(self):
        content = "---\ntitle: Solo\n---\n"
        fm, body = parse(content)
        assert fm == {"title": "Solo"}
        assert body == ""

    def test_no_closing_delimiter_treated_as_no_frontmatter(self):
        content = "---\ntitle: Broken\n"
        fm, body = parse(content)
        assert fm == {}
        assert body == content

    def test_block_list_tags(self):
        content = "---\ntags:\n  - swift\n  - ios\n---\nBody."
        fm, body = parse(content)
        assert fm["tags"] == ["swift", "ios"]

    def test_inline_list_tags(self):
        content = "---\ntags: [swift, ios]\n---\nBody."
        fm, body = parse(content)
        assert fm["tags"] == ["swift", "ios"]


class TestSerialize:
    def test_roundtrip_with_frontmatter(self):
        original = "---\ntitle: My Note\ntags:\n- swift\n- ios\n---\nBody here."
        fm, body = parse(original)
        result = serialize(fm, body)
        # Re-parse to verify integrity (YAML key order may differ)
        fm2, body2 = parse(result)
        assert fm2 == fm
        assert body2 == body

    def test_empty_frontmatter_returns_body_only(self):
        result = serialize({}, "Just body.")
        assert result == "Just body."

    def test_serialize_produces_valid_yaml(self):
        import yaml
        fm = {"title": "Test", "tags": ["a", "b"]}
        result = serialize(fm, "body")
        assert result.startswith("---\n")
        assert "\n---\n" in result
        # Extract and re-parse YAML portion
        inner = result.split("\n---\n")[0][4:]
        parsed = yaml.safe_load(inner)
        assert parsed == fm

    def test_none_value_produces_yaml_null(self):
        # serialize is transparent — None values produce YAML null.
        # Callers (update_frontmatter) are responsible for filtering Nones before calling serialize.
        fm = {"title": "Test", "empty_key": None}
        result = serialize(fm, "body")
        assert "null" in result  # documents actual behavior: callers must pre-filter Nones

    def test_unicode_preserved(self):
        fm = {"title": "日本語"}
        result = serialize(fm, "")
        fm2, _ = parse(result)
        assert fm2["title"] == "日本語"
