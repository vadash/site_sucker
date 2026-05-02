<#
.SYNOPSIS
    Strips online-only resources from HTML for offline browsing.

.DESCRIPTION
    Removes or neutralizes HTML elements that block offline rendering:
    - Removes remote CSS/JS links (load.php) that weren't downloaded
    - Removes preconnect/dns-prefetch hints (useless offline)
    - Removes tracking/analytics scripts and pixels
    - Removes online-only navigation links (EditURI, Atom feeds, etc.)
    - Optionally injects minimal fallback CSS

.PARAMETER OutputDir
    Path to the directory containing downloaded HTML files.

.OUTPUTS
    int
    Number of HTML files modified.

.EXAMPLE
    Repair-OfflineHtml -OutputDir "./downloads/wiki.example.com"
#>
function Repair-OfflineHtml {
    [CmdletBinding()]
    [OutputType([int])]
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutputDir
    )

    Write-Host "`n[4/4] Stripping online-only resources for offline browsing..." -ForegroundColor Cyan

    $htmlFiles = Get-ChildItem -Path $OutputDir -Recurse -Include "*.html", "*.htm" -ErrorAction SilentlyContinue
    $modifiedCount = 0

    foreach ($f in $htmlFiles) {
        $raw = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $raw) { continue }

        $original = $raw
        $modified = $false

        # Remove remote load.php stylesheets (MediaWiki ResourceLoader - never downloaded)
        $raw = $raw -replace '<link\s+[^>]*rel=(")stylesheet(")[^>]*href="https?://[^"]*load\.php[^"]*\?[^"]*"[^>]*/?>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # Remove remote load.php scripts
        $raw = $raw -replace '<script[^>]*src="https?://[^"]*load\.php[^"]*"[^>]*>.*?</script>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # Remove preconnect hints (no effect offline)
        $raw = $raw -replace '<link\s+[^>]*rel=(")preconnect(")[^>]*/?>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # Remove dns-prefetch hints (no effect offline)
        $raw = $raw -replace '<link\s+[^>]*rel=(")dns-prefetch(")[^>]*/?>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # Remove EditURI link
        $raw = $raw -replace '<link\s+[^>]*rel=(")EditURI(")[^>]*/?>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # Remove alternate feed links (Atom, RSS - not available offline)
        $raw = $raw -replace '<link\s+[^>]*rel=(")alternate(")[^>]*type="application/(atom|rss)\+xml"[^>]*/?>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # Remove analytics/tracking scripts (Matomo, Google Analytics, etc.)
        $raw = $raw -replace '<script[^>]*>\s*var\s+_paq\s*=\s*window\._paq.*?</script>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # Remove noscript tracking pixels
        $raw = $raw -replace '<noscript>\s*<img[^>]*(?:matomo|analytics|doubleclick|google-analytics)[^>]*/?>\s*</noscript>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # Remove inline event logging and analytics calls
        $raw = $raw -replace '\.push\(\s*\[?\s*(")trackPageView(").*?\);?', ''
        $raw = $raw -replace '\.push\(\s*\[?\s*(")enableLinkTracking(").*?\);?', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # phpBB-specific: Remove posting.php (reply forms) - useless offline
        $raw = $raw -replace '<a\s+[^>]*href="posting\.php[^"]*"[^>]*>.*?</a>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # phpBB-specific: Remove tradegold.php links (trade pages, not available offline)
        $raw = $raw -replace '<a\s+[^>]*href="tradegold\.php[^"]*"[^>]*>.*?</a>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # phpBB-specific: Remove memberlist.php links (user profiles, not downloaded)
        $raw = $raw -replace '<a\s+[^>]*href="memberlist\.php[^"]*"[^>]*>.*?</a>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # phpBB-specific: Remove search.php links (search doesn't work offline)
        $raw = $raw -replace '<a\s+[^>]*href="search\.php[^"]*"[^>]*>.*?</a>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        # phpBB-specific: Remove ucp/mcp.php links (user/mod control panels)
        $raw = $raw -replace '<a\s+[^>]*href="(ucp|mcp)\.php[^"]*"[^>]*>.*?</a>', ''
        if ($raw -ne $original) { $modified = $true; $original = $raw }

        if ($modified) {
            # Inject minimal fallback CSS to ensure page is readable without remote styles
            $fallbackStyle = @'

<style>
/* Minimal fallback CSS for offline browsing */
body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0; }
#content { max-width: 960px; margin: 0 auto; padding: 20px; }
h1, h2, h3 { margin-top: 1.5em; }
a { color: #0645ad; text-decoration: none; }
a:hover { text-decoration: underline; }
.mw-body-content { padding: 1em; }
</style>
'@
            # Insert fallback style before </head>
            $raw = $raw -replace '</head>', "$fallbackStyle</head>"

            Set-Content -Path $f.FullName -Value $raw -NoNewline
            $modifiedCount++
        }
    }

    if ($modifiedCount -gt 0) {
        Write-Host "  Cleaned $modifiedCount HTML file(s) for offline use" -ForegroundColor Yellow
    }

    return $modifiedCount
}
