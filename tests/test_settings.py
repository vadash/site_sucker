"""Tests for settings module."""

import json
from pathlib import Path

import pytest

from site_sucker import settings


def test_load_settings_default():
    """Test loading default settings when no file exists."""
    result = settings.load_settings(None)
    assert result["UserAgent"] == settings.DEFAULT_SETTINGS["UserAgent"]
    assert result["Timeout"] == settings.DEFAULT_SETTINGS["Timeout"]
    assert result["ParallelDownloads"] == 2


def test_load_settings_from_file(tmp_path: Path):
    """Test loading settings from a JSON file."""
    settings_file = tmp_path / "test_settings.json"
    custom_settings = {
        "UserAgent": "Custom Agent",
        "Timeout": 30,
        "ParallelDownloads": 8,
    }

    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(custom_settings, f)

    result = settings.load_settings(settings_file)

    assert result["UserAgent"] == "Custom Agent"
    assert result["Timeout"] == 30
    assert result["ParallelDownloads"] == 8
    # Defaults should still be present for missing keys
    assert "Retries" in result


def test_load_settings_invalid_json(tmp_path: Path, capsys):
    """Test handling of invalid JSON in settings file."""
    settings_file = tmp_path / "invalid.json"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json }")

    result = settings.load_settings(settings_file)

    # Should fall back to defaults
    assert result == settings.DEFAULT_SETTINGS
    captured = capsys.readouterr()
    assert "Warning" in captured.out


def test_merge_cli_overrides_parallel():
    """Test merging parallel override."""
    base = {"ParallelDownloads": 2, "MaxDepth": 0}
    result = settings.merge_cli_overrides(base, parallel=8)

    assert result["ParallelDownloads"] == 8
    assert result["MaxDepth"] == 0


def test_merge_cli_overrides_depth():
    """Test merging depth override."""
    base = {"ParallelDownloads": 2, "MaxDepth": 0}
    result = settings.merge_cli_overrides(base, depth=5)

    assert result["ParallelDownloads"] == 2
    assert result["MaxDepth"] == 5


def test_merge_cli_overrides_both():
    """Test merging both overrides."""
    base = {"ParallelDownloads": 2, "MaxDepth": 0}
    result = settings.merge_cli_overrides(base, parallel=16, depth=3)

    assert result["ParallelDownloads"] == 16
    assert result["MaxDepth"] == 3


def test_merge_cli_overrides_zero_values():
    """Test that zero values don't override (defaults logic)."""
    base = {"ParallelDownloads": 4, "MaxDepth": 5}
    result = settings.merge_cli_overrides(base, parallel=0, depth=0)

    # Zeros should not override existing values
    assert result["ParallelDownloads"] == 4
    assert result["MaxDepth"] == 5


def test_merge_cli_overrides_extra_reject_single():
    """Test merging a single extra reject pattern."""
    base = {"RejectPatterns": ["pattern1"]}
    result = settings.merge_cli_overrides(base, extra_reject=["f=31&"])

    assert "f=31&" in result["RejectPatterns"]
    assert "pattern1" in result["RejectPatterns"]


def test_merge_cli_overrides_extra_reject_multiple_flags():
    """Test merging multiple extra reject patterns via separate flags."""
    base = {"RejectPatterns": ["pattern1"]}
    result = settings.merge_cli_overrides(base, extra_reject=["f=31&", "f=8&", "f=11&"])

    assert "f=31&" in result["RejectPatterns"]
    assert "f=8&" in result["RejectPatterns"]
    assert "f=11&" in result["RejectPatterns"]
    assert "pattern1" in result["RejectPatterns"]


def test_merge_cli_overrides_extra_reject_semicolon_delimited():
    """Test merging semicolon-delimited reject patterns."""
    base = {"RejectPatterns": ["pattern1"]}
    result = settings.merge_cli_overrides(base, extra_reject=["f=31&;f=8&;f=11&"])

    assert "f=31&" in result["RejectPatterns"]
    assert "f=8&" in result["RejectPatterns"]
    assert "f=11&" in result["RejectPatterns"]
    assert "pattern1" in result["RejectPatterns"]


def test_merge_cli_overrides_extra_reject_mixed():
    """Test mixing semicolon-delimited and single patterns."""
    base = {"RejectPatterns": []}
    result = settings.merge_cli_overrides(base, extra_reject=["f=31&;f=8&", "f=11&"])

    assert "f=31&" in result["RejectPatterns"]
    assert "f=8&" in result["RejectPatterns"]
    assert "f=11&" in result["RejectPatterns"]


def test_merge_cli_overrides_extra_reject_whitespace_handling():
    """Test that whitespace is trimmed from semicolon-delimited patterns."""
    base = {"RejectPatterns": []}
    result = settings.merge_cli_overrides(base, extra_reject=["f=31& ; f=8& ; f=11&"])

    assert "f=31&" in result["RejectPatterns"]
    assert "f=8&" in result["RejectPatterns"]
    assert "f=11&" in result["RejectPatterns"]


def test_merge_cli_overrides_does_not_mutate_original():
    """Test that the original settings dict is not mutated."""
    base = {"RejectPatterns": ["pattern1"]}
    original_patterns = base["RejectPatterns"].copy()

    settings.merge_cli_overrides(base, extra_reject=["f=31&"])

    assert base["RejectPatterns"] == original_patterns
    assert "f=31&" not in base["RejectPatterns"]


# JSONC Tests

def test_strip_jsonc_line_comments():
    """Test removing line comments."""
    content = '''{
  "key": "value",  // this is a comment
  "another": "test"
}'''
    result = settings._strip_jsonc_comments(content)
    assert "// this is a comment" not in result
    assert '"key": "value",' in result
    assert '"another": "test"' in result


def test_strip_jsonc_block_comments():
    """Test removing block comments."""
    content = '''{
  /* this is a block comment */
  "key": "value",
  /* multi
     line
     comment */
  "another": "test"
}'''
    result = settings._strip_jsonc_comments(content)
    assert "/* this is a block comment */" not in result
    assert "/* multi" not in result
    assert '"key": "value"' in result
    assert '"another": "test"' in result


def test_strip_jsonc_preserves_urls():
    """Test that URLs with :// are preserved."""
    content = r'''{
  "url": "https://example.com",  // comment
  "another": "http://test.org"
}'''
    result = settings._strip_jsonc_comments(content)
    assert '"url": "https://example.com",' in result
    assert '"another": "http://test.org"' in result


def test_strip_jsonc_preserves_slashes_in_strings():
    """Test that // inside strings are preserved."""
    content = r'''{
  "path": "C:\\Users\\test",  // comment
  "regex": "//pattern",
  "empty": ""
}'''
    result = settings._strip_jsonc_comments(content)
    # After comment removal, the Windows path backslashes remain
    assert '"path": "C:\\\\Users\\\\test",' in result
    assert '"regex": "//pattern"' in result
    assert '// comment' not in result


def test_strip_jsonc_escaped_quotes():
    """Test handling of escaped quotes in strings."""
    content = r'''{
  "text": "say \"hello\"", // comment after
  "empty": ""
}'''
    result = settings._strip_jsonc_comments(content)
    assert '"text": "say \\"hello\\"",' in result
    assert '// comment after' not in result


def test_load_jsonc_file(tmp_path: Path):
    """Test loading settings from a JSONC file."""
    settings_file = tmp_path / "test_settings.jsonc"
    content = '''{
  // This is a comment
  "UserAgent": "Custom Agent",
  "Timeout": 30,
  /* Block comment */
  "ParallelDownloads": 8
}'''
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(content)

    result = settings.load_settings(settings_file)

    assert result["UserAgent"] == "Custom Agent"
    assert result["Timeout"] == 30
    assert result["ParallelDownloads"] == 8


def test_load_jsonc_filters_underscore_keys(tmp_path: Path):
    """Test that keys starting with _ are filtered out (backwards compat)."""
    settings_file = tmp_path / "old_style.jsonc"
    content = '''{
  "_comment": "This is an old-style comment key",
  "_internal": "should be filtered",
  "UserAgent": "Keep this",
  "Timeout": 15
}'''
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(content)

    result = settings.load_settings(settings_file)

    assert "_comment" not in result
    assert "_internal" not in result
    assert result["UserAgent"] == "Keep this"
    assert result["Timeout"] == 15


def test_load_jsonc_fallback_to_json(tmp_path: Path, monkeypatch):
    """Test that .jsonc is tried first, then .json."""
    # Create both files
    jsonc_file = tmp_path / "settings.jsonc"
    json_file = tmp_path / "settings.json"

    jsonc_content = '{"Timeout": 99}'
    json_content = '{"Timeout": 88}'

    with open(jsonc_file, "w", encoding="utf-8") as f:
        f.write(jsonc_content)
    with open(json_file, "w", encoding="utf-8") as f:
        f.write(json_content)

    # Change to the temp directory
    monkeypatch.chdir(tmp_path)

    result = settings.load_settings(None)
    # Should prefer .jsonc
    assert result["Timeout"] == 99


def test_load_json_fallback_when_no_jsonc(tmp_path: Path, monkeypatch):
    """Test that .json is used when .jsonc doesn't exist."""
    json_file = tmp_path / "settings.json"
    json_content = '{"Timeout": 77}'

    with open(json_file, "w", encoding="utf-8") as f:
        f.write(json_content)

    # Change to the temp directory
    monkeypatch.chdir(tmp_path)

    result = settings.load_settings(None)
    assert result["Timeout"] == 77
