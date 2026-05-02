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

# Block specific URL patterns (e.g., phpBB forum categories)
.venv\Scripts\python.exe -m site_sucker https://forum.example.com --reject "f=31&;f=8&;f=11&"
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

## Examples

### forum.median-xl.com

```bash
.venv\Scripts\site-sucker.exe -d 3 --reject "f=1&;f=2&;f=3&;f=5&;f=6&;f=7&;f=8&;f=9&;f=10&;f=11&;f=12&;f=13&;f=14&;f=15&;f=16&;f=17&;f=18&;f=19&;f=20&;f=21&;f=22&;f=23&;f=24&;f=26&;f=27&;f=28&;f=29&;f=30&;f=31&;f=32&;f=33&;f=34&;f=35&;f=36&;f=37&;f=38&;f=39&;f=41&;f=42&;f=43&;f=44&;f=45&;f=46&;f=47&;f=48&;f=49&;f=50&;f=51&;f=52&;f=53&;f=54&;f=55&;f=56&;f=57&;f=58&;f=59&;f=60&;f=61&;f=62&;f=63&;f=64&;f=65&;f=66&;f=67&;f=68&;f=69&;f=70&;f=71&;f=72&;f=73&;f=74&;f=75&;f=76&;f=77&;f=78&;f=79&;f=80&;f=81&;f=82&;f=83&;f=84&;f=85&;f=86&;f=87&;f=88&;f=89&;f=90&;f=91&;f=92&;f=93&;f=94&;f=95&;f=96&;f=97&;f=98&;f=99&;f=100&" https://forum.median-xl.com
```
