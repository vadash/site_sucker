"""CLI entry point for SiteSucker."""

import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from site_sucker import mirror, report, settings


def normalize_url(url: str) -> str:
    """Normalize URL by adding https:// scheme if missing.

    Args:
        url: URL string to normalize.

    Returns:
        URL with https:// scheme if it was missing.
    """
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="SiteSucker - Universal Wiki/Site Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s https://wiki.projectdiablo2.com/wiki/Main_Page
  %(prog)s https://example.com --parallel 8 --depth 2
        """,
    )

    parser.add_argument(
        "url",
        nargs="?",
        help="The base URL to mirror",
    )

    parser.add_argument(
        "-o", "--output-dir",
        help="Output directory path (default: ./downloads/<domain>)",
    )

    parser.add_argument(
        "-s", "--settings",
        dest="settings_path",
        help="Path to custom settings.jsonc (default: ./settings.jsonc)",
    )

    parser.add_argument(
        "-d", "--depth",
        type=int,
        default=0,
        help="Maximum recursion depth (default: 0 = unlimited)",
    )

    parser.add_argument(
        "-p", "--parallel",
        type=int,
        default=4,
        help="Number of parallel downloads for external media (default: 4)",
    )

    parser.add_argument(
        "-r", "--reject",
        dest="extra_reject",
        action="append",
        help="Additional URL patterns to reject. Use ; for multiple patterns. "
             "Supports range expressions: {1..100}, {1..100..2}, {1..100%%4,25,40}. "
             "Example: --reject 'f={1..100%%4,25,40}&' rejects forum IDs 1-100 except 4,25,40",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted download from existing output directory. "
             "Uses Python BFS crawler instead of wget --mirror to bypass 429 bot protection. "
             "Requires --output-dir pointing to existing download.",
    )

    return parser.parse_args()


def interactive_prompt(default_url: str = "", default_output: str = "",
                       default_depth: int = 0, default_parallel: int = 4) -> tuple[str, str, int, int]:
    """Prompt user for missing parameters interactively.

    Args:
        default_url: Default URL value.
        default_output: Default output directory.
        default_depth: Default max depth.
        default_parallel: Default parallel downloads.

    Returns:
        Tuple of (url, output_dir, depth, parallel).
    """
    print("\nSiteSucker - Universal Site Downloader")
    print("=" * 50)

    if not default_url:
        url_input = input("Site URL to mirror: ").strip()
        if not url_input:
            print("Error: URL is required.")
            raise SystemExit(1)
        url = url_input
    else:
        url = default_url

    if not default_output:
        output_input = input(f"Output folder [{default_output}]: ").strip()
        output_dir = output_input or default_output
    else:
        output_dir = default_output

    depth_input = input(f"Max depth (0=unlimited) [{default_depth}]: ").strip()
    depth = int(depth_input) if depth_input else default_depth

    parallel_input = input(f"Number of parallel downloads [{default_parallel}]: ").strip()
    parallel = int(parallel_input) if parallel_input else default_parallel

    return url, output_dir, depth, parallel


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load settings
    cfg = settings.load_settings(args.settings_path)

    # Merge CLI overrides
    cfg = settings.merge_cli_overrides(cfg, args.parallel, args.depth, args.extra_reject)

    # Parse URL and determine target domain
    url = args.url
    target_domain = ""

    if not url:
        # Interactive mode
        output_root = Path(cfg.output_root)

        # Need URL first to determine defaults
        try:
            test_url = urlparse(url)
        except Exception:
            test_url = None

        url, output_dir, depth, parallel = interactive_prompt(
            default_parallel=cfg.parallel_downloads,
            default_depth=cfg.max_depth,
        )

        cfg = settings.merge_cli_overrides(cfg, parallel, depth, None)
    else:
        try:
            parsed = urlparse(url)
            target_domain = parsed.hostname or ""
        except Exception as e:
            print(f"Error: Invalid URL: {url}")
            raise SystemExit(1) from e

        # Determine output directory
        if args.output_dir:
            output_dir = args.output_dir
        else:
            output_dir = Path(cfg.output_root) / target_domain

    # Normalize URL scheme
    url = normalize_url(url)

    # Final URL parsing
    try:
        parsed = urlparse(url)
        target_domain = parsed.hostname or ""
    except Exception as e:
        print(f"Error: Invalid URL: {url}")
        raise SystemExit(1) from e

    if not target_domain:
        print(f"Error: Could not extract domain from URL: {url}")
        raise SystemExit(1)

    # Create output directory (resolve to absolute path to prevent file bleed)
    output_path = Path(output_dir).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now()

    try:
        # Execute the mirror
        failed_urls = mirror.invoke_site_mirror(
            url=url,
            output_dir=output_path,
            target_domain=target_domain,
            settings=cfg,
            resume=args.resume,
        )

        # Write report
        report.write_site_report(
            output_dir=output_path,
            start_time=start_time,
            failed_urls=failed_urls,
        )
    except Exception as e:
        print(f"Error during download: {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
