"""Tests for settings module."""

import json
import logging
from pathlib import Path

from site_sucker import settings
from site_sucker.settings import Settings

# Range Expression Tests


def test_expand_reject_expression_no_expression():
    """Test that patterns without expressions are returned as-is."""
    result = settings._expand_reject_expression("action=")
    assert result == ["action="]


def test_expand_reject_expression_basic_range():
    """Test basic range expansion {1..5}."""
    result = settings._expand_reject_expression("f={1..5}&")
    assert result == ["f=1&", "f=2&", "f=3&", "f=4&", "f=5&"]


def test_expand_reject_expression_range_with_step():
    """Test range expansion with step {1..10..2}."""
    result = settings._expand_reject_expression("f={1..10..2}&")
    assert result == ["f=1&", "f=3&", "f=5&", "f=7&", "f=9&"]


def test_expand_reject_expression_range_with_exclusions():
    """Test range expansion with exclusions {1..10%3,7}."""
    result = settings._expand_reject_expression("f={1..10%3,7}&")
    # Should exclude 3 and 7
    assert result == ["f=1&", "f=2&", "f=4&", "f=5&", "f=6&", "f=8&", "f=9&", "f=10&"]


def test_expand_reject_expression_forum_example():
    """Test the real-world forum.median-xl.com example."""
    result = settings._expand_reject_expression("f={1..100%4,25,40}&")
    # Should generate 97 patterns (100 total minus 4, 25, 40)
    assert len(result) == 97
    # Check some specific values
    assert "f=1&" in result
    assert "f=3&" in result
    assert "f=4&" not in result
    assert "f=5&" in result
    assert "f=24&" in result
    assert "f=25&" not in result
    assert "f=26&" in result
    assert "f=39&" in result
    assert "f=40&" not in result
    assert "f=41&" in result
    assert "f=100&" in result


def test_expand_reject_expression_single_value():
    """Test expression that expands to single value."""
    result = settings._expand_reject_expression("f={5..5}&")
    assert result == ["f=5&"]


def test_expand_reject_expression_negative_step():
    """Test range with negative step."""
    result = settings._expand_reject_expression("f={10..1..-1}&")
    assert result == [
        "f=10&",
        "f=9&",
        "f=8&",
        "f=7&",
        "f=6&",
        "f=5&",
        "f=4&",
        "f=3&",
        "f=2&",
        "f=1&",
    ]


def test_expand_reject_expression_multiple_exclusions():
    """Test range with multiple exclusions."""
    result = settings._expand_reject_expression("id={1..20%2,3,5,7,11,13,17,19}&")
    # Should only include prime numbers from 1..20 (excluding the primes listed as exclusions)
    # Wait, this is excluding primes, so it should include non-primes
    expected = [
        "id=1&",
        "id=4&",
        "id=6&",
        "id=8&",
        "id=9&",
        "id=10&",
        "id=12&",
        "id=14&",
        "id=15&",
        "id=16&",
        "id=18&",
        "id=20&",
    ]
    assert result == expected


def test_expand_reject_expression_invalid_syntax():
    """Test that invalid expressions are returned as-is."""
    result = settings._expand_reject_expression("f={invalid}&")
    # Invalid expressions should be returned as-is
    assert result == ["f={invalid}&"]


def test_expand_reject_expression_empty_range():
    """Test expression with empty result after exclusions."""
    result = settings._expand_reject_expression("f={5..5%5}&")
    # Should return the original expression since expansion is empty
    assert result == ["f={5..5%5}&"]


def test_merge_cli_overrides_with_expressions():
    """Test that expressions are expanded during CLI override merge."""
    base = Settings(reject_patterns=["pattern1"])
    result = settings.merge_cli_overrides(base, extra_reject=["f={1..5%3}&"])

    # Should have pattern1 plus expanded f=1&, f=2&, f=4&, f=5& (excluding 3)
    assert "pattern1" in result.reject_patterns
    assert "f=1&" in result.reject_patterns
    assert "f=2&" in result.reject_patterns
    assert "f=3&" not in result.reject_patterns
    assert "f=4&" in result.reject_patterns
    assert "f=5&" in result.reject_patterns


def test_merge_cli_overrides_mixed_literals_and_expressions():
    """Test mixing literal patterns and expressions."""
    base = Settings(reject_patterns=[])
    result = settings.merge_cli_overrides(base, extra_reject=["action=", "f={1..3}&"])

    assert "action=" in result.reject_patterns
    assert "f=1&" in result.reject_patterns
    assert "f=2&" in result.reject_patterns
    assert "f=3&" in result.reject_patterns


def test_load_settings_default(tmp_path: Path, monkeypatch):
    """Test loading default settings when no file exists."""
    # Change to temp directory where no settings file exists
    monkeypatch.chdir(tmp_path)
    result = settings.load_settings(None)
    assert result.user_agent == Settings().user_agent
    assert result.timeout == Settings().timeout
    assert result.parallel_downloads == 2


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

    assert result.user_agent == "Custom Agent"
    assert result.timeout == 30
    assert result.parallel_downloads == 8
    # Defaults should still be present for missing keys
    assert result.retries == 3


def test_load_settings_invalid_json(tmp_path: Path, caplog):
    """Test handling of invalid JSON in settings file."""
    caplog.set_level(logging.WARNING)
    settings_file = tmp_path / "invalid.json"
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json }")

    result = settings.load_settings(settings_file)

    # Should fall back to defaults
    assert result.user_agent == Settings().user_agent
    assert "Warning" in caplog.text or "Failed" in caplog.text


def test_merge_cli_overrides_parallel():
    """Test merging parallel override."""
    base = Settings(parallel_downloads=2, max_depth=0)
    result = settings.merge_cli_overrides(base, parallel=8)

    assert result.parallel_downloads == 8
    assert result.max_depth == 0


def test_merge_cli_overrides_depth():
    """Test merging depth override."""
    base = Settings(parallel_downloads=2, max_depth=0)
    result = settings.merge_cli_overrides(base, depth=5)

    assert result.parallel_downloads == 2
    assert result.max_depth == 5


def test_merge_cli_overrides_both():
    """Test merging both overrides."""
    base = Settings(parallel_downloads=2, max_depth=0)
    result = settings.merge_cli_overrides(base, parallel=16, depth=3)

    assert result.parallel_downloads == 16
    assert result.max_depth == 3


def test_merge_cli_overrides_zero_values():
    """Test that zero values don't override (defaults logic)."""
    base = Settings(parallel_downloads=4, max_depth=5)
    result = settings.merge_cli_overrides(base, parallel=0, depth=0)

    # Zeros should not override existing values
    assert result.parallel_downloads == 4
    assert result.max_depth == 5


def test_merge_cli_overrides_extra_reject_single():
    """Test merging a single extra reject pattern."""
    base = Settings(reject_patterns=["pattern1"])
    result = settings.merge_cli_overrides(base, extra_reject=["f=31&"])

    assert "f=31&" in result.reject_patterns
    assert "pattern1" in result.reject_patterns


def test_merge_cli_overrides_extra_reject_multiple_flags():
    """Test merging multiple extra reject patterns via separate flags."""
    base = Settings(reject_patterns=["pattern1"])
    result = settings.merge_cli_overrides(base, extra_reject=["f=31&", "f=8&", "f=11&"])

    assert "f=31&" in result.reject_patterns
    assert "f=8&" in result.reject_patterns
    assert "f=11&" in result.reject_patterns
    assert "pattern1" in result.reject_patterns


def test_merge_cli_overrides_extra_reject_semicolon_delimited():
    """Test merging semicolon-delimited reject patterns."""
    base = Settings(reject_patterns=["pattern1"])
    result = settings.merge_cli_overrides(base, extra_reject=["f=31&;f=8&;f=11&"])

    assert "f=31&" in result.reject_patterns
    assert "f=8&" in result.reject_patterns
    assert "f=11&" in result.reject_patterns
    assert "pattern1" in result.reject_patterns


def test_merge_cli_overrides_extra_reject_mixed():
    """Test mixing semicolon-delimited and single patterns."""
    base = Settings(reject_patterns=[])
    result = settings.merge_cli_overrides(base, extra_reject=["f=31&;f=8&", "f=11&"])

    assert "f=31&" in result.reject_patterns
    assert "f=8&" in result.reject_patterns
    assert "f=11&" in result.reject_patterns


def test_merge_cli_overrides_extra_reject_whitespace_handling():
    """Test that whitespace is trimmed from semicolon-delimited patterns."""
    base = Settings(reject_patterns=[])
    result = settings.merge_cli_overrides(base, extra_reject=["f=31& ; f=8& ; f=11&"])

    assert "f=31&" in result.reject_patterns
    assert "f=8&" in result.reject_patterns
    assert "f=11&" in result.reject_patterns


def test_merge_cli_overrides_does_not_mutate_original():
    """Test that the original settings is not mutated."""
    base = Settings(reject_patterns=["pattern1"])
    original_patterns = list(base.reject_patterns)

    settings.merge_cli_overrides(base, extra_reject=["f=31&"])

    assert list(base.reject_patterns) == original_patterns
    assert "f=31&" not in base.reject_patterns


# JSONC Tests


def test_strip_jsonc_line_comments():
    """Test removing line comments."""
    content = """{
  "key": "value",  // this is a comment
  "another": "test"
}"""
    result = settings._strip_jsonc_comments(content)
    assert "// this is a comment" not in result
    assert '"key": "value",' in result
    assert '"another": "test"' in result


def test_strip_jsonc_block_comments():
    """Test removing block comments."""
    content = """{
  /* this is a block comment */
  "key": "value",
  /* multi
     line
     comment */
  "another": "test"
}"""
    result = settings._strip_jsonc_comments(content)
    assert "/* this is a block comment */" not in result
    assert "/* multi" not in result
    assert '"key": "value"' in result
    assert '"another": "test"' in result


def test_strip_jsonc_preserves_urls():
    """Test that URLs with :// are preserved."""
    content = r"""{
  "url": "https://example.com",  // comment
  "another": "http://test.org"
}"""
    result = settings._strip_jsonc_comments(content)
    assert '"url": "https://example.com",' in result
    assert '"another": "http://test.org"' in result


def test_strip_jsonc_preserves_slashes_in_strings():
    """Test that // inside strings are preserved."""
    content = r"""{
  "path": "C:\\Users\\test",  // comment
  "regex": "//pattern",
  "empty": ""
}"""
    result = settings._strip_jsonc_comments(content)
    # After comment removal, the Windows path backslashes remain
    assert '"path": "C:\\\\Users\\\\test",' in result
    assert '"regex": "//pattern"' in result
    assert "// comment" not in result


def test_strip_jsonc_escaped_quotes():
    """Test handling of escaped quotes in strings."""
    content = r"""{
  "text": "say \"hello\"", // comment after
  "empty": ""
}"""
    result = settings._strip_jsonc_comments(content)
    assert '"text": "say \\"hello\\"",' in result
    assert "// comment after" not in result


def test_load_jsonc_file(tmp_path: Path):
    """Test loading settings from a JSONC file."""
    settings_file = tmp_path / "test_settings.jsonc"
    content = """{
  // This is a comment
  "UserAgent": "Custom Agent",
  "Timeout": 30,
  /* Block comment */
  "ParallelDownloads": 8
}"""
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(content)

    result = settings.load_settings(settings_file)

    assert result.user_agent == "Custom Agent"
    assert result.timeout == 30
    assert result.parallel_downloads == 8


def test_load_jsonc_filters_underscore_keys(tmp_path: Path):
    """Test that keys starting with _ are filtered out (backwards compat)."""
    settings_file = tmp_path / "old_style.jsonc"
    content = """{
  "_comment": "This is an old-style comment key",
  "_internal": "should be filtered",
  "UserAgent": "Keep this",
  "Timeout": 15
}"""
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(content)

    result = settings.load_settings(settings_file)

    assert result.user_agent == "Keep this"
    assert result.timeout == 15


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
    assert result.timeout == 99


def test_load_json_fallback_when_no_jsonc(tmp_path: Path, monkeypatch):
    """Test that .json is used when .jsonc doesn't exist."""
    json_file = tmp_path / "settings.json"
    json_content = '{"Timeout": 77}'

    with open(json_file, "w", encoding="utf-8") as f:
        f.write(json_content)

    # Change to the temp directory
    monkeypatch.chdir(tmp_path)

    result = settings.load_settings(None)
    assert result.timeout == 77
