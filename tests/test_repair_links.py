"""Tests for repair_links module."""

from pathlib import Path

import pytest

from site_sucker import repair_links


def test_repair_external_links_empty_urls(tmp_path: Path, capsys):
    """Test with no external URLs to rewrite."""
    result = repair_links.repair_external_links(
        tmp_path,
        tmp_path / "images",
        set(),
    )

    assert result == 0
    captured = capsys.readouterr()
    assert "No external URLs to rewrite" in captured.out


def test_repair_external_links_basic(tmp_path: Path, sample_html: str):
    """Test basic external link rewriting."""
    # Create HTML file with external links
    html_dir = tmp_path / "pages"
    html_dir.mkdir()
    html_file = html_dir / "test.html"
    html_file.write_text(sample_html)

    # Create media directory with downloaded files
    media_dir = tmp_path / "images"
    media_dir.mkdir()

    # Create dummy downloaded files
    (media_dir / "style.css").write_text("body { margin: 0; }")
    (media_dir / "script.js").write_text("console.log('test');")

    external_urls = {
        "https://cdn.example.com/style.css",
        "https://cdn.example.com/script.js",
    }

    result = repair_links.repair_external_links(
        tmp_path,
        media_dir,
        external_urls,
    )

    # Should have modified the HTML file
    assert result == 1

    # Check that links were rewritten
    updated_content = html_file.read_text()
    assert "../images/style.css" in updated_content
    assert "../images/script.js" in updated_content


def test_repair_external_links_strip_crossorigin(tmp_path: Path):
    """Test that crossorigin and integrity attributes are stripped."""
    html_dir = tmp_path / "pages"
    html_dir.mkdir()
    html_file = html_dir / "test.html"

    original_html = '''<html>
<head>
    <link rel="stylesheet" href="https://cdn.example.com/style.css"
          crossorigin="anonymous" integrity="sha384-abc">
</head>
</html>'''
    html_file.write_text(original_html)

    media_dir = tmp_path / "images"
    media_dir.mkdir()
    (media_dir / "style.css").write_text("body {}")

    external_urls = {"https://cdn.example.com/style.css"}

    repair_links.repair_external_links(tmp_path, media_dir, external_urls)

    updated_content = html_file.read_text()
    assert 'crossorigin=' not in updated_content
    assert 'integrity=' not in updated_content


def test_repair_external_links_css_absolute_paths(tmp_path: Path, sample_css: str):
    """Test CSS absolute path conversion."""
    css_dir = tmp_path / "css"
    css_dir.mkdir()
    css_file = css_dir / "style.css"
    css_file.write_text(sample_css)

    # No external URLs, but CSS should still be processed for absolute paths
    result = repair_links.repair_external_links(
        tmp_path,
        tmp_path / "images",
        set(),
    )

    # Check that absolute paths were converted to relative
    updated_css = css_file.read_text()
    # url('/images/bg.png') should be converted to relative
    assert "url('/images/bg.png')" not in updated_css


def test_repair_external_links_nested_directories(tmp_path: Path):
    """Test link rewriting in nested directory structure."""
    # Create nested structure
    deep_dir = tmp_path / "level1" / "level2" / "level3"
    deep_dir.mkdir(parents=True)

    html_file = deep_dir / "test.html"
    html_file.write_text('<img src="https://cdn.example.com/image.png">')

    media_dir = tmp_path / "images"
    media_dir.mkdir()
    (media_dir / "image.png").write_text("PNG data")

    external_urls = {"https://cdn.example.com/image.png"}

    repair_links.repair_external_links(tmp_path, media_dir, external_urls)

    updated_content = html_file.read_text()
    # Should go up 3 levels then into images
    assert "../../../images/image.png" in updated_content
