"""Tests for mirror module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from site_sucker.settings import Settings
from site_sucker.wget import build_wget_args


def test_pass2_includes_nc_flag(sample_settings: Settings, tmp_path: Path):
    """Test that Pass 2 (media download) includes -nc flag for resume support."""
    # Verify that build_wget_args with no_link_conversion=True includes -nc
    pass2_args = build_wget_args(
        sample_settings,
        tmp_path / "images",
        no_link_conversion=True,
        extra_args=[
            "--level=1",
            "--no-directories",
            "-nc",
        ],
    )

    # Verify -nc is present
    assert "-nc" in pass2_args


@patch("site_sucker.crawler.subprocess.run")
@patch("site_sucker.crawler.get_wget_path")
def test_wget_crawler_used_when_resume_false(
    mock_get_wget_path: MagicMock,
    mock_subprocess_run: MagicMock,
    sample_settings: Settings,
    tmp_path: Path,
):
    """Test that WgetCrawler is used when resume=False."""
    from site_sucker.crawler import WgetCrawler

    # Mock wget path and subprocess
    mock_get_wget_path.return_value = tmp_path / "wget.exe"
    mock_subprocess_run.return_value = MagicMock(returncode=0)

    crawler = WgetCrawler(
        url="https://example.com",
        output_dir=tmp_path,
        target_domain="example.com",
        settings=sample_settings,
    )

    result = crawler.run()

    # Verify result indicates no internal link repair needed
    assert not result.needs_internal_link_repair
    assert result.failed_urls == []


@patch("site_sucker.crawler.bfs_crawl_loop")
def test_bfs_crawler_used_when_resume_true(
    mock_bfs_crawl_loop: MagicMock,
    sample_settings: Settings,
    tmp_path: Path,
):
    """Test that BFSCrawler is used when resume=True."""
    from site_sucker.crawler import BFSCrawler

    crawler = BFSCrawler(
        url="https://example.com",
        output_dir=tmp_path,
        target_domain="example.com",
        settings=sample_settings,
    )

    result = crawler.run()

    # Verify bfs_crawl_loop was called
    mock_bfs_crawl_loop.assert_called_once()

    # Verify result indicates internal link repair is needed
    assert result.needs_internal_link_repair
    assert result.failed_urls == []
