# SiteSucker - Universal Wiki/Site Downloader

A Python-based site mirroring tool for creating offline copies of wikis and websites. Converts the original PowerShell implementation to Python with uv for dependency management.

## Features

- **Full Site Mirroring**: Downloads entire sites using wget
- **Parallel Downloads**: Configurable parallelism for external media
- **Intelligent Deduplication**: URL normalization removes duplicates
- **Offline Optimization**: Strips online-only resources (tracking, feeds)
- **Forum Support**: Special handling for phpBB and MediaWiki
- **Configurable**: JSON-based settings with CLI overrides

## Requirements

- **OS**: Windows 11
- **Python**: 3.11+
- **uv**: For package management (optional, for development)

## Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone <repo-url>
cd site_sucker

# Install in development mode
uv pip install -e .
```

### Using pip

```bash
# Clone the repository
git clone <repo-url>
cd site_sucker

# Install in development mode
pip install -e .
```

## Usage

After installation, run the tool using one of these methods:

### Method 1: Python Module (Recommended)

```bash
# Show help
.venv\Scripts\python.exe -m site_sucker --help

# Interactive mode
.venv\Scripts\python.exe -m site_sucker

# Direct mode with URL
.venv\Scripts\python.exe -m site_sucker https://wiki.example.com/wiki/Main_Page

# With options
.venv\Scripts\python.exe -m site_sucker https://example.com --parallel 8 --depth 2
```

### Method 2: Installed Script

```bash
# Show help
.venv\Scripts\site-sucker.exe --help

# Interactive mode
.venv\Scripts\site-sucker.exe

# Direct mode with URL
.venv\Scripts\site-sucker.exe https://wiki.example.com/wiki/Main_Page

# With options
.venv\Scripts\site-sucker.exe https://example.com -o ./my_mirrors/example --parallel 8
```

### Interactive Mode

When you run without arguments, you'll be prompted for:
- Site URL to mirror
- Output folder (default: `./downloads/<domain>`)
- Max depth (default: 0 = unlimited)
- Parallel downloads (default: 4)

### Direct Mode Examples

```bash
# Basic usage
.venv\Scripts\python.exe -m site_sucker https://wiki.example.com/wiki/Main_Page

# Custom output directory
.venv\Scripts\python.exe -m site_sucker https://example.com -o ./my_mirrors/example

# Custom parallelism and depth
.venv\Scripts\python.exe -m site_sucker https://example.com --parallel 8 --depth 2

# Custom settings file
.venv\Scripts\python.exe -m site_sucker https://example.com --settings ./my_settings.json
```

## Configuration

The `settings.json` file controls download behavior:

```json
{
  "UserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
  "Timeout": 15,
  "Retries": 3,
  "MaxDepth": 0,
  "OutputRoot": "./downloads",
  "WaitBetweenRequests": 0.5,
  "ParallelDownloads": 2,
  "RejectPatterns": [
    "action=", "oldid=", "diff=", "printable=",
    "returnto=", "redirect=", "Special:", "Talk:",
    "User:", "User_talk:", "Category_talk:",
    "load.php", "api.php"
  ],
  "RejectDomains": [
    "analytics.wikitide.net",
    "matomo."
  ],
  "MediaExtensions": [
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp4", ".webm", ".avi", ".mkv", ".mov",
    ".svg", ".ico", ".bmp", ".css", ".js", ".woff2"
  ]
}
```

### Settings Explained

| Setting | Description |
|---------|-------------|
| `UserAgent` | User-Agent string for HTTP requests |
| `Timeout` | Connection timeout in seconds |
| `Retries` | Number of retry attempts for failed downloads |
| `MaxDepth` | Maximum recursion depth (0 = unlimited) |
| `OutputRoot` | Default root directory for downloads |
| `WaitBetweenRequests` | Delay between requests (helps avoid rate limiting) |
| `ParallelDownloads` | Number of parallel downloads for external media |
| `RejectPatterns` | URL patterns to skip (for deduplication) |
| `RejectDomains` | Domains to exclude (e.g., analytics) |
| `MediaExtensions` | File extensions considered as media |

## Download Pipeline

SiteSucker uses a 4-pass process:

```
Pass 1: Full site mirror (wget --mirror)
  - Downloads all pages within target domain
  - Applies reject patterns to skip low-value URLs
  - Converts links to local paths

Pass 2: External media collection and download
  - Scans HTML for external media URLs
  - Deduplicates URLs (strips query strings)
  - Downloads in parallel batches

Pass 3: External URL rewriting
  - Rewrites external CDN URLs to local paths
  - Converts absolute CSS paths to relative
  - Strips CORS-blocking attributes

Pass 4: Offline optimization
  - Removes online-only resources (load.php, feeds)
  - Strips tracking/analytics scripts
  - Removes phpBB offline-useless links
  - Injects fallback CSS for readability
```

## Project Structure

```
site_sucker/
├── bin/
│   └── wget.exe              # Wget binary (Windows)
├── src/
│   └── site_sucker/
│       ├── __init__.py
│       ├── __main__.py       # CLI entry point
│       ├── settings.py       # Configuration loading
│       ├── wget.py           # Wget wrapper
│       ├── mirror.py         # Pipeline orchestrator
│       ├── media.py          # External media scanner
│       ├── repair_links.py   # URL rewriter
│       ├── repair_offline.py # Offline optimizer
│       └── report.py         # Report generator
├── tests/
│   ├── conftest.py           # Test fixtures
│   ├── test_settings.py
│   ├── test_wget.py
│   ├── test_media.py
│   ├── test_repair_links.py
│   ├── test_repair_offline.py
│   └── test_report.py
├── settings.json             # Default configuration
├── pyproject.toml            # uv project config
└── README.md
```

## Development

### Running Tests

```bash
# Using the test scripts (recommended)
.\run_tests.bat
# or
.\run_tests.ps1

# Or directly with pytest
.venv\Scripts\python.exe -m pytest

# With coverage
.venv\Scripts\python.exe -m pytest --cov=site_sucker
```

### Building

```bash
# Using uv
uv build

# Using pip
pip install build
python -m build
```

## Migration from PowerShell

This Python implementation maintains feature parity with the original PowerShell version:

| PowerShell | Python |
|------------|--------|
| `site_sucker.ps1` | `src/site_sucker/__main__.py` |
| `SiteSucker.psm1` | `src/site_sucker/__init__.py` |
| `Get-WgetPath.ps1` | `src/site_sucker/wget.py::get_wget_path()` |
| `New-WgetArgs.ps1` | `src/site_sucker/wget.py::build_wget_args()` |
| `Invoke-SiteMirror.ps1` | `src/site_sucker/mirror.py::invoke_site_mirror()` |
| `Get-ExternalMedia.ps1` | `src/site_sucker/media.py::get_external_media()` |
| `Repair-ExternalLinks.ps1` | `src/site_sucker/repair_links.py::repair_external_links()` |
| `Repair-OfflineHtml.ps1` | `src/site_sucker/repair_offline.py::repair_offline_html()` |
| `Write-SiteReport.ps1` | `src/site_sucker/report.py::write_site_report()` |

## License

Same as the original PowerShell implementation.

## Contributing

Contributions are welcome! Please ensure tests pass before submitting PRs.

```bash
uv run pytest
```
