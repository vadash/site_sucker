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


def _check_path_exists(path: Path) -> bool:
    """Check if a path exists and is a file."""
    return path.exists() and path.is_file()


# Extensions wget may append via --adjust-extension based on Content-Type.
# .html is the most common (text/html), but wget also appends the actual
# content-type extension on top of query-string filenames, producing
# double extensions like "style.css@ver=123.css".
_ADJUST_EXTENSION_SUFFIXES = (".html", ".htm", ".css", ".js", ".json", ".xml")


def file_exists_on_disk(expected_path: Path) -> bool:
    """Check if a file exists on disk, accounting for wget's --adjust-extension behavior.

    Wget appends extensions based on Content-Type. For .php URLs it adds .html,
    but for CSS/JS URLs with query strings it produces double extensions like
    "style.css@ver=123.css". We check the exact path plus all plausible suffixes.

    Args:
        expected_path: Expected path from url_to_filepath().

    Returns:
        True if file exists (with or without an appended extension).
    """
    if _check_path_exists(expected_path):
        return True

    for suffix in _ADJUST_EXTENSION_SUFFIXES:
        if _check_path_exists(Path(str(expected_path) + suffix)):
            return True

    return False


def resolve_local_file(expected_path: Path, output_dir: Path) -> Path | None:
    """Resolve which file actually exists on disk (accounting for --adjust-extension).

    Checks locations in order:
    1. Exact expected path
    2. With content-type extension appended (wget's --adjust-extension behavior)
    3. Flattened to output_dir root (wget without -r saves files flat)

    Args:
        expected_path: Expected path from url_to_filepath().
        output_dir: Root output directory for flattened file fallback.

    Returns:
        Actual file path if it exists, None otherwise.
    """
    if _check_path_exists(expected_path):
        return expected_path

    for suffix in _ADJUST_EXTENSION_SUFFIXES:
        suffixed = Path(str(expected_path) + suffix)
        if _check_path_exists(suffixed):
            return suffixed

    # Fallback: check flattened path (wget without -r saves files at root)
    # e.g., expected images/art/foo.jpg -> check output_dir/foo.jpg
    flat_path = output_dir / expected_path.name
    if _check_path_exists(flat_path):
        return flat_path

    return None


def discover_links(
    html_file: Path,
    base_url: str,
    target_domain: str,
    reject_patterns: list[str] | None = None,
    reject_domains: list[str] | None = None,
) -> set[str]:
    """Extract all internal links and page requisites from an HTML file.

    Replicates wget's --page-requisites behavior by extracting both navigation
    links (<a> tags) and embedded resources (img, script, link, video, audio, source).

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

    def _add_url(url_attr: str):
        """Add a URL to the links set after validation and filtering."""
        # Skip anchors, JS, mailto, and inline base64 data
        if url_attr.startswith(("#", "javascript:", "mailto:", "data:")):
            return

        absolute_url = urljoin(base_url, url_attr)

        try:
            parsed = urlparse(absolute_url)
        except Exception:
            return

        if parsed.scheme not in ("http", "https"):
            return
        if parsed.hostname != target_domain:
            return

        if reject_patterns:
            if any(pattern in absolute_url for pattern in reject_patterns):
                return

        if reject_domains:
            if any(parsed.hostname == domain for domain in reject_domains if parsed.hostname):
                return

        normalized = absolute_url.split("#")[0]
        links.add(normalized)

    # 1. Grab normal HTML navigation links
    for tag in soup.find_all("a", href=True):
        _add_url(tag["href"])

    # 2. Grab internal page requisites (images, css, js, video, audio)
    for tag in soup.find_all(["img", "script", "link", "video", "audio", "source"]):
        for attr in ("src", "href", "data-src"):
            val = tag.get(attr)
            if val:
                _add_url(val)

    return links


def discover_css_imports(
    css_file: Path,
    base_url: str,
    target_domain: str,
    reject_patterns: list[str] | None = None,
    reject_domains: list[str] | None = None,
) -> set[str]:
    """Extract CSS @import references from a CSS file.

    Parses CSS files for @import statements (both url("...") and "..." syntax).
    This ensures CSS dependency chains are downloaded during BFS crawling.

    Args:
        css_file: Path to CSS file to parse.
        base_url: Base URL of this CSS file (used to resolve relative paths).
        target_domain: Primary domain to filter URLs (only keep URLs to this domain).
        reject_patterns: List of substring patterns to reject.
        reject_domains: List of domains to reject.

    Returns:
        Set of absolute CSS URLs belonging to target_domain, after reject filtering.
    """
    imports = set()

    try:
        with open(css_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except (IOError, OSError):
        return imports

    if not content:
        return imports

    # Match @import url("...") and @import "..." patterns
    import_pattern = re.compile(
        r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\'](?:\s*\))?;'
    )

    for match in import_pattern.finditer(content):
        import_path = match.group(1)

        # Skip external imports (http/https)
        if import_path.startswith(('http://', 'https://')):
            continue

        # Resolve relative import against base URL
        absolute_url = urljoin(base_url, import_path)

        try:
            parsed = urlparse(absolute_url)
        except Exception:
            continue

        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.hostname != target_domain:
            continue

        if reject_patterns:
            if any(pattern in absolute_url for pattern in reject_patterns):
                continue

        if reject_domains:
            if any(parsed.hostname == domain for domain in reject_domains if parsed.hostname):
                continue

        imports.add(absolute_url)

    return imports


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
    total_cached = 0
    failed_downloads = 0

    print(f"\n[*] BFS crawl: {target_domain} (depth={max_depth if max_depth > 0 else 'unlimited'})")

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
            # Show short URL path (domain already in header)
            parsed_url = urlparse(current_url)
            short_path = parsed_url.path + (f"?{parsed_url.query}" if parsed_url.query else "")
            print(f"  [{iteration}] GET {short_path}")

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
                "-r",            # Recursive mode needed for directory hierarchy
                "--level=1",     # No actual recursion, fetch single page
                "--no-parent",   # Don't traverse up
                "--adjust-extension",
                current_url,
            ]

            result = subprocess.run(args, capture_output=True, env=env)

            if result.returncode not in (0, 8):
                failed_downloads += 1
                stderr_output = result.stderr.decode("utf-8", errors="replace").strip()
                print(f"         ↳ wget exit {result.returncode}")
                if stderr_output:
                    # Show first line of stderr (usually the error message)
                    first_line = stderr_output.split("\n")[0]
                    print(f"         ↳ {first_line}")

            total_downloaded += 1

            # Respect rate limiting
            if wait_seconds > 0:
                time.sleep(wait_seconds)
        else:
            total_cached += 1
            # Show progress using carriage return (overwrite in-place)
            print(f"\r  Cached: {total_cached}, Downloaded: {total_downloaded}", end="", flush=True)

        # Resolve the actual file path (with or without .html suffix)
        actual_path = resolve_local_file(expected_path, output_dir)
        if not actual_path:
            print(f"    Error: File not found after download attempt: {expected_path}")
            continue

        # Parse HTML files for links AND CSS files for @import statements
        # (Skips parsing .png, .js files to save CPU)
        if actual_path.suffix.lower() in [".html", ".htm", ""]:
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

        elif actual_path.suffix.lower() == ".css":
            # Parse CSS for @import statements (e.g., @import url("colors.css"))
            css_imports = discover_css_imports(
                actual_path,
                current_url,
                target_domain,
                reject_patterns,
                reject_domains,
            )

            # Enqueue discovered CSS @import URLs at depth+1
            for css_url in css_imports:
                if css_url not in visited:
                    queue.append((css_url, depth + 1))

    # Clear the progress line by printing newline
    if total_cached > 0:
        print()

    failure_suffix = f" ({failed_downloads} failed)" if failed_downloads > 0 else ""
    print(f"[*] BFS complete: {len(visited)} visited, {total_downloaded} downloaded{failure_suffix}")
