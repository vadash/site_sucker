"""Tests for resume module (Python BFS crawler)."""

from pathlib import Path

import pytest

from site_sucker.resume import (
    crawl_loop,
    discover_links,
    file_exists_on_disk,
    resolve_local_file,
    url_to_filepath,
)


def test_url_to_filepath_basic():
    """Test basic URL to filepath conversion."""
    output_dir = Path("/downloads")

    # Simple URL
    result = url_to_filepath("https://example.com/page.html", output_dir)
    assert result == Path("/downloads/page.html")

    # URL with leading slash in path
    result = url_to_filepath("https://example.com/wiki/Main_Page", output_dir)
    assert result == Path("/downloads/wiki/Main_Page")


def test_url_to_filepath_root_url():
    """Test root URL is mapped to index.html."""
    output_dir = Path("/downloads")

    # Root URL
    result = url_to_filepath("https://example.com/", output_dir)
    assert result == Path("/downloads/index.html")

    # Bare domain (no trailing slash)
    result = url_to_filepath("https://example.com", output_dir)
    assert result == Path("/downloads/index.html")


def test_url_to_filepath_trailing_slash():
    """Test trailing-slash URL is mapped to index.html."""
    output_dir = Path("/downloads")

    result = url_to_filepath("https://example.com/wiki/", output_dir)
    assert result == Path("/downloads/wiki/index.html")


def test_url_to_filepath_with_query():
    """Test URL with query parameters (? becomes @)."""
    output_dir = Path("/downloads")

    # URL with query params - ? becomes @
    result = url_to_filepath("https://example.com/viewtopic.php?f=40&t=123", output_dir)
    assert result == Path("/downloads/viewtopic.php@f=40&t=123")


def test_url_to_filepath_with_fragment():
    """Test URL with fragment is stripped."""
    output_dir = Path("/downloads")

    # Fragment should be stripped
    result = url_to_filepath("https://example.com/page.html#section", output_dir)
    assert result == Path("/downloads/page.html")


def test_url_to_filepath_slash_escaping_in_query():
    """Test that slashes in query params are escaped to %2F."""
    output_dir = Path("/downloads")

    # URL with / in query params (should escape to avoid directory creation)
    result = url_to_filepath("https://example.com/search?q=test/term", output_dir)
    assert result == Path("/downloads/search@q=test%2Fterm")


def test_file_exists_on_disk_exact_match(tmp_path):
    """Test file existence check with exact match."""
    # Create test file
    test_file = tmp_path / "page.html"
    test_file.write_text("<html>test</html>")

    assert file_exists_on_disk(test_file) is True


def test_file_exists_on_disk_html_appended(tmp_path):
    """Test file existence check with .html appended (wget behavior)."""
    # Create file with .html extension
    test_file = tmp_path / "page.html"
    test_file.write_text("<html>test</html>")

    # Check base path without .html
    base_path = tmp_path / "page"
    assert file_exists_on_disk(base_path) is True


def test_file_exists_on_disk_not_found(tmp_path):
    """Test file existence check when file doesn't exist."""
    base_path = tmp_path / "nonexistent"
    assert file_exists_on_disk(base_path) is False


def test_resolve_local_file_exact_match(tmp_path):
    """Test resolve_local_file returns exact match."""
    test_file = tmp_path / "page.html"
    test_file.write_text("<html>test</html>")

    result = resolve_local_file(test_file)
    assert result == test_file


def test_resolve_local_file_html_appended(tmp_path):
    """Test resolve_local_file finds .html appended version."""
    test_file = tmp_path / "page.html"
    test_file.write_text("<html>test</html>")

    base_path = tmp_path / "page"
    result = resolve_local_file(base_path)
    assert result == test_file


def test_resolve_local_file_not_found(tmp_path):
    """Test resolve_local_file returns None when not found."""
    base_path = tmp_path / "nonexistent"
    assert resolve_local_file(base_path) is None


def test_discover_links_basic(tmp_path, sample_html):
    """Test basic link discovery from HTML."""
    html_file = tmp_path / "test.html"
    html_file.write_text(sample_html)

    links = discover_links(
        html_file,
        base_url="https://example.com/test.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    # Should find the internal link but not external or cdn links
    assert "https://example.com/page.html" in links
    assert "https://external.com/page.html" not in links
    assert "https://cdn.example.com/style.css" not in links


def test_discover_links_reject_patterns(tmp_path, sample_html):
    """Test that reject patterns filter out links."""
    html_file = tmp_path / "test.html"
    html_file.write_text(sample_html)

    links = discover_links(
        html_file,
        base_url="https://example.com/test.html",
        target_domain="example.com",
        reject_patterns=["page.html"],  # Reject this specific page
        reject_domains=[],
    )

    # Should be filtered out by reject pattern
    assert "https://example.com/page.html" not in links


def test_discover_links_reject_domains(tmp_path, sample_html):
    """Test that reject domains filter out links."""
    html_file = tmp_path / "test.html"
    html_file.write_text(sample_html)

    links = discover_links(
        html_file,
        base_url="https://example.com/test.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=["example.com"],  # Reject the entire domain
    )

    # Should be filtered out by reject domain
    assert "https://example.com/page.html" not in links


def test_discover_links_non_http(tmp_path):
    """Test that non-HTTP links are skipped."""
    html = """<html>
        <a href="mailto:test@example.com">Email</a>
        <a href="javascript:void(0)">JS</a>
        <a href="#section">Anchor</a>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/test.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    # Should be empty - no valid http/https links
    assert len(links) == 0


def test_discover_links_relative(tmp_path):
    """Test that relative links are resolved using base_url."""
    html = """<html>
        <a href="/wiki/Main_Page">Absolute relative</a>
        <a href="subpage.html">Relative to current</a>
        <a href="../parent.html">Parent relative</a>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/wiki/index.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    assert "https://example.com/wiki/Main_Page" in links
    assert "https://example.com/wiki/subpage.html" in links
    assert "https://example.com/parent.html" in links


def test_discover_links_mixed_absolute_and_relative(tmp_path):
    """Test that both absolute and relative links are discovered."""
    html = """<html>
        <a href="https://example.com/absolute.html">Absolute</a>
        <a href="/root-relative.html">Root relative</a>
        <a href="relative.html">Relative</a>
        <a href="https://other-domain.com/page.html">External</a>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/dir/page.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    assert "https://example.com/absolute.html" in links
    assert "https://example.com/root-relative.html" in links
    assert "https://example.com/dir/relative.html" in links
    assert "https://other-domain.com/page.html" not in links


def test_discover_links_fragment_normalization(tmp_path):
    """Test that fragments are stripped for link normalization."""
    html = """<html>
        <a href="https://example.com/page.html#section1">Link 1</a>
        <a href="https://example.com/page.html#section2">Link 2</a>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/test.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    # Should have only one link (fragments stripped)
    assert len(links) == 1
    assert "https://example.com/page.html" in links


def test_discover_links_page_requisites_images(tmp_path):
    """Test that <img> src URLs are discovered as page requisites."""
    html = """<html>
        <body>
            <img src="/images/sword.png" alt="Sword">
            <img src="https://example.com/images/shield.jpg" alt="Shield">
            <img src="https://other.com/image.png" alt="External">
        </body>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/wiki/page.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    assert "https://example.com/images/sword.png" in links
    assert "https://example.com/images/shield.jpg" in links
    assert "https://other.com/image.png" not in links


def test_discover_links_page_requisites_scripts(tmp_path):
    """Test that <script> src URLs are discovered as page requisites."""
    html = """<html>
        <head>
            <script src="/js/app.js"></script>
            <script src="https://example.com/js/vendor.js"></script>
            <script src="https://cdn.other.com/lib.js"></script>
        </head>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/page.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    assert "https://example.com/js/app.js" in links
    assert "https://example.com/js/vendor.js" in links
    assert "https://cdn.other.com/lib.js" not in links


def test_discover_links_page_requisites_stylesheet(tmp_path):
    """Test that <link> href URLs are discovered as page requisites."""
    html = """<html>
        <head>
            <link rel="stylesheet" href="/css/style.css">
            <link rel="stylesheet" href="https://example.com/css/theme.css">
            <link rel="preconnect" href="https://fonts.googleapis.com">
        </head>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/page.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    assert "https://example.com/css/style.css" in links
    assert "https://example.com/css/theme.css" in links
    # External preconnect link should not be included (different domain)
    assert "https://fonts.googleapis.com" not in links


def test_discover_links_page_requisites_video_audio_source(tmp_path):
    """Test that <video>, <audio>, <source> URLs are discovered."""
    html = """<html>
        <body>
            <video src="/videos/intro.mp4"></video>
            <audio src="/audio/podcast.mp3"></audio>
            <video>
                <source src="/videos/trailer.webm" type="video/webm">
            </video>
        </body>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/page.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    assert "https://example.com/videos/intro.mp4" in links
    assert "https://example.com/audio/podcast.mp3" in links
    assert "https://example.com/videos/trailer.webm" in links


def test_discover_links_skips_data_urls(tmp_path):
    """Test that data: URLs are not added to the crawl queue."""
    html = """<html>
        <body>
            <img src="data:image/png;base64,iVBOR...">
            <img src="/images/real.png" alt="Real">
        </body>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/page.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    assert len(links) == 1
    assert "https://example.com/images/real.png" in links


def test_discover_links_data_src_attribute(tmp_path):
    """Test that data-src attributes (lazy-loaded images) are discovered."""
    html = """<html>
        <body>
            <img data-src="/images/lazy.png" alt="Lazy loaded">
            <img data-src="https://example.com/images/lazy2.jpg" alt="Another lazy">
        </body>
    </html>"""

    html_file = tmp_path / "test.html"
    html_file.write_text(html)

    links = discover_links(
        html_file,
        base_url="https://example.com/page.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    assert "https://example.com/images/lazy.png" in links
    assert "https://example.com/images/lazy2.jpg" in links


def test_discover_links_sample_html_includes_page_requisites(tmp_path, sample_html):
    """Test that sample_html fixture's page requisites are now discovered."""
    html_file = tmp_path / "test.html"
    html_file.write_text(sample_html)

    links = discover_links(
        html_file,
        base_url="https://example.com/test.html",
        target_domain="example.com",
        reject_patterns=[],
        reject_domains=[],
    )

    # Navigation link still works
    assert "https://example.com/page.html" in links
    # Page requisites on same domain are now discovered
    assert "https://example.com/local/image.jpg" in links
    # External resources are filtered out (different domain)
    assert "https://cdn.example.com/style.css" not in links
    assert "https://cdn.example.com/script.js" not in links
