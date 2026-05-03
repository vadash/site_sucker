"""Tests for file_iter module."""

from pathlib import Path

import pytest

from site_sucker.file_iter import write_if_changed


def test_write_if_changed_writes_when_content_differs(tmp_path: Path):
    """Test that write_if_changed writes when content differs."""
    test_file = tmp_path / "test.txt"
    original = "original content"
    new_content = "new content"

    # Write original content
    test_file.write_text(original, encoding="utf-8")

    # Call write_if_changed with different content
    result = write_if_changed(test_file, original, new_content)

    # Should return True (file was written)
    assert result is True

    # File should contain new content
    assert test_file.read_text(encoding="utf-8") == new_content


def test_write_if_changed_skips_when_content_same(tmp_path: Path):
    """Test that write_if_changed skips writing when content is the same."""
    test_file = tmp_path / "test.txt"
    content = "same content"

    # Write original content
    test_file.write_text(content, encoding="utf-8")

    # Get original modification time
    original_mtime = test_file.stat().st_mtime

    # Call write_if_changed with same content
    result = write_if_changed(test_file, content, content)

    # Should return False (file was not written)
    assert result is False

    # File should still have same content
    assert test_file.read_text(encoding="utf-8") == content

    # Modification time should not have changed
    # (Note: this might be flaky on systems with low mtime resolution)
    assert test_file.stat().st_mtime == original_mtime


def test_write_if_changed_creates_new_file(tmp_path: Path):
    """Test that write_if_changed creates a new file if it doesn't exist."""
    test_file = tmp_path / "new_file.txt"
    original = ""  # File doesn't exist, so original is empty
    new_content = "new file content"

    # Call write_if_changed for non-existent file
    result = write_if_changed(test_file, original, new_content)

    # Should return True (file was written)
    assert result is True

    # File should exist with new content
    assert test_file.exists()
    assert test_file.read_text(encoding="utf-8") == new_content


def test_write_if_changed_with_unicode(tmp_path: Path):
    """Test that write_if_changed handles Unicode content correctly."""
    test_file = tmp_path / "unicode.txt"
    original = "Original with émojis 🎉"
    new_content = "New with ünicode 🚀"

    # Write original content
    test_file.write_text(original, encoding="utf-8")

    # Call write_if_changed with different Unicode content
    result = write_if_changed(test_file, original, new_content)

    # Should return True (file was written)
    assert result is True

    # File should contain new Unicode content
    assert test_file.read_text(encoding="utf-8") == new_content


def test_write_if_changed_with_newlines(tmp_path: Path):
    """Test that write_if_changed preserves newline handling."""
    test_file = tmp_path / "newlines.txt"
    original = "line1\nline2\nline3"
    new_content = "line1\nline2\nline3\nline4"

    # Write original content
    test_file.write_text(original, encoding="utf-8")

    # Call write_if_changed with content with different newlines
    result = write_if_changed(test_file, original, new_content)

    # Should return True (file was written)
    assert result is True

    # File should contain new content with preserved newlines
    assert test_file.read_text(encoding="utf-8") == new_content
