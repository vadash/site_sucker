"""Shared fixtures for SiteSucker tests."""

import json
from pathlib import Path

import pytest

from site_sucker.settings import Settings


@pytest.fixture
def sample_settings(tmp_path: Path) -> Settings:
    """Create a sample Settings instance.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Settings instance.
    """
    return Settings(
        user_agent="Mozilla/5.0 Test",
        timeout=10,
        retries=2,
        max_depth=0,
        output_root="./downloads",
        wait_between_requests=0.5,
        parallel_downloads=2,
        reject_patterns=["action=", "Special:"],
        reject_domains=["analytics.example.com"],
        media_extensions=[".png", ".jpg", ".css"],
    )


@pytest.fixture
def settings_file(tmp_path: Path, sample_settings: Settings) -> Path:
    """Create a sample settings.json file.

    Args:
        tmp_path: Pytest temporary path fixture.
        sample_settings: Sample settings fixture.

    Returns:
        Path to the created settings file.
    """
    settings_path = tmp_path / "settings.json"
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(sample_settings.to_legacy_dict(), f)
    return settings_path


@pytest.fixture
def sample_html() -> str:
    """Sample HTML content with various links and resources.

    Returns:
        HTML string.
    """
    return '''<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <link rel="stylesheet" href="https://cdn.example.com/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <script src="https://cdn.example.com/script.js"></script>
</head>
<body>
    <h1>Test Page</h1>
    <img src="https://cdn.example.com/image.png" alt="External">
    <img src="/local/image.jpg" alt="Local">
    <a href="https://example.com/page.html">Local Link</a>
    <a href="https://external.com/page.html">External Link</a>
    <script src="https://cdn.example.com/load.php?modules=jquery"></script>
</body>
</html>'''


@pytest.fixture
def sample_css() -> str:
    """Sample CSS content with external and absolute paths.

    Returns:
        CSS string.
    """
    return '''/* Test CSS */
body {
    background-image: url('/images/bg.png');
    font-family: url('https://fonts.example.com/font.woff2');
}

.banner {
    background: url('https://cdn.example.com/banner.jpg');
}
'''
