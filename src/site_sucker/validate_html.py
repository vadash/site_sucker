"""HTML validation for detecting incomplete or corrupted downloads."""

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

from site_sucker.file_iter import iter_html_files

logger = logging.getLogger(__name__)

# Control characters that should never appear in valid HTML content.
# Excludes: tab (0x09), newline (0x0A), carriage return (0x0D).
# Includes: DEL (0x7F) and C0 controls (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F).
_CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


def validate_html_string(content: str) -> dict[str, bool]:
    """Validate a single HTML string for structural integrity using BeautifulSoup.

    Checks for common issues that indicate broken HTML:
    - Missing head element
    - Missing body element
    - Empty body content (no visible text)
    - Binary/control characters in content (corrupted download)

    Args:
        content: HTML content string to validate.

    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "missing_head": bool,
            "missing_body": bool,
            "empty_body": bool,
            "has_binary_content": bool
        }
    """
    results: dict[str, bool] = {
        "valid": True,
        "missing_head": False,
        "missing_body": False,
        "empty_body": False,
        "has_binary_content": False,
    }

    if not content:
        results["valid"] = False
        return results

    # Check for binary/control characters that indicate corrupted content.
    # These should never appear in valid HTML (tab/newline/CR are excluded).
    if _CONTROL_CHAR_RE.search(content):
        results["has_binary_content"] = True
        results["valid"] = False

    # Use regex to check for original presence of head/body tags
    # BeautifulSoup's lxml parser auto-adds missing tags, so we check the raw content first
    has_head_tag = bool(re.search(r'<head[^>]*>', content, re.IGNORECASE))
    has_body_tag = bool(re.search(r'<body[^>]*>', content, re.IGNORECASE))

    # Parse with BeautifulSoup - lxml handles broken HTML gracefully
    soup = BeautifulSoup(content, 'lxml')

    # Check for head element in original content
    if not has_head_tag:
        results["missing_head"] = True
        results["valid"] = False

    # Check for body element in original content
    if not has_body_tag:
        results["missing_body"] = True
        results["valid"] = False

    # Check for empty body (no visible text content)
    # Only check if we had a body tag in the original content
    if has_body_tag:
        body = soup.find('body')
        if body:
            # Get all text content from body, excluding script/style tags
            # BeautifulSoup's get_text() automatically handles this
            text_content = body.get_text(separator=' ', strip=True)

            # Check if there's any meaningful text (more than 5 non-whitespace chars)
            # This catches truly empty bodies but allows short content like <h1>Content</h1>
            if len(text_content) < 5:
                results["empty_body"] = True
                results["valid"] = False

    return results


def validate_html_files(output_dir: Path | str) -> dict[str, bool | list[str]]:
    """Validate HTML files for structural integrity using BeautifulSoup.

    Checks for common issues that indicate incomplete or corrupted downloads:
    - Missing head element
    - Missing body element
    - Empty body content (no visible text)

    Args:
        output_dir: Path to the directory containing downloaded HTML files.

    Returns:
        Dictionary with validation results:
        {
            "missing_head": ["file1.html", ...],
            "missing_body": ["file1.html", ...],
            "empty_body": ["file1.html", ...],
            "all_valid": bool
        }
    """
    output_dir = Path(output_dir)

    results: dict[str, bool | list[str]] = {
        "missing_head": [],
        "missing_body": [],
        "empty_body": [],
        "has_binary_content": [],
        "all_valid": True,
    }

    for html_file, raw in iter_html_files(output_dir):
        # Use the shared validation function
        validation = validate_html_string(raw)

        if not validation["valid"]:
            results["all_valid"] = False

            if validation["missing_head"]:
                missing_head = results["missing_head"]
                if isinstance(missing_head, list):
                    missing_head.append(str(html_file.relative_to(output_dir)))

            if validation["missing_body"]:
                missing_body = results["missing_body"]
                if isinstance(missing_body, list):
                    missing_body.append(str(html_file.relative_to(output_dir)))

            if validation["empty_body"]:
                empty_body = results["empty_body"]
                if isinstance(empty_body, list):
                    empty_body.append(str(html_file.relative_to(output_dir)))

            if validation["has_binary_content"]:
                has_binary_content = results["has_binary_content"]
                if isinstance(has_binary_content, list):
                    has_binary_content.append(str(html_file.relative_to(output_dir)))

    return results


def print_validation_results(results: dict[str, bool | list[str]]) -> None:
    """Print validation results in a user-friendly format.

    Args:
        results: Validation results dictionary from validate_html_files().
    """
    if results["all_valid"]:
        logger.info("✓ HTML validation passed: All HTML files are structurally complete")
        return

    logger.warning("⚠ HTML validation detected issues:")
    logger.info("=" * 60)

    missing_head = results.get("missing_head")
    if isinstance(missing_head, list) and missing_head:
        logger.info("  Missing head element (%d files):", len(missing_head))
        for f in missing_head[:5]:
            logger.info("    - %s", f)
        if len(missing_head) > 5:
            logger.info("    ... and %d more", len(missing_head) - 5)

    missing_body = results.get("missing_body")
    if isinstance(missing_body, list) and missing_body:
        logger.info("  Missing body element (%d files):", len(missing_body))
        for f in missing_body[:5]:
            logger.info("    - %s", f)
        if len(missing_body) > 5:
            logger.info("    ... and %d more", len(missing_body) - 5)

    empty_body = results.get("empty_body")
    if isinstance(empty_body, list) and empty_body:
        logger.info("  Empty body content (%d files):", len(empty_body))
        for f in empty_body[:5]:
            logger.info("    - %s", f)
        if len(empty_body) > 5:
            logger.info("    ... and %d more", len(empty_body) - 5)

    has_binary_content = results.get("has_binary_content")
    if isinstance(has_binary_content, list) and has_binary_content:
        logger.info("  Binary/control characters detected (%d files):", len(has_binary_content))
        for f in has_binary_content[:5]:
            logger.info("    - %s", f)
        if len(has_binary_content) > 5:
            logger.info("    ... and %d more", len(has_binary_content) - 5)

    logger.info("=" * 60)
    logger.warning("This indicates an incomplete download. Possible causes:")
    logger.warning("  - Network timeout or connection loss during wget pass 1")
    logger.warning("  - Server returning incomplete content")
    logger.warning("  - Wget interrupted or crashed")
    logger.warning("Recommendation: Re-run the download or check the site manually in a browser")
