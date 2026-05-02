"""Settings loader for SiteSucker."""

import json
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "UserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Timeout": 15,
    "Retries": 3,
    "MaxDepth": 0,
    "OutputRoot": "./downloads",
    "WaitBetweenRequests": 0.5,
    "ParallelDownloads": 2,
    "RejectPatterns": [],
    "RejectDomains": [],
    "MediaExtensions": [
        ".png", ".jpg", ".jpeg", ".gif", ".webp",
        ".mp4", ".webm", ".avi", ".mkv", ".mov",
        ".svg", ".ico", ".bmp", ".css", ".js", ".woff2"
    ],
}


def load_settings(settings_path: Path | str | None = None) -> dict[str, Any]:
    """Load settings from JSON file, falling back to defaults.

    Args:
        settings_path: Path to settings.json file. If None, looks for
            settings.json in the current directory.

    Returns:
        Dictionary containing merged settings (file overrides defaults).
    """
    settings = DEFAULT_SETTINGS.copy()

    if settings_path is None:
        settings_path = Path.cwd() / "settings.json"
    else:
        settings_path = Path(settings_path)

    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
                settings.update(user_settings)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load settings from {settings_path}: {e}")
            print("Using default settings.")
    else:
        print(f"Settings file not found at {settings_path}. Using defaults.")

    return settings


def merge_cli_overrides(settings: dict[str, Any], parallel: int | None = None,
                        depth: int | None = None) -> dict[str, Any]:
    """Merge CLI parameter overrides into settings.

    Args:
        settings: Base settings dictionary.
        parallel: Override for ParallelDownloads.
        depth: Override for MaxDepth.

    Returns:
        Updated settings dictionary.
    """
    result = settings.copy()

    if parallel is not None and parallel > 0:
        result["ParallelDownloads"] = parallel

    if depth is not None and depth > 0:
        result["MaxDepth"] = depth

    return result
