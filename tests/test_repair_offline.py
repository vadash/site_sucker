"""Tests for repair_offline module."""

from pathlib import Path

import pytest

from site_sucker import repair_offline


def test_repair_offline_html_removes_load_php(tmp_path: Path):
    """Test removal of MediaWiki load.php resources."""
    html_file = tmp_path / "test.html"
    original_html = '''<html>
<head>
    <link rel="stylesheet" href="https://example.com/load.php?modules=site">
    <script src="https://example.com/load.php?modules=jquery"></script>
</head>
</html>'''
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert "load.php" not in updated_content
    # Fallback style should be injected
    assert "<style>" in updated_content
    assert "font-family: Arial" in updated_content


def test_repair_offline_html_removes_preconnect(tmp_path: Path):
    """Test removal of preconnect and dns-prefetch hints."""
    html_file = tmp_path / "test.html"
    original_html = '''<html>
<head>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="dns-prefetch" href="https://cdn.example.com">
</head>
</html>'''
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert 'rel="preconnect"' not in updated_content
    assert 'rel="dns-prefetch"' not in updated_content


def test_repair_offline_html_removes_feeds(tmp_path: Path):
    """Test removal of RSS/Atom feed links."""
    html_file = tmp_path / "test.html"
    original_html = '''<html>
<head>
    <link rel="alternate" type="application/atom+xml" href="/feed.atom">
    <link rel="alternate" type="application/rss+xml" href="/feed.rss">
</head>
</html>'''
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert 'type="application/atom+xml"' not in updated_content
    assert 'type="application/rss+xml"' not in updated_content


def test_repair_offline_html_removes_tracking(tmp_path: Path):
    """Test removal of analytics and tracking scripts."""
    html_file = tmp_path / "test.html"
    original_html = '''<html>
<head>
    <script>
        var _paq = window._paq = window._paq || [];
        _paq.push(['trackPageView']);
    </script>
    <noscript>
        <img src="https://matomo.example.com/piwik.php?idsite=1" />
    </noscript>
</head>
</html>'''
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert "_paq" not in updated_content
    assert "trackPageView" not in updated_content
    assert "matomo" not in updated_content.lower()


def test_repair_offline_html_phpbb_links(tmp_path: Path):
    """Test removal of phpBB-specific offline-useless links."""
    html_file = tmp_path / "test.html"
    original_html = '''<html>
<body>
    <a href="posting.php?mode=reply">Reply</a>
    <a href="tradegold.php">Trade</a>
    <a href="memberlist.php">Members</a>
    <a href="search.php">Search</a>
    <a href="ucp.php">User CP</a>
    <a href="mcp.php">Mod CP</a>
</body>
</html>'''
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert 'href="posting.php' not in updated_content
    assert 'href="tradegold.php' not in updated_content
    assert 'href="memberlist.php' not in updated_content
    assert 'href="search.php' not in updated_content
    assert 'href="ucp.php' not in updated_content
    assert 'href="mcp.php' not in updated_content


def test_repair_offline_html_multiple_files(tmp_path: Path):
    """Test processing multiple HTML files."""
    (tmp_path / "page1.html").write_text(
        '<link rel="stylesheet" href="https://example.com/load.php?modules=site">'
    )
    (tmp_path / "page2.html").write_text(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
    )
    (tmp_path / "page3.htm").write_text(
        '<script>var _paq = window._paq || [];</script>'
    )

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 3
