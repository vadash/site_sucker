"""Tests for report module."""

from datetime import datetime
from pathlib import Path

import pytest

from site_sucker import report


def test_format_size_bytes():
    """Test formatting byte sizes."""
    assert report.format_size(100) == "100 bytes"
    assert report.format_size(1024) == "1.00 KB"
    assert report.format_size(1536) == "1.50 KB"
    assert report.format_size(1_048_576) == "1.00 MB"
    assert report.format_size(2_621_440) == "2.50 MB"
    assert report.format_size(1_073_741_824) == "1.00 GB"


def test_write_site_report_basic(tmp_path: Path, capsys):
    """Test basic report generation."""
    # Create some test files
    (tmp_path / "test.txt").write_text("test content")

    start_time = datetime.now()

    report.write_site_report(tmp_path, start_time, None)

    captured = capsys.readouterr()
    assert "DOWNLOAD COMPLETE" in captured.out
    assert "Total files:     1" in captured.out
    assert "Failed downloads: 0" in captured.out


def test_write_site_report_with_failures(tmp_path: Path, capsys):
    """Test report generation with failed URLs."""
    (tmp_path / "test.txt").write_text("test content")

    failed_urls = [
        "https://example.com/missing1.png",
        "https://example.com/missing2.jpg",
    ]

    report.write_site_report(tmp_path, datetime.now(), failed_urls)

    captured = capsys.readouterr()
    assert "Failed downloads: 2" in captured.out

    # Check that failures.log was created
    fail_log = tmp_path / "failures.log"
    assert fail_log.exists()
    log_content = fail_log.read_text()
    assert "https://example.com/missing1.png" in log_content
    assert "https://example.com/missing2.jpg" in log_content


def test_write_site_report_multiple_files(tmp_path: Path, capsys):
    """Test report with multiple files of different sizes."""
    (tmp_path / "small.txt").write_text("x" * 100)
    (tmp_path / "large.txt").write_text("y" * 5000)

    report.write_site_report(tmp_path, datetime.now(), None)

    captured = capsys.readouterr()
    assert "Total files:     2" in captured.out
    # Should be around 5.10 KB
    assert "KB" in captured.out
