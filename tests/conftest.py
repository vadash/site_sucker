"""Shared fixtures for SiteSucker tests."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def sample_settings(tmp_path: Path) -> dict:
    """Create a sample settings dictionary.

    Args:
        tmp_path: Pytest temporary path fixture.

    Returns:
        Settings dictionary.
    """
    return {
        "UserAgent": "Mozilla/5.0 Test",
        "Timeout": 10,
        "Retries": 2,
        "MaxDepth": 0,
        "OutputRoot": "./downloads",
        "WaitBetweenRequests": 0.5,
        "ParallelDownloads": 2,
        "RejectPatterns": ["action=", "Special:"],
        "RejectDomains": ["analytics.example.com"],
        "MediaExtensions": [".png", ".jpg", ".css"],
    }


@pytest.fixture
def settings_file(tmp_path: Path, sample_settings: dict) -> Path:
    """Create a sample settings.json file.

    Args:
        tmp_path: Pytest temporary path fixture.
        sample_settings: Sample settings fixture.

    Returns:
        Path to the created settings file.
    """
    settings_path = tmp_path / "settings.json"
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(sample_settings, f)
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
