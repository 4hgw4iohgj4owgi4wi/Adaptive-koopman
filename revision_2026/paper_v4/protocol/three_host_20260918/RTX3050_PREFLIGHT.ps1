[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Python,
    [string]$Paper = ''
)

$ErrorActionPreference = 'Stop'
if (-not $Paper) { $Paper = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')) }
if (-not (Test-Path -LiteralPath $Python)) { throw "PYTHON_NOT_FOUND:$Python" }
$required = @(
    'tools\build_device_g0_g2_protocol.py',
    'tools\gpu_g0_g2_qualify_device.py',
    'tools\e16_negative_cases_three_host.py',
    'protocol\RTX5080_G0_G2_20260915_v5.json',
    'protocol\three_host_20260918\RTX3050_E16_CASES.json',
    'results\20260915_R4_P1_2MS01\raw.npz',
    'results\20260915_R4_P1_2MS01\substeps.npz',
    'results\20260915_R4_P1_2MS01\solver.jsonl',
    'results\20260915_R4_P1_2MS01\status.json'
)
$missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $Paper $_)) })
if ($missing.Count -gt 0) { throw ('REQUIRED_FILES_MISSING:' + ($missing -join ',')) }
$deviceJson = & $Python -c "import json,platform,torch; print(json.dumps({'host':platform.node(),'cuda':torch.cuda.is_available(),'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,'torch':torch.__version__,'cuda_build':torch.version.cuda,'capability':torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None,'memory':torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else None}))"
$device = $deviceJson | ConvertFrom-Json
if (-not $device.cuda) { throw 'CUDA_NOT_AVAILABLE' }
if ($device.device -notmatch 'RTX 3050') { throw "WRONG_DEVICE:$($device.device)" }
$running = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and $_.CommandLine -match 'paper_v4_core' })
if ($running.Count -gt 0) { throw "EXPERIMENT_PROCESS_CONFLICT:$($running.ProcessId -join ',')" }
[pscustomobject]@{
    status='PASS_RTX3050_PREFLIGHT'; checked_at=(Get-Date -Format o); paper=$Paper
    host=$device.host; device=$device.device; torch=$device.torch; cuda_build=$device.cuda_build
    capability=$device.capability; memory_bytes=$device.memory; required_files=$required.Count
    experiment_processes=0; authorization='DEV_PRE_V2_FIXED_SAMPLE_AND_NON_DYNAMICS_ONLY'
} | ConvertTo-Json -Depth 5
