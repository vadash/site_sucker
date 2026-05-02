"""Settings loader for SiteSucker."""

import json
import re
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


def _strip_jsonc_comments(content: str) -> str:
    """Remove // and /* */ style comments from JSON content.

    Preserves comments inside string literals. This is a simple regex-based
    implementation that handles common cases correctly.

    Args:
        content: Raw JSONC file content.

    Returns:
        JSON content with comments removed.
    """
    # Remove block comments /* ... */
    # Use a negative lookahead to avoid matching inside strings
    pattern_block = r'/\*(?:(?!\*/)[\s\S])*\*/'
    content = re.sub(pattern_block, '', content)

    # Remove line comments // ...
    # Must handle: URLs with "://", strings containing "//", etc.
    # Strategy: remove // comments only when not inside a string
    lines = content.split('\n')
    result_lines = []
    for line in lines:
        in_string = False
        escape = False
        comment_start = -1

        for i, char in enumerate(line):
            if escape:
                escape = False
                continue

            if char == '\\':
                escape = True
                continue

            if char == '"' and not escape:
                in_string = not in_string
                continue

            if not in_string and char == '/' and i + 1 < len(line) and line[i + 1] == '/':
                comment_start = i
                break

        if comment_start >= 0:
            result_lines.append(line[:comment_start])
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


def load_settings(settings_path: Path | str | None = None) -> dict[str, Any]:
    """Load settings from JSON/JSONC file, falling back to defaults.

    Args:
        settings_path: Path to settings.json or settings.jsonc file.
            If None, looks for settings.jsonc first, then settings.json.

    Returns:
        Dictionary containing merged settings (file overrides defaults).
    """
    settings = DEFAULT_SETTINGS.copy()

    if settings_path is None:
        # Try .jsonc first, then fall back to .json
        jsonc_path = Path.cwd() / "settings.jsonc"
        json_path = Path.cwd() / "settings.json"
        if jsonc_path.exists():
            settings_path = jsonc_path
        elif json_path.exists():
            settings_path = json_path
        else:
            settings_path = jsonc_path  # Use for error message
    else:
        settings_path = Path(settings_path)

    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if this is a JSONC file (has comments)
            if settings_path.suffix == '.jsonc':
                content = _strip_jsonc_comments(content)

            user_settings = json.loads(content)

            # Filter out internal keys (starting with _) for backwards compatibility
            user_settings = {k: v for k, v in user_settings.items() if not k.startswith('_')}

            settings.update(user_settings)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load settings from {settings_path}: {e}")
            print("Using default settings.")
    else:
        print(f"Settings file not found at {settings_path}. Using defaults.")

    return settings


def merge_cli_overrides(settings: dict[str, Any], parallel: int | None = None,
                        depth: int | None = None, extra_reject: list[str] | None = None) -> dict[str, Any]:
    """Merge CLI parameter overrides into settings.

    Args:
        settings: Base settings dictionary.
        parallel: Override for ParallelDownloads.
        depth: Override for MaxDepth.
        extra_reject: Additional reject patterns. Supports semicolon-delimited values.

    Returns:
        Updated settings dictionary (original is never mutated).
    """
    result = settings.copy()

    if parallel is not None and parallel > 0:
        result["ParallelDownloads"] = parallel

    if depth is not None and depth > 0:
        result["MaxDepth"] = depth

    if extra_reject:
        # Split semicolon-delimited patterns and append to RejectPatterns
        additional_patterns = []
        for reject_list in extra_reject:
            additional_patterns.extend(p.strip() for p in reject_list.split(";") if p.strip())

        if additional_patterns:
            # Create a new list to avoid mutating the original settings
            result["RejectPatterns"] = list(result.get("RejectPatterns", [])) + additional_patterns

    return result
