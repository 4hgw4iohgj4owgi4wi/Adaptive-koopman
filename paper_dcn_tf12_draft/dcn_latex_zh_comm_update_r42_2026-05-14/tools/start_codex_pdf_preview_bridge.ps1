$ProjectDir = Split-Path -Parent $PSScriptRoot
$PdfPath = Join-Path $ProjectDir "manuscript_zh_comm_update_final.pdf"
$OutDir = Join-Path $ProjectDir "codex_pdf_preview"
$LogPath = Join-Path $OutDir "preview_bridge.log"
$ErrPath = Join-Path $OutDir "preview_bridge.err.log"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Args = @(
    (Join-Path $PSScriptRoot "codex_pdf_preview_bridge.py"),
    "--pdf", $PdfPath,
    "--out", $OutDir,
    "--dpi", "130",
    "--pages", "all",
    "--watch",
    "--interval", "1.5"
)

Start-Process -FilePath "python" `
    -ArgumentList $Args `
    -WorkingDirectory $ProjectDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $LogPath `
    -RedirectStandardError $ErrPath `
    -PassThru
