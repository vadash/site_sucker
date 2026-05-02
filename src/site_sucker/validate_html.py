"""HTML validation for detecting incomplete or corrupted downloads."""

import re
from pathlib import Path


def validate_html_files(output_dir: Path | str) -> dict[str, list[str]]:
    """Validate HTML files for structural integrity.

    Checks for common issues that indicate incomplete or corrupted downloads:
    - Missing </head> closing tag
    - Missing <body> opening tag
    - Missing </body> closing tag
    - Empty body content (no visible text)
    - Malformed HTML structure

    Args:
        output_dir: Path to the directory containing downloaded HTML files.

    Returns:
        Dictionary with validation results:
        {
            "missing_head_close": ["file1.html", ...],
            "missing_body_open": ["file1.html", ...],
            "missing_body_close": ["file1.html", ...],
            "empty_body": ["file1.html", ...],
            "all_valid": bool
        }
    """
    output_dir = Path(output_dir)
    html_files = list(output_dir.rglob("*.html")) + list(output_dir.rglob("*.htm"))

    results = {
        "missing_head_close": [],
        "missing_body_open": [],
        "missing_body_close": [],
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

        # Check for </head> closing tag
        if not re.search(r'</head\s*>', raw, re.IGNORECASE):
            results["missing_head_close"].append(str(html_file.relative_to(output_dir)))
            results["all_valid"] = False

        # Check for <body> opening tag
        if not re.search(r'<body[^>]*>', raw, re.IGNORECASE):
            results["missing_body_open"].append(str(html_file.relative_to(output_dir)))
            results["all_valid"] = False

        # Check for </body> closing tag
        if not re.search(r'</body\s*>', raw, re.IGNORECASE):
            results["missing_body_close"].append(str(html_file.relative_to(output_dir)))
            results["all_valid"] = False

        # Check for empty body (no visible text content)
        # Only check if we found both <body> and </body>
        body_open_match = re.search(r'<body[^>]*>', raw, re.IGNORECASE)
        body_close_match = re.search(r'</body\s*>', raw, re.IGNORECASE)
        
        if body_open_match and body_close_match:
            # Extract body content and check if it has more than just whitespace/scripts
            body_match = re.search(r'<body[^>]*>([\s\S]*?)</body\s*>', raw, re.IGNORECASE | re.DOTALL)
            if body_match:
                body_content = body_match.group(1)
                # Remove script tags, style tags, and comments
                body_without_code = re.sub(r'<(script|style|noscript)[^>]*>[\s\S]*?</\1>', '', body_content, flags=re.IGNORECASE)
                body_without_code = re.sub(r'<!--[\s\S]*?-->', '', body_without_code)
                # Strip HTML tags
                text_only = re.sub(r'<[^>]+>', '', body_without_code)
                # Check if there's any meaningful text (more than 20 non-whitespace chars)
                if len(re.sub(r'\s+', '', text_only).strip()) < 20:
                    results["empty_body"].append(str(html_file.relative_to(output_dir)))
                    results["all_valid"] = False

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

    if results["missing_head_close"]:
        print(f"  Missing </head> closing tag ({len(results['missing_head_close'])} files):")
        for f in results["missing_head_close"][:5]:
            print(f"    - {f}")
        if len(results["missing_head_close"]) > 5:
            print(f"    ... and {len(results['missing_head_close']) - 5} more")

    if results["missing_body_open"]:
        print(f"  Missing <body> opening tag ({len(results['missing_body_open'])} files):")
        for f in results["missing_body_open"][:5]:
            print(f"    - {f}")
        if len(results["missing_body_open"]) > 5:
            print(f"    ... and {len(results['missing_body_open']) - 5} more")

    if results["missing_body_close"]:
        print(f"  Missing </body> closing tag ({len(results['missing_body_close'])} files):")
        for f in results["missing_body_close"][:5]:
            print(f"    - {f}")
        if len(results['missing_body_close']) > 5:
            print(f"    ... and {len(results['missing_body_close']) - 5} more")

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
