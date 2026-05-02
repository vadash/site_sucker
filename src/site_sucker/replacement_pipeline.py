"""Unified replacement pipeline with validation and error logging.

This module provides a centralized way to apply regex replacements to HTML/CSS files
with built-in validation to prevent corrupting files. If a replacement breaks the
file structure, it is automatically reverted and logged for debugging.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class ReplacementStep:
    """A single replacement step in the pipeline.

    Attributes:
        name: Human-readable description of what this step does.
        pattern: Compiled regex pattern to search for, or callable that returns modified content.
        replacement: Replacement string or callable for re.sub(), used only if pattern is a regex.
        flags: Regex flags (only used if pattern is a string).
    """
    name: str
    pattern: re.Pattern[str] | Callable[[str], str]
    replacement: str | Callable[[re.Match[str]], str] | None = None
    flags: int = 0


def _is_css_file(file_path: Path) -> bool:
    """Check if a file is a CSS file."""
    return file_path.suffix.lower() == '.css'


def _validate_content(content: str, file_path: Path, original_content: str = "") -> tuple[bool, str]:
    """Validate content after a replacement step.

    For HTML files, checks that no structural tags were accidentally removed:
    - If </head> was present before but is now missing: reject
    - If </body> was present before but is now missing: reject
    - If <body> was present before but is now missing: reject

    For CSS files, just checks content is non-empty.

    Args:
        content: The content to validate.
        file_path: Path to the file (used to determine file type).
        original_content: The content before the replacement (for comparison).

    Returns:
        Tuple of (is_valid, error_message).
    """
    if _is_css_file(file_path):
        # CSS validation: just check non-empty
        if not content.strip():
            return False, "CSS content is empty"
        return True, ""
    else:
        # HTML validation - check that no structural tags were removed
        issues = []

        had_head_close = bool(re.search(r'</head\s*>', original_content, re.IGNORECASE))
        has_head_close = bool(re.search(r'</head\s*>', content, re.IGNORECASE))
        if had_head_close and not has_head_close:
            issues.append("missing </head>")

        had_body_open = bool(re.search(r'<body[^>]*>', original_content, re.IGNORECASE))
        has_body_open = bool(re.search(r'<body[^>]*>', content, re.IGNORECASE))
        if had_body_open and not has_body_open:
            issues.append("missing <body>")

        had_body_close = bool(re.search(r'</body\s*>', original_content, re.IGNORECASE))
        has_body_close = bool(re.search(r'</body\s*>', content, re.IGNORECASE))
        if had_body_close and not has_body_close:
            issues.append("missing </body>")

        if issues:
            return False, f"HTML validation failed: {', '.join(issues)}"

    return True, ""


def _log_failure(
    log_dir: Path,
    counter: int,
    file_path: Path,
    content: str,
    step: ReplacementStep,
    error_message: str,
) -> Path:
    """Log a failed replacement to the log directory.

    Creates a numbered subdirectory with:
    - The file content at the point of failure
    - A pattern.txt file with the step details and error

    Args:
        log_dir: Base log directory.
        counter: Failure counter (for numbering subdirectories).
        file_path: Original file path.
        content: File content at point of failure.
        step: The replacement step that failed.
        error_message: Validation error message.

    Returns:
        Path to the created log subdirectory.
    """
    # Create zero-padded numbered directory
    failure_dir = log_dir / f"{counter:05d}"
    failure_dir.mkdir(parents=True, exist_ok=True)

    # Copy the file content
    log_file_path = failure_dir / file_path.name
    with open(log_file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Write pattern.txt with step details
    pattern_file = failure_dir / "pattern.txt"
    with open(pattern_file, "w", encoding="utf-8") as f:
        f.write(f"Step: {step.name}\n")
        f.write(f"File: {file_path}\n")
        f.write(f"Error: {error_message}\n")
        f.write("\n")
        if isinstance(step.pattern, re.Pattern):
            f.write(f"Pattern: {step.pattern.pattern}\n")
            f.write(f"Flags: {step.flags}\n")
        else:
            f.write(f"Pattern: <callable>\n")
        if step.replacement:
            if callable(step.replacement):
                f.write(f"Replacement: <callable>\n")
            else:
                f.write(f"Replacement: {step.replacement}\n")
        else:
            f.write(f"Replacement: <none - callable pattern>\n")

    return failure_dir


def run_replacement_pipeline(
    file_path: Path,
    steps: list[ReplacementStep],
    log_dir: Path | None = None,
) -> int:
    """Run a series of replacement steps on a file with validation.

    Each step is applied sequentially. After each step:
    - If content changed: validate the result
    - If validation fails: revert the change and log to log_dir
    - If validation passes or content unchanged: continue to next step

    After all steps, write the final content (only if modified).

    Args:
        file_path: Path to the file to process.
        steps: List of replacement steps to apply in order.
        log_dir: Directory to log failures. If None, failures are reverted but not logged.

    Returns:
        Number of steps that were successfully applied (changed content and passed validation).
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            original_content = f.read()
    except (IOError, OSError):
        return 0

    if not original_content:
        return 0

    current_content = original_content
    successful_steps = 0

    # Determine the starting counter value by checking existing log directories
    failure_counter = 1
    if log_dir and log_dir.exists():
        existing_logs = [d for d in log_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        if existing_logs:
            max_counter = max(int(d.name) for d in existing_logs)
            failure_counter = max_counter + 1

    for step in steps:
        new_content = current_content

        # Apply the replacement
        if isinstance(step.pattern, re.Pattern):
            # Regex-based replacement
            new_content = step.pattern.sub(step.replacement, current_content)
        elif callable(step.pattern):
            # Callable-based transformation
            new_content = step.pattern(current_content)
        else:
            continue

        # Check if content changed
        if new_content == current_content:
            continue

        # Validate the new content (pass current_content as baseline for comparison)
        is_valid, error_message = _validate_content(new_content, file_path, current_content)

        if is_valid:
            # Keep the change
            current_content = new_content
            successful_steps += 1
        else:
            # Revert the change
            if log_dir:
                _log_failure(
                    log_dir,
                    failure_counter,
                    file_path,
                    new_content,
                    step,
                    error_message,
                )
                failure_counter += 1

    # Write final content only if modified
    if current_content != original_content:
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(current_content)

    return successful_steps
