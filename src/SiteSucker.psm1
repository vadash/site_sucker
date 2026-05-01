# SiteSucker Module
# Universal Wiki/Site Downloader for PowerShell 7+

$moduleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Dot-source all private functions
$privateFunctions = Get-ChildItem -Path (Join-Path $moduleRoot "*.ps1") -Exclude "*.psm1"

foreach ($func in $privateFunctions) {
    . $func.FullName
}

# Export all functions for use
Export-ModuleMember -Function @(
    'Invoke-SiteMirror',
    'Get-WgetPath',
    'New-WgetArgs',
    'Get-ExternalMedia',
    'Repair-ExternalLinks',
    'Repair-OfflineHtml',
    'Write-SiteReport'
)
