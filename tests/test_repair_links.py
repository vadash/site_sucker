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


def test_repair_external_links_css_import_inlining(tmp_path: Path, capsys):
    """Test CSS @import inlining to avoid CORS."""
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()

    # Create imported CSS file
    imported_css = styles_dir / "colors.css"
    imported_css.write_text("body { color: red; }")

    # Create main CSS with @import
    main_css = styles_dir / "main.css"
    main_css.write_text('@import url("colors.css");\nbody { margin: 0; }')

    # No external URLs, just process CSS
    repair_links.repair_external_links(tmp_path, tmp_path / "images", set())

    # Check that @import was inlined
    updated_main = main_css.read_text()
    assert "@import" not in updated_main
    assert "body { color: red; }" in updated_main
    assert "/* Inlined from colors.css */" in updated_main


def test_repair_external_links_css_import_not_found(tmp_path: Path):
    """Test CSS @import with missing file is handled gracefully."""
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()

    main_css = styles_dir / "main.css"
    main_css.write_text('@import url("missing.css");\nbody { margin: 0; }')

    repair_links.repair_external_links(tmp_path, tmp_path / "images", set())

    updated_main = main_css.read_text()
    # Should leave a comment about missing file
    assert "/* @import \"missing.css\" - FILE NOT FOUND */" in updated_main


def test_repair_external_links_css_import_external_stripped(tmp_path: Path):
    """Test external CSS @import (http/https) is stripped."""
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()

    main_css = styles_dir / "main.css"
    main_css.write_text(
        '@import url("https://fonts.googleapis.com/css?family=Test");\n'
        '@import url("colors.css");\n'
        'body { margin: 0; }'
    )

    # Create local import
    (styles_dir / "colors.css").write_text("body { color: red; }")

    repair_links.repair_external_links(tmp_path, tmp_path / "images", set())

    updated_main = main_css.read_text()
    # External @import should be stripped
    assert "fonts.googleapis.com" not in updated_main
    # Local @import should be inlined
    assert "body { color: red; }" in updated_main


def test_repair_external_links_css_strip_google_fonts(tmp_path: Path, capsys):
    """Test Google Fonts @import stripping."""
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()

    main_css = styles_dir / "main.css"
    main_css.write_text(
        '@import url("https://fonts.googleapis.com/css?family=Source+Sans+Pro");\n'
        'body { font-family: Arial; }'
    )

    repair_links.repair_external_links(tmp_path, tmp_path / "images", set())

    updated_main = main_css.read_text()
    # Google Fonts import should be removed
    assert "fonts.googleapis.com" not in updated_main
    assert "Google Fonts @import stripped" in updated_main

    captured = capsys.readouterr()
    assert "Stripped 1 external font @import" in captured.out


def test_repair_external_links_css_strip_external_url(tmp_path: Path, capsys):
    """Test external url() in CSS is neutralized."""
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()

    main_css = styles_dir / "main.css"
    main_css.write_text(
        '.logo { background: url("https://www.median-xl.com/styles/img/logo.png"); }\n'
        'body { margin: 0; }'
    )

    repair_links.repair_external_links(tmp_path, tmp_path / "images", set())

    updated_main = main_css.read_text()
    # External URL should be replaced with about:blank
    assert "about:blank" in updated_main
    assert "External URL stripped" in updated_main

    captured = capsys.readouterr()
    assert "Neutralized 1 external url() reference" in captured.out


def test_repair_internal_links_absolute_urls(tmp_path: Path):
    """Test internal link rewriting with absolute URLs."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "Main_Page.html").write_text("<html><body>content</body></html>")

    html_file = wiki_dir / "index.html"
    html_file.write_text(
        '<html><body><a href="https://example.com/wiki/Main_Page.html">Link</a></body></html>'
    )

    result = repair_links.repair_internal_links(tmp_path, "example.com")
    assert result == 1

    updated = html_file.read_text()
    assert "Main_Page.html" in updated
    assert "https://example.com" not in updated


def test_repair_internal_links_relative_urls(tmp_path: Path):
    """Test internal link rewriting with relative URLs."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    (wiki_dir / "page.html").write_text("<html><body>content</body></html>")

    html_file = wiki_dir / "index.html"
    html_file.write_text(
        '<html><body><a href="/wiki/page.html">Link</a></body></html>'
    )

    result = repair_links.repair_internal_links(tmp_path, "example.com")
    assert result == 1

    updated = html_file.read_text()
    assert "page.html" in updated
    assert "/wiki/page.html" not in updated


def test_repair_internal_links_sibling_directories(tmp_path: Path):
    """Test internal link rewriting across sibling directories (relpath ../ navigation)."""
    wiki_dir = tmp_path / "wiki"
    forum_dir = tmp_path / "forum"
    wiki_dir.mkdir()
    forum_dir.mkdir()

    (forum_dir / "index.html").write_text("<html><body>forum</body></html>")

    # wiki/page.html links to forum/index.html (sibling directory)
    html_file = wiki_dir / "page.html"
    html_file.write_text(
        '<html><body><a href="https://example.com/forum/index.html">Forum</a></body></html>'
    )

    result = repair_links.repair_internal_links(tmp_path, "example.com")
    assert result == 1

    updated = html_file.read_text()
    assert "../forum/index.html" in updated
    assert "https://example.com" not in updated


def test_repair_internal_links_preserves_external_links(tmp_path: Path):
    """Test that external domain links are left unchanged."""
    html_file = tmp_path / "index.html"
    html_file.write_text(
        '<html><body><a href="https://other-domain.com/page.html">External</a></body></html>'
    )

    result = repair_links.repair_internal_links(tmp_path, "example.com")
    assert result == 0

    updated = html_file.read_text()
    assert "https://other-domain.com/page.html" in updated
