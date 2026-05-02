"""Settings loader for SiteSucker."""

import copy
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


def _expand_reject_expression(pattern: str) -> list[str]:
    """Expand range expressions in reject patterns.

    Supports syntax like:
    - {1..100} → expands to 1,2,3,...,100
    - {1..100..2} → expands to 1,3,5,...,99 (step 2)
    - {1..100%4,25,40} → expands to 1..100 excluding 4,25,40

    The expression is embedded in a pattern string, e.g., "f={1..100%4,25,40}&"
    → ["f=1&", "f=2&", "f=3&", "f=5&", ..., "f=100&"]

    Args:
        pattern: A reject pattern that may contain {EXPR} blocks.

    Returns:
        List of expanded patterns. If no expressions found, returns [pattern].
    """
    # Find all {...} blocks in the pattern
    # Use regex to find expressions, but we need to handle nested braces properly
    # For simplicity, we'll find the outermost {...} and expand it

    expr_pattern = r'\{([^{}]+)\}'
    matches = list(re.finditer(expr_pattern, pattern))

    if not matches:
        # No expression found, return as-is
        return [pattern]

    # For each match, expand the expression
    # We process from right to left to preserve string positions
    results = [pattern]

    for match in reversed(matches):
        expr = match.group(1)
        start, end = match.span()
        full_match = match.group(0)  # Includes braces: {expr}

        new_results = []
        for result in results:
            # Split the pattern around the expression
            prefix = result[:start]
            suffix = result[end:]

            # Parse the expression
            # Format: START..END or START..END..STEP or START..END%EXCLUDES
            expanded_values = _parse_range_expression(expr)

            # Check if expansion was successful
            # If _parse_range_expression returns the expr unchanged, it means parsing failed
            # We need to check if the expanded values look like a valid range
            is_valid_range = _is_valid_range_expression(expanded_values, expr)

            if not is_valid_range:
                # Invalid expression, keep the original pattern with braces
                new_results.append(result)
            else:
                # Generate expanded patterns
                for value in expanded_values:
                    new_results.append(f"{prefix}{value}{suffix}")

        results = new_results

    return results


def _is_valid_range_expression(values: list[str], original_expr: str) -> bool:
    """Check if the expanded values represent a valid range expression.

    Args:
        values: List of expanded values from _parse_range_expression.
        original_expr: The original expression string.

    Returns:
        True if values represent a valid range expansion, False otherwise.
    """
    if len(values) == 1:
        # Single value could be a valid single-item range or an invalid expression
        # Check if it's a number (valid range like {5..5}) or the original expr (invalid)
        try:
            int(values[0])
            return True  # It's a number, valid range
        except ValueError:
            # Not a number, check if it's the original expression
            return values[0] != original_expr
    return len(values) > 1


def _parse_range_expression(expr: str) -> list[str]:
    """Parse a range expression and return the list of values.

    Args:
        expr: Expression string like "1..100", "1..100..2", or "1..100%4,25,40"

    Returns:
        List of string values from the expanded range.
    """
    # Check for exclusions (%)
    if '%' in expr:
        range_part, exclude_part = expr.split('%', 1)
        excludes = set(e.strip() for e in exclude_part.split(',') if e.strip())
    else:
        range_part = expr
        excludes = set()

    # Parse range part: START..END or START..END..STEP
    if '..' not in range_part:
        # Not a valid range expression, return as-is
        return [expr]

    parts = range_part.split('..')
    if len(parts) < 2 or len(parts) > 3:
        # Invalid format, return as-is
        return [expr]

    try:
        start = int(parts[0].strip()) if parts[0].strip() else None
        end = int(parts[1].strip()) if parts[1].strip() else None
        step = int(parts[2].strip()) if len(parts) == 3 and parts[2].strip() else 1

        if start is None or end is None:
            # Invalid range, return as-is
            return [expr]

        # Generate range values
        values = []
        current = start
        while (step > 0 and current <= end) or (step < 0 and current >= end):
            str_val = str(current)
            if str_val not in excludes:
                values.append(str_val)
            current += step

        # If all values were excluded, return the original expression
        if not values:
            return [expr]

        return values

    except ValueError:
        # Invalid number format, return as-is
        return [expr]


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
    settings = copy.deepcopy(DEFAULT_SETTINGS)

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
    result = copy.deepcopy(settings)

    if parallel is not None and parallel > 0:
        result["ParallelDownloads"] = parallel

    if depth is not None and depth > 0:
        result["MaxDepth"] = depth

    if extra_reject:
        # Split semicolon-delimited patterns and append to RejectPatterns
        additional_patterns = []
        for reject_list in extra_reject:
            # First split by semicolon
            for pattern in reject_list.split(";"):
                pattern = pattern.strip()
                if not pattern:
                    continue

                # Expand any range expressions in the pattern
                expanded = _expand_reject_expression(pattern)
                if expanded != [pattern]:
                    print(f"Expanded --reject \"{pattern}\" → {len(expanded)} patterns:")
                    for i, p in enumerate(expanded, 1):
                        print(f"  {i:4d}. {p}")
                additional_patterns.extend(expanded)

        if additional_patterns:
            # Create a new list to avoid mutating the original settings
            result["RejectPatterns"] = list(result.get("RejectPatterns", [])) + additional_patterns

    return result
