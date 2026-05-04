"""Tests for url_filter module (shared URL extraction)."""

from bs4 import BeautifulSoup

from site_sucker.url_filter import (
    extract_internal_urls,
    should_reject_url,
)


def test_extract_internal_urls_basic_navigation():
    """Test extraction of basic <a> navigation links."""
    html = """<html>
        <body>
            <a href="https://example.com/page.html">Link</a>
            <a href="/about">About</a>
            <a href="contact.html">Contact</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
    )

    assert "https://example.com/page.html" in urls
    assert "https://example.com/about" in urls
    assert "https://example.com/contact.html" in urls


def test_extract_internal_urls_relative_resolution():
    """Test that relative URLs are resolved using base_url."""
    html = """<html>
        <body>
            <a href="/wiki/Main_Page">Absolute relative</a>
            <a href="subpage.html">Relative to current</a>
            <a href="../parent.html">Parent relative</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/wiki/index.html",
        target_domain="example.com",
    )

    assert "https://example.com/wiki/Main_Page" in urls
    assert "https://example.com/wiki/subpage.html" in urls
    assert "https://example.com/parent.html" in urls


def test_extract_internal_urls_filters_external_domain():
    """Test that external domain URLs are filtered out."""
    html = """<html>
        <body>
            <a href="https://example.com/internal.html">Internal</a>
            <a href="https://other-domain.com/external.html">External</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
    )

    assert "https://example.com/internal.html" in urls
    assert "https://other-domain.com/external.html" not in urls


def test_extract_internal_urls_reject_patterns():
    """Test that reject patterns filter out URLs."""
    html = """<html>
        <body>
            <a href="https://example.com/page.html">Normal</a>
            <a href="https://example.com/Special:Contributions">Special</a>
            <a href="https://example.com/index.php?action=edit">Action</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
        reject_patterns=["Special:", "action="],
    )

    assert "https://example.com/page.html" in urls
    assert "https://example.com/Special:Contributions" not in urls
    assert "https://example.com/index.php?action=edit" not in urls


def test_extract_internal_urls_reject_domains():
    """Test that reject domains filter out URLs."""
    html = """<html>
        <body>
            <a href="https://example.com/page.html">Normal</a>
            <a href="https://analytics.example.com/track">Analytics</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
        reject_domains=["analytics.example.com"],
    )

    assert "https://example.com/page.html" in urls
    assert "https://analytics.example.com/track" not in urls


def test_extract_internal_urls_skips_non_http_schemes():
    """Test that non-HTTP schemes are skipped."""
    html = """<html>
        <body>
            <a href="https://example.com/page.html">HTTPS</a>
            <a href="mailto:test@example.com">Email</a>
            <a href="javascript:void(0)">JS</a>
            <a href="#section">Anchor</a>
            <a href="data:text/plain,hello">Data</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
    )

    # Only HTTPS link should be included
    assert len(urls) == 1
    assert "https://example.com/page.html" in urls


def test_extract_internal_urls_fragment_stripping():
    """Test that fragments are stripped for normalization."""
    html = """<html>
        <body>
            <a href="https://example.com/page.html#section1">Section 1</a>
            <a href="https://example.com/page.html#section2">Section 2</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
    )

    # Should have only one URL (fragments stripped)
    assert len(urls) == 1
    assert "https://example.com/page.html" in urls
    assert "#section1" not in str(urls)
    assert "#section2" not in str(urls)


def test_extract_internal_urls_page_requisites_images():
    """Test that <img> src URLs are extracted as page requisites."""
    html = """<html>
        <body>
            <img src="/images/sword.png" alt="Sword">
            <img src="https://example.com/images/shield.jpg" alt="Shield">
            <img src="https://other.com/image.png" alt="External">
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/wiki/page.html",
        target_domain="example.com",
    )

    assert "https://example.com/images/sword.png" in urls
    assert "https://example.com/images/shield.jpg" in urls
    assert "https://other.com/image.png" not in urls


def test_extract_internal_urls_page_requisites_scripts():
    """Test that <script> src URLs are extracted as page requisites."""
    html = """<html>
        <head>
            <script src="/js/app.js"></script>
            <script src="https://example.com/js/vendor.js"></script>
            <script src="https://cdn.other.com/lib.js"></script>
        </head>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/page.html",
        target_domain="example.com",
    )

    assert "https://example.com/js/app.js" in urls
    assert "https://example.com/js/vendor.js" in urls
    assert "https://cdn.other.com/lib.js" not in urls


def test_extract_internal_urls_page_requisites_stylesheet():
    """Test that <link> href URLs for stylesheets are extracted."""
    html = """<html>
        <head>
            <link rel="stylesheet" href="/css/style.css">
            <link rel="stylesheet" href="https://example.com/css/theme.css">
            <link rel="preconnect" href="https://fonts.googleapis.com">
        </head>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/page.html",
        target_domain="example.com",
    )

    assert "https://example.com/css/style.css" in urls
    assert "https://example.com/css/theme.css" in urls
    # External preconnect link should not be included (different domain)
    assert "https://fonts.googleapis.com" not in urls


def test_extract_internal_urls_page_requisites_video_audio_source():
    """Test that <video>, <audio>, <source> URLs are extracted."""
    html = """<html>
        <body>
            <video src="/videos/intro.mp4"></video>
            <audio src="/audio/podcast.mp3"></audio>
            <video>
                <source src="/videos/trailer.webm" type="video/webm">
            </video>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/page.html",
        target_domain="example.com",
    )

    assert "https://example.com/videos/intro.mp4" in urls
    assert "https://example.com/audio/podcast.mp3" in urls
    assert "https://example.com/videos/trailer.webm" in urls


def test_extract_internal_urls_data_src_attribute():
    """Test that data-src attributes (lazy-loaded images) are extracted."""
    html = """<html>
        <body>
            <img data-src="/images/lazy.png" alt="Lazy loaded">
            <img data-src="https://example.com/images/lazy2.jpg" alt="Another lazy">
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/page.html",
        target_domain="example.com",
    )

    assert "https://example.com/images/lazy.png" in urls
    assert "https://example.com/images/lazy2.jpg" in urls


def test_extract_internal_urls_mixed_navigation_and_resources():
    """Test that both navigation links and resources are extracted together."""
    html = """<html>
        <head>
            <link rel="stylesheet" href="/css/style.css">
            <script src="/js/app.js"></script>
        </head>
        <body>
            <a href="/about">About Us</a>
            <img src="/images/logo.png" alt="Logo">
            <video src="/videos/intro.mp4"></video>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
    )

    # Should have all types of URLs
    assert "https://example.com/css/style.css" in urls
    assert "https://example.com/js/app.js" in urls
    assert "https://example.com/about" in urls
    assert "https://example.com/images/logo.png" in urls
    assert "https://example.com/videos/intro.mp4" in urls


def test_extract_internal_urls_empty_html():
    """Test with empty HTML content."""
    soup = BeautifulSoup("", "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
    )

    assert len(urls) == 0


def test_extract_internal_urls_no_links():
    """Test with HTML that has no links or resources."""
    html = """<html>
        <body>
            <h1>Welcome</h1>
            <p>This page has no links.</p>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
    )

    assert len(urls) == 0


def test_extract_internal_urls_case_insensitive_domain():
    """Test that domain matching is case-insensitive (per RFC 3986)."""
    html = """<html>
        <body>
            <a href="https://Example.com/page.html">Mixed case</a>
            <a href="https://EXAMPLE.COM/page2.html">Upper case</a>
            <a href="https://example.com/page3.html">Lower case</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://example.com/index.html",
        target_domain="example.com",
    )

    # All should be included since domain matching is case-insensitive
    # URLs are returned in their original case (not normalized)
    assert len(urls) == 3
    assert "https://Example.com/page.html" in urls
    assert "https://EXAMPLE.COM/page2.html" in urls
    assert "https://example.com/page3.html" in urls


def test_should_reject_url_basic():
    """Test basic URL rejection for different schemes."""
    assert should_reject_url("#section", "example.com") is True
    assert should_reject_url("javascript:void(0)", "example.com") is True
    assert should_reject_url("mailto:test@example.com", "example.com") is True
    assert should_reject_url("data:text/plain,hello", "example.com") is True


def test_should_reject_url_external_domain():
    """Test that external domains are rejected."""
    assert should_reject_url("https://example.com/page.html", "example.com") is False
    assert should_reject_url("https://other.com/page.html", "example.com") is True


def test_should_reject_url_patterns():
    """Test that reject patterns work."""
    assert (
        should_reject_url(
            "https://example.com/index.php?action=edit", "example.com", reject_patterns=["action="]
        )
        is True
    )

    assert (
        should_reject_url(
            "https://example.com/Special:Contributions", "example.com", reject_patterns=["Special:"]
        )
        is True
    )


def test_should_reject_url_domains():
    """Test that reject domains work."""
    assert (
        should_reject_url(
            "https://analytics.example.com/track",
            "example.com",
            reject_domains=["analytics.example.com"],
        )
        is True
    )


def test_should_reject_url_regex_pattern():
    """Test that reject patterns work as regex, not just substrings."""
    # Simple substring patterns still work
    assert (
        should_reject_url(
            "https://example.com/index.php?action=edit",
            "example.com",
            reject_patterns=["action="],
        )
        is True
    )

    # Regex pattern: Reddit comment permalink (post_id/slug/comment_id)
    pattern = "/comments/[^/]+/[^/]+/[^/]+"
    # Comment permalink should be rejected (has comment_id after slug)
    assert (
        should_reject_url(
            "https://old.reddit.com/r/sub/comments/abc123/post_slug/ojf123/",
            "old.reddit.com",
            reject_patterns=[pattern],
        )
        is True
    )
    # Post URL should NOT be rejected (only post_id/slug, no comment_id)
    assert (
        should_reject_url(
            "https://old.reddit.com/r/sub/comments/abc123/post_slug/",
            "old.reddit.com",
            reject_patterns=[pattern],
        )
        is False
    )


def test_extract_internal_urls_regex_reject_pattern():
    """Test that regex reject patterns filter URLs in extract_internal_urls."""
    html = """<html>
        <body>
            <a href="https://old.reddit.com/r/sub/comments/abc123/post_slug/">Post</a>
            <a href="https://old.reddit.com/r/sub/comments/abc123/post_slug/ojf123/">Comment</a>
            <a href="https://old.reddit.com/r/sub/comments/abc123/post_slug/?sort=new">Sorted</a>
        </body>
    </html>"""

    soup = BeautifulSoup(html, "lxml")
    urls = extract_internal_urls(
        soup,
        base_url="https://old.reddit.com/r/sub/",
        target_domain="old.reddit.com",
        reject_patterns=["/comments/[^/]+/[^/]+/[^/]+", "sort="],
    )

    assert "https://old.reddit.com/r/sub/comments/abc123/post_slug/" in urls
    assert "https://old.reddit.com/r/sub/comments/abc123/post_slug/ojf123/" not in urls
    assert "https://old.reddit.com/r/sub/comments/abc123/post_slug/?sort=new" not in urls
