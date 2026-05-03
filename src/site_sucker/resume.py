"""Resume mode: Python-based BFS crawler to bypass 429 bot protection.

Replaces wget's built-in spidering with Python-managed link discovery and native HTTP fetching.
Uses requests.Session for persistent connections and automatic retry with backoff.
"""

import logging
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bs4 import BeautifulSoup

from site_sucker.paths import get_actual_save_path, url_to_filepath
from site_sucker.settings import Settings

logger = logging.getLogger(__name__)
from site_sucker.url_filter import extract_internal_urls, should_reject_url


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
    try:
        with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except (IOError, OSError):
        return set()

    if not content:
        return set()

    soup = BeautifulSoup(content, "lxml")

    # Use shared URL extraction utility
    return extract_internal_urls(
        soup,
        base_url,
        target_domain,
        reject_patterns,
        reject_domains,
    )


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

    import_pattern = re.compile(r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\'](?:\s*\))?;')

    for match in import_pattern.finditer(content):
        import_path = match.group(1)

        if import_path.startswith(('http://', 'https://')):
            continue

        absolute_url = urljoin(base_url, import_path)

        # Use shared URL filter
        if should_reject_url(
            absolute_url,
            target_domain,
            reject_patterns,
            reject_domains,
        ):
            continue

        imports.add(absolute_url)

    return imports


class ResumeCrawler:
    """Manages the BFS crawl state and native HTTP fetching."""

    def __init__(self, output_dir: Path, target_domain: str, settings: Settings, session: requests.Session | None = None):
        self.output_dir = output_dir
        self.target_domain = target_domain
        self.settings = settings

        self.max_depth = settings.max_depth
        self.wait_seconds = settings.wait_between_requests
        self.timeout = settings.timeout
        self.retries = settings.retries

        self.reject_patterns = settings.reject_patterns
        self.reject_domains = settings.reject_domains

        # State
        self.visited = set()
        self.queue = deque()
        self.stats = {"downloaded": 0, "cached": 0, "failed": 0}

        # Configure requests session with retry logic
        # Allow session injection for testing
        self.session = session if session is not None else self._build_default_session()

    def _build_default_session(self) -> requests.Session:
        """Build a default requests session with retry logic.

        Returns:
            Configured requests.Session instance.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": self.settings.user_agent, "Accept-Encoding": "identity"})
        return session

    def fetch_file(self, url: str, save_path: Path) -> bool:
        """Fetch a file natively using Python, handling redirects and retries.

        Args:
            url: URL to fetch.
            save_path: Where to save the file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            response = self.session.get(url, timeout=self.timeout, stream=False)
            response.raise_for_status()

            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(response.content)
            return True
        except requests.RequestException as e:
            logger.error("Fetch failed: %s", e)
            return False

    def run(self, seed_url: str):
        """Execute the BFS crawl loop.

        Args:
            seed_url: Starting URL for the crawl.
        """
        self.queue.append((seed_url, 0))
        iteration = 0

        logger.info("[*] BFS crawl: %s (depth=%s)", self.target_domain, self.max_depth if self.max_depth > 0 else 'unlimited')

        while self.queue:
            iteration += 1
            current_url, depth = self.queue.popleft()

            if current_url in self.visited:
                continue
            self.visited.add(current_url)

            if self.max_depth > 0 and depth > self.max_depth:
                continue

            # Determine where this file lives locally
            base_path = url_to_filepath(current_url, self.output_dir)
            actual_path = get_actual_save_path(base_path)

            file_existed = actual_path.exists()

            # Download if missing
            if not file_existed:
                parsed_url = urlparse(current_url)
                short_path = parsed_url.path + (f"?{parsed_url.query}" if parsed_url.query else "")
                print(f"\r  [{len(self.visited)} visited | {len(self.queue)} queued] GET {short_path}", end="", flush=True)

                success = self.fetch_file(current_url, actual_path)

                if success:
                    self.stats["downloaded"] += 1
                else:
                    self.stats["failed"] += 1
                    continue

                if self.wait_seconds > 0:
                    time.sleep(self.wait_seconds)
            else:
                self.stats["cached"] += 1
                print(
                    f"\r  [{len(self.visited)} visited | {len(self.queue)} queued]"
                    f" cached: {self.stats['cached']}, downloaded: {self.stats['downloaded']}",
                    end="", flush=True,
                )

            # Parse the file for new links
            self.process_discovered_links(current_url, actual_path, depth)

        print()  # newline after progress counter

        failure_suffix = f" ({self.stats['failed']} failed)" if self.stats['failed'] > 0 else ""
        logger.info("[*] BFS complete: %d visited, %d downloaded%s", len(self.visited), self.stats['downloaded'], failure_suffix)

    def process_discovered_links(self, current_url: str, local_path: Path, current_depth: int):
        """Extract links from HTML or CSS and add to queue.

        Args:
            current_url: The URL of the file being parsed.
            local_path: Local path to the file.
            current_depth: Current depth in the BFS tree.
        """
        if local_path.suffix.lower() in [".html", ".htm"]:
            new_links = discover_links(
                local_path,
                current_url,
                self.target_domain,
                self.reject_patterns,
                self.reject_domains,
            )
            for link in new_links:
                if link not in self.visited:
                    self.queue.append((link, current_depth + 1))

        elif local_path.suffix.lower() == ".css":
            css_imports = discover_css_imports(
                local_path,
                current_url,
                self.target_domain,
                self.reject_patterns,
                self.reject_domains,
            )
            for css_url in css_imports:
                if css_url not in self.visited:
                    self.queue.append((css_url, current_depth + 1))


def crawl_loop(
    url: str,
    output_dir: Path,
    target_domain: str,
    settings: Settings,
    wget_path: Path | None = None,
) -> None:
    """Entry point for the resume crawler.

    Args:
        url: Seed URL to start crawling from.
        output_dir: Output directory for downloaded files.
        target_domain: Primary domain being mirrored.
        settings: Settings instance.
        wget_path: Ignored (kept for backwards compatibility).
    """
    crawler = ResumeCrawler(output_dir, target_domain, settings)
    crawler.run(url)
