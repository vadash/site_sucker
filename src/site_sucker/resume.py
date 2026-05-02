"""Resume mode: Python-based BFS crawler to bypass 429 bot protection.

Replaces wget's built-in spidering with Python-managed link discovery.
Wget becomes a single-file downloader (--level=1, no recursion).
"""

import os
import re
import subprocess
import time
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def url_to_filepath(url: str, output_dir: Path) -> Path:
    """Convert a URL to its expected local file path (wget --restrict-file-names=windows).

    Does NOT append .html extension — that's handled by file_exists_on_disk().
    This is a forward-only mapping: we don't need to reverse-engineer filenames.

    Args:
        url: The URL to convert.
        output_dir: Root output directory.

    Returns:
        Expected local file path (may or may not exist).
    """
    parsed = urlparse(url)

    # Reconstruct path with query params, but fragment
    # wget converts ? and # to @ for Windows compatibility
    path = parsed.path

    # Handle root URLs and trailing slashes (Wget saves these as index.html)
    if not path or path.endswith("/"):
        path = path + "index.html"

    # Append query parameters (if any) - wget converts ? to @
    if parsed.query:
        # Escape / in query params as %2F to avoid directory creation
        escaped_query = parsed.query.replace("/", "%2F")
        path = f"{path}@{escaped_query}"

    # Don't include fragments - wget strips them

    # Build full path
    if path.startswith("/"):
        path = path[1:]  # Remove leading slash for relative path

    full_path = output_dir / path
    return full_path


def file_exists_on_disk(expected_path: Path) -> bool:
    """Check if a file exists on disk, accounting for wget's --adjust-extension behavior.

    Wget appends .html to files without extensions when Content-Type is text/html.
    We check both the exact path and the .html-appended variant.

    Args:
        expected_path: Expected path from url_to_filepath().

    Returns:
        True if file exists (with or without .html suffix).
    """
    # Check exact match first
    if expected_path.exists() and expected_path.is_file():
        return True

    # Check with .html appended (wget's adjust-extension behavior)
    html_path = Path(str(expected_path) + ".html")
    if html_path.exists() and html_path.is_file():
        return True

    return False


def resolve_local_file(expected_path: Path) -> Path | None:
    """Resolve which file actually exists on disk (with or without .html suffix).

    Args:
        expected_path: Expected path from url_to_filepath().

    Returns:
        Actual file path if it exists, None otherwise.
    """
    # Check exact match first
    if expected_path.exists() and expected_path.is_file():
        return expected_path

    # Check with .html appended
    html_path = Path(str(expected_path) + ".html")
    if html_path.exists() and html_path.is_file():
        return html_path

    return None


def discover_links(
    html_file: Path,
    base_url: str,
    target_domain: str,
    reject_patterns: list[str] | None = None,
    reject_domains: list[str] | None = None,
) -> set[str]:
    """Extract all internal links from an HTML file using BeautifulSoup.

    Args:
        html_file: Path to HTML file to parse.
        base_url: Base URL of this HTML file (used to resolve relative links).
        target_domain: Primary domain to filter links (only keep links to this domain).
        reject_patterns: List of substring patterns to reject (e.g., ["action=", "Special:"]).
        reject_domains: List of domains to reject (e.g., ["analytics.example.com"]).

    Returns:
        Set of absolute URLs belonging to target_domain, after reject filtering.
    """
    links = set()

    try:
        with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except (IOError, OSError):
        return links

    if not content:
        return links

    soup = BeautifulSoup(content, "lxml")

    # Extract all href attributes from <a> tags
    for tag in soup.find_all("a", href=True):
        href = tag["href"]

        # Skip anchors, javascript, and mailto links
        if href.startswith(("#", "javascript:", "mailto:")):
            continue

        # Convert relative links to absolute using base_url
        absolute_url = urljoin(base_url, href)

        # Parse URL
        try:
            parsed = urlparse(absolute_url)
        except Exception:
            continue

        # Skip non-HTTP links
        if parsed.scheme not in ("http", "https"):
            continue

        # Check if belongs to target domain
        if parsed.hostname != target_domain:
            continue

        # Apply reject patterns (substring match)
        if reject_patterns:
            rejected = False
            for pattern in reject_patterns:
                if pattern in absolute_url:
                    rejected = True
                    break
            if rejected:
                continue

        # Apply reject domains (hostname match)
        if reject_domains:
            if any(parsed.hostname == domain for domain in reject_domains if parsed.hostname):
                continue

        # Normalize URL: strip fragment to avoid duplicates
        normalized = absolute_url.split("#")[0]
        links.add(normalized)

    return links


def crawl_loop(
    url: str,
    output_dir: Path,
    target_domain: str,
    settings: dict[str, Any],
    wget_path: Path,
) -> None:
    """BFS crawl loop: discover links, download missing files, repeat.

    Wget is only used as a single-file downloader (--level=1, no recursion).
    All crawl state (visited, queue, depth) is managed in Python.

    Args:
        url: Seed URL to start crawling from.
        output_dir: Output directory for downloaded files.
        target_domain: Primary domain being mirrored.
        settings: Configuration dictionary.
        wget_path: Path to wget.exe binary.
    """
    # Disable proxies for subprocess calls
    env = os.environ.copy()
    for var in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
        env.pop(var, None)

    # Get settings
    max_depth = settings.get("MaxDepth", 0)
    wait_seconds = settings.get("WaitBetweenRequests", 1.5)
    user_agent = settings["UserAgent"]
    timeout = settings["Timeout"]
    retries = settings["Retries"]

    # Crawl state
    visited = set()
    queue = deque()
    queue.append((url, 0))  # (url, depth)

    reject_patterns = settings.get("RejectPatterns", [])
    reject_domains = settings.get("RejectDomains", [])

    iteration = 0
    total_downloaded = 0

    print(f"\n[*] Starting BFS crawl loop from {url}")
    print(f"    MaxDepth: {max_depth if max_depth > 0 else 'unlimited'}")
    print(f"    Target domain: {target_domain}")

    while queue:
        iteration += 1
        current_url, depth = queue.popleft()

        # Skip if already visited
        if current_url in visited:
            continue
        visited.add(current_url)

        # Skip if depth exceeded
        if max_depth > 0 and depth > max_depth:
            continue

        # Map URL to expected file path
        expected_path = url_to_filepath(current_url, output_dir)
        file_existed = file_exists_on_disk(expected_path)

        # Download if missing
        if not file_existed:
            print(f"  [{iteration}] Downloading (depth={depth}): {current_url}")

            # Build wget args for single-page fetch
            args = [
                str(wget_path),
                "-e", "robots=off",
                "--no-proxy",
                "--no-verbose",
                "--restrict-file-names=windows",
                "--no-host-directories",
                f"--directory-prefix={output_dir}",
                f"--user-agent={user_agent}",
                f"--timeout={timeout}",
                f"--tries={retries}",
                "--header=Accept-Encoding: identity",
                "--level=1",  # No recursion, fetch single page
                "--adjust-extension",
                current_url,
            ]

            result = subprocess.run(args, capture_output=True, env=env)

            if result.returncode not in (0, 8):
                print(f"    Warning: wget exited with code {result.returncode}")

            total_downloaded += 1

            # Respect rate limiting
            if wait_seconds > 0:
                time.sleep(wait_seconds)
        else:
            print(f"  [{iteration}] Using cached (depth={depth}): {current_url}")

        # Resolve the actual file path (with or without .html suffix)
        actual_path = resolve_local_file(expected_path)
        if not actual_path:
            print(f"    Error: File not found after download attempt: {expected_path}")
            continue

        # Parse HTML for links (regardless of whether we just downloaded or used cache)
        new_links = discover_links(
            actual_path,
            current_url,
            target_domain,
            reject_patterns,
            reject_domains,
        )

        # Enqueue newly discovered links at depth+1
        for link in new_links:
            if link not in visited:
                queue.append((link, depth + 1))

    print(f"\n[*] BFS crawl complete:")
    print(f"    Visited {len(visited)} URLs")
    print(f"    Downloaded {total_downloaded} new files")
