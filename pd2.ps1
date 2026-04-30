#Requires -Version 7.0
# PD2 Wiki Mirror — Windows 11 / PS 7.5
# Fixed: Removed conflicting --continue, relaxed ErrorAction so dead Discord links don't crash the script.

[CmdletBinding()]
param(
    [string]$OutputDir  = (Join-Path $PSScriptRoot "pd2-wiki"),
    [string]$BaseURL    = "https://wiki.projectdiablo2.com/",
    [double]$WaitSec    = 0
)

# Changed to Continue: If an image is dead, ignore it and keep going!
$ErrorActionPreference = "Continue"

# ── DISABLE PROXIES ────────────────────────────────────────────────────────
$env:http_proxy  = $null
$env:https_proxy = $null
$env:all_proxy   = $null
$env:HTTP_PROXY  = $null
$env:HTTPS_PROXY = $null

$WgetPath = Join-Path $PSScriptRoot "wget.exe"

if (-not (Test-Path $WgetPath)) {
    Write-Error "wget.exe not found in $PSScriptRoot. Please ensure it is in the same folder as this script."
    return
}

# Removed --continue to stop it from clashing with --mirror
$commonArgs = @(
    "-e", "robots=off",
    "--no-proxy",
    "--convert-links",
    "--adjust-extension",
    "--page-requisites",
    "--no-verbose",
    "--restrict-file-names=windows",
    "--directory-prefix=$OutputDir",
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "--timeout=15", 
    "--tries=3"     
)

# ── PASS 1 : Full wiki mirror ──────────────────────────────────────────────
Write-Host "`n[1/2] Mirroring $BaseURL (Proxies Disabled, Timeouts Active) ..." -ForegroundColor Cyan

$rejectRegex = '.*(action=|oldid=|diff=|printable=|returnto=|redirect=|Special:|Special%3A|Talk:|Talk%3A|User:|User%3A|User_talk:|User_talk%3A|Category_talk:|Category_talk%3A|load\.php|api\.php).*'

$pass1Args = @(
    "--mirror",
    "--no-parent",
    "--reject-regex", $rejectRegex
)

& $WgetPath @commonArgs $pass1Args $BaseURL

if ($LASTEXITCODE -notin 0,8) {          
    Write-Warning "wget exited with code $LASTEXITCODE"
}

# ── PASS 2 : External links (Images & Videos ONLY) ─────────────────────────
Write-Host "`n[2/2] Collecting external media (images/videos) from downloaded HTML..." -ForegroundColor Cyan

$htmlFiles = Get-ChildItem -Path $OutputDir -Recurse -Include "*.html","*.htm"
$extUrls   = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

$pattern = '(?:href|src)=["''](https?://[^"''#]+)'
$mediaRegex = '(?i)\.(png|jpe?g|gif|webp|mp4|webm|avi|mkv|mov)(\?.*)?$'

foreach ($f in $htmlFiles) {
    $raw = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
    if (-not $raw) { continue }
    
    [regex]::Matches($raw, $pattern) | ForEach-Object { 
        $url = $_.Groups[1].Value
        
        if ($url -match "wiki\.projectdiablo2\.com") { return }
        if ($url -notmatch $mediaRegex) { return }

        [void]$extUrls.Add($url) 
    }
}

Write-Host "Found $($extUrls.Count) unique external media URLs" -ForegroundColor Yellow

$i = 0
foreach ($url in $extUrls) {
    $i++
    Write-Host "  [$i/$($extUrls.Count)] $url"
    
    # Run wget for external files without killing the script on failure
    & $WgetPath @commonArgs "--level=1" $url 2>&1 | Out-Null
}

Write-Host "`nDone. Saved to: $OutputDir" -ForegroundColor Green
