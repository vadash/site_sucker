"""Tests for report module."""

import logging
from datetime import datetime
from pathlib import Path

from site_sucker import report


def test_format_size_bytes():
    """Test formatting byte sizes."""
    assert report.format_size(100) == "100 bytes"
    assert report.format_size(1024) == "1.00 KB"
    assert report.format_size(1536) == "1.50 KB"
    assert report.format_size(1_048_576) == "1.00 MB"
    assert report.format_size(2_621_440) == "2.50 MB"
    assert report.format_size(1_073_741_824) == "1.00 GB"


def test_write_site_report_basic(tmp_path: Path, caplog):
    """Test basic report generation."""
    caplog.set_level(logging.INFO)
    # Create some test files
    (tmp_path / "test.txt").write_text("test content")

    start_time = datetime.now()

    report.write_site_report(tmp_path, start_time, None)

    assert "DOWNLOAD COMPLETE" in caplog.text
    assert "Total files:     1" in caplog.text
    assert "Failed downloads: 0" in caplog.text


def test_write_site_report_with_failures(tmp_path: Path, caplog):
    """Test report generation with failed URLs."""
    caplog.set_level(logging.INFO)
    (tmp_path / "test.txt").write_text("test content")

    failed_urls = [
        "https://example.com/missing1.png",
        "https://example.com/missing2.jpg",
    ]

    report.write_site_report(tmp_path, datetime.now(), failed_urls)

    assert "Failed downloads: 2" in caplog.text

    # Check that failures.log was created
    fail_log = tmp_path / "failures.log"
    assert fail_log.exists()
    log_content = fail_log.read_text()
    assert "https://example.com/missing1.png" in log_content
    assert "https://example.com/missing2.jpg" in log_content


def test_write_site_report_multiple_files(tmp_path: Path, caplog):
    """Test report with multiple files of different sizes."""
    caplog.set_level(logging.INFO)
    (tmp_path / "small.txt").write_text("x" * 100)
    (tmp_path / "large.txt").write_text("y" * 5000)

    report.write_site_report(tmp_path, datetime.now(), None)

    assert "Total files:     2" in caplog.text
    # Should be around 5.10 KB
    assert "KB" in caplog.text
