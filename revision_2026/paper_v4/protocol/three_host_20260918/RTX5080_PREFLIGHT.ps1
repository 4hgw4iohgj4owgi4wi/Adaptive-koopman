[CmdletBinding()]
param(
    [string]$Python = 'E:\anaconda\envs\pytorch_new\python.exe',
    [string]$Paper = ''
)

$ErrorActionPreference = 'Stop'
if (-not $Paper) {
    $Paper = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
}
if (-not (Test-Path -LiteralPath $Python)) { throw "PYTHON_NOT_FOUND:$Python" }
if (-not (Test-Path -LiteralPath $Paper)) { throw "PAPER_NOT_FOUND:$Paper" }

$deviceJson = & $Python -c "import json,platform,torch; print(json.dumps({'host':platform.node(),'cuda':torch.cuda.is_available(),'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,'torch':torch.__version__,'cuda_build':torch.version.cuda}))"
$device = $deviceJson | ConvertFrom-Json
if (-not $device.cuda) { throw 'CUDA_NOT_AVAILABLE' }
if ($device.device -notmatch 'RTX 5080') { throw "WRONG_DEVICE:$($device.device)" }

$protocol = Join-Path $Paper 'protocol\R5_STRICT_N1_GPU_20260918_v3.json'
if (-not (Test-Path -LiteralPath $protocol)) { throw 'N1_V3_PROTOCOL_MISSING' }
$data = Get-Content -LiteralPath $protocol -Raw | ConvertFrom-Json
$problems = @()
foreach ($item in $data.identity_files) {
    $path = Join-Path $Paper $item.path
    if (-not (Test-Path -LiteralPath $path)) {
        $problems += "MISSING:$($item.path)"
        continue
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $item.sha256) { $problems += "MISMATCH:$($item.path)" }
}
if ($problems.Count -gt 0) { throw ('IDENTITY_PROBLEMS:' + ($problems -join ',')) }

$target = Join-Path $Paper $data.run.output
if (Test-Path -LiteralPath $target) { throw "OUTPUT_ALREADY_EXISTS:$target" }
$running = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^python' -and $_.CommandLine -match 'paper_v4_core'
})
if ($running.Count -gt 0) { throw "EXPERIMENT_PROCESS_CONFLICT:$($running.ProcessId -join ',')" }

[pscustomobject]@{
    status = 'PASS_RTX5080_PREFLIGHT'
    checked_at = (Get-Date -Format o)
    paper = $Paper
    host = $device.host
    device = $device.device
    torch = $device.torch
    cuda_build = $device.cuda_build
    protocol = 'protocol/R5_STRICT_N1_GPU_20260918_v3.json'
    protocol_sha256 = (Get-FileHash -LiteralPath $protocol -Algorithm SHA256).Hash.ToLower()
    identity_files = $data.identity_files.Count
    target_output_absent = $true
    experiment_processes = 0
} | ConvertTo-Json -Depth 5
