"""Tests for wget module."""

from pathlib import Path

import pytest

from site_sucker import wget


def test_get_wget_path_exists(sample_settings: dict, tmp_path: Path):
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


def test_build_wget_args_basic(sample_settings: dict):
    """Test building basic wget arguments."""
    args = wget.build_wget_args(sample_settings, "/tmp/output")

    assert "-e" in args
    assert "robots=off" in args
    assert "--no-proxy" in args
    assert "--no-verbose" in args
    assert "--level=inf" in args
    assert "--directory-prefix=/tmp/output" in args
    assert f"--user-agent={sample_settings['UserAgent']}" in args
    assert f"--timeout={sample_settings['Timeout']}" in args
    assert f"--tries={sample_settings['Retries']}" in args
    assert "--header=Accept-Encoding: identity" in args


def test_build_wget_args_with_max_depth(sample_settings: dict):
    """Test building wget arguments with a specific max depth."""
    sample_settings["MaxDepth"] = 4
    args = wget.build_wget_args(sample_settings, "/tmp/output")
    assert "--level=4" in args


def test_build_wget_args_with_wait(sample_settings: dict):
    """Test building wget arguments with wait between requests."""
    sample_settings["WaitBetweenRequests"] = 1.5
    args = wget.build_wget_args(sample_settings, "/tmp/output")

    assert "--wait=1.5" in args
    assert "--random-wait" in args


def test_build_wget_args_no_link_conversion(sample_settings: dict):
    """Test building wget arguments without link conversion."""
    args = wget.build_wget_args(
        sample_settings,
        "/tmp/output",
        no_link_conversion=True,
    )

    assert "--convert-links" not in args
    assert "--adjust-extension" not in args


def test_build_wget_args_with_link_conversion(sample_settings: dict):
    """Test building wget arguments with link conversion (default)."""
    args = wget.build_wget_args(sample_settings, "/tmp/output")

    assert "--convert-links" in args
    assert "--adjust-extension" in args


def test_build_wget_args_with_reject_patterns(sample_settings: dict):
    """Test building wget arguments with reject patterns."""
    args = wget.build_wget_args(sample_settings, "/tmp/output")

    # Should include reject regex for patterns
    assert "--reject-regex" in args
    # Should include forum-specific pattern with POSIX [0-9] not \d
    assert any("viewtopic\\.php.*&p=[0-9]+" in arg for arg in args)
    assert any("viewtopic\\.php\\?p=[0-9]+" in arg for arg in args)


def test_build_wget_args_extra_args(sample_settings: dict):
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
    settings = {
        "UserAgent": "Test",
        "Timeout": 10,
        "Retries": 2,
        "RejectPatterns": ["f=31&", "f=8&", "f=11&"],
        "RejectDomains": [],
    }

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
