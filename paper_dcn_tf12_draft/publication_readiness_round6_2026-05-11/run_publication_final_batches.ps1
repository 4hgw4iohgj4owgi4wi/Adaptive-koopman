$ErrorActionPreference = "Stop"

$Repo = "D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main"
$Python = "E:\anaconda\envs\pytorch_new\python.exe"
$Runner = Join-Path $Repo "tf14_remaining_experiments_20260509\run_tf14_remaining_experiments.py"
$Gate = Join-Path $Repo "paper_dcn_tf12_draft\publication_readiness_round5_2026-05-11\derive_publication_gate_tables.py"
$OutputRoot = Join-Path $Repo "paper_dcn_tf12_draft\publication_final_runs_2026-05-11"
$GateOut = Join-Path $Repo "paper_dcn_tf12_draft\publication_final_gate_2026-05-11"
$Transcript = Join-Path $Repo "paper_dcn_tf12_draft\publication_readiness_round6_2026-05-11\final_batches_transcript.log"

Set-Location $Repo
New-Item -ItemType Directory -Force -Path (Split-Path $Transcript) | Out-Null
Start-Transcript -Path $Transcript -Append

try {
    & $Python $Runner --experiments E0 --full-final-seeds --include-zoh-surrogate --output-root $OutputRoot --continue-on-error --retry-exceptions
    & $Python $Runner --experiments E2 --full-final-seeds --include-zoh-surrogate --output-root $OutputRoot --continue-on-error --retry-exceptions
    & $Python $Runner --experiments E3 --full-final-seeds --output-root $OutputRoot --continue-on-error --retry-exceptions
    & $Python $Runner --experiments E7 --full-final-seeds --include-zoh-surrogate --output-root $OutputRoot --continue-on-error --retry-exceptions
    & $Python $Gate --stage-root $OutputRoot --out-dir $GateOut
}
finally {
    Stop-Transcript
}
