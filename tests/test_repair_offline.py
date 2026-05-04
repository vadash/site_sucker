"""Tests for repair_offline module."""

from pathlib import Path

from site_sucker import repair_offline


def test_repair_offline_html_removes_load_php(tmp_path: Path):
    """Test removal of MediaWiki load.php resources."""
    html_file = tmp_path / "test.html"
    original_html = """<html>
<head>
    <link rel="stylesheet" href="https://example.com/load.php?modules=site">
    <script src="https://example.com/load.php?modules=jquery"></script>
</head>
</html>"""
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
    original_html = """<html>
<head>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="dns-prefetch" href="https://cdn.example.com">
</head>
</html>"""
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert 'rel="preconnect"' not in updated_content
    assert 'rel="dns-prefetch"' not in updated_content


def test_repair_offline_html_removes_feeds(tmp_path: Path):
    """Test removal of RSS/Atom feed links."""
    html_file = tmp_path / "test.html"
    original_html = """<html>
<head>
    <link rel="alternate" type="application/atom+xml" href="/feed.atom">
    <link rel="alternate" type="application/rss+xml" href="/feed.rss">
</head>
</html>"""
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert 'type="application/atom+xml"' not in updated_content
    assert 'type="application/rss+xml"' not in updated_content


def test_repair_offline_html_removes_tracking(tmp_path: Path):
    """Test removal of analytics and tracking scripts."""
    html_file = tmp_path / "test.html"
    original_html = """<html>
<head>
    <script>
        var _paq = window._paq = window._paq || [];
        _paq.push(['trackPageView']);
    </script>
    <noscript>
        <img src="https://matomo.example.com/piwik.php?idsite=1" />
    </noscript>
</head>
</html>"""
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
    original_html = """<html>
<body>
    <a href="posting.php?mode=reply">Reply</a>
    <a href="tradegold.php">Trade</a>
    <a href="memberlist.php">Members</a>
    <a href="search.php">Search</a>
    <a href="ucp.php">User CP</a>
    <a href="mcp.php">Mod CP</a>
</body>
</html>"""
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
    (tmp_path / "page3.htm").write_text("<script>var _paq = window._paq || [];</script>")

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 3


def test_repair_offline_html_removes_fontawesome_loader(tmp_path: Path):
    """Test removal of FontAwesome CDN loader script."""
    html_file = tmp_path / "test.html"
    original_html = """<html>
<head>
    <script src='images/9a832b96e0.js'></script>
    <link rel="stylesheet" href="https://use.fontawesome.com/9a832b96e0.css">
</head>
</html>"""
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    # FontAwesome loader script should be removed
    assert "9a832b96e0.js" not in updated_content
    # External FA CSS link should be removed (no crossorigin attribute in this case)
    assert "use.fontawesome.com" not in updated_content


def test_repair_offline_html_removes_fontawesome_config(tmp_path: Path):
    """Test removal of window.FontAwesomeCdnConfig."""
    html_file = tmp_path / "test.html"
    original_html = """<html>
<head>
    <script>
    window.FontAwesomeCdnConfig = {
        autoA11y: { enabled: true },
        useUrl: "use.fontawesome.com"
    };
    </script>
</head>
</html>"""
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert "FontAwesomeCdnConfig" not in updated_content


def test_repair_offline_html_removes_google_analytics(tmp_path: Path):
    """Test removal of Google Analytics bootstrap script."""
    html_file = tmp_path / "test.html"
    original_html = """<html>
<head>
    <script>(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
    (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
    m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
    })(window,document,'script','//www.google-analytics.com/analytics.js','ga');</script>
    <script>ga('create', 'UA-12345', 'auto');</script>
    <script>ga('send', 'pageview');</script>
</head>
</html>"""
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    # GA bootstrap should be removed
    assert "GoogleAnalyticsObject" not in updated_content
    assert "google-analytics.com/analytics.js" not in updated_content
    # GA calls should be removed
    assert "ga('create'" not in updated_content
    assert "ga('send'" not in updated_content


def test_repair_offline_html_preserves_local_load_php(tmp_path: Path):
    """Test that wget-converted local load.php references are preserved."""
    html_file = tmp_path / "test.html"
    original_html = """<html>
<head>
    <link rel="stylesheet" href="../w/load.php%3Fmodules%3Dsite">
    <script src="load.php@modules=jquery"></script>
</head>
</html>"""
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    # Local load.php references should be preserved
    assert "load.php%3Fmodules%3Dsite" in updated_content
    assert "load.php@modules=jquery" in updated_content


def test_repair_offline_html_removes_mixed_tracking(tmp_path: Path):
    """Test removal of both Matomo and Google Analytics."""
    html_file = tmp_path / "test.html"
    original_html = """<html>
<head>
    <script>
        var _paq = window._paq || [];
        _paq.push(['trackPageView']);
    </script>
    <script>(function(i,s,o,g,r,a,m){...})
    ('window,document,'script','//www.google-analytics.com/analytics.js','ga');</script>
    <script src='images/9a832b96e0.js'></script>
</head>
</html>"""
    html_file.write_text(original_html)

    result = repair_offline.repair_offline_html(tmp_path)

    assert result == 1

    updated_content = html_file.read_text()
    assert "_paq" not in updated_content
    assert "google-analytics.com" not in updated_content
    assert "9a832b96e0.js" not in updated_content
