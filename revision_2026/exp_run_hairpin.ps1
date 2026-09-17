$ErrorActionPreference='Stop'
$expRev='D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026'
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1'
Set-Location (Join-Path $expRev 'paper_v4\src')
& 'E:\anaconda\envs\pytorch_new\python.exe' -B -m paper_v4_core.e01_hairpin_batch --root (Join-Path $expRev 'paper_v4_results\20260909_E01_HAIRPIN01')
exit $LASTEXITCODE
