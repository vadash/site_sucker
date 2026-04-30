# SiteSucker Module
# Universal Wiki/Site Downloader for PowerShell 7+

$moduleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# Dot-source all private functions
$privateFunctions = Get-ChildItem -Path (Join-Path $moduleRoot "*.ps1") -Exclude "*.psm1"

foreach ($func in $privateFunctions) {
    . $func.FullName
}

# Export public functions
Export-ModuleMember -Function @(
    'Invoke-SiteMirror'
)
