<#
.SYNOPSIS
    Scans downloaded HTML for external media URLs.

.DESCRIPTION
    Parses all HTML files in the output directory to find external media URLs
    (images, videos, CSS, JS, fonts) that are hosted on different domains.
    Performs deduplication and URL normalization.

.PARAMETER OutputDir
    Path to the directory containing downloaded HTML files.

.PARAMETER TargetDomain
    The primary domain being mirrored (used to exclude internal URLs).

.PARAMETER Settings
    Hashtable containing configuration from settings.json.

.OUTPUTS
    System.Collections.Generic.HashSet[string]
    Set of unique external media URLs.

.EXAMPLE
    $urls = Get-ExternalMedia -OutputDir "./downloads" -TargetDomain "wiki.projectdiablo2.com" -Settings $Settings
#>
function Get-ExternalMedia {
    [CmdletBinding()]
    [OutputType([System.Collections.Generic.HashSet[string]])]
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutputDir,

        [Parameter(Mandatory = $true)]
        [string]$TargetDomain,

        [Parameter(Mandatory = $true)]
        [hashtable]$Settings
    )

    Write-Host "`n[2/2] Collecting external media from downloaded HTML..." -ForegroundColor Cyan

    $htmlFiles = Get-ChildItem -Path $OutputDir -Recurse -Include "*.html", "*.htm" -ErrorAction SilentlyContinue
    $extUrls = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

    # Regex to find href/src attributes
    $pattern = '(?:href|src)=["''](https?://[^"''#]+)'

    # Build media extension regex
    $escapedExtensions = $Settings.MediaExtensions | ForEach-Object { [regex]::Escape($_) }
    $mediaRegex = "(?i)($($escapedExtensions -join '|'))(\?.*)?$"

    $urlCount = 0
    $mediaCount = 0

    foreach ($f in $htmlFiles) {
        $raw = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $raw) { continue }

        [regex]::Matches($raw, $pattern) | ForEach-Object {
            $urlCount++
            $url = $_.Groups[1].Value

            # Skip URLs from the target domain
            if ($url -match [regex]::Escape($TargetDomain)) { return }

            # Skip non-media URLs
            if ($url -notmatch $mediaRegex) { return }

            # Normalize URL: strip query string for deduplication
            $normalizedUrl = $url -split '\?' | Select-Object -First 1

            if ($extUrls.Add($normalizedUrl)) {
                $mediaCount++
            }
        }
    }

    Write-Host "Scanned $urlCount URLs, found $($extUrls.Count) unique external media URLs" -ForegroundColor Yellow
    return $extUrls
}
