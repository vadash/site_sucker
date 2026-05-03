"""Tests for __main__.py module."""

import argparse
from pathlib import Path
from urllib.parse import urlparse

import pytest

from site_sucker import settings
from site_sucker.__main__ import normalize_url, parse_args, resolve_config


class TestNormalizeUrl:
    """Tests for normalize_url() function."""

    def test_adds_https_to_plain_url(self):
        """Test that https:// is added to URL without scheme."""
        assert normalize_url("example.com") == "https://example.com"
        assert normalize_url("example.com/page") == "https://example.com/page"

    def test_preserves_existing_http_scheme(self):
        """Test that existing http:// scheme is preserved."""
        assert normalize_url("http://example.com") == "http://example.com"

    def test_preserves_existing_https_scheme(self):
        """Test that existing https:// scheme is preserved."""
        assert normalize_url("https://example.com") == "https://example.com"


class TestParseArgs:
    """Tests for parse_args() function."""

    def test_default_values(self):
        """Test that default argument values are correct."""
        # Simulate no command-line arguments
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["site-sucker"]
            args = parse_args()
            assert args.url is None
            assert args.output_dir is None
            assert args.settings_path is None
            assert args.depth == 0
            assert args.parallel == 4
            assert args.extra_reject is None
            assert args.resume is False
        finally:
            sys.argv = old_argv

    def test_url_provided(self):
        """Test parsing with URL provided."""
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["site-sucker", "https://example.com"]
            args = parse_args()
            assert args.url == "https://example.com"
        finally:
            sys.argv = old_argv

    def test_all_options(self):
        """Test parsing with all options provided."""
        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "site-sucker",
                "https://example.com",
                "-o", "custom_output",
                "-s", "custom_settings.json",
                "-d", "5",
                "-p", "8",
                "-r", "action=",
                "-r", "Special:",
                "--resume"
            ]
            args = parse_args()
            assert args.url == "https://example.com"
            assert args.output_dir == "custom_output"
            assert args.settings_path == "custom_settings.json"
            assert args.depth == 5
            assert args.parallel == 8
            assert args.extra_reject == ["action=", "Special:"]
            assert args.resume is True
        finally:
            sys.argv = old_argv


class TestResolveConfig:
    """Tests for resolve_config() function."""

    def test_url_with_output_dir(self, tmp_path: Path):
        """Test resolution with URL and explicit output directory."""
        args = argparse.Namespace(
            url="https://example.com",
            output_dir=str(tmp_path / "custom_output"),
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root="./downloads",
            parallel_downloads=4,
            max_depth=0,
        )

        url, output_path, target_domain, updated_cfg = resolve_config(args, cfg)

        assert url == "https://example.com"
        assert target_domain == "example.com"
        assert output_path == tmp_path / "custom_output"
        assert output_path.exists()
        assert updated_cfg == cfg

    def test_url_without_output_dir(self, tmp_path: Path):
        """Test resolution with URL but no output directory (uses default)."""
        args = argparse.Namespace(
            url="https://example.com",
            output_dir=None,
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root=str(tmp_path),
            parallel_downloads=4,
            max_depth=0,
        )

        url, output_path, target_domain, updated_cfg = resolve_config(args, cfg)

        assert url == "https://example.com"
        assert target_domain == "example.com"
        assert output_path == tmp_path / "example.com"
        assert output_path.exists()
        assert updated_cfg == cfg

    def test_url_normalization(self, tmp_path: Path):
        """Test that URL scheme is normalized to https."""
        args = argparse.Namespace(
            url="example.com/page.html",
            output_dir=None,
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root=str(tmp_path),
            parallel_downloads=4,
            max_depth=0,
        )

        url, output_path, target_domain, _ = resolve_config(args, cfg)

        assert url == "https://example.com/page.html"
        assert target_domain == "example.com"

    def test_http_url_preserved(self, tmp_path: Path):
        """Test that http:// URL scheme is preserved."""
        args = argparse.Namespace(
            url="http://example.com",
            output_dir=None,
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root=str(tmp_path),
            parallel_downloads=4,
            max_depth=0,
        )

        url, output_path, target_domain, _ = resolve_config(args, cfg)

        assert url == "http://example.com"

    def test_invalid_url_with_empty_hostname_raises_system_exit(self, tmp_path: Path):
        """Test that URL without hostname raises SystemExit."""
        args = argparse.Namespace(
            url="https://",  # Valid URL format but empty hostname
            output_dir=None,
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root=str(tmp_path),
            parallel_downloads=4,
            max_depth=0,
        )

        with pytest.raises(SystemExit):
            resolve_config(args, cfg)

    def test_url_without_domain_raises_system_exit(self, tmp_path: Path):
        """Test that URL without domain raises SystemExit."""
        args = argparse.Namespace(
            url="https://",
            output_dir=None,
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root=str(tmp_path),
            parallel_downloads=4,
            max_depth=0,
        )

        with pytest.raises(SystemExit):
            resolve_config(args, cfg)

    def test_output_path_is_absolute(self, tmp_path: Path):
        """Test that output path is resolved to absolute path."""
        args = argparse.Namespace(
            url="https://example.com",
            output_dir="relative/path/output",
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root="./downloads",
            parallel_downloads=4,
            max_depth=0,
        )

        _, output_path, _, _ = resolve_config(args, cfg)

        # Should be an absolute path
        assert output_path.is_absolute()
        # Should resolve the relative path
        assert "relative" in str(output_path)
        assert "path" in str(output_path)
        assert "output" in str(output_path)

    def test_interactive_mode_requires_url(self, tmp_path: Path, monkeypatch):
        """Test that interactive mode (no URL) requires user input."""
        args = argparse.Namespace(
            url=None,
            output_dir=None,
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root=str(tmp_path),
            parallel_downloads=4,
            max_depth=0,
        )

        # Mock input to provide URL, output dir, depth, and parallel
        # The function prompts for these values in order
        inputs = ["https://example.com", "", "", ""]
        mock_input = lambda x: inputs.pop(0) if inputs else ""
        monkeypatch.setattr("builtins.input", mock_input)

        url, output_path, target_domain, _ = resolve_config(args, cfg)

        assert url == "https://example.com"
        assert target_domain == "example.com"

    def test_complex_url_with_port_and_path(self, tmp_path: Path):
        """Test URL with port number and path."""
        args = argparse.Namespace(
            url="https://example.com:8080/wiki/Main_Page",
            output_dir=None,
            settings_path=None,
            parallel=4,
            depth=0,
            extra_reject=None,
            resume=False,
        )
        cfg = settings.Settings(
            output_root=str(tmp_path),
            parallel_downloads=4,
            max_depth=0,
        )

        url, output_path, target_domain, _ = resolve_config(args, cfg)

        assert url == "https://example.com:8080/wiki/Main_Page"
        assert target_domain == "example.com"
