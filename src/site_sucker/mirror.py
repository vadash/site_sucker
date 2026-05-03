"""Main mirroring pipeline orchestrator."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from site_sucker.media import get_external_media
from site_sucker.repair_links import repair_external_links, repair_internal_links
from site_sucker.repair_offline import repair_offline_html
from site_sucker.report import write_site_report
from site_sucker.resume import crawl_loop
from site_sucker.validate_html import print_validation_results, validate_html_files
from site_sucker.wget import build_wget_args, get_wget_path


def invoke_site_mirror(
    url: str,
    output_dir: Path | str,
    target_domain: str,
    settings: dict[str, Any],
    resume: bool = False,
) -> list[str]:
    """Execute the two-pass site mirroring process.

    Orchestrates:
    1. Pass 1: Full site mirror using wget --mirror (or resume mode with BFS crawler)
    2. Pass 2: Download external media with parallelism
    3. Pass 3: Rewrite external URLs in HTML to local paths
    4. Pass 4: Strip online-only resources for offline browsing

    Args:
        url: The base URL to mirror.
        output_dir: Output directory path.
        target_domain: Primary domain (used to filter external media).
        settings: Configuration dictionary.
        resume: If True, use Python BFS crawler instead of wget --mirror.

    Returns:
        List of failed URLs (if any).
    """
    output_dir = Path(output_dir)
    failed_urls = []

    # Disable proxies for subprocess calls
    env = os.environ.copy()
    for var in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
        env.pop(var, None)

    wget_path = get_wget_path()

    # ── PASS 1: Full site mirror (or resume mode) ───────────────────────────────────
    if resume:
        print(f"\n[1/4] Resume mode: Python BFS crawler (bypassing 429 bot protection) ...")
        crawl_loop(url, output_dir, target_domain, settings)

        # Rewrite internal HTML-to-HTML links (wget didn't do --convert-links)
        repair_internal_links(output_dir, target_domain)
    else:
        print(f"\n[1/4] Mirroring {url} (Proxies Disabled, Timeouts Active) ...")

        pass1_args = build_wget_args(
            settings,
            output_dir,
            extra_args=[
                "-r",
                "-N",
                "--no-remove-listing",
                "--no-parent",
                "--page-requisites",
                f"--domains={target_domain}",
            ],
        )

        result = subprocess.run(
            [str(wget_path), *pass1_args, url],
            capture_output=False,
            env=env,
        )

        if result.returncode not in (0, 8):
            print(f"Warning: wget pass 1 exited with code {result.returncode}")

        # ── VALIDATION: Check HTML integrity ────────────────────────────────────────
        validation_results = validate_html_files(output_dir)
        print_validation_results(validation_results)

    # Create log directory for failed replacements (CSS pipeline only)
    log_dir = output_dir / "logs"

    # ── PASS 2: External media with parallelism ────────────────────────────────
    ext_urls = get_external_media(output_dir, target_domain, settings)

    if not ext_urls:
        print("No external media URLs found. Skipping pass 2 & 3.")
        # Still run pass 4 to clean offline HTML
        repair_offline_html(output_dir)
        return failed_urls

    # Create media subdirectory
    media_dir = output_dir / "images"
    media_dir.mkdir(exist_ok=True)

    print(f"\nDownloading external media (parallel: {settings['ParallelDownloads']})...")

    pass2_args = build_wget_args(
        settings,
        media_dir,
        no_link_conversion=True,
        extra_args=[
            "--level=1",
            "--no-directories",
            "-nc",
        ],
    )

    # Process all URLs in parallel using a single thread pool
    url_list = list(ext_urls)
    total_urls = len(url_list)

    print(f"  Downloading {total_urls} external media file(s)...")

    with ThreadPoolExecutor(max_workers=settings["ParallelDownloads"]) as executor:
        futures = {
            executor.submit(
                subprocess.run,
                [str(wget_path), *pass2_args, url],
                capture_output=True,
                env=env,
            ): url
            for url in url_list
        }

        completed_count = 0
        for future in as_completed(futures):
            url = futures[future]
            completed_count += 1
            print(f"  [{completed_count}/{total_urls}] {url}")

            try:
                result = future.result()
                if result.returncode not in (0, 8):
                    failed_urls.append(url)
            except Exception:
                failed_urls.append(url)

    # ── PASS 3: Rewrite external URLs to local paths ────────────────────
    repair_external_links(output_dir, media_dir, ext_urls, log_dir)

    # ── PASS 4: Strip online-only resources for offline browsing ────────────────
    repair_offline_html(output_dir)

    return failed_urls
