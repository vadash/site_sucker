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
