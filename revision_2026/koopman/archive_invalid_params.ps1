$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman\universal_v2').Path
$archive = Join-Path $root 'invalid_parameter_range_20260822'
if (-not (Test-Path -LiteralPath $archive)) {
    New-Item -ItemType Directory -Path $archive | Out-Null
}
$sourceDir = Join-Path $root 'parameters'
if (Test-Path -LiteralPath $sourceDir) {
    $resolvedSource = (Resolve-Path -LiteralPath $sourceDir).Path
    if (-not $resolvedSource.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Source escaped result root: $resolvedSource"
    }
    Move-Item -LiteralPath $resolvedSource -Destination (Join-Path $archive 'parameters')
}
$files = @(
    'parameter_tasks.csv', 'online_adaptation.csv',
    't5\adaptation_complete.json', 't5\adaptation_results.json',
    't5\A-K0.npz', 't5\A-K1.npz', 't5\A-K4.npz', 't5\A-K5-linear.npz'
)
foreach ($relative in $files) {
    $source = Join-Path $root $relative
    if (Test-Path -LiteralPath $source) {
        $flatName = $relative.Replace('\', '__')
        Move-Item -LiteralPath $source -Destination (Join-Path $archive $flatName)
    }
}
Write-Output $archive
