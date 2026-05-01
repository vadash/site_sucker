<#
.SYNOPSIS
    Builds wget argument array from settings and CLI parameters.

.DESCRIPTION
    Constructs the common wget arguments used across all invocations,
    combining default settings from settings.json with runtime overrides.

.PARAMETER Settings
    Hashtable containing configuration from settings.json.

.PARAMETER OutputDir
    Output directory path for downloaded files.

.PARAMETER ExtraArgs
    Additional arguments to pass to wget (e.g., --mirror, --no-parent).

.OUTPUTS
    System.String[]
    Array of wget command-line arguments.

.EXAMPLE
    $args = New-WgetArgs -Settings $Settings -OutputDir "./downloads" -ExtraArgs @("--mirror", "--no-parent")
#>
function New-WgetArgs {
    [CmdletBinding()]
    [OutputType([string[]])]
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Settings,

        [Parameter(Mandatory = $true)]
        [string]$OutputDir,

        [Parameter(Mandatory = $false)]
        [string[]]$ExtraArgs = @(),

        [Parameter(Mandatory = $false)]
        [switch]$NoLinkConversion
    )

    $commonArgs = @(
        "-e", "robots=off",
        "--no-proxy",
        "--no-verbose",
        "--restrict-file-names=windows",
        "--no-host-directories",
        "--directory-prefix=$OutputDir",
        "--user-agent=$($Settings.UserAgent)",
        "--timeout=$($Settings.Timeout)",
        "--tries=$($Settings.Retries)"
    )

    # Add wait if specified (helps avoid 429 rate limiting)
    if ($Settings.WaitBetweenRequests -gt 0) {
        $commonArgs += "--wait=$($Settings.WaitBetweenRequests)"
        $commonArgs += "--random-wait"  # Adds jitter to avoid bot detection
    }

    # Only add link conversion for pass 1 (mirroring), not pass 2 (plain downloads)
    if (-not $NoLinkConversion) {
        $commonArgs += "--convert-links"
        $commonArgs += "--adjust-extension"
    }

    # Build reject-regex from patterns and domains
    $rejectPatterns = $Settings.RejectPatterns -join '|'
    $rejectDomains = $Settings.RejectDomains -join '|'

    $rejectParts = @()
    if ($rejectPatterns) {
        $rejectParts += $rejectPatterns
    }
    if ($rejectDomains) {
        $rejectParts += "($rejectDomains)"
    }

    if ($rejectParts.Count -gt 0) {
        $combinedReject = $rejectParts -join '|'
        $commonArgs += "--reject-regex", ".*($combinedReject).*"
    }

    # Add any extra arguments
    if ($ExtraArgs) {
        $commonArgs += $ExtraArgs
    }

    Write-Verbose "wget args: $($commonArgs -join ' ')"
    return $commonArgs
}
