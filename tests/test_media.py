"""Tests for media module."""

from dataclasses import replace
from pathlib import Path

from site_sucker import media
from site_sucker.settings import Settings


def test_get_external_media_basic(tmp_path: Path, sample_settings: Settings):
    """Test basic external media extraction."""
    # Create sample HTML file
    html_file = tmp_path / "test.html"
    html_content = """<html>
<body>
    <img src="https://cdn.example.com/image.png">
    <img src="https://cdn.example.com/photo.jpg?timestamp=123">
    <img src="/local/image.png">
</body>
</html>"""
    html_file.write_text(html_content)

    ext_urls = media.get_external_media(tmp_path, "example.com", sample_settings)

    assert len(ext_urls) == 2
    assert "https://cdn.example.com/image.png" in ext_urls
    assert "https://cdn.example.com/photo.jpg" in ext_urls  # Query stripped


def test_get_external_media_dedup(tmp_path: Path, sample_settings: Settings):
    """Test URL deduplication."""
    html_file = tmp_path / "test.html"
    html_content = """<html>
<body>
    <img src="https://cdn.example.com/image.png">
    <img src="https://cdn.example.com/image.png?v=1">
    <img src="https://cdn.example.com/image.png?v=2">
</body>
</html>"""
    html_file.write_text(html_content)

    ext_urls = media.get_external_media(tmp_path, "example.com", sample_settings)

    # Should deduplicate to single URL
    assert len(ext_urls) == 1
    assert "https://cdn.example.com/image.png" in ext_urls


def test_get_external_media_filters_target_domain(tmp_path: Path, sample_settings: Settings):
    """Test that target domain URLs are filtered out."""
    html_file = tmp_path / "test.html"
    html_content = """<html>
<body>
    <img src="https://example.com/image.png">
    <img src="https://cdn.example.com/photo.jpg">
</body>
</html>"""
    html_file.write_text(html_content)

    ext_urls = media.get_external_media(tmp_path, "example.com", sample_settings)

    # Should only include external CDN, not target domain
    assert len(ext_urls) == 1
    assert "https://cdn.example.com/photo.jpg" in ext_urls
    assert "https://example.com/image.png" not in ext_urls


def test_get_external_media_filters_extensions(tmp_path: Path, sample_settings: Settings):
    """Test that only media extensions are included."""
    sample_settings = replace(sample_settings, media_extensions=[".png", ".jpg"])

    html_file = tmp_path / "test.html"
    html_content = """<html>
<body>
    <img src="https://cdn.example.com/image.png">
    <a href="https://cdn.example.com/page.html">Link</a>
    <script src="https://cdn.example.com/script.js"></script>
</body>
</html>"""
    html_file.write_text(html_content)

    ext_urls = media.get_external_media(tmp_path, "example.com", sample_settings)

    # Should only include PNG, not HTML or JS
    assert len(ext_urls) == 1
    assert "https://cdn.example.com/image.png" in ext_urls


def test_get_external_media_multiple_files(tmp_path: Path, sample_settings: Settings):
    """Test scanning multiple HTML files."""
    (tmp_path / "page1.html").write_text('<img src="https://cdn.example.com/image1.png">')
    (tmp_path / "page2.html").write_text('<img src="https://cdn.example.com/image2.png">')
    (tmp_path / "page3.htm").write_text('<img src="https://cdn.example.com/image3.png">')

    ext_urls = media.get_external_media(tmp_path, "example.com", sample_settings)

    assert len(ext_urls) == 3
    assert "https://cdn.example.com/image1.png" in ext_urls
    assert "https://cdn.example.com/image2.png" in ext_urls
    assert "https://cdn.example.com/image3.png" in ext_urls


def test_get_external_media_from_css_url(tmp_path: Path, sample_settings: Settings):
    """Test extracting media URLs from CSS url() references."""
    # Add .webp and .svg to extensions for this test
    sample_settings = replace(
        sample_settings, media_extensions=[".png", ".jpg", ".css", ".webp", ".svg"]
    )

    # Create a CSS file with url() references
    css_file = tmp_path / "styles" / "test.css"
    css_file.parent.mkdir(parents=True, exist_ok=True)
    css_content = """
body {
    background: url(https://cdn.example.com/images/bg.webp);
}
.logo {
    background-image: url("https://cdn.example.com/images/logo.png");
}
.icon {
    background: url('https://cdn.example.com/icon.svg');
}
.local {
    background: url(/local/image.png);
}
"""
    css_file.write_text(css_content)

    # Also create an HTML file
    html_file = tmp_path / "test.html"
    html_file.write_text('<link rel="stylesheet" href="styles/test.css">')

    ext_urls = media.get_external_media(tmp_path, "example.com", sample_settings)

    # Should find the 3 external URLs from CSS, not the local one
    assert len(ext_urls) == 3
    assert "https://cdn.example.com/images/bg.webp" in ext_urls
    assert "https://cdn.example.com/images/logo.png" in ext_urls
    assert "https://cdn.example.com/icon.svg" in ext_urls


def test_get_external_media_from_css_and_html(tmp_path: Path, sample_settings: Settings):
    """Test scanning both HTML and CSS for media URLs."""
    css_file = tmp_path / "styles" / "main.css"
    css_file.parent.mkdir(parents=True, exist_ok=True)
    css_file.write_text("background: url(https://cdn.example.com/css-bg.jpg);")

    html_file = tmp_path / "test.html"
    html_file.write_text(
        '<link rel="stylesheet" href="styles/main.css">\n'
        '<img src="https://cdn.example.com/html-img.png">'
    )

    ext_urls = media.get_external_media(tmp_path, "example.com", sample_settings)

    # Should find both HTML and CSS external URLs
    assert len(ext_urls) == 2
    assert "https://cdn.example.com/css-bg.jpg" in ext_urls
    assert "https://cdn.example.com/html-img.png" in ext_urls


def test_get_external_media_css_with_quotes_variations(tmp_path: Path, sample_settings: Settings):
    """Test CSS url() with various quote styles."""
    sample_settings = replace(sample_settings, media_extensions=[".png", ".jpg", ".webp"])

    css_file = tmp_path / "styles.css"
    css_content = """
.bg1 { background: url(https://cdn.example.com/img1.webp); }
.bg2 { background: url("https://cdn.example.com/img2.webp"); }
.bg3 { background: url('https://cdn.example.com/img3.webp'); }
"""
    css_file.write_text(css_content)

    ext_urls = media.get_external_media(tmp_path, "example.com", sample_settings)

    assert len(ext_urls) == 3
    assert "https://cdn.example.com/img1.webp" in ext_urls
    assert "https://cdn.example.com/img2.webp" in ext_urls
    assert "https://cdn.example.com/img3.webp" in ext_urls
