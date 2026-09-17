$ErrorActionPreference='Continue'
$root='D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026'
function SHA($p){ (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$runId = "${stamp}_KFIX_R01"
$runDir = Join-Path $root 'koopman_predict_v3r_results\runs'
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
$run = Join-Path $runDir $runId
if (Test-Path $run) { throw "run dir exists: $run" }
New-Item -ItemType Directory -Path $run | Out-Null
$f0 = Join-Path $run 'f0'
New-Item -ItemType Directory -Path $f0 | Out-Null

# 1. environment
$envInfo = [ordered]@{ hostname=$env:COMPUTERNAME; project_root='D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'; now=(Get-Date).ToString('o') }
$envInfo.torch = (& 'E:\anaconda\envs\pytorch_new\python.exe' -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')" 2>&1 | Out-String).Trim()
$envInfo.disk = ((Get-PSDrive D,E -ErrorAction SilentlyContinue | Select-Object Name,@{N='FreeGiB';E={[math]::Round($_.Free/1GB,2)}} | ConvertTo-Json -Compress) -replace '"','')
$envInfo | ConvertTo-Json | Out-File (Join-Path $f0 'environment.json') -Encoding utf8

# 2. processes
$procs = Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|matlab' } | Select-Object ProcessId,Name
$procs | ConvertTo-Json | Out-File (Join-Path $f0 'processes.txt') -Encoding utf8

# 3. baseline identity
$v3src = Join-Path $root 'koopman_predict_v3'
$identity = [ordered]@{ run_id=$runId }
$identity.taskbook_koopman_fix_sha256 = SHA (Join-Path $root 'koopman_fix.md')
$identity.historical_taskbook_p5_sha256 = SHA (Join-Path $root 'koopman_p5.md')
$identity.historical_protocol_v3_sha256 = SHA (Join-Path $v3src 'config\protocol_v3.json')
$manifestJson = (& 'E:\anaconda\envs\pytorch_new\python.exe' -B -c "import sys,json; sys.path.insert(0,r'$v3src\src'); from frozen import frozen_source_manifest; from contracts_v2 import json_sha256; import pathlib; print(json_sha256(frozen_source_manifest(pathlib.Path(r'$v3src'))))" 2>&1 | Select-Object -Last 1).Trim()
$identity.historical_v3_source_manifest_sha256 = $manifestJson
$base='D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026\koopman_predict_auto_results\runs\20260901_214725_AUTO_PREDICT_AUTO_R04_R01'
$identity.n5_manifest_sha256 = SHA (Join-Path $base 'n5\data_manifest.csv')
$identity.n5_normalization_sha256 = SHA (Join-Path $base 'n5\normalization_train_only.npz')
$p5b = Join-Path $root 'koopman_predict_v3_results\runs\20260902_115833_KOOPMAN_V2_GDM_RK_R01\p5b'
$identity.p5b_selection_sha256 = SHA (Join-Path $p5b 'selection.json')
$identity.p5b_complete_sha256 = SHA (Join-Path $p5b 'complete.json')
$identity.p5b_cv_C16_sha256 = SHA (Join-Path $p5b 'cv_C16.csv')
$identity.p5b_cv_C32_sha256 = SHA (Join-Path $p5b 'cv_C32.csv')
$identity.p5b_cv_A2_sha256 = SHA (Join-Path $p5b 'cv_A2.csv')
$identity | ConvertTo-Json | Out-File (Join-Path $f0 'baseline_identity.json') -Encoding utf8

# 4. known issues
$lines = @(
'{"id":"E01","description":"early stop saved current model not best","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E02","description":"best_step was actually stop_step","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E03","description":"early stop monitor only 256 random windows","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E04","description":"resume missing best/patience/RNG state","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E05","description":"checkpoint presence treated as fold complete","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E06","description":"old checkpoints reused across source identities","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E07","description":"stage rerun overwrote source manifest","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E08","description":"AF stress read old validation","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E09","description":"log claimed no validation read while AF did","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E10","description":"A1 budget 2000 vs others 17000","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E11","description":"CVaR weighted share dominated loss","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E12","description":"CVaR unstratified per batch","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E13","description":"quantile/min_samples hardcoded","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E14","description":"per-fold raw rows/models missing","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E15","description":"AF no paired damped/free comparison","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E16","description":"rho(F)<1 misread as overall stability","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E17","description":"broad except swallowed AF errors","status":"CONFIRMED_FROM_HISTORY"}',
'{"id":"E18","description":"P5B referenced missing solution file","status":"CONFIRMED_FROM_HISTORY"}'
)
$lines | Out-File (Join-Path $f0 'known_issues.json') -Encoding utf8

# 5. split status
$confirmCount = (& 'E:\anaconda\envs\pytorch_new\python.exe' -B -c "import csv; rows=list(csv.DictReader(open(r'$base\n5\data_manifest.csv',encoding='utf-8-sig'))); print(sum(1 for r in rows if r['split']=='confirm'))" 2>&1 | Select-Object -Last 1).Trim()
$split = [ordered]@{
  old_validation_status='CONTAMINATED_D5_BY_AF'
  old_validation_note='AF stress rollout read old validation D5 windows in historical run; never usable as unseen validation again'
  old_development_status='DEVELOPMENT_EVIDENCE_ONLY'
  confirm_access_count=$confirmCount
  new_validation_plan='seed_start 991000, 48 base families, 168 trajectories, frozen generator, sealed manifest; no model evaluation until V0'
  train_status='ALLOWED'
}
$split | ConvertTo-Json | Out-File (Join-Path $f0 'split_status.json') -Encoding utf8

$complete = [ordered]@{ stage='F0'; status='PASS'; run_id=$runId; now=(Get-Date).ToString('o') }
$complete | ConvertTo-Json | Out-File (Join-Path $f0 'complete.json') -Encoding utf8
"RUN_ID=$runId"
