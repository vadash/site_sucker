"""Crawler abstraction for unified wget and BFS crawling modes.

Provides a common interface for both wget-based mirroring and Python BFS crawling,
enabling the mirror pipeline to be mode-agnostic.
"""

import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from site_sucker.resume import crawl_loop as bfs_crawl_loop
from site_sucker.settings import Settings
from site_sucker.validate_html import print_validation_results, validate_html_files
from site_sucker.wget import build_wget_args, get_wget_path


@dataclass
class CrawlResult:
    """Result of a crawl operation.

    Attributes:
        failed_urls: List of URLs that failed to download.
        needs_internal_link_repair: True if BFS mode was used (requires internal link rewriting).
    """
    failed_urls: list[str]
    needs_internal_link_repair: bool


class CrawlerBase(ABC):
    """Abstract base class for crawler implementations."""

    def __init__(
        self,
        url: str,
        output_dir: Path,
        target_domain: str,
        settings: Settings,
    ):
        """Initialize the crawler.

        Args:
            url: The seed URL to start crawling from.
            output_dir: Directory to save downloaded files.
            target_domain: Primary domain being mirrored.
            settings: Settings instance.
        """
        self.url = url
        self.output_dir = Path(output_dir)
        self.target_domain = target_domain
        self.settings = settings

    @abstractmethod
    def run(self) -> CrawlResult:
        """Execute the crawl.

        Returns:
            CrawlResult with failed URLs and a flag indicating if internal link repair is needed.
        """
        pass


class WgetCrawler(CrawlerBase):
    """Wget-based crawler for full site mirroring."""

    def run(self) -> CrawlResult:
        """Execute wget-based mirroring.

        Runs wget with --mirror flags, then validates HTML integrity.

        Returns:
            CrawlResult with empty failed_urls (wget handles its own retries) and
            needs_internal_link_repair=False (wget's --convert-links handles this).
        """
        print(f"\n[1/4] Mirroring {self.url} (wget mode)...")

        # Disable proxies for subprocess calls
        env = os.environ.copy()
        for var in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
            env.pop(var, None)

        wget_path = get_wget_path()

        pass1_args = build_wget_args(
            self.settings,
            self.output_dir,
            extra_args=[
                "-r",
                "-N",
                "--no-remove-listing",
                "--no-parent",
                "--page-requisites",
                f"--domains={self.target_domain}",
            ],
        )

        result = subprocess.run(
            [str(wget_path), *pass1_args, self.url],
            capture_output=False,
            env=env,
        )

        if result.returncode not in (0, 8):
            print(f"Warning: wget pass 1 exited with code {result.returncode}")

        # Validate HTML integrity
        validation_results = validate_html_files(self.output_dir)
        print_validation_results(validation_results)

        return CrawlResult(
            failed_urls=[],
            needs_internal_link_repair=False,
        )


class BFSCrawler(CrawlerBase):
    """Python-based BFS crawler for resume mode (bypasses 429 bot protection)."""

    def run(self) -> CrawlResult:
        """Execute Python BFS crawling.

        Runs the native HTTP crawler that bypasses wget's -nc + --convert-links incompatibility.

        Returns:
            CrawlResult with empty failed_urls (BFS crawler tracks its own failures) and
            needs_internal_link_repair=True (wget didn't run, so links need rewriting).
        """
        print(f"\n[1/4] Resume mode: Python BFS crawler (bypassing 429 bot protection)...")

        bfs_crawl_loop(
            self.url,
            self.output_dir,
            self.target_domain,
            self.settings,
        )

        return CrawlResult(
            failed_urls=[],
            needs_internal_link_repair=True,
        )
