"""File iteration utilities for HTML and CSS processing.

Shared by media scanner, link repair, offline repair, and validation modules.
"""

from collections.abc import Iterator
from pathlib import Path

from bs4 import BeautifulSoup


def iter_html_files(output_dir: Path) -> Iterator[tuple[Path, str]]:
    """Iterate over all HTML files in the output directory.

    Yields tuples of (file_path, content) with standard error handling.
    Files with read errors or empty content are skipped.

    Args:
        output_dir: Root directory to search for HTML files.

    Yields:
        Tuples of (file_path, content) for each valid HTML file.
    """
    output_dir = Path(output_dir)
    html_files = list(output_dir.rglob("*.html")) + list(output_dir.rglob("*.htm"))

    for html_file in html_files:
        try:
            with open(html_file, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue

        if not content:
            continue

        yield html_file, content


def iter_parsed_html(output_dir: Path) -> Iterator[tuple[Path, BeautifulSoup]]:
    """Iterate over all HTML files in the output directory, parsed with BeautifulSoup.

    Yields tuples of (file_path, soup) with standard error handling.
    Files with read errors or empty content are skipped.

    Args:
        output_dir: Root directory to search for HTML files.

    Yields:
        Tuples of (file_path, BeautifulSoup) for each valid HTML file.
    """
    for file_path, content in iter_html_files(output_dir):
        yield file_path, BeautifulSoup(content, "lxml")


def iter_css_files(output_dir: Path) -> Iterator[tuple[Path, str]]:
    """Iterate over all CSS files in the output directory.

    Yields tuples of (file_path, content) with standard error handling.
    Files with read errors or empty content are skipped.

    Args:
        output_dir: Root directory to search for CSS files.

    Yields:
        Tuples of (file_path, content) for each valid CSS file.
    """
    output_dir = Path(output_dir)
    css_files = list(output_dir.rglob("*.css"))

    for css_file in css_files:
        try:
            with open(css_file, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue

        if not content:
            continue

        yield css_file, content


def write_if_changed(file_path: Path, original: str, new_content: str) -> bool:
    """Write content to file only if it has changed.

    Compares the original content with the new content and only writes to disk
    if they differ. This avoids unnecessary disk writes and preserves file timestamps.

    Args:
        file_path: Path to the file to write.
        original: Original file content (for comparison).
        new_content: New content to write if different from original.

    Returns:
        True if file was written (content changed), False otherwise.
    """
    if new_content != original:
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            f.write(new_content)
        return True
    return False
