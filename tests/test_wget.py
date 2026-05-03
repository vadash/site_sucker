"""Tests for wget module."""

from dataclasses import replace
from pathlib import Path

import pytest

from site_sucker import wget
from site_sucker.settings import Settings


def test_get_wget_path_exists(sample_settings: Settings, tmp_path: Path):
    """Test get_wget_path when wget.exe exists."""
    # Create a temporary bin directory with wget.exe
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wget_exe = bin_dir / "wget.exe"
    wget_exe.touch()

    # Temporarily change to the temp directory structure
    # We need to mock the __file__ path resolution
    # Since this is complex, we'll just test that the function works
    # when called from the actual project structure
    import site_sucker.wget as wget_module
    original_file = wget_module.__file__

    try:
        # Point to our temp directory
        fake_module_path = tmp_path / "src" / "site_sucker" / "wget.py"
        fake_module_path.parent.mkdir(parents=True, exist_ok=True)
        fake_module_path.touch()

        wget_module.__file__ = str(fake_module_path)

        result = wget.get_wget_path()
        assert result == wget_exe
    finally:
        wget_module.__file__ = original_file


def test_get_wget_path_not_found(tmp_path: Path):
    """Test get_wget_path when wget.exe doesn't exist."""
    import site_sucker.wget as wget_module
    original_file = wget_module.__file__

    try:
        # Create a directory structure without wget.exe
        fake_module_path = tmp_path / "src" / "site_sucker" / "wget.py"
        fake_module_path.parent.mkdir(parents=True, exist_ok=True)
        fake_module_path.touch()

        # Create bin directory but no wget.exe
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()

        wget_module.__file__ = str(fake_module_path)

        with pytest.raises(FileNotFoundError, match="wget.exe not found"):
            wget.get_wget_path()
    finally:
        wget_module.__file__ = original_file


def test_build_wget_args_basic(sample_settings: Settings):
    """Test building basic wget arguments."""
    args = wget.build_wget_args(sample_settings, "/tmp/output")

    assert "-e" in args
    assert "robots=off" in args
    assert "--no-proxy" in args
    assert "--no-verbose" in args
    assert "--level=inf" in args
    assert "--directory-prefix=/tmp/output" in args
    assert f"--user-agent={sample_settings.user_agent}" in args
    assert f"--timeout={sample_settings.timeout}" in args
    assert f"--tries={sample_settings.retries}" in args
    assert "--header=Accept-Encoding: identity" in args


def test_build_wget_args_with_max_depth(sample_settings: Settings):
    """Test building wget arguments with a specific max depth."""
    sample_settings = replace(sample_settings, max_depth=4)
    args = wget.build_wget_args(sample_settings, "/tmp/output")
    assert "--level=4" in args


def test_build_wget_args_with_wait(sample_settings: Settings):
    """Test building wget arguments with wait between requests."""
    sample_settings = replace(sample_settings, wait_between_requests=1.5)
    args = wget.build_wget_args(sample_settings, "/tmp/output")

    assert "--wait=1.5" in args
    assert "--random-wait" in args


def test_build_wget_args_no_link_conversion(sample_settings: Settings):
    """Test building wget arguments without link conversion."""
    args = wget.build_wget_args(
        sample_settings,
        "/tmp/output",
        no_link_conversion=True,
    )

    assert "--convert-links" not in args
    assert "--adjust-extension" not in args


def test_build_wget_args_with_link_conversion(sample_settings: Settings):
    """Test building wget arguments with link conversion (default)."""
    args = wget.build_wget_args(sample_settings, "/tmp/output")

    assert "--convert-links" in args
    assert "--adjust-extension" in args


def test_build_wget_args_with_reject_patterns(sample_settings: Settings):
    """Test building wget arguments with reject patterns."""
    args = wget.build_wget_args(sample_settings, "/tmp/output")

    # Should include reject regex for patterns
    assert "--reject-regex" in args
    # Should include forum-specific pattern with POSIX [0-9] not \d
    assert any("viewtopic\\.php.*&p=[0-9]+" in arg for arg in args)
    assert any("viewtopic\\.php\\?p=[0-9]+" in arg for arg in args)


def test_build_wget_args_with_phpbb_sort_and_sid_patterns():
    """Test that phpBB sort and session ID reject patterns are included."""
    settings = Settings(
        user_agent="Test",
        timeout=10,
        retries=2,
        reject_patterns=["&sk=", "&sd=", "&st=", "&sid="],
        reject_domains=[],
    )

    args = wget.build_wget_args(settings, "/tmp/output")

    # Should include reject regex
    assert "--reject-regex" in args

    # The patterns should be present in the combined regex
    reject_regex_args = [args[i + 1] for i, arg in enumerate(args) if arg == "--reject-regex"]
    combined_regex = " ".join(reject_regex_args)

    # Verify each phpBB pattern is present
    assert "&sk=" in combined_regex
    assert "&sd=" in combined_regex
    assert "&st=" in combined_regex
    assert "&sid=" in combined_regex


def test_build_wget_args_extra_args(sample_settings: Settings):
    """Test building wget arguments with extra arguments."""
    args = wget.build_wget_args(
        sample_settings,
        "/tmp/output",
        extra_args=["-r", "-N", "--no-remove-listing", "--no-parent"],
    )

    assert "-r" in args
    assert "-N" in args
    assert "--no-remove-listing" in args
    assert "--no-parent" in args


def test_build_wget_args_with_extra_reject_patterns():
    """Test that extra reject patterns from CLI are included in wget args."""
    settings = Settings(
        user_agent="Test",
        timeout=10,
        retries=2,
        reject_patterns=["f=31&", "f=8&", "f=11&"],
        reject_domains=[],
    )

    args = wget.build_wget_args(settings, "/tmp/output")

    # The patterns should be combined into a reject-regex
    reject_regex_args = [args[i + 1] for i, arg in enumerate(args) if arg == "--reject-regex"]

    # Should have at least one --reject-regex argument
    assert len(reject_regex_args) >= 1

    # The patterns should be present in the combined regex
    combined_regex = " ".join(reject_regex_args)
    assert "f=31&" in combined_regex
    assert "f=8&" in combined_regex
    assert "f=11&" in combined_regex


def test_get_clean_env_removes_proxy_vars(monkeypatch):
    """Test that get_clean_env removes proxy environment variables."""
    # Set some proxy environment variables
    monkeypatch.setenv("http_proxy", "http://proxy.example.com:8080")
    monkeypatch.setenv("https_proxy", "https://proxy.example.com:8080")
    monkeypatch.setenv("all_proxy", "socks5://proxy.example.com:1080")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.com:8080")
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy.example.com:8080")

    env = wget.get_clean_env()

    # All proxy variables should be removed
    assert "http_proxy" not in env
    assert "https_proxy" not in env
    assert "all_proxy" not in env
    assert "HTTP_PROXY" not in env
    assert "HTTPS_PROXY" not in env

    # Other environment variables should be preserved
    assert "PATH" in env


def test_get_clean_env_preserves_other_env(monkeypatch):
    """Test that get_clean_env preserves non-proxy environment variables."""
    monkeypatch.setenv("CUSTOM_VAR", "custom_value")

    env = wget.get_clean_env()

    assert env.get("CUSTOM_VAR") == "custom_value"


def test_get_clean_env_returns_copy():
    """Test that get_clean_env returns a copy of the environment."""

    env1 = wget.get_clean_env()
    env2 = wget.get_clean_env()

    # Modifying one should not affect the other
    env1["TEST_VAR"] = "test_value"
    assert "TEST_VAR" not in env2

