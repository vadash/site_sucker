"""Wget binary resolver and argument builder."""

import os
from pathlib import Path

from site_sucker.settings import Settings


def get_wget_path() -> Path:
    """Resolve the path to wget.exe binary.

    Looks for wget.exe in the bin/ directory relative to the project root.

    Returns:
        Path to wget.exe.

    Raises:
        FileNotFoundError: If wget.exe is not found in bin/ directory.
    """
    # Assume we're in src/site_sucker/, go up to project root
    module_dir = Path(__file__).parent.parent.parent
    wget_path = module_dir / "bin" / "wget.exe"

    if not wget_path.exists():
        raise FileNotFoundError(
            f"wget.exe not found at: {wget_path}. "
            "Please ensure wget.exe is in the bin/ directory."
        )

    return wget_path


def build_wget_args(
    settings: Settings,
    output_dir: Path | str,
    extra_args: list[str] | None = None,
    no_link_conversion: bool = False,
) -> list[str]:
    """Build wget argument array from settings and CLI parameters.

    Args:
        settings: Settings instance.
        output_dir: Output directory path for downloaded files.
        extra_args: Additional arguments to pass to wget.
        no_link_conversion: If True, skip --convert-links and --adjust-extension.

    Returns:
        List of wget command-line arguments.
    """
    args = [
        "-e", "robots=off",
        "--no-proxy",
        "--no-verbose",
        "--restrict-file-names=windows",
        "--no-host-directories",
        f"--directory-prefix={output_dir}",
        f"--user-agent={settings.user_agent}",
        f"--timeout={settings.timeout}",
        f"--tries={settings.retries}",
        "--header=Accept-Encoding: identity",
    ]

    # Respect MaxDepth (0 = infinite)
    if settings.max_depth > 0:
        args.append(f"--level={settings.max_depth}")
    else:
        args.append("--level=inf")

    # Add wait if specified (helps avoid 429 rate limiting)
    if settings.wait_between_requests > 0:
        args.append(f"--wait={settings.wait_between_requests}")
        args.append("--random-wait")

    # Only add link conversion for pass 1 (mirroring), not pass 2 (plain downloads)
    if not no_link_conversion:
        args.append("--convert-links")
        args.append("--adjust-extension")

    # Build reject-regex from patterns and domains
    reject_parts = []

    if settings.reject_patterns:
        reject_parts.extend(settings.reject_patterns)

    if settings.reject_domains:
        reject_domains = "|".join(settings.reject_domains)
        reject_parts.append(f"({reject_domains})")

    # Forum-specific: reject viewtopic.php?p= per-post duplicates
    # Split into separate patterns to avoid POSIX ERE precedence bugs with |
    reject_parts.append(r"viewtopic\.php.*&p=[0-9]+")
    reject_parts.append(r"viewtopic\.php\?p=[0-9]+")

    if reject_parts:
        combined = "|".join(reject_parts)
        args.append("--reject-regex")
        args.append(f".*({combined}).*")

    if extra_args:
        args.extend(extra_args)

    return args


def get_clean_env() -> dict[str, str]:
    """Get a clean environment with proxy variables removed.

    Creates a copy of the current environment and removes all proxy-related
    environment variables to prevent subprocess calls from using proxies.

    Returns:
        Environment dictionary with proxy variables removed.
    """
    env = os.environ.copy()
    for var in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
        env.pop(var, None)
    return env
