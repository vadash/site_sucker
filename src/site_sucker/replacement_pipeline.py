"""Unified replacement pipeline with validation and error logging.

This module provides a centralized way to apply regex replacements to HTML/CSS files
with built-in validation to prevent corrupting files. If a replacement breaks the
file structure, it is automatically reverted and logged for debugging.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from site_sucker.file_iter import write_if_changed


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
    return file_path.suffix.lower() == ".css"


def _validate_content(
    content: str, file_path: Path, original_content: str = ""
) -> tuple[bool, str]:
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

        had_head_close = bool(re.search(r"</head\s*>", original_content, re.IGNORECASE))
        has_head_close = bool(re.search(r"</head\s*>", content, re.IGNORECASE))
        if had_head_close and not has_head_close:
            issues.append("missing </head>")

        had_body_open = bool(re.search(r"<body[^>]*>", original_content, re.IGNORECASE))
        has_body_open = bool(re.search(r"<body[^>]*>", content, re.IGNORECASE))
        if had_body_open and not has_body_open:
            issues.append("missing <body>")

        had_body_close = bool(re.search(r"</body\s*>", original_content, re.IGNORECASE))
        has_body_close = bool(re.search(r"</body\s*>", content, re.IGNORECASE))
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
            f.write("Pattern: <callable>\n")
        if step.replacement:
            if callable(step.replacement):
                f.write("Replacement: <callable>\n")
            else:
                f.write(f"Replacement: {step.replacement}\n")
        else:
            f.write("Replacement: <none - callable pattern>\n")

    return failure_dir


def _apply_step(
    step: ReplacementStep,
    current_content: str,
) -> str:
    """Apply a single replacement step to content.

    Args:
        step: The replacement step to apply.
        current_content: Current content string.

    Returns:
        Content after applying the step (unchanged if step is invalid).
    """
    if isinstance(step.pattern, re.Pattern):
        repl = step.replacement if step.replacement is not None else ""
        return step.pattern.sub(repl, current_content)
    if callable(step.pattern):
        return step.pattern(current_content)
    return current_content


def _get_failure_counter(log_dir: Path | None) -> int:
    """Determine the starting failure counter by checking existing log directories.

    Args:
        log_dir: Base log directory, or None.

    Returns:
        Next available failure counter value.
    """
    if not log_dir or not log_dir.exists():
        return 1

    existing_logs = [d for d in log_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    if existing_logs:
        return max(int(d.name) for d in existing_logs) + 1
    return 1


def _handle_step_result(
    step: ReplacementStep,
    new_content: str,
    current_content: str,
    file_path: Path,
    log_dir: Path | None,
    failure_counter: list[int],
) -> str:
    """Validate a step's result and either keep or revert the change.

    Args:
        step: The step that was applied.
        new_content: Content after applying the step.
        current_content: Content before the step.
        file_path: File being processed.
        log_dir: Log directory for failures, or None.
        failure_counter: Mutable single-element list holding the counter.

    Returns:
        The content to use going forward (new_content if valid, current_content if reverted).
    """
    is_valid, error_message = _validate_content(new_content, file_path, current_content)

    if is_valid:
        return new_content

    # Revert: log the failure if a log directory was provided
    if log_dir:
        _log_failure(log_dir, failure_counter[0], file_path, new_content, step, error_message)
        failure_counter[0] += 1

    return current_content


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
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            original_content = f.read()
    except OSError:
        return 0

    if not original_content:
        return 0

    current_content = original_content
    successful_steps = 0

    failure_counter = [_get_failure_counter(log_dir)]

    for step in steps:
        new_content = _apply_step(step, current_content)

        if new_content == current_content:
            continue

        prev_content = current_content
        current_content = _handle_step_result(
            step, new_content, prev_content, file_path, log_dir, failure_counter
        )
        if current_content != prev_content:
            successful_steps += 1

    # Write final content only if modified
    if current_content != original_content:
        write_if_changed(file_path, original_content, current_content)

    return successful_steps
