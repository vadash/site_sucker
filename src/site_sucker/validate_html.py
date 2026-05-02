"""HTML validation for detecting incomplete or corrupted downloads."""

import re
from pathlib import Path

from bs4 import BeautifulSoup


def validate_html_string(content: str) -> dict[str, bool]:
    """Validate a single HTML string for structural integrity using BeautifulSoup.

    Checks for common issues that indicate broken HTML:
    - Missing head element
    - Missing body element
    - Empty body content (no visible text)

    Args:
        content: HTML content string to validate.

    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "missing_head": bool,
            "missing_body": bool,
            "empty_body": bool
        }
    """
    results = {
        "valid": True,
        "missing_head": False,
        "missing_body": False,
        "empty_body": False,
    }

    if not content:
        results["valid"] = False
        return results

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


def validate_html_files(output_dir: Path | str) -> dict[str, list[str]]:
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
    html_files = list(output_dir.rglob("*.html")) + list(output_dir.rglob("*.htm"))

    results = {
        "missing_head": [],
        "missing_body": [],
        "empty_body": [],
        "all_valid": True,
    }

    for html_file in html_files:
        try:
            with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        except IOError:
            continue

        if not raw:
            continue

        # Use the shared validation function
        validation = validate_html_string(raw)

        if not validation["valid"]:
            results["all_valid"] = False

            if validation["missing_head"]:
                results["missing_head"].append(str(html_file.relative_to(output_dir)))

            if validation["missing_body"]:
                results["missing_body"].append(str(html_file.relative_to(output_dir)))

            if validation["empty_body"]:
                results["empty_body"].append(str(html_file.relative_to(output_dir)))

    return results


def print_validation_results(results: dict[str, list[str]]) -> None:
    """Print validation results in a user-friendly format.

    Args:
        results: Validation results dictionary from validate_html_files().
    """
    if results["all_valid"]:
        print("\n✓ HTML validation passed: All HTML files are structurally complete")
        return

    print("\n⚠ HTML validation detected issues:")
    print("=" * 60)

    if results["missing_head"]:
        print(f"  Missing head element ({len(results['missing_head'])} files):")
        for f in results["missing_head"][:5]:
            print(f"    - {f}")
        if len(results["missing_head"]) > 5:
            print(f"    ... and {len(results['missing_head']) - 5} more")

    if results["missing_body"]:
        print(f"  Missing body element ({len(results['missing_body'])} files):")
        for f in results["missing_body"][:5]:
            print(f"    - {f}")
        if len(results["missing_body"]) > 5:
            print(f"    ... and {len(results['missing_body']) - 5} more")

    if results["empty_body"]:
        print(f"  Empty body content ({len(results['empty_body'])} files):")
        for f in results["empty_body"][:5]:
            print(f"    - {f}")
        if len(results['empty_body']) > 5:
            print(f"    ... and {len(results['empty_body']) - 5} more")

    print("=" * 60)
    print("This indicates an incomplete download. Possible causes:")
    print("  - Network timeout or connection loss during wget pass 1")
    print("  - Server returning incomplete content")
    print("  - Wget interrupted or crashed")
    print("\nRecommendation: Re-run the download or check the site manually in a browser")
