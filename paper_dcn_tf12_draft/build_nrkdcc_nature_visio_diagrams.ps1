param(
    [string]$OutputDir = "D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\paper_dcn_tf12_draft\nature_visio_diagrams_2026-05-21_review_clean_v5_reference_style"
)

$ErrorActionPreference = "Stop"

function New-OutputDir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Set-CellFormula {
    param($Shape, [string]$Cell, [string]$Formula)
    try {
        $Shape.CellsU($Cell).FormulaU = $Formula
    } catch {
        # Some Visio versions/stencils expose slightly different cells.
    }
}

function Set-BaseStyle {
    param(
        $Shape,
        [string]$Fill,
        [string]$Line,
        [string]$Text = "RGB(37,54,79)",
        [double]$LineWeight = 1.1,
        [double]$FontSize = 7.8,
        [bool]$Bold = $false,
        [string]$Align = "1"
    )
    Set-CellFormula $Shape "FillForegnd" $Fill
    Set-CellFormula $Shape "LineColor" $Line
    Set-CellFormula $Shape "LineWeight" ("{0} pt" -f $LineWeight)
    Set-CellFormula $Shape "Rounding" "0.08 in"
    Set-CellFormula $Shape "Char.Color" $Text
    Set-CellFormula $Shape "Char.Size" ("{0} pt" -f $FontSize)
    Set-CellFormula $Shape "Char.Font" 'FONT("Microsoft YaHei UI")'
    Set-CellFormula $Shape "Para.HorzAlign" $Align
    Set-CellFormula $Shape "VerticalAlign" "1"
    if ($Bold) {
        Set-CellFormula $Shape "Char.Style" "1"
    } else {
        Set-CellFormula $Shape "Char.Style" "0"
    }
}

function Add-TextBox {
    param(
        $Page,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$H,
        [string]$Text,
        [double]$FontSize = 8.0,
        [string]$Color = "RGB(37,54,79)",
        [bool]$Bold = $false,
        [string]$Align = "1"
    )
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = $Text
    Set-CellFormula $s "FillPattern" "0"
    Set-CellFormula $s "LinePattern" "0"
    Set-CellFormula $s "Char.Color" $Color
    Set-CellFormula $s "Char.Size" ("{0} pt" -f $FontSize)
    Set-CellFormula $s "Char.Font" 'FONT("Microsoft YaHei UI")'
    Set-CellFormula $s "Para.HorzAlign" $Align
    Set-CellFormula $s "VerticalAlign" "1"
    if ($Bold) { Set-CellFormula $s "Char.Style" "1" }
    return $s
}

function Add-Box {
    param(
        $Page,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$H,
        [string]$Text,
        [string]$Fill,
        [string]$Line,
        [double]$FontSize = 7.6,
        [double]$LineWeight = 1.1
    )
    $outer = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $outer.Text = ""
    Set-BaseStyle $outer $Fill $Line "RGB(37,54,79)" $LineWeight $FontSize $false "1"

    $parts = @(
        $Text -split "(`r`n|`n|`r)" |
        Where-Object { $_ -ne "`r`n" -and $_ -ne "`n" -and $_ -ne "`r" } |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_.Length -gt 0 }
    )

    if ($parts.Count -le 1) {
        $outer.Text = $Text
        return $outer
    }

    $marginX = [Math]::Min(0.12, $W * 0.06)
    $topPad = 0.08
    $bottomPad = 0.09
    $gap = 0.035
    $titleH = [Math]::Min(0.27, [Math]::Max(0.20, $H * 0.21))
    $chipCount = $parts.Count - 1
    $availableH = $H - $titleH - $topPad - $bottomPad - ($gap * ($chipCount - 1))
    $chipH = [Math]::Max(0.11, $availableH / $chipCount)
    $chipFont = [Math]::Max(4.4, [Math]::Min(6.1, $FontSize - 1.25))
    if ($chipCount -ge 5) { $chipFont = [Math]::Min($chipFont, 5.0) }

    $titleY = $Y + $H / 2 - $topPad - $titleH / 2
    Add-TextBox $Page $X $titleY ($W - 2 * $marginX) $titleH $parts[0] ([Math]::Min(7.0, $FontSize)) "RGB(37,54,79)" $true "1" | Out-Null

    $startY = $Y + $H / 2 - $topPad - $titleH - $gap - $chipH / 2
    for ($idx = 1; $idx -lt $parts.Count; $idx++) {
        $chipY = $startY - (($idx - 1) * ($chipH + $gap))
        $chip = $Page.DrawRectangle(
            $X - $W / 2 + $marginX,
            $chipY - $chipH / 2,
            $X + $W / 2 - $marginX,
            $chipY + $chipH / 2
        )
        $chip.Text = $parts[$idx]
        Set-BaseStyle $chip "RGB(255,255,255)" $Line "RGB(37,54,79)" 0.55 $chipFont $false "1"
        Set-CellFormula $chip "FillTransparency" "3%"
        Set-CellFormula $chip "Rounding" "0.045 in"
    }
    return $outer
}

function Add-Lane {
    param(
        $Page,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$H,
        [string]$Label,
        [string]$Color,
        [string]$Fill
    )
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = ""
    Set-CellFormula $s "FillForegnd" $Fill
    Set-CellFormula $s "FillTransparency" "18%"
    Set-CellFormula $s "LineColor" $Color
    Set-CellFormula $s "LineWeight" "1.0 pt"
    Set-CellFormula $s "LinePattern" "2"
    Set-CellFormula $s "Rounding" "0.12 in"
    try { $s.SendToBack() } catch {}
    Add-TextBox $Page ($X - $W / 2 + 1.35) ($Y + $H / 2 - 0.20) 2.45 0.30 $Label 7.2 $Color $true "0" | Out-Null
    return $s
}

function Add-SectionFrame {
    param(
        $Page,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$H,
        [string]$Title,
        [string]$Line,
        [string]$Fill = "RGB(255,255,255)"
    )
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = ""
    Set-CellFormula $s "FillForegnd" $Fill
    Set-CellFormula $s "FillTransparency" "4%"
    Set-CellFormula $s "LineColor" $Line
    Set-CellFormula $s "LineWeight" "1.35 pt"
    Set-CellFormula $s "LinePattern" "2"
    Set-CellFormula $s "Rounding" "0.08 in"
    Add-TextBox $Page $X ($Y + $H / 2 - 0.18) ($W - 0.22) 0.30 $Title 7.6 $Line $true "1" | Out-Null
    return $s
}

function Add-Line {
    param(
        $Page,
        [double]$X1,
        [double]$Y1,
        [double]$X2,
        [double]$Y2,
        [string]$Color = "RGB(65,105,165)",
        [bool]$Arrow = $true,
        [bool]$Dash = $false,
        [double]$Weight = 1.25,
        [string]$Label = ""
    )
    $l = $Page.DrawLine($X1, $Y1, $X2, $Y2)
    Set-CellFormula $l "LineColor" $Color
    Set-CellFormula $l "LineWeight" ("{0} pt" -f $Weight)
    if ($Arrow) { Set-CellFormula $l "EndArrow" "13" }
    if ($Dash) { Set-CellFormula $l "LinePattern" "2" }
    if ($Label -ne "") {
        Add-TextBox $Page (($X1 + $X2) / 2) (($Y1 + $Y2) / 2 + 0.13) 1.35 0.25 $Label 6.5 $Color $false "1" | Out-Null
    }
    return $l
}

function Add-Diamond {
    param(
        $Page,
        [double]$X,
        [double]$Y,
        [double]$W,
        [double]$H,
        [string]$Text,
        [string]$Fill,
        [string]$Line
    )
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = $Text
    Set-BaseStyle $s $Fill $Line "RGB(37,54,79)" 1.2 7.4 $false "1"
    Set-CellFormula $s "Angle" "45 deg"
    # Keep the text horizontal while the shape is rotated.
    Set-CellFormula $s "TxtAngle" "-45 deg"
    return $s
}

function Add-VehiclePayloadIcon {
    param($Page, [double]$Cx, [double]$Cy)
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $ink = "RGB(37,54,79)"
    $payload = $Page.DrawRectangle($Cx - 0.33, $Cy - 0.18, $Cx + 0.33, $Cy + 0.18)
    $payload.Text = "载荷"
    Set-BaseStyle $payload "RGB(232,242,247)" $teal $ink 1.0 5.6 $false "1"
    $pts = @(
        [pscustomobject]@{ X = $Cx - 0.72; Y = $Cy + 0.42; Label = "V1" },
        [pscustomobject]@{ X = $Cx + 0.72; Y = $Cy + 0.42; Label = "V2" },
        [pscustomobject]@{ X = $Cx - 0.72; Y = $Cy - 0.42; Label = "V3" },
        [pscustomobject]@{ X = $Cx + 0.72; Y = $Cy - 0.42; Label = "V4" }
    )
    foreach ($p in $pts) {
        $v = $Page.DrawRectangle($p.X - 0.16, $p.Y - 0.10, $p.X + 0.16, $p.Y + 0.10)
        $v.Text = $p.Label
        Set-BaseStyle $v "RGB(255,247,235)" $orange $ink 0.85 4.8 $false "1"
        Add-Line $Page $p.X $p.Y $Cx $Cy $teal $false $false 0.8 "" | Out-Null
    }
    Add-Line $Page ($Cx - 0.72) ($Cy + 0.42) ($Cx + 0.72) ($Cy + 0.42) $blue $false $true 0.7 "" | Out-Null
    Add-Line $Page ($Cx - 0.72) ($Cy - 0.42) ($Cx + 0.72) ($Cy - 0.42) $blue $false $true 0.7 "" | Out-Null
}

function Add-VehicleGlyph {
    param(
        $Page,
        [double]$X,
        [double]$Y,
        [string]$Fill = "RGB(226,72,88)",
        [double]$Scale = 1.0,
        [double]$AngleDeg = 0.0
    )
    $w = 0.22 * $Scale
    $h = 0.42 * $Scale
    $body = $Page.DrawRectangle($X - $w / 2, $Y - $h / 2, $X + $w / 2, $Y + $h / 2)
    Set-BaseStyle $body $Fill "RGB(37,54,79)" "RGB(255,255,255)" 0.65 (5.5 * $Scale) $false "1"
    Set-CellFormula $body "Rounding" "0.045 in"
    $win = $Page.DrawRectangle($X - $w * 0.30, $Y + $h * 0.08, $X + $w * 0.30, $Y + $h * 0.28)
    Set-BaseStyle $win "RGB(214,235,255)" "RGB(65,105,165)" "RGB(37,54,79)" 0.35 (4.2 * $Scale) $false "1"
    Set-CellFormula $win "Rounding" "0.025 in"
    $nose = $Page.DrawOval($X - $w * 0.22, $Y - $h * 0.30, $X + $w * 0.22, $Y - $h * 0.14)
    Set-BaseStyle $nose "RGB(255,255,255)" $Fill "RGB(37,54,79)" 0.25 (4.0 * $Scale) $false "1"
    foreach ($s in @($body, $win, $nose)) {
        if ([Math]::Abs($AngleDeg) -gt 1e-9) { Set-CellFormula $s "Angle" ("{0} deg" -f $AngleDeg) }
    }
    return $body
}

function Add-RoadScene {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H)
    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $rose = "RGB(201,93,99)"
    $road = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    Set-BaseStyle $road "RGB(248,250,251)" $ink $ink 0.75 6.0 $false "1"
    for ($i = 1; $i -le 4; $i++) {
        $lx = $X - $W / 2 + $i * $W / 5
        Add-Line $Page $lx ($Y - $H / 2 + 0.10) $lx ($Y + $H / 2 - 0.10) "RGB(150,160,170)" $false $true 0.55 "" | Out-Null
    }
    Add-Line $Page ($X - $W * 0.28) ($Y - $H * 0.38) ($X - $W * 0.28) ($Y + $H * 0.36) $teal $false $true 0.85 "" | Out-Null
    Add-Line $Page ($X - $W * 0.05) ($Y - $H * 0.30) ($X - $W * 0.05) ($Y + $H * 0.30) $rose $false $true 0.85 "" | Out-Null
    Add-Line $Page ($X + $W * 0.18) ($Y - $H * 0.20) ($X + $W * 0.18) ($Y + $H * 0.22) $rose $false $true 0.85 "" | Out-Null
    Add-VehicleGlyph $Page ($X - $W * 0.28) ($Y - $H * 0.28) "RGB(138,190,65)" 0.95 | Out-Null
    Add-VehicleGlyph $Page ($X - $W * 0.05) ($Y - $H * 0.12) "RGB(226,72,88)" 1.0 | Out-Null
    Add-VehicleGlyph $Page ($X + $W * 0.18) ($Y + $H * 0.02) "RGB(226,72,88)" 1.0 | Out-Null
    Add-VehicleGlyph $Page ($X + $W * 0.18) ($Y + $H * 0.20) "RGB(226,72,88)" 1.0 | Out-Null
    Add-VehicleGlyph $Page ($X + $W * 0.40) ($Y + $H * 0.34) "RGB(138,190,65)" 0.95 | Out-Null
    Add-Line $Page ($X - $W * 0.05) ($Y - $H * 0.02) ($X + $W * 0.18) ($Y + $H * 0.10) $rose $true $true 0.85 "" | Out-Null
    Add-Line $Page ($X + $W * 0.18) ($Y + $H * 0.10) ($X + $W * 0.18) ($Y + $H * 0.28) $rose $true $true 0.85 "" | Out-Null
    Add-TextBox $Page $X ($Y + $H / 2 + 0.22) ($W + 0.10) 0.22 "Four-vehicle cooperative payload transport" 5.8 $blue $true "1" | Out-Null
}

function Add-NeuralNetGlyph {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Label)
    $blue = "RGB(65,105,165)"
    Add-TextBox $Page $X ($Y + $H / 2 - 0.14) $W 0.22 $Label 6.0 "RGB(37,54,79)" $true "1" | Out-Null
    $layers = @(4, 6, 5, 3)
    $xs = @(
        ($X - $W * 0.36),
        ($X - $W * 0.12),
        ($X + $W * 0.14),
        ($X + $W * 0.36)
    )
    $prevNodes = @()
    for ($li = 0; $li -lt $layers.Count; $li++) {
        $count = $layers[$li]
        $nodes = @()
        for ($j = 0; $j -lt $count; $j++) {
            $ny = $Y - $H * 0.28 + ($j + 0.5) * ($H * 0.58 / $count)
            $r = 0.045
            $node = $Page.DrawOval($xs[$li] - $r, $ny - $r, $xs[$li] + $r, $ny + $r)
            $fill = if ($li -eq 0) { "RGB(190,225,176)" } elseif ($li -eq ($layers.Count - 1)) { "RGB(255,213,128)" } else { "RGB(218,230,248)" }
            Set-BaseStyle $node $fill $blue "RGB(37,54,79)" 0.35 4.0 $false "1"
            $nodes += ,@($xs[$li], $ny)
        }
        if ($li -gt 0) {
            foreach ($a in $prevNodes) {
                foreach ($b in $nodes) {
                    Add-Line $Page $a[0] $a[1] $b[0] $b[1] "RGB(140,165,205)" $false $false 0.22 "" | Out-Null
                }
            }
        }
        $prevNodes = $nodes
    }
}

function Add-MiniRoadSnapshot {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Caption)
    $box = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    Set-BaseStyle $box "RGB(249,250,251)" "RGB(180,190,200)" "RGB(37,54,79)" 0.45 4.5 $false "1"
    for ($i = 1; $i -le 3; $i++) {
        $ly = $Y - $H / 2 + $i * $H / 4
        Add-Line $Page ($X - $W * 0.42) $ly ($X + $W * 0.42) $ly "RGB(165,173,181)" $false $true 0.35 "" | Out-Null
    }
    Add-VehicleGlyph $Page ($X - $W * 0.22) ($Y + $H * 0.16) "RGB(226,72,88)" 0.55 90 | Out-Null
    Add-VehicleGlyph $Page ($X + $W * 0.02) ($Y + $H * 0.03) "RGB(226,72,88)" 0.55 90 | Out-Null
    Add-VehicleGlyph $Page ($X + $W * 0.24) ($Y - $H * 0.08) "RGB(138,190,65)" 0.55 90 | Out-Null
    Add-TextBox $Page $X ($Y - $H / 2 - 0.08) $W 0.13 $Caption 4.2 "RGB(37,54,79)" $false "1" | Out-Null
}

function New-VisioDoc {
    param($Visio, [string]$Path, [scriptblock]$DrawPage)
    $doc = $Visio.Documents.Add("")
    $page = $Visio.ActivePage
    & $DrawPage $page
    $doc.SaveAs($Path)
    try {
        $pdfPath = [System.IO.Path]::ChangeExtension($Path, ".pdf")
        $doc.ExportAsFixedFormat(1, $pdfPath, 1, 0)
    } catch {}
    $doc.Close()
}

function Setup-Page {
    param($Page, [string]$Name)
    $Page.Name = $Name
    Set-CellFormula $Page.PageSheet "PageWidth" "16 in"
    Set-CellFormula $Page.PageSheet "PageHeight" "9 in"
    Set-CellFormula $Page.PageSheet "DrawingScale" "1 in"
    Set-CellFormula $Page.PageSheet "PageScale" "1 in"
    $bg = $Page.DrawRectangle(0, 0, 16, 9)
    Set-CellFormula $bg "FillForegnd" "RGB(250,251,253)"
    Set-CellFormula $bg "LinePattern" "0"
    try { $bg.SendToBack() } catch {}
}

function Draw-Framework {
    param($Page)
    Setup-Page $Page "NR-KDCC framework"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGray = "RGB(246,248,250)"

    Add-TextBox $Page 8.0 8.60 14.8 0.38 "NR-KDCC: two-layer network-resilient cooperative transport framework" 11.8 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.22 14.8 0.28 "上层做路径/角色/通信重构决策，下层做四车 Koopman-MPC 维护；车间感知通信与上下层参考/命令通信分开建模" 7.2 $blue $false "1" | Out-Null

    Add-RoadScene $Page 1.35 4.25 1.55 5.45
    Add-Box $Page 1.35 7.38 1.70 0.66 "传感/通信输入`n局部状态、载荷、邻车消息" $paleGray $ink 5.6 | Out-Null
    Add-Box $Page 1.35 1.05 1.70 0.66 "车辆执行器`nax, delta, fault" $paleTeal $teal 5.6 | Out-Null

    Add-Lane $Page 8.70 5.88 12.55 4.50 "Upper-level network-resilient reconfiguration" $blue $paleBlue | Out-Null
    Add-Lane $Page 8.70 1.78 12.55 2.55 "Lower-level model-driven formation maintenance" $teal $paleTeal | Out-Null

    Add-Box $Page 3.35 6.75 1.60 1.10 "Observation`nvehicle states`ncomm packets`nfault flags" $paleGray $blue 5.75 | Out-Null
    Add-MiniRoadSnapshot $Page 3.35 5.75 1.22 0.55 "traffic snapshot" | Out-Null
    Add-MiniRoadSnapshot $Page 3.35 5.05 1.22 0.55 "delayed view" | Out-Null

    Add-Box $Page 5.40 6.05 1.62 2.18 "Bilinear Koopman model`nlift z=phi(x)`nA,B,N_l operators`nshort-horizon rollout" "RGB(242,247,255)" $blue 5.85 | Out-Null
    Add-NeuralNetGlyph $Page 7.30 6.05 2.05 2.05 "Networked residual/role diagnosis" | Out-Null
    Add-Box $Page 9.42 6.65 1.70 0.96 "Reference publisher`nteam_ref_step`nper-vehicle xref_win" $paleOrange $orange 5.75 | Out-Null
    Add-Box $Page 9.42 5.42 1.70 0.96 "Decision publisher`nplanned_u_stack`nFTC/phase-role mode" $paleOrange $orange 5.75 | Out-Null
    Add-Box $Page 11.65 6.65 1.92 0.96 "Upper->lower reference channel`nupper_lower_comm_ref`ndelay/drop/bias/noise" $paleTeal $teal 5.35 | Out-Null
    Add-Box $Page 11.65 5.42 1.92 0.96 "Upper->lower command channel`nupper_lower_comm`ndelay/drop/bias/noise" $paleTeal $teal 5.35 | Out-Null
    Add-Box $Page 13.80 6.05 1.86 1.92 "Twin-world projection`nnominal / delayed / faulty`nconstraint and certificate check`naccepted or degraded" $paleRose $rose 5.45 | Out-Null
    Add-MiniRoadSnapshot $Page 14.68 6.60 0.82 0.38 "ok" | Out-Null
    Add-MiniRoadSnapshot $Page 14.68 5.55 0.82 0.38 "risk" | Out-Null

    Add-Box $Page 3.35 1.95 1.72 1.16 "Local vehicle layer`nx_i,k, u_i,k-1`nconnection/force states`nperceived team ey" "RGB(244,248,253)" $teal 5.65 | Out-Null
    Add-Box $Page 5.55 1.95 1.92 1.16 "Vehicle-to-vehicle perception`nrelative state`nrelative distance`ncomm_team_ey" $paleTeal $teal 5.50 | Out-Null
    Add-Box $Page 7.90 1.95 1.96 1.16 "Communication-quality consensus`nquality_global q`nloss/delay summary`nremote-state prediction" $paleTeal $teal 5.35 | Out-Null
    Add-Box $Page 10.25 1.95 1.92 1.16 "Delay-compensated Koopman-MPC`ntrack delivered xref_win`nconnection and distance costs`nlocal u_i*" "RGB(241,248,247)" $teal 5.35 | Out-Null
    Add-Box $Page 12.55 1.95 1.86 1.16 "FDI/FTC and safety filter`nmode switching`ncommand projection`nbound tightening/fallback" $paleRose $rose 5.35 | Out-Null
    Add-Box $Page 14.35 1.95 1.28 1.16 "Execution`nlower_received_stack`nactuator fault`nu_act" $paleGray $blue 5.30 | Out-Null

    Add-Line $Page 2.12 6.70 2.54 6.70 $blue $true $true 0.90 "" | Out-Null
    Add-Line $Page 4.15 6.28 4.60 6.28 $blue $true $false 1.05 "" | Out-Null
    Add-Line $Page 6.20 6.05 6.28 6.05 $blue $true $false 1.05 "" | Out-Null
    Add-Line $Page 8.32 6.05 8.57 6.62 $orange $true $false 1.05 "" | Out-Null
    Add-Line $Page 8.32 6.05 8.57 5.44 $orange $true $false 1.05 "" | Out-Null
    Add-Line $Page 10.27 6.65 10.69 6.65 $teal $true $false 1.05 "ref" | Out-Null
    Add-Line $Page 10.27 5.42 10.69 5.42 $teal $true $false 1.05 "cmd" | Out-Null
    Add-Line $Page 12.61 6.65 12.87 6.25 $rose $true $false 1.00 "" | Out-Null
    Add-Line $Page 12.61 5.42 12.87 5.82 $rose $true $false 1.00 "" | Out-Null

    Add-Line $Page 11.65 5.94 11.65 2.58 $teal $true $true 0.95 "delivered ref" | Out-Null
    Add-Line $Page 12.55 4.94 12.55 2.58 $rose $true $true 0.95 "delivered cmd" | Out-Null
    Add-Line $Page 2.12 1.95 2.49 1.95 $teal $true $false 1.00 "" | Out-Null
    Add-Line $Page 4.21 1.95 4.59 1.95 $teal $true $false 1.00 "" | Out-Null
    Add-Line $Page 6.51 1.95 6.92 1.95 $teal $true $false 1.00 "" | Out-Null
    Add-Line $Page 8.88 1.95 9.29 1.95 $teal $true $false 1.00 "" | Out-Null
    Add-Line $Page 11.21 1.95 11.62 1.95 $rose $true $false 1.00 "" | Out-Null
    Add-Line $Page 13.48 1.95 13.71 1.95 $blue $true $false 1.00 "" | Out-Null
    Add-Line $Page 14.35 1.36 14.35 0.90 $blue $false $true 0.85 "" | Out-Null
    Add-Line $Page 14.35 0.90 1.35 0.90 $blue $false $true 0.85 "closed-loop logs" | Out-Null
    Add-Line $Page 1.35 0.90 1.35 3.05 $blue $true $true 0.85 "" | Out-Null
    Add-Line $Page 7.90 1.34 7.90 0.72 $rose $false $true 0.85 "" | Out-Null
    Add-Line $Page 7.90 0.72 12.55 0.72 $rose $false $true 0.85 "low q / unsafe margin" | Out-Null
    Add-Line $Page 12.55 0.72 12.55 1.36 $rose $true $true 0.85 "" | Out-Null

    Add-TextBox $Page 8.0 0.22 14.8 0.24 "图意：上层负责重构和跨层发布，下层负责物理闭环维护；两类通信扰动分别影响参考窗口、控制命令和邻车感知，再由证书/保护层限制风险。" 6.25 $ink $false "1" | Out-Null
}

function Draw-Flow {
    param($Page)
    Setup-Page $Page "NR-KDCC online flow"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGray = "RGB(246,248,250)"

    Add-TextBox $Page 8.0 8.58 14.8 0.38 "NR-KDCC closed-loop signal flow with two communication channels" 11.8 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.18 14.8 0.28 "单周期：状态观测 -> 上层参考/命令发布 -> 下层感知通信与 Koopman-MPC -> 证书/保护 -> 执行并反馈" 7.05 $teal $false "1" | Out-Null

    Add-Lane $Page 8.0 6.35 15.0 2.00 "Upper-level branch" $orange $paleOrange | Out-Null
    Add-Lane $Page 8.0 4.05 15.0 2.10 "Lower-level branch" $teal $paleTeal | Out-Null
    Add-Lane $Page 8.0 1.55 15.0 1.95 "Safety and feedback branch" $rose $paleRose | Out-Null

    Add-Box $Page 1.30 6.42 1.78 1.06 "State observation`nx_i,k, q_L,k`nu_i,k-1`ncomm/fault flags" $paleGray $blue 6.05 | Out-Null
    Add-Box $Page 3.44 6.42 1.90 1.06 "Upper reference synthesis`nteam_ref_step`npath preview`nxref_win" $paleOrange $orange 5.95 | Out-Null
    Add-Box $Page 5.70 6.42 2.04 1.06 "Reference channel`nupper_lower_comm_ref`ndelay/drop/bias/noise`nreceived xref" $paleTeal $teal 5.70 | Out-Null
    Add-Box $Page 8.10 6.42 2.02 1.06 "FDI + role manager`nresidual diagnosis`nphase-role`nFTC mode" $paleBlue $blue 5.85 | Out-Null
    Add-Box $Page 10.55 6.42 2.05 1.06 "Command publisher`nplanned_u_stack`nFTC switching`nu_sent_stack" $paleOrange $orange 5.80 | Out-Null
    Add-Box $Page 13.00 6.42 2.06 1.06 "Command channel`nupper_lower_comm`ndelay/drop/bias/noise`nlower_received" $paleTeal $teal 5.70 | Out-Null

    Add-Box $Page 1.30 4.05 1.78 1.10 "Local correction`nperceived team ey`nxk_for_control`nload state" "RGB(244,248,253)" $teal 5.85 | Out-Null
    Add-Box $Page 3.54 4.05 2.06 1.10 "Vehicle-to-vehicle channel`nrelative state`nrelative distance`ncomm_team_ey" $paleTeal $teal 5.80 | Out-Null
    Add-Box $Page 5.92 4.05 2.02 1.10 "Quality consensus`nquality_global q`nloss/delay estimate`nnetwork state" $paleTeal $teal 5.75 | Out-Null
    Add-Box $Page 8.22 4.05 2.00 1.10 "Delay compensation`npush_states`nremote prediction`nperceived substitute" "RGB(241,248,247)" $teal 5.65 | Out-Null
    Add-Box $Page 10.55 4.05 2.08 1.10 "Koopman-MPC`nbilinear rollout`ntracking + connection cost`nlocal u_i*" "RGB(241,248,247)" $teal 5.75 | Out-Null
    Add-Box $Page 13.02 4.05 2.08 1.10 "Connection repair`nadjacent control`ncoop correction`ndesired_u_stack" $paleTeal $teal 5.65 | Out-Null

    Add-Box $Page 13.02 1.92 2.08 1.02 "Actuator/fault layer`nfault injection`nactuator limits`nactual_u_stack" $paleRose $rose 5.65 | Out-Null
    Add-Diamond $Page 10.42 1.92 1.36 1.02 "Certificate`npass?" "RGB(255,248,238)" $orange | Out-Null
    Add-Box $Page 7.64 1.92 2.08 1.02 "Safety filter`ncommand projection`ntightened bounds`ndegraded fallback" $paleRose $rose 5.65 | Out-Null
    Add-Box $Page 4.86 1.92 2.08 1.02 "Execution log`nu_act`ncomm/fault/cert traces`nmetrics" $paleGray $blue 5.75 | Out-Null
    Add-Box $Page 2.05 1.92 2.05 1.02 "Experiment boundary`nE9 comm architecture`n5-10 step delay`nbaseline switch" "RGB(244,248,253)" $blue 5.45 | Out-Null

    Add-Line $Page 2.19 6.42 2.49 6.42 $orange $true $false 1.05 "" | Out-Null
    Add-Line $Page 4.39 6.42 4.68 6.42 $teal $true $false 1.05 "ref" | Out-Null
    Add-Line $Page 6.72 6.42 7.09 6.42 $blue $true $false 1.05 "" | Out-Null
    Add-Line $Page 9.11 6.42 9.53 6.42 $orange $true $false 1.05 "" | Out-Null
    Add-Line $Page 11.58 6.42 11.97 6.42 $teal $true $false 1.05 "cmd" | Out-Null
    Add-Line $Page 13.00 5.89 13.00 4.60 $rose $true $true 0.95 "delivered u" | Out-Null
    Add-Line $Page 5.70 5.89 5.70 4.60 $teal $true $true 0.95 "delivered xref" | Out-Null
    Add-Line $Page 8.10 5.89 8.10 4.60 $blue $true $true 0.90 "mode/q" | Out-Null

    Add-Line $Page 2.19 4.05 2.51 4.05 $teal $true $false 1.05 "" | Out-Null
    Add-Line $Page 4.57 4.05 4.91 4.05 $teal $true $false 1.05 "" | Out-Null
    Add-Line $Page 6.93 4.05 7.22 4.05 $teal $true $false 1.05 "" | Out-Null
    Add-Line $Page 9.22 4.05 9.51 4.05 $teal $true $false 1.05 "" | Out-Null
    Add-Line $Page 11.59 4.05 11.98 4.05 $teal $true $false 1.05 "" | Out-Null
    Add-Line $Page 13.02 3.50 13.02 2.43 $rose $true $false 1.05 "" | Out-Null
    Add-Line $Page 12.00 1.92 11.10 1.92 $orange $true $false 1.05 "" | Out-Null
    Add-Line $Page 9.74 1.92 8.68 1.92 $blue $true $false 1.05 "yes" | Out-Null
    Add-Line $Page 6.60 1.92 5.90 1.92 $blue $true $false 1.05 "" | Out-Null
    Add-Line $Page 3.82 1.92 3.08 1.92 $blue $true $false 1.00 "" | Out-Null

    Add-Line $Page 10.42 1.42 10.42 0.78 $rose $true $true 1.00 "no" | Out-Null
    Add-Line $Page 10.42 0.78 14.60 0.78 $rose $false $true 0.90 "" | Out-Null
    Add-Line $Page 14.60 0.78 14.60 4.05 $rose $false $true 0.90 "" | Out-Null
    Add-Line $Page 14.60 4.05 14.06 4.05 $rose $true $true 0.90 "protect/retry" | Out-Null
    Add-Line $Page 5.92 3.50 5.92 2.64 $rose $false $true 0.80 "" | Out-Null
    Add-Line $Page 5.92 2.64 7.64 2.64 $rose $false $true 0.80 "" | Out-Null
    Add-Line $Page 7.64 2.64 7.64 2.43 $rose $true $true 0.80 "low q" | Out-Null
    Add-Line $Page 4.86 2.43 4.86 3.05 $blue $false $true 0.90 "" | Out-Null
    Add-Line $Page 4.86 3.05 1.30 3.05 $blue $false $true 0.90 "" | Out-Null
    Add-Line $Page 1.30 3.05 1.30 5.89 $blue $true $true 0.90 "next k" | Out-Null

    Add-TextBox $Page 8.0 0.26 14.7 0.30 "图意：橙色上层链路决定参考与候选命令，青色下层链路处理车间通信和 MPC，玫红回路表示通信退化、故障或证书失败后的保护路径。" 6.45 $ink $false "1" | Out-Null
}

function Draw-TechnicalRoute {
    param($Page)
    Setup-Page $Page "NR-KDCC technical route"

    $ink = "RGB(37,54,79)"
    $slate = "RGB(84,104,128)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $green = "RGB(100,145,74)"
    $purple = "RGB(126,104,164)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGreen = "RGB(242,248,238)"
    $palePurple = "RGB(245,242,250)"
    $paleGray = "RGB(246,248,250)"

    Add-TextBox $Page 8.0 8.64 14.9 0.36 "NR-KDCC 论文技术路线图：从协同运输建模到投稿级证据链" 11.5 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.25 14.9 0.28 "按最新上下两层代码逻辑组织：物理模型 -> 数据与 Koopman -> 双通信通道 -> 下层 MPC -> FDI/FTC 安全证明 -> 实验证据" 6.9 $slate $false "1" | Out-Null

    Add-SectionFrame $Page 2.75 6.48 4.75 2.65 "1  协同运输构型与大地坐标建模" $orange "RGB(255,250,245)" | Out-Null
    Add-VehiclePayloadIcon $Page 1.45 6.45
    Add-TextBox $Page 1.45 5.62 1.65 0.18 "四车-载荷几何关系" 5.2 $orange $false "1" | Out-Null
    Add-Box $Page 3.22 6.92 1.92 0.76 "坐标与误差`ne_y, e_psi, e_s`nteam center" $paleOrange $orange 5.2 | Out-Null
    Add-Box $Page 3.22 5.94 1.92 0.76 "车辆-载荷动力学`nax, delta, r, vy`nconnection force" $paleOrange $orange 5.2 | Out-Null

    Add-SectionFrame $Page 8.00 6.48 4.75 2.65 "2  离线数据生成与双线性 Koopman 学习" $blue "RGB(245,249,255)" | Out-Null
    Add-Box $Page 6.35 6.92 1.55 0.76 "覆盖式激励`nspeed / curvature`nfault / comm samples" $paleBlue $blue 4.95 | Out-Null
    Add-NeuralNetGlyph $Page 8.00 6.53 1.72 1.48 "lifting network"
    Add-Box $Page 9.68 6.92 1.56 0.76 "双线性算子`nA, B, N_l`nridge regularization" $paleBlue $blue 4.95 | Out-Null
    Add-Box $Page 9.68 5.93 1.56 0.76 "训练证据`nloss curve`nshort/medium rollout" $paleBlue $blue 4.95 | Out-Null

    Add-SectionFrame $Page 13.25 6.48 4.75 2.65 "3  上下两层通信与重构决策" $teal "RGB(244,251,250)" | Out-Null
    Add-Box $Page 11.68 6.92 1.50 0.76 "上层协调`nreference publisher`nrole / mode" $paleTeal $teal 4.95 | Out-Null
    Add-Box $Page 13.25 6.92 1.50 0.76 "跨层通信`nupper_lower_ref`nupper_lower_cmd" $paleTeal $teal 4.95 | Out-Null
    Add-Box $Page 14.82 6.92 1.50 0.76 "车间感知`nrelative state`nteam e_y" $paleTeal $teal 4.95 | Out-Null
    Add-Box $Page 13.25 5.93 1.94 0.76 "通信退化注入`ndelay / dropout`nbias / noise" $paleRose $rose 4.95 | Out-Null

    Add-SectionFrame $Page 4.20 3.62 6.55 2.35 "4  下层延迟补偿一致性 Koopman-MPC" $green "RGB(247,252,244)" | Out-Null
    Add-Box $Page 1.80 3.90 1.48 0.76 "参考接收`nreceived xref`npath preview" $paleGreen $green 4.95 | Out-Null
    Add-Box $Page 3.40 3.90 1.48 0.76 "质量一致性`nquality q`nloss/delay estimate" $paleGreen $green 4.95 | Out-Null
    Add-Box $Page 5.00 3.90 1.48 0.76 "延迟补偿`npush_states`nremote prediction" $paleGreen $green 4.95 | Out-Null
    Add-Box $Page 6.60 3.90 1.48 0.76 "MPC求解`ntracking cost`nconnection cost" $paleGreen $green 4.95 | Out-Null
    Add-Box $Page 4.20 2.82 3.15 0.56 "输出：每车局部控制 u_i*，并修正队形中心、横纵误差和相邻连接误差" $paleGray $green 4.75 | Out-Null

    Add-SectionFrame $Page 11.80 3.62 6.55 2.35 "5  FDI/FTC 安全保护与 Lyapunov 证书" $purple "RGB(249,246,252)" | Out-Null
    Add-Box $Page 9.38 3.90 1.52 0.76 "故障检测`nresidual monitor`nonline FDI" $palePurple $purple 4.95 | Out-Null
    Add-Box $Page 11.05 3.90 1.52 0.76 "容错切换`nFTC mode`nrole schedule" $palePurple $purple 4.95 | Out-Null
    Add-Box $Page 12.72 3.90 1.52 0.76 "安全滤波`nprojection`ntightened bounds" $paleRose $rose 4.95 | Out-Null
    Add-Box $Page 14.38 3.90 1.52 0.76 "稳定性证书`nISS/UUB margin`nunsafe fallback" $paleRose $rose 4.95 | Out-Null
    Add-Box $Page 11.80 2.82 3.15 0.56 "输出：受限控制 u_act 与证书日志，用于解释通信/故障压力下为何不发散" $paleGray $purple 4.75 | Out-Null

    Add-SectionFrame $Page 8.00 1.18 14.90 1.68 "6  投稿级实验证据链与主文图表落点" $slate "RGB(255,255,255)" | Out-Null
    Add-Box $Page 2.15 1.20 2.25 0.82 "学习有效性`ntraining loss`nrollout vs linear model`ndynamics RMSE" $paleBlue $blue 5.00 | Out-Null
    Add-Box $Page 5.35 1.20 2.25 0.82 "控制主结果`nteam center trajectory`nper-vehicle e_y/e_s`nforce components" $paleGreen $green 5.00 | Out-Null
    Add-Box $Page 8.55 1.20 2.25 0.82 "严格基线对齐`nAKE-M / physical DMPC`ncomm-stress boundary`nRMSE table" $paleOrange $orange 5.00 | Out-Null
    Add-Box $Page 11.75 1.20 2.25 0.82 "消融验证`nno role schedule`nno delay compensation`nno FDI/FTC" $paleTeal $teal 5.00 | Out-Null
    Add-Box $Page 14.55 1.20 1.72 0.82 "安全证据`ncertificate margin`nconstraint violation`nrisk cases" $paleRose $rose 4.85 | Out-Null

    Add-Line $Page 5.12 6.48 5.62 6.48 $blue $true $false 1.05 "" | Out-Null
    Add-Line $Page 10.38 6.48 10.88 6.48 $teal $true $false 1.05 "" | Out-Null
    Add-Line $Page 13.25 5.16 8.30 4.78 $teal $false $true 0.82 "delivered ref/cmd + V2V packets" | Out-Null
    Add-Line $Page 8.30 4.78 6.70 4.16 $teal $true $true 0.82 "" | Out-Null
    Add-Line $Page 7.48 3.62 8.52 3.62 $purple $true $false 1.05 "u_i*, q, residual" | Out-Null
    Add-Line $Page 4.20 2.45 4.20 2.02 $green $false $true 0.82 "" | Out-Null
    Add-Line $Page 4.20 2.02 5.35 1.76 $green $true $true 0.82 "" | Out-Null
    Add-Line $Page 11.80 2.45 11.80 2.02 $rose $false $true 0.82 "" | Out-Null
    Add-Line $Page 11.80 2.02 11.75 1.76 $rose $true $true 0.82 "" | Out-Null
    Add-Line $Page 14.95 3.20 15.45 3.20 $rose $false $true 0.75 "" | Out-Null
    Add-Line $Page 15.45 3.20 15.45 6.05 $rose $false $true 0.75 "" | Out-Null
    Add-Line $Page 15.45 6.05 14.25 6.05 $rose $true $true 0.75 "fallback feedback" | Out-Null

    Add-TextBox $Page 8.0 0.24 14.8 0.24 "图意：该图用于论文引言末或方法开头，强调每个贡献都有对应模块与实验落点；不是单周期控制流程图。" 6.2 $ink $false "1" | Out-Null
}

function Add-FourVehicle4WSDiagram {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Title = "四车协同搬运 / 4WS 上层模型")
    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $bg = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $bg.Text = ""
    Set-BaseStyle $bg "RGB(255,251,246)" $orange $ink 0.95 5.4 $false "1"
    Add-TextBox $Page $X ($Y + $H / 2 - 0.14) ($W - 0.12) 0.20 $Title 5.7 $orange $true "1" | Out-Null

    $payload = $Page.DrawRectangle($X - $W * 0.25, $Y - $H * 0.10, $X + $W * 0.25, $Y + $H * 0.10)
    $payload.Text = "payload"
    Set-BaseStyle $payload "RGB(232,226,238)" "RGB(126,104,164)" $ink 0.85 4.6 $false "1"
    Set-CellFormula $payload "FillTransparency" "8%"
    Add-Line $Page ($X - $W * 0.34) $Y ($X + $W * 0.34) $Y "RGB(150,160,170)" $false $true 0.65 "" | Out-Null
    Add-Line $Page $X ($Y - $H * 0.26) $X ($Y + $H * 0.26) "RGB(150,160,170)" $false $true 0.65 "" | Out-Null

    $cars = @(
        [pscustomobject]@{ X = $X - $W * 0.35; Y = $Y + $H * 0.23; A = -18; L = "V1" },
        [pscustomobject]@{ X = $X + $W * 0.35; Y = $Y + $H * 0.23; A = 18; L = "V2" },
        [pscustomobject]@{ X = $X - $W * 0.35; Y = $Y - $H * 0.23; A = 18; L = "V3" },
        [pscustomobject]@{ X = $X + $W * 0.35; Y = $Y - $H * 0.23; A = -18; L = "V4" }
    )
    foreach ($c in $cars) {
        Add-VehicleGlyph $Page $c.X $c.Y "RGB(118,193,204)" 0.75 $c.A | Out-Null
        Add-TextBox $Page $c.X ($c.Y - 0.24) 0.36 0.12 $c.L 4.4 $ink $true "1" | Out-Null
        Add-Line $Page $c.X $c.Y $X $Y $teal $false $false 0.65 "" | Out-Null
        Add-Line $Page ($c.X - 0.16) ($c.Y + 0.13) ($c.X - 0.32) ($c.Y + 0.26) $rose $true $false 0.55 "" | Out-Null
        Add-Line $Page ($c.X + 0.16) ($c.Y - 0.13) ($c.X + 0.32) ($c.Y - 0.26) $rose $true $false 0.55 "" | Out-Null
    }
    Add-TextBox $Page ($X - $W * 0.30) ($Y - $H * 0.39) 0.88 0.16 "delta_f / delta_r" 4.2 $rose $false "1" | Out-Null
    Add-TextBox $Page ($X + $W * 0.20) ($Y - $H * 0.39) 1.18 0.16 "X_L,Y_L,psi_L,v_L" 4.2 $blue $false "1" | Out-Null
}

function Add-SingleVehicleDynamicsDiagram {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Title = "单车动力学 / 执行层模型")
    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $bg = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $bg.Text = ""
    Set-BaseStyle $bg "RGB(246,251,251)" $teal $ink 0.95 5.4 $false "1"
    Add-TextBox $Page $X ($Y + $H / 2 - 0.14) ($W - 0.12) 0.20 $Title 5.7 $teal $true "1" | Out-Null
    $body = $Page.DrawRectangle($X - $W * 0.12, $Y - $H * 0.24, $X + $W * 0.12, $Y + $H * 0.24)
    $body.Text = "m, I_z"
    Set-BaseStyle $body "RGB(232,242,247)" $blue $ink 0.85 4.8 $false "1"
    Set-CellFormula $body "Rounding" "0.045 in"
    foreach ($dy in @(($H * 0.17), (-1 * $H * 0.17))) {
        $fl = $Page.DrawRectangle($X - $W * 0.19, $Y + $dy - 0.035, $X - $W * 0.08, $Y + $dy + 0.035)
        Set-BaseStyle $fl "RGB(255,255,255)" $ink $ink 0.45 3.6 $false "1"
        $fr = $Page.DrawRectangle($X + $W * 0.08, $Y + $dy - 0.035, $X + $W * 0.19, $Y + $dy + 0.035)
        Set-BaseStyle $fr "RGB(255,255,255)" $ink $ink 0.45 3.6 $false "1"
    }
    Add-Line $Page $X $Y ($X + $W * 0.33) $Y $blue $true $false 0.85 "v_x" | Out-Null
    Add-Line $Page $X $Y $X ($Y + $H * 0.35) $teal $true $false 0.85 "v_y" | Out-Null
    Add-Line $Page ($X - $W * 0.25) ($Y + $H * 0.22) ($X - $W * 0.34) ($Y + $H * 0.34) $rose $true $false 0.65 "F_yf" | Out-Null
    Add-Line $Page ($X + $W * 0.25) ($Y - $H * 0.22) ($X + $W * 0.35) ($Y - $H * 0.34) $rose $true $false 0.65 "F_yr" | Out-Null
    Add-Line $Page ($X - $W * 0.31) ($Y - $H * 0.18) ($X - $W * 0.31) ($Y + $H * 0.18) $orange $true $true 0.65 "r" | Out-Null
    Add-TextBox $Page ($X + $W * 0.28) ($Y - $H * 0.37) 1.15 0.16 "states: v_y, r, e_y, e_psi" 4.0 $ink $false "1" | Out-Null
}

function Add-KoopmanNetworkDiagram {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Title = "离线 Koopman 数据-网络识别")
    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $purple = "RGB(126,104,164)"
    $bg = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $bg.Text = ""
    Set-BaseStyle $bg "RGB(246,250,255)" $blue $ink 0.95 5.4 $false "1"
    Add-TextBox $Page $X ($Y + $H / 2 - 0.14) ($W - 0.12) 0.20 $Title 5.7 $blue $true "1" | Out-Null

    $chipX = $X - $W * 0.38
    foreach ($idx in 0..2) {
        $cy = $Y + (0.20 - 0.20 * $idx)
        $chip = $Page.DrawRectangle($chipX - 0.18, $cy - 0.055, $chipX + 0.18, $cy + 0.055)
        $chip.Text = @("x,u,q", "delay", "fault")[$idx]
        Set-BaseStyle $chip "RGB(255,255,255)" $blue $ink 0.45 3.4 $false "1"
        Set-CellFormula $chip "Rounding" "0.02 in"
    }

    $layers = @(
        [pscustomobject]@{ X = $X - $W * 0.19; Ys = @(-0.22, 0.00, 0.22) },
        [pscustomobject]@{ X = $X - $W * 0.01; Ys = @(-0.30, -0.10, 0.10, 0.30) },
        [pscustomobject]@{ X = $X + $W * 0.18; Ys = @(-0.22, 0.00, 0.22) },
        [pscustomobject]@{ X = $X + $W * 0.34; Ys = @(-0.12, 0.12) }
    )
    for ($li = 0; $li -lt $layers.Count - 1; $li++) {
        foreach ($y1 in $layers[$li].Ys) {
            foreach ($y2 in $layers[$li + 1].Ys) {
                Add-Line $Page $layers[$li].X ($Y + $y1) $layers[$li + 1].X ($Y + $y2) $blue $false $false 0.28 "" | Out-Null
            }
        }
    }
    foreach ($layer in $layers) {
        foreach ($dy in $layer.Ys) {
            $node = $Page.DrawOval($layer.X - 0.035, $Y + $dy - 0.035, $layer.X + 0.035, $Y + $dy + 0.035)
            Set-BaseStyle $node "RGB(226,237,252)" $blue $ink 0.45 3.0 $false "1"
        }
    }
    $op = $Page.DrawRectangle($X + $W * 0.31, $Y - $H * 0.36, $X + $W * 0.48, $Y - $H * 0.22)
    $op.Text = "A,B,N"
    Set-BaseStyle $op "RGB(245,242,250)" $purple $ink 0.65 4.2 $true "1"
    Set-CellFormula $op "Rounding" "0.02 in"
    Add-TextBox $Page ($X - $W * 0.12) ($Y - $H * 0.39) 0.88 0.14 "phi_theta(x)" 4.1 $teal $false "1" | Out-Null
}

function Add-SafetyLayerDiagram {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Title = "安全层诊断-容错-证书保护")
    $ink = "RGB(37,54,79)"
    $rose = "RGB(201,93,99)"
    $purple = "RGB(126,104,164)"
    $green = "RGB(100,145,74)"
    $orange = "RGB(230,138,53)"
    $bg = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $bg.Text = ""
    Set-BaseStyle $bg "RGB(255,247,248)" $rose $ink 0.95 5.4 $false "1"
    if ($Title -ne "") {
        Add-TextBox $Page $X ($Y + $H / 2 - 0.14) ($W - 0.12) 0.20 $Title 5.7 $rose $true "1" | Out-Null
    }

    $fdi = $Page.DrawRectangle($X - $W * 0.45, $Y - 0.12, $X - $W * 0.27, $Y + 0.12)
    $fdi.Text = "FDI`nr_i"
    Set-BaseStyle $fdi "RGB(255,255,255)" $rose $ink 0.65 4.2 $true "1"
    Set-CellFormula $fdi "Rounding" "0.02 in"

    $bounds = $Page.DrawRectangle($X - 0.25, $Y + $H * 0.26, $X + 0.02, $Y + $H * 0.41)
    $bounds.Text = "PPC`nbounds"
    Set-BaseStyle $bounds "RGB(255,255,255)" $purple $ink 0.65 4.0 $true "1"
    Set-CellFormula $bounds "Rounding" "0.02 in"

    $force = $Page.DrawRectangle($X + 0.08, $Y + $H * 0.26, $X + 0.35, $Y + $H * 0.41)
    $force.Text = "F_L`nlimit"
    Set-BaseStyle $force "RGB(255,255,255)" $orange $ink 0.65 3.9 $true "1"
    Set-CellFormula $force "Rounding" "0.02 in"

    $cert = $Page.DrawRectangle($X - 0.23, $Y - $H * 0.41, $X + 0.23, $Y - $H * 0.26)
    $cert.Text = "ISS`nmargin"
    Set-BaseStyle $cert "RGB(255,255,255)" $purple $ink 0.65 3.9 $true "1"
    Set-CellFormula $cert "Rounding" "0.02 in"

    $shield = $Page.DrawRectangle($X - 0.20, $Y - 0.22, $X + 0.20, $Y + 0.22)
    $shield.Text = "FTC`nPPC`npayload"
    Set-BaseStyle $shield "RGB(253,239,240)" $rose $ink 0.95 4.2 $true "1"
    Set-CellFormula $shield "Rounding" "0.05 in"

    $out = $Page.DrawRectangle($X + $W * 0.28, $Y - 0.13, $X + $W * 0.49, $Y + 0.13)
    $out.Text = "u_safe`nfallback"
    Set-BaseStyle $out "RGB(242,248,238)" $green $ink 0.65 4.0 $true "1"
    Set-CellFormula $out "Rounding" "0.02 in"

    Add-Line $Page ($X - $W * 0.27) $Y ($X - 0.20) $Y $rose $true $false 0.65 "" | Out-Null
    Add-Line $Page ($X - 0.11) ($Y + $H * 0.26) ($X - 0.07) ($Y + 0.22) $purple $true $false 0.60 "" | Out-Null
    Add-Line $Page ($X + 0.22) ($Y + $H * 0.26) ($X + 0.10) ($Y + 0.22) $orange $true $false 0.60 "" | Out-Null
    Add-Line $Page $X ($Y - $H * 0.26) $X ($Y - 0.22) $purple $true $false 0.60 "" | Out-Null
    Add-Line $Page ($X + 0.20) $Y ($X + $W * 0.28) $Y $green $true $false 0.75 "" | Out-Null
}

function Add-SignalBlock {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Text, [string]$Fill, [string]$Line, [double]$FontSize = 6.4)
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = $Text
    Set-BaseStyle $s $Fill $Line "RGB(37,54,79)" 0.95 $FontSize $false "1"
    Set-CellFormula $s "Rounding" "0.025 in"
    return $s
}

function Add-OperatorNode {
    param($Page, [double]$X, [double]$Y, [string]$Text, [string]$Fill = "RGB(230,238,250)", [string]$Line = "RGB(65,105,165)")
    $s = $Page.DrawOval($X - 0.16, $Y - 0.16, $X + 0.16, $Y + 0.16)
    $s.Text = $Text
    Set-BaseStyle $s $Fill $Line "RGB(37,54,79)" 0.95 7.2 $true "1"
    return $s
}

function Add-NewFramework {
    param($Page)
    Setup-Page $Page "NR-KDCC four-layer framework"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $green = "RGB(100,145,74)"
    $purple = "RGB(126,104,164)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGreen = "RGB(242,248,238)"
    $palePurple = "RGB(245,242,250)"

    Add-TextBox $Page 8.0 8.62 14.9 0.38 "NR-KDCC 四层协同控制框架" 12.0 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.25 14.9 0.24 "离线层提供输入感知稳定投影 Koopman 模型与证据，上层生成 4WS 局部路径，下层执行通信质量感知 MPC，安全层贯穿 FDI/FTC、PPC guard、货物保护和证书回退" 6.6 $blue $false "1" | Out-Null

    Add-Lane $Page 8.0 6.92 15.0 1.78 "Offline layer: model/data foundation" $blue $paleBlue | Out-Null
    Add-Lane $Page 8.0 5.13 15.0 1.72 "Upper layer: 4WS cooperative transport planning" $orange $paleOrange | Out-Null
    Add-Lane $Page 8.0 3.30 15.0 1.72 "Lower layer: vehicle-level delay-compensated Koopman-MPC" $teal $paleTeal | Out-Null
    Add-Lane $Page 8.0 1.45 15.0 1.72 "Safety layer: FDI / FTC / Lyapunov certificate" $rose $paleRose | Out-Null

    Add-KoopmanNetworkDiagram $Page 1.70 6.92 2.18 1.34 "IRSP Koopman 网络识别"
    Add-FourVehicle4WSDiagram $Page 1.70 5.10 2.18 1.34 "上层 4WS 协同搬运模型"
    Add-SingleVehicleDynamicsDiagram $Page 1.70 3.30 2.18 1.34 "下层单车动力学模型"
    Add-SafetyLayerDiagram $Page 1.70 1.30 2.18 1.12 ""

    Add-Box $Page 3.92 6.92 1.76 1.02 "离线数据生成`n曲率/速度覆盖`n通信/故障样本`n执行器退化" $paleBlue $blue 5.45 | Out-Null
    Add-Box $Page 6.12 6.92 1.76 1.02 "双线性 Koopman`nz=phi_theta(x)`nA,B,N_l`nIRSP 谱投影" $paleBlue $blue 5.25 | Out-Null
    Add-Box $Page 8.32 6.92 1.76 1.02 "模型证据库`ntraining loss`nrollout RMSE`n6D/raw ablation" $paleBlue $blue 5.35 | Out-Null
    Add-Box $Page 10.52 6.92 1.76 1.02 "约束/证书模板`nconnection/force bounds`nPPC guard`nISS/UUB margin" $palePurple $purple 5.10 | Out-Null

    Add-Box $Page 3.92 5.13 1.76 1.02 "上层状态融合`nteam center`nload pose`nq_comm / fault" $paleOrange $orange 5.35 | Out-Null
    Add-Box $Page 6.12 5.13 1.76 1.02 "4WS 参考生成`nX_L,Y_L,psi_L`nv_ref, kappa_ref`nxref_win" $paleOrange $orange 5.35 | Out-Null
    Add-Box $Page 8.32 5.13 1.76 1.02 "角色/相位调度`nleader role`ncurvature trim`nFTC/payload hint" $paleOrange $orange 5.20 | Out-Null
    Add-Box $Page 10.52 5.13 1.76 1.02 "跨层通信`nreference channel`ncommand channel`ndelay/drop/bias" $paleTeal $teal 5.35 | Out-Null

    Add-Box $Page 3.92 3.30 1.76 1.02 "车间感知通信`nrelative state`nrelative distance`nteam e_y" $paleTeal $teal 5.35 | Out-Null
    Add-Box $Page 6.12 3.30 1.76 1.02 "质量一致性`nquality consensus`nremote prediction`npush states" $paleTeal $teal 5.35 | Out-Null
    Add-Box $Page 8.32 3.30 1.76 1.02 "逐车 Koopman-MPC`ntracking/conn/force cost`ninput shrink`nu_i*" $paleGreen $green 5.10 | Out-Null
    Add-Box $Page 10.52 3.30 1.76 1.02 "执行层`nax, delta_f, delta_r`nu_safe / u_act`nactuator limits" $paleGreen $green 5.25 | Out-Null

    Add-Box $Page 3.92 1.45 1.76 1.02 "在线 FDI`nresidual r_i`nfault flag`nnoise/attack flag" $paleRose $rose 5.35 | Out-Null
    Add-Box $Page 6.12 1.45 1.76 1.02 "FTC / 保护切换`nrole reassignment`ncommand repair`npayload mode" $paleRose $rose 5.15 | Out-Null
    Add-Box $Page 8.32 1.45 1.76 1.02 "安全滤波`nprojection`nPPC tightened bounds`npayload protection" $paleRose $rose 5.10 | Out-Null
    Add-Box $Page 10.52 1.45 1.76 1.02 "Lyapunov/ISS 证书`nmodewise pass?`nmargin log`nfallback trigger" $palePurple $purple 5.05 | Out-Null

    Add-Box $Page 13.35 4.42 2.28 6.12 "四层协作总线`nIRSP model -> Koopman-MPC`n4WS ref / upper replan`nlower feedback -> upper update`nveto / payload fallback`nlogs -> evidence update" "RGB(248,250,251)" $ink 5.10 | Out-Null

    Add-Line $Page 4.80 6.92 5.24 6.92 $blue $true $false 1.0 "" | Out-Null
    Add-Line $Page 7.00 6.92 7.44 6.92 $blue $true $false 1.0 "" | Out-Null
    Add-Line $Page 9.20 6.92 9.64 6.92 $purple $true $false 1.0 "" | Out-Null
    Add-Line $Page 4.80 5.13 5.24 5.13 $orange $true $false 1.0 "" | Out-Null
    Add-Line $Page 7.00 5.13 7.44 5.13 $orange $true $false 1.0 "" | Out-Null
    Add-Line $Page 9.20 5.13 9.64 5.13 $teal $true $false 1.0 "" | Out-Null
    Add-Line $Page 4.80 3.30 5.24 3.30 $teal $true $false 1.0 "" | Out-Null
    Add-Line $Page 7.00 3.30 7.44 3.30 $green $true $false 1.0 "" | Out-Null
    Add-Line $Page 9.20 3.30 9.64 3.30 $green $true $false 1.0 "" | Out-Null
    Add-Line $Page 4.80 1.45 5.24 1.45 $rose $true $false 1.0 "" | Out-Null
    Add-Line $Page 7.00 1.45 7.44 1.45 $rose $true $false 1.0 "" | Out-Null
    Add-Line $Page 9.20 1.45 9.64 1.45 $purple $true $false 1.0 "" | Out-Null

    Add-Line $Page 6.12 6.40 6.12 5.65 $blue $true $true 0.85 "model" | Out-Null
    Add-Line $Page 8.32 6.40 8.32 6.08 $green $false $true 0.78 "operators" | Out-Null
    Add-Line $Page 8.32 6.08 9.42 6.08 $green $false $true 0.78 "" | Out-Null
    Add-Line $Page 9.42 6.08 9.42 3.86 $green $false $true 0.78 "" | Out-Null
    Add-Line $Page 9.42 3.86 8.32 3.86 $green $true $true 0.78 "" | Out-Null
    Add-Line $Page 11.40 6.92 12.21 6.92 $purple $true $true 0.78 "model" | Out-Null
    Add-Line $Page 10.52 4.61 10.52 3.86 $teal $true $true 0.85 "ref/cmd" | Out-Null
    Add-Line $Page 10.52 2.78 10.52 1.98 $rose $true $true 0.85 "cert log" | Out-Null
    Add-Line $Page 11.40 5.30 12.21 5.30 $teal $true $true 0.78 "ref/cmd" | Out-Null
    Add-Line $Page 12.21 4.96 11.40 4.96 $orange $true $true 0.78 "replan" | Out-Null
    Add-Line $Page 11.40 3.30 12.21 3.30 $teal $true $true 0.78 "feedback" | Out-Null
    Add-Line $Page 11.40 1.45 12.21 1.45 $rose $true $true 0.78 "veto" | Out-Null

    Add-TextBox $Page 8.0 0.22 14.8 0.24 "图意：四层不是串行堆叠；离线层下发 IRSP Koopman 模型和证书模板，上层发布 4WS 局部路径，下层执行通信质量感知闭环，安全层用 FDI/FTC、PPC guard 和货物保护进行约束、受力折中与回退。" 5.9 $ink $false "1" | Out-Null
}

function Add-NewSignalFlow {
    param($Page)
    Setup-Page $Page "NR-KDCC block signal flow"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $green = "RGB(100,145,74)"
    $purple = "RGB(126,104,164)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGreen = "RGB(242,248,238)"
    $palePurple = "RGB(245,242,250)"

    Add-TextBox $Page 8.0 8.58 14.9 0.36 "NR-KDCC 控制流程信号框图" 12.0 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.22 14.9 0.24 "小方块表示变量/功能模块，圆形表示代数运算，菱形表示判断，虚线表示通信退化或安全回退通道" 6.8 $blue $false "1" | Out-Null

    Add-SignalBlock $Page 0.90 7.35 0.90 0.34 "x_i(k)" $paleBlue $blue 6.0 | Out-Null
    Add-SignalBlock $Page 0.90 6.75 0.90 0.34 "q(k)" $paleTeal $teal 6.0 | Out-Null
    Add-SignalBlock $Page 0.90 6.15 0.90 0.34 "r_ref" $paleOrange $orange 6.0 | Out-Null
    Add-SignalBlock $Page 0.90 5.55 0.90 0.34 "u(k-1)" $paleGreen $green 6.0 | Out-Null
    Add-SignalBlock $Page 0.90 4.95 0.90 0.34 "fault" $paleRose $rose 6.0 | Out-Null

    Add-SignalBlock $Page 2.25 7.05 1.35 0.48 "观测融合" $paleBlue $blue 6.2 | Out-Null
    Add-SignalBlock $Page 4.45 7.05 1.55 0.48 "状态提升 z=phi_theta(x)" $paleBlue $blue 5.6 | Out-Null
    Add-SignalBlock $Page 6.15 7.05 1.35 0.48 "IRSP Koopman 预测" $paleBlue $blue 5.4 | Out-Null
    Add-OperatorNode $Page 7.45 7.05 "×" $palePurple $purple | Out-Null
    Add-SignalBlock $Page 8.70 7.05 1.35 0.48 "4WS参考模型" $paleOrange $orange 5.8 | Out-Null
    Add-SignalBlock $Page 10.25 7.05 1.35 0.48 "xref_win" $paleOrange $orange 5.8 | Out-Null
    Add-SignalBlock $Page 11.85 7.05 1.48 0.48 "参考通信通道" $paleTeal $teal 5.8 | Out-Null
    Add-SignalBlock $Page 13.55 7.05 1.42 0.48 "delivered ref" $paleTeal $teal 5.8 | Out-Null

    Add-SignalBlock $Page 2.25 5.70 1.35 0.48 "车间通信" $paleTeal $teal 6.2 | Out-Null
    Add-SignalBlock $Page 4.00 5.70 1.42 0.48 "质量一致性" $paleTeal $teal 6.0 | Out-Null
    Add-OperatorNode $Page 5.28 5.70 "Σ" $paleTeal $teal | Out-Null
    Add-SignalBlock $Page 6.65 5.70 1.52 0.48 "延迟补偿" $paleGreen $green 6.0 | Out-Null
    Add-SignalBlock $Page 8.28 5.70 1.50 0.48 "远端状态预测" $paleGreen $green 5.8 | Out-Null
    Add-OperatorNode $Page 9.62 5.70 "+" $paleGreen $green | Out-Null
    Add-SignalBlock $Page 10.95 5.70 1.50 0.48 "MPC代价/约束`ntrack+conn+force" $paleGreen $green 5.2 | Out-Null
    Add-OperatorNode $Page 12.32 5.70 "min" $paleGreen $green | Out-Null
    Add-SignalBlock $Page 13.75 5.70 1.42 0.48 "u_i*" $paleGreen $green 6.0 | Out-Null

    Add-SignalBlock $Page 3.05 4.22 1.48 0.48 "FDI残差" $paleRose $rose 6.0 | Out-Null
    Add-Diamond $Page 4.72 4.22 0.82 0.58 "fault?" $paleRose $rose | Out-Null
    Add-SignalBlock $Page 6.25 4.22 1.28 0.48 "FTC切换" $paleRose $rose 6.0 | Out-Null
    Add-SignalBlock $Page 7.80 4.22 1.28 0.48 "角色/曲率修正" $paleOrange $orange 5.6 | Out-Null
    Add-SignalBlock $Page 9.35 4.22 1.28 0.48 "命令发布" $paleOrange $orange 6.0 | Out-Null
    Add-SignalBlock $Page 10.95 4.22 1.42 0.48 "命令通信通道" $paleTeal $teal 5.8 | Out-Null
    Add-SignalBlock $Page 12.55 4.22 1.28 0.48 "u_recv" $paleTeal $teal 6.0 | Out-Null

    Add-SignalBlock $Page 5.20 2.72 1.40 0.48 "安全滤波`nPPC guard" $paleRose $rose 5.4 | Out-Null
    Add-Diamond $Page 7.00 2.72 0.92 0.62 "cert?" $palePurple $purple | Out-Null
    Add-SignalBlock $Page 8.75 2.72 1.48 0.48 "投影/收紧`nu_safe" $paleRose $rose 5.4 | Out-Null
    Add-SignalBlock $Page 10.55 2.72 1.48 0.48 "货物保护`n降级回退" $paleRose $rose 5.4 | Out-Null
    Add-OperatorNode $Page 12.10 2.72 "Σ" $paleRose $rose | Out-Null
    Add-SignalBlock $Page 13.70 2.72 1.42 0.48 "u_act" $paleGreen $green 6.0 | Out-Null
    Add-SignalBlock $Page 15.05 2.72 0.72 0.48 "plant" $paleBlue $blue 5.8 | Out-Null

    Add-SignalBlock $Page 2.25 1.45 1.48 0.44 "日志/指标" "RGB(246,248,250)" $ink 5.8 | Out-Null
    Add-SignalBlock $Page 4.25 1.45 1.48 0.44 "轨迹误差" $paleBlue $blue 5.8 | Out-Null
    Add-SignalBlock $Page 6.25 1.45 1.48 0.44 "连接误差/利用率" $paleGreen $green 5.5 | Out-Null
    Add-SignalBlock $Page 8.25 1.45 1.48 0.44 "受力/约束审计" $paleRose $rose 5.5 | Out-Null

    Add-Line $Page 1.35 7.35 1.58 7.08 $blue $true $false 0.9 "" | Out-Null
    Add-Line $Page 1.35 6.75 1.58 6.98 $teal $true $false 0.9 "" | Out-Null
    Add-Line $Page 1.35 6.15 1.35 6.55 $orange $false $true 0.75 "r_ref" | Out-Null
    Add-Line $Page 1.35 6.55 7.45 6.55 $orange $false $true 0.75 "" | Out-Null
    Add-Line $Page 7.45 6.55 7.45 6.89 $orange $true $true 0.75 "" | Out-Null
    Add-Line $Page 1.35 5.55 1.58 5.78 $green $true $false 0.9 "" | Out-Null
    Add-Line $Page 1.35 4.95 2.31 4.28 $rose $true $false 0.9 "" | Out-Null

    Add-Line $Page 2.92 7.05 3.68 7.05 $blue $true $false 0.95 "" | Out-Null
    Add-Line $Page 5.22 7.05 5.48 7.05 $blue $true $false 0.95 "" | Out-Null
    Add-Line $Page 6.82 7.05 7.29 7.05 $purple $true $false 0.95 "" | Out-Null
    Add-Line $Page 7.61 7.05 8.02 7.05 $orange $true $false 0.95 "" | Out-Null
    Add-Line $Page 9.38 7.05 9.57 7.05 $orange $true $false 0.95 "" | Out-Null
    Add-Line $Page 10.93 7.05 11.11 7.05 $teal $true $false 0.95 "" | Out-Null
    Add-Line $Page 12.59 7.05 12.84 7.05 $teal $true $false 0.95 "" | Out-Null

    Add-Line $Page 13.55 6.81 13.55 6.20 $teal $false $true 0.85 "ref" | Out-Null
    Add-Line $Page 13.55 6.20 9.62 6.20 $teal $false $true 0.85 "" | Out-Null
    Add-Line $Page 9.62 6.20 9.62 5.86 $teal $true $true 0.85 "" | Out-Null
    Add-Line $Page 2.92 5.70 3.29 5.70 $teal $true $false 0.95 "" | Out-Null
    Add-Line $Page 2.25 5.46 2.25 5.18 $teal $false $true 0.72 "raw packet" | Out-Null
    Add-Line $Page 2.25 5.18 5.28 5.18 $teal $false $true 0.72 "" | Out-Null
    Add-Line $Page 5.28 5.18 5.28 5.54 $teal $true $true 0.72 "" | Out-Null
    Add-Line $Page 4.71 5.70 5.12 5.70 $teal $true $false 0.95 "" | Out-Null
    Add-Line $Page 5.44 5.70 5.89 5.70 $green $true $false 0.95 "" | Out-Null
    Add-Line $Page 7.41 5.70 7.53 5.70 $green $true $false 0.95 "" | Out-Null
    Add-Line $Page 9.03 5.70 9.46 5.70 $green $true $false 0.95 "" | Out-Null
    Add-Line $Page 9.78 5.70 10.20 5.70 $green $true $false 0.95 "" | Out-Null
    Add-Line $Page 11.70 5.70 12.16 5.70 $green $true $false 0.95 "" | Out-Null
    Add-Line $Page 12.48 5.70 13.04 5.70 $green $true $false 0.95 "" | Out-Null

    Add-Line $Page 13.75 5.46 13.75 4.70 $orange $false $true 0.95 "u_i*" | Out-Null
    Add-Line $Page 13.75 4.70 9.35 4.70 $orange $false $true 0.95 "" | Out-Null
    Add-Line $Page 9.35 4.70 9.35 4.46 $orange $true $true 0.95 "" | Out-Null
    Add-Line $Page 3.05 5.46 3.05 4.41 $rose $true $true 0.75 "residual" | Out-Null
    Add-Line $Page 3.79 4.22 4.31 4.22 $rose $true $false 0.9 "" | Out-Null
    Add-Line $Page 5.13 4.22 5.61 4.22 $rose $true $false 0.9 "yes" | Out-Null
    Add-Line $Page 4.72 3.93 4.72 3.72 $green $false $true 0.82 "no" | Out-Null
    Add-Line $Page 4.72 3.72 9.35 3.72 $green $false $true 0.82 "" | Out-Null
    Add-Line $Page 9.35 3.72 9.35 3.98 $green $true $true 0.82 "" | Out-Null
    Add-Line $Page 6.89 4.22 7.16 4.22 $orange $true $false 0.9 "" | Out-Null
    Add-Line $Page 8.44 4.22 8.71 4.22 $orange $true $false 0.9 "" | Out-Null
    Add-Line $Page 9.99 4.22 10.24 4.22 $teal $true $false 0.9 "" | Out-Null
    Add-Line $Page 11.66 4.22 11.91 4.22 $teal $true $false 0.9 "" | Out-Null
    Add-Line $Page 12.55 3.98 12.55 3.38 $rose $false $true 0.72 "candidate u" | Out-Null
    Add-Line $Page 12.55 3.38 5.20 3.38 $rose $false $true 0.72 "" | Out-Null
    Add-Line $Page 5.20 3.38 5.20 3.00 $rose $true $true 0.72 "" | Out-Null
    Add-Line $Page 5.90 2.72 6.54 2.72 $purple $true $false 0.9 "" | Out-Null
    Add-Line $Page 7.46 2.72 8.01 2.72 $rose $true $false 0.9 "pass" | Out-Null
    Add-Line $Page 8.75 2.48 8.75 2.20 $rose $false $true 0.72 "projected u" | Out-Null
    Add-Line $Page 8.75 2.20 12.10 2.20 $rose $false $true 0.72 "" | Out-Null
    Add-Line $Page 12.10 2.20 12.10 2.56 $rose $true $true 0.72 "" | Out-Null
    Add-Line $Page 11.29 2.72 11.94 2.72 $rose $true $false 0.9 "" | Out-Null
    Add-Line $Page 12.26 2.72 12.99 2.72 $green $true $false 0.9 "" | Out-Null
    Add-Line $Page 14.41 2.72 14.69 2.72 $blue $true $false 0.9 "" | Out-Null

    Add-Line $Page 7.00 2.25 7.00 1.90 $rose $false $true 0.75 "fail" | Out-Null
    Add-Line $Page 7.00 1.90 10.55 1.90 $rose $false $true 0.75 "" | Out-Null
    Add-Line $Page 10.55 1.90 10.55 2.48 $rose $true $true 0.75 "" | Out-Null

    Add-Line $Page 15.05 2.48 15.05 0.82 $blue $false $true 0.75 "next k" | Out-Null
    Add-Line $Page 15.05 0.82 0.30 0.82 $blue $false $true 0.75 "" | Out-Null
    Add-Line $Page 0.30 0.82 0.30 7.35 $blue $false $true 0.75 "" | Out-Null
    Add-Line $Page 0.30 7.35 0.45 7.35 $blue $true $true 0.75 "" | Out-Null

    Add-Line $Page 14.10 2.48 14.10 2.08 $rose $false $true 0.60 "" | Out-Null
    Add-Line $Page 14.10 2.08 8.25 2.08 $rose $false $true 0.60 "" | Out-Null
    Add-Line $Page 8.25 2.08 8.25 1.68 $rose $true $true 0.60 "" | Out-Null
    Add-Line $Page 14.00 2.48 14.00 1.98 $green $false $true 0.60 "" | Out-Null
    Add-Line $Page 14.00 1.98 6.25 1.98 $green $false $true 0.60 "" | Out-Null
    Add-Line $Page 6.25 1.98 6.25 1.68 $green $true $true 0.60 "" | Out-Null
    Add-Line $Page 13.90 2.48 13.90 1.88 $blue $false $true 0.60 "" | Out-Null
    Add-Line $Page 13.90 1.88 4.25 1.88 $blue $false $true 0.60 "" | Out-Null
    Add-Line $Page 4.25 1.88 4.25 1.68 $blue $true $true 0.60 "" | Out-Null
    Add-Line $Page 13.80 2.48 13.80 1.78 $ink $false $true 0.60 "" | Out-Null
    Add-Line $Page 13.80 1.78 2.25 1.78 $ink $false $true 0.60 "" | Out-Null
    Add-Line $Page 2.25 1.78 2.25 1.68 $ink $true $true 0.60 "" | Out-Null

    Add-TextBox $Page 8.0 0.22 14.8 0.24 "图意：控制流程图只表达单周期数据流与判断关系；最新正文中的 IRSP、通信质量一致性、PPC guard、货物保护和 Lyapunov/ISS 证书均在该流程中有对应入口与反馈。" 5.9 $ink $false "1" | Out-Null
}

# Review-clean versions used after the 2026-05-21 figure audit.
# The older functions are kept above for traceability; these later definitions
# intentionally override them before Draw-Framework/Draw-Flow are invoked.
function Add-PathLine {
    param(
        $Page,
        [object[]]$Pts,
        [string]$Color = "RGB(65,105,165)",
        [bool]$Dash = $false,
        [double]$Weight = 1.0,
        [string]$Label = ""
    )
    for ($i = 0; $i -lt ($Pts.Count - 1); $i++) {
        $arrow = ($i -eq ($Pts.Count - 2))
        $p1 = $Pts[$i]
        $p2 = $Pts[$i + 1]
        Add-Line $Page $p1[0] $p1[1] $p2[0] $p2[1] $Color $arrow $Dash $Weight "" | Out-Null
    }
    if ($Label -ne "") {
        $mid = $Pts[[Math]::Floor(($Pts.Count - 1) / 2)]
        Add-TextBox $Page $mid[0] ($mid[1] + 0.12) 1.35 0.23 $Label 5.6 $Color $false "1" | Out-Null
    }
}

function Add-TinyChip {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Text, [string]$Fill, [string]$Line, [double]$FontSize = 5.4)
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = $Text
    Set-BaseStyle $s $Fill $Line "RGB(37,54,79)" 0.72 $FontSize $false "1"
    Set-CellFormula $s "Rounding" "0.045 in"
    return $s
}

function Add-ReviewLegend {
    param($Page, [double]$X, [double]$Y)
    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $orange = "RGB(230,138,53)"
    $teal = "RGB(47,156,149)"
    $rose = "RGB(201,93,99)"
    $purple = "RGB(126,104,164)"
    Add-TextBox $Page $X ($Y + 0.42) 2.35 0.22 "图例" 6.4 $ink $true "0" | Out-Null
    Add-TinyChip $Page ($X - 0.82) ($Y + 0.16) 0.20 0.14 "" "RGB(237,243,251)" $blue 4.0 | Out-Null
    Add-TextBox $Page ($X + 0.07) ($Y + 0.16) 1.70 0.16 "蓝：离线模型" 5.0 $ink $false "0" | Out-Null
    Add-TinyChip $Page ($X - 0.82) ($Y - 0.06) 0.20 0.14 "" "RGB(255,247,235)" $orange 4.0 | Out-Null
    Add-TextBox $Page ($X + 0.08) ($Y - 0.06) 1.72 0.16 "橙：上层规划" 5.0 $ink $false "0" | Out-Null
    Add-TinyChip $Page ($X - 0.82) ($Y - 0.28) 0.20 0.14 "" "RGB(232,247,246)" $teal 4.0 | Out-Null
    Add-TextBox $Page ($X + 0.11) ($Y - 0.28) 1.78 0.16 "青/绿：下层控制" 5.0 $ink $false "0" | Out-Null
    Add-TinyChip $Page ($X - 0.82) ($Y - 0.50) 0.20 0.14 "" "RGB(253,239,240)" $rose 4.0 | Out-Null
    Add-TextBox $Page ($X + 0.10) ($Y - 0.50) 1.78 0.16 "红/紫：安全证书" 5.0 $ink $false "0" | Out-Null
    Add-Line $Page ($X + 0.88) ($Y + 0.15) ($X + 1.35) ($Y + 0.15) $blue $true $false 0.8 "" | Out-Null
    Add-TextBox $Page ($X + 1.98) ($Y + 0.15) 1.12 0.16 "实线：数据/控制" 4.9 $ink $false "0" | Out-Null
    Add-Line $Page ($X + 0.88) ($Y - 0.13) ($X + 1.35) ($Y - 0.13) $purple $true $true 0.8 "" | Out-Null
    Add-TextBox $Page ($X + 2.04) ($Y - 0.13) 1.24 0.16 "虚线：反馈/回退" 4.9 $ink $false "0" | Out-Null
}

function Add-CleanKoopmanIcon {
    param($Page, [double]$X, [double]$Y)
    $blue = "RGB(65,105,165)"
    $green = "RGB(100,145,74)"
    $orange = "RGB(230,138,53)"
    $layers = @(
        @{ X = $X - 0.50; N = 3; Fill = "RGB(225,241,218)" },
        @{ X = $X - 0.12; N = 5; Fill = "RGB(224,234,249)" },
        @{ X = $X + 0.28; N = 4; Fill = "RGB(224,234,249)" },
        @{ X = $X + 0.62; N = 2; Fill = "RGB(255,232,184)" }
    )
    $last = @()
    foreach ($layer in $layers) {
        $nodes = @()
        for ($i = 0; $i -lt $layer.N; $i++) {
            $ny = $Y - 0.34 + ($i + 0.5) * (0.68 / $layer.N)
            $n = $Page.DrawOval($layer.X - 0.045, $ny - 0.045, $layer.X + 0.045, $ny + 0.045)
            Set-BaseStyle $n $layer.Fill $blue "RGB(37,54,79)" 0.35 3.8 $false "1"
            $nodes += ,@($layer.X, $ny)
        }
        if ($last.Count -gt 0) {
            foreach ($a in $last) {
                foreach ($b in $nodes) {
                    Add-Line $Page $a[0] $a[1] $b[0] $b[1] "RGB(143,166,203)" $false $false 0.22 "" | Out-Null
                }
            }
        }
        $last = $nodes
    }
    Add-TinyChip $Page ($X - 0.45) ($Y - 0.55) 0.58 0.17 "data" "RGB(237,243,251)" $blue 4.2 | Out-Null
    Add-TinyChip $Page ($X + 0.30) ($Y - 0.55) 0.76 0.17 "A,B,N_l" "RGB(242,248,238)" $green 4.2 | Out-Null
    Add-Line $Page ($X - 0.12) ($Y + 0.34) ($X + 0.40) ($Y + 0.34) $orange $true $false 0.75 "IRSP" | Out-Null
}

function Add-Clean4WSIcon {
    param($Page, [double]$X, [double]$Y)
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $blue = "RGB(65,105,165)"
    $payload = $Page.DrawRectangle($X - 0.58, $Y - 0.14, $X + 0.58, $Y + 0.14)
    $payload.Text = "货物"
    Set-BaseStyle $payload "RGB(241,238,249)" "RGB(126,104,164)" "RGB(37,54,79)" 0.85 5.0 $false "1"
    $pts = @(
        @{ X = $X - 0.78; Y = $Y + 0.36; A = -22; L = "V1" },
        @{ X = $X + 0.78; Y = $Y + 0.36; A = 22; L = "V2" },
        @{ X = $X - 0.78; Y = $Y - 0.36; A = 22; L = "V3" },
        @{ X = $X + 0.78; Y = $Y - 0.36; A = -22; L = "V4" }
    )
    foreach ($p in $pts) {
        Add-VehicleGlyph $Page $p.X $p.Y "RGB(226,72,88)" 0.70 $p.A | Out-Null
        Add-TextBox $Page $p.X ($p.Y - 0.24) 0.30 0.14 $p.L 4.5 "RGB(37,54,79)" $true "1" | Out-Null
        Add-Line $Page $p.X $p.Y $X $Y $teal $false $false 0.75 "" | Out-Null
    }
    Add-Line $Page ($X - 0.98) ($Y + 0.55) ($X - 0.78) ($Y + 0.44) $orange $true $false 0.8 "" | Out-Null
    Add-Line $Page ($X + 0.98) ($Y + 0.55) ($X + 0.78) ($Y + 0.44) $orange $true $false 0.8 "" | Out-Null
    Add-Line $Page ($X - 0.98) ($Y - 0.55) ($X - 0.78) ($Y - 0.44) $orange $true $false 0.8 "" | Out-Null
    Add-Line $Page ($X + 0.98) ($Y - 0.55) ($X + 0.78) ($Y - 0.44) $orange $true $false 0.8 "" | Out-Null
}

function Add-CleanVehicleIcon {
    param($Page, [double]$X, [double]$Y)
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $rose = "RGB(201,93,99)"
    $body = $Page.DrawRectangle($X - 0.46, $Y - 0.30, $X + 0.46, $Y + 0.30)
    $body.Text = "m_i, I_z"
    Set-BaseStyle $body "RGB(239,247,252)" $blue "RGB(37,54,79)" 0.9 5.0 $false "1"
    foreach ($dx in @(-0.38, 0.38)) {
        foreach ($dy in @(-0.38, 0.38)) {
            $wheel = $Page.DrawRectangle($X + $dx - 0.20, $Y + $dy - 0.045, $X + $dx + 0.20, $Y + $dy + 0.045)
            Set-BaseStyle $wheel "RGB(255,255,255)" $blue "RGB(37,54,79)" 0.45 3.8 $false "1"
        }
    }
    Add-Line $Page ($X - 0.18) $Y ($X + 0.72) $Y $blue $true $false 1.0 "v_x" | Out-Null
    Add-Line $Page $X ($Y - 0.18) $X ($Y + 0.70) $teal $true $false 1.0 "v_y" | Out-Null
    Add-Line $Page ($X - 0.62) ($Y + 0.58) ($X - 0.38) ($Y + 0.40) $rose $true $false 0.8 "F_{y,f}" | Out-Null
    Add-Line $Page ($X + 0.62) ($Y - 0.58) ($X + 0.38) ($Y - 0.40) $rose $true $false 0.8 "F_{y,r}" | Out-Null
}

function Add-CleanSafetyIcon {
    param($Page, [double]$X, [double]$Y)
    $rose = "RGB(201,93,99)"
    $purple = "RGB(126,104,164)"
    $green = "RGB(100,145,74)"
    $ink = "RGB(37,54,79)"
    Add-TinyChip $Page ($X - 0.60) ($Y + 0.36) 0.62 0.20 "FDI" "RGB(253,239,240)" $rose 4.8 | Out-Null
    Add-TinyChip $Page ($X - 0.60) $Y 0.62 0.20 "PPC" "RGB(253,239,240)" $rose 4.8 | Out-Null
    Add-TinyChip $Page ($X - 0.60) ($Y - 0.36) 0.62 0.20 "ISS" "RGB(245,242,250)" $purple 4.8 | Out-Null
    $safe = $Page.DrawOval($X + 0.28, $Y - 0.28, $X + 0.84, $Y + 0.28)
    $safe.Text = "保护`n信号融合"
    Set-BaseStyle $safe "RGB(244,249,241)" $green $ink 0.95 5.0 $true "1"
    Add-Line $Page ($X - 0.29) ($Y + 0.36) ($X + 0.28) ($Y + 0.14) $rose $true $false 0.65 "" | Out-Null
    Add-Line $Page ($X - 0.29) $Y ($X + 0.28) $Y $rose $true $false 0.65 "" | Out-Null
    Add-Line $Page ($X - 0.29) ($Y - 0.36) ($X + 0.28) ($Y - 0.14) $purple $true $false 0.65 "" | Out-Null
}

function Add-NewFramework {
    param($Page)
    Setup-Page $Page "NR-KDCC review-clean framework"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $green = "RGB(100,145,74)"
    $purple = "RGB(126,104,164)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGreen = "RGB(242,248,238)"
    $palePurple = "RGB(245,242,250)"

    Add-TextBox $Page 8.0 8.60 14.9 0.36 "网络韧性 Koopman 延迟补偿协同控制（NR-KDCC）总体框架" 11.4 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.26 14.7 0.24 "离线模型、上层 4WS 规划、下层通信质量感知 MPC 与安全证书不是简单串联，而是通过参考、反馈、回退和证据日志形成闭环协作。" 6.4 $blue $false "1" | Out-Null

    Add-Lane $Page 8.0 6.95 15.0 1.50 "离线层：数据与 Koopman 模型" $blue $paleBlue | Out-Null
    Add-Lane $Page 8.0 5.25 15.0 1.50 "上层：4WS 协同搬运规划" $orange $paleOrange | Out-Null
    Add-Lane $Page 8.0 3.55 15.0 1.50 "下层：延迟补偿 Koopman-MPC" $teal $paleTeal | Out-Null
    Add-Lane $Page 8.0 1.85 15.0 1.50 "安全层：FDI/FTC、PPC 与证书回退" $rose $paleRose | Out-Null

    Add-CleanKoopmanIcon $Page 2.05 6.92
    Add-Clean4WSIcon $Page 2.05 5.22
    Add-CleanVehicleIcon $Page 2.05 3.55
    Add-CleanSafetyIcon $Page 1.82 1.85

    Add-Box $Page 4.10 6.95 1.80 0.90 "场景数据覆盖`n速度/曲率/通信`n故障与噪声注入" $paleBlue $blue 5.55 | Out-Null
    Add-Box $Page 6.55 6.95 1.80 0.90 "双线性 Koopman`n升维网络 phi_theta`nA,B,N_l 算子矩阵" $paleBlue $blue 5.45 | Out-Null
    Add-Box $Page 9.00 6.95 1.80 0.90 "稳定投影（IRSP）`n谱半径约束`n岭回归正则" $palePurple $purple 5.50 | Out-Null
    Add-Box $Page 11.45 6.95 1.80 0.90 "证据与模板`n训练/rollout 误差`n约束边界模板" $paleBlue $blue 5.50 | Out-Null

    Add-Box $Page 4.10 5.25 1.80 0.90 "状态融合`n队形中心/载荷位姿`n链路质量 q" $paleOrange $orange 5.55 | Out-Null
    Add-Box $Page 6.55 5.25 1.80 0.90 "4WS 局部路径`nX_L,Y_L,psi_L`nv_ref,kappa_ref" $paleOrange $orange 5.55 | Out-Null
    Add-Box $Page 9.00 5.25 1.80 0.90 "角色与曲率调度`nleader/role schedule`n受力提示" $paleOrange $orange 5.45 | Out-Null
    Add-Box $Page 11.45 5.25 1.80 0.90 "跨层参考/命令通道`n时延、丢包、偏置`n质量权重" $paleTeal $teal 5.35 | Out-Null

    Add-Box $Page 4.10 3.55 1.80 0.90 "车间相对观测`n相对位姿/距离`n连接误差" $paleTeal $teal 5.55 | Out-Null
    Add-Box $Page 6.55 3.55 1.80 0.90 "延迟补偿一致性`n远端状态预测`n质量加权融合" $paleTeal $teal 5.45 | Out-Null
    Add-Box $Page 9.00 3.55 1.80 0.90 "Koopman-MPC`n跟踪+连接+受力代价`n输入/状态约束" $paleGreen $green 5.35 | Out-Null
    Add-Box $Page 11.45 3.55 1.80 0.90 "车辆执行层`na_x,delta_f,delta_r`nu_act" $paleGreen $green 5.55 | Out-Null

    Add-Box $Page 4.10 1.85 1.80 0.90 "残差诊断（FDI）`nr_i/state mismatch`nfault flag" $paleRose $rose 5.45 | Out-Null
    Add-Box $Page 6.55 1.85 1.80 0.90 "容错控制（FTC）`n角色重分配`n命令修复" $paleRose $rose 5.55 | Out-Null
    Add-Box $Page 9.00 1.85 1.80 0.90 "安全滤波（PPC）`n误差边界收紧`n货物受力保护" $paleRose $rose 5.35 | Out-Null
    Add-Box $Page 11.45 1.85 1.80 0.90 "证书/回退`nLyapunov 裕度`nISS/UUB 日志" $palePurple $purple 5.35 | Out-Null

    foreach ($y in @(6.95, 5.25, 3.55, 1.85)) {
        $c = if ($y -eq 6.95) { $blue } elseif ($y -eq 5.25) { $orange } elseif ($y -eq 3.55) { $teal } else { $rose }
        Add-Line $Page 5.00 $y 5.65 $y $c $true $false 0.95 "" | Out-Null
        Add-Line $Page 7.45 $y 8.10 $y $c $true $false 0.95 "" | Out-Null
        Add-Line $Page 9.90 $y 10.55 $y $c $true $false 0.95 "" | Out-Null
    }

    Add-PathLine $Page @(@(6.55,6.50),@(6.55,6.04),@(9.00,6.04),@(9.00,4.00)) $blue $true 0.80 "模型/算子"
    Add-PathLine $Page @(@(11.45,4.80),@(11.45,4.18),@(10.25,4.18),@(10.25,3.98)) $orange $true 0.80 "参考/命令"
    Add-PathLine $Page @(@(9.00,3.10),@(9.00,2.72),@(8.70,2.72),@(8.70,2.30)) $rose $true 0.80 "候选控制+残差"
    Add-PathLine $Page @(@(9.95,1.85),@(10.35,1.85),@(10.35,3.10),@(11.05,3.10)) $green $true 0.85 "安全控制"
    Add-PathLine $Page @(@(11.45,3.10),@(11.45,2.72),@(12.75,2.72),@(12.75,5.25),@(12.35,5.25)) $teal $true 0.75 "反馈/重规划"
    Add-PathLine $Page @(@(11.45,1.40),@(11.45,1.10),@(4.10,1.10),@(4.10,1.40)) $purple $true 0.70 "日志证据"

    Add-ReviewLegend $Page 14.05 1.00
    Add-TextBox $Page 8.0 0.24 14.8 0.25 "图意：框架图只保留各层核心模块；安全层同时接收下层候选控制和系统残差，输出安全控制、回退决策和证据日志，不再画成独立旁路。" 5.8 $ink $false "1" | Out-Null
}

function Add-NewSignalFlow {
    param($Page)
    Setup-Page $Page "NR-KDCC review-clean control flow"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $green = "RGB(100,145,74)"
    $purple = "RGB(126,104,164)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGreen = "RGB(242,248,238)"
    $palePurple = "RGB(245,242,250)"

    Add-TextBox $Page 8.0 8.60 14.9 0.36 "NR-KDCC 单周期控制流程图" 11.4 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.25 14.8 0.24 "控制器不能直接读取真实故障标签；故障只作用到通信/执行器/车辆系统，FDI 由残差、状态不一致和控制响应推断。" 6.35 $blue $false "1" | Out-Null

    Add-SectionFrame $Page 3.65 6.70 5.60 1.25 "状态感知与模型预测" $blue "RGB(250,252,255)" | Out-Null
    Add-SectionFrame $Page 9.80 6.70 6.10 1.25 "MPC 优化与命令通信" $green "RGB(250,252,255)" | Out-Null
    Add-SectionFrame $Page 7.35 4.45 8.35 1.55 "故障诊断与安全仲裁" $rose "RGB(255,252,252)" | Out-Null
    Add-SectionFrame $Page 12.85 4.45 3.65 1.55 "执行器与车辆系统" $blue "RGB(250,252,255)" | Out-Null

    Add-SignalBlock $Page 1.00 7.05 1.15 0.44 "x_i,q,ref" $paleBlue $blue 5.8 | Out-Null
    Add-SignalBlock $Page 2.35 7.05 1.18 0.44 "观测融合" $paleBlue $blue 5.9 | Out-Null
    Add-SignalBlock $Page 3.85 7.05 1.24 0.44 "Koopman`n提升/预测" $paleBlue $blue 5.2 | Out-Null
    Add-SignalBlock $Page 5.40 7.05 1.24 0.44 "参考调制`n4WS+q" $paleOrange $orange 5.2 | Out-Null

    Add-SignalBlock $Page 7.15 7.05 1.20 0.44 "MPC优化" $paleGreen $green 5.9 | Out-Null
    Add-SignalBlock $Page 8.65 7.05 1.12 0.44 "u_i*" $paleGreen $green 6.2 | Out-Null
    Add-SignalBlock $Page 10.05 7.05 1.24 0.44 "命令通信" $paleTeal $teal 5.9 | Out-Null
    Add-SignalBlock $Page 11.50 7.05 1.10 0.44 "u_recv" $paleTeal $teal 6.1 | Out-Null
    Add-SignalBlock $Page 13.00 7.05 1.28 0.44 "候选控制`nu_c" $paleOrange $orange 5.5 | Out-Null

    Add-SignalBlock $Page 2.35 4.75 1.20 0.44 "残差生成`nr_i" $paleRose $rose 5.5 | Out-Null
    Add-SignalBlock $Page 3.90 4.75 1.20 0.44 "FDI诊断" $paleRose $rose 5.9 | Out-Null
    Add-Diamond $Page 5.35 4.75 0.82 0.58 "fault?" $paleRose $rose | Out-Null
    Add-SignalBlock $Page 6.85 4.75 1.28 0.44 "FTC模式`n角色/命令修复" $paleRose $rose 5.2 | Out-Null
    Add-SignalBlock $Page 8.55 4.75 1.32 0.44 "安全滤波`nPPC guard" $paleRose $rose 5.2 | Out-Null
    Add-Diamond $Page 10.10 4.75 0.82 0.58 "cert?" $palePurple $purple | Out-Null
    Add-SignalBlock $Page 11.70 4.75 1.30 0.44 "执行控制`nu_act" $paleGreen $green 5.5 | Out-Null
    Add-SignalBlock $Page 13.55 4.75 1.28 0.44 "执行器/车辆" $paleBlue $blue 5.7 | Out-Null
    Add-SignalBlock $Page 14.95 5.70 1.12 0.38 "外部故障`n/退化" $paleRose $rose 5.2 | Out-Null

    Add-SignalBlock $Page 9.75 3.25 1.34 0.44 "投影/收紧`nu_safe" $paleRose $rose 5.3 | Out-Null
    Add-SignalBlock $Page 11.55 3.25 1.34 0.44 "货物保护`n降级回退" $paleRose $rose 5.3 | Out-Null

    $bus = $Page.DrawRectangle(1.20, 1.24, 14.80, 1.86)
    $bus.Text = "monitoring / logging bus：轨迹误差、连接误差、连接利用率、载荷力、证书裕度、触发时刻"
    Set-BaseStyle $bus "RGB(248,250,251)" $ink $ink 0.95 6.0 $false "1"
    Set-CellFormula $bus "FillTransparency" "6%"

    Add-Line $Page 1.58 7.05 1.76 7.05 $blue $true $false 0.95 "" | Out-Null
    Add-Line $Page 2.94 7.05 3.23 7.05 $blue $true $false 0.95 "" | Out-Null
    Add-Line $Page 4.47 7.05 4.78 7.05 $orange $true $false 0.95 "" | Out-Null
    Add-Line $Page 6.02 7.05 6.55 7.05 $green $true $false 0.95 "" | Out-Null
    Add-Line $Page 7.75 7.05 8.09 7.05 $green $true $false 0.95 "" | Out-Null
    Add-Line $Page 9.21 7.05 9.43 7.05 $teal $true $false 0.95 "" | Out-Null
    Add-Line $Page 10.67 7.05 10.95 7.05 $teal $true $false 0.95 "" | Out-Null
    Add-Line $Page 12.05 7.05 12.36 7.05 $orange $true $false 0.95 "" | Out-Null

    Add-PathLine $Page @(@(13.00,6.83),@(13.00,5.35),@(8.55,5.35),@(8.55,4.97)) $orange $true 0.85 "候选控制"
    Add-Line $Page 2.95 4.75 3.30 4.75 $rose $true $false 0.95 "" | Out-Null
    Add-Line $Page 4.50 4.75 4.94 4.75 $rose $true $false 0.95 "" | Out-Null
    Add-Line $Page 5.76 4.75 6.21 4.75 $rose $true $false 0.95 "yes" | Out-Null
    Add-PathLine $Page @(@(5.35,4.46),@(5.35,4.02),@(8.55,4.02),@(8.55,4.53)) $green $true 0.80 "no"
    Add-Line $Page 7.49 4.75 7.89 4.75 $rose $true $false 0.95 "" | Out-Null
    Add-Line $Page 9.21 4.75 9.69 4.75 $purple $true $false 0.95 "" | Out-Null

    Add-Line $Page 10.51 4.75 11.05 4.75 $green $true $false 0.95 "pass" | Out-Null
    Add-PathLine $Page @(@(10.10,4.46),@(10.10,3.72),@(9.75,3.72),@(9.75,3.47)) $rose $true 0.85 "fail"
    Add-Line $Page 10.42 3.25 10.88 3.25 $rose $true $false 0.95 "" | Out-Null
    Add-PathLine $Page @(@(11.55,3.47),@(11.55,4.18),@(11.70,4.18),@(11.70,4.53)) $rose $true 0.85 "fallback"
    Add-Line $Page 12.35 4.75 12.91 4.75 $blue $true $false 0.95 "" | Out-Null

    Add-PathLine $Page @(@(14.95,5.51),@(14.95,4.75),@(14.19,4.75)) $rose $true 0.80 "作用到 plant"
    Add-PathLine $Page @(@(13.55,4.53),@(13.55,2.18),@(2.35,2.18),@(2.35,4.53)) $rose $true 0.75 "响应/残差"
    Add-PathLine $Page @(@(13.55,4.53),@(13.55,1.86)) $ink $true 0.70 "log"
    Add-PathLine $Page @(@(7.15,6.83),@(7.15,6.18),@(3.85,6.18),@(3.85,6.83)) $blue $true 0.70 "预测误差反馈"
    Add-PathLine $Page @(@(8.00,1.86),@(8.00,2.42),@(10.10,2.42),@(10.10,4.46)) $purple $true 0.70 "证书裕度"
    Add-PathLine $Page @(@(5.00,1.86),@(5.00,2.66),@(5.95,2.66),@(5.95,6.55),@(5.40,6.55),@(5.40,6.83)) $orange $true 0.70 "重规划指标"

    Add-ReviewLegend $Page 2.35 0.68
    Add-TextBox $Page 8.0 0.22 14.8 0.25 "图意：流程图按 u_i* -> u_recv -> u_c -> PPC/cert -> u_act 的顺序表达。故障不进入 FDI 真值口，而是改变执行器/plant 响应，FDI 通过残差闭环触发 FTC 与安全回退。" 5.8 $ink $false "1" | Out-Null
}

function Add-ReviewLegendV2 {
    param($Page, [double]$X, [double]$Y, [string]$Mode = "framework")
    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $orange = "RGB(230,138,53)"
    $teal = "RGB(47,156,149)"
    $green = "RGB(100,145,74)"
    $rose = "RGB(201,93,99)"
    $purple = "RGB(126,104,164)"
    Add-TextBox $Page $X ($Y + 0.48) 2.80 0.20 "图例" 7.0 $ink $true "0" | Out-Null
    Add-TinyChip $Page ($X - 1.05) ($Y + 0.23) 0.18 0.13 "" "RGB(237,243,251)" $blue 4.0 | Out-Null
    Add-TextBox $Page ($X - 0.25) ($Y + 0.23) 1.48 0.17 "蓝：模型/车辆系统" 5.6 $ink $false "0" | Out-Null
    Add-TinyChip $Page ($X - 1.05) ($Y + 0.02) 0.18 0.13 "" "RGB(255,247,235)" $orange 4.0 | Out-Null
    Add-TextBox $Page ($X - 0.21) ($Y + 0.02) 1.56 0.17 "橙：参考/命令链路" 5.6 $ink $false "0" | Out-Null
    Add-TinyChip $Page ($X - 1.05) ($Y - 0.19) 0.18 0.13 "" "RGB(232,247,246)" $teal 4.0 | Out-Null
    Add-TextBox $Page ($X - 0.21) ($Y - 0.19) 1.54 0.17 "青/绿：通信/MPC" 5.6 $ink $false "0" | Out-Null
    Add-TinyChip $Page ($X - 1.05) ($Y - 0.40) 0.18 0.13 "" "RGB(253,239,240)" $rose 4.0 | Out-Null
    Add-TextBox $Page ($X - 0.18) ($Y - 0.40) 1.70 0.17 "红：故障/安全诊断" 5.6 $ink $false "0" | Out-Null
    Add-TinyChip $Page ($X + 1.00) ($Y + 0.23) 0.18 0.13 "" "RGB(245,242,250)" $purple 4.0 | Out-Null
    Add-TextBox $Page ($X + 1.80) ($Y + 0.23) 1.40 0.17 "紫：证书链路" 5.6 $ink $false "0" | Out-Null
    Add-Line $Page ($X + 0.95) ($Y - 0.02) ($X + 1.36) ($Y - 0.02) $blue $true $false 0.8 "" | Out-Null
    Add-TextBox $Page ($X + 2.14) ($Y - 0.02) 1.42 0.17 "实线：数据/控制" 5.6 $ink $false "0" | Out-Null
    Add-Line $Page ($X + 0.95) ($Y - 0.28) ($X + 1.36) ($Y - 0.28) $purple $true $true 0.8 "" | Out-Null
    Add-TextBox $Page ($X + 2.18) ($Y - 0.28) 1.52 0.17 "虚线：反馈/回退" 5.6 $ink $false "0" | Out-Null
}

function Add-NewFramework {
    param($Page)
    Setup-Page $Page "NR-KDCC review-clean framework v2"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $green = "RGB(100,145,74)"
    $purple = "RGB(126,104,164)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGreen = "RGB(242,248,238)"
    $palePurple = "RGB(245,242,250)"

    Add-TextBox $Page 8.0 8.60 14.9 0.34 "网络韧性 Koopman 延迟补偿协同控制（NR-KDCC）总体框架" 11.2 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.27 14.7 0.22 "四层共同构成闭环：离线层给出模型与约束模板，上层给出 4WS 参考，下层执行通信质量感知 MPC，安全层在线诊断、过滤、证书监测和回退。" 6.25 $blue $false "1" | Out-Null

    Add-Lane $Page 8.0 6.95 15.0 1.50 "离线层：数据与 Koopman 模型" $blue $paleBlue | Out-Null
    Add-Lane $Page 8.0 5.25 15.0 1.50 "上层：4WS 协同搬运规划" $orange $paleOrange | Out-Null
    Add-Lane $Page 8.0 3.55 15.0 1.50 "下层：延迟补偿 Koopman-MPC" $teal $paleTeal | Out-Null
    Add-Lane $Page 8.0 1.85 15.0 1.50 "安全层：FDI/FTC、PPC 与证书回退" $rose $paleRose | Out-Null

    Add-CleanKoopmanIcon $Page 2.05 6.92
    Add-Clean4WSIcon $Page 2.05 5.22
    Add-CleanVehicleIcon $Page 2.05 3.55
    Add-CleanSafetyIcon $Page 1.82 1.85

    Add-Box $Page 4.10 6.95 1.80 0.90 "场景数据覆盖`n速度/曲率/通信`n故障与噪声注入" $paleBlue $blue 5.55 | Out-Null
    Add-Box $Page 6.55 6.95 1.80 0.90 "双线性 Koopman`n升维网络 phi_theta`nA,B,N_l 算子" $paleBlue $blue 5.55 | Out-Null
    Add-Box $Page 9.00 6.95 1.80 0.90 "稳定投影（IRSP）`n谱半径约束`n岭回归正则" $palePurple $purple 5.50 | Out-Null
    Add-Box $Page 11.45 6.95 1.80 0.90 "约束/证书模板库`nPPC 边界`n载荷/连接约束" $paleBlue $blue 5.50 | Out-Null

    Add-Box $Page 4.10 5.25 1.80 0.90 "状态融合`n队形中心/载荷位姿`n链路质量 q" $paleOrange $orange 5.55 | Out-Null
    Add-Box $Page 6.55 5.25 1.80 0.90 "4WS 局部路径`nX_L,Y_L,psi_L`nv_ref,kappa_ref" $paleOrange $orange 5.55 | Out-Null
    Add-Box $Page 9.00 5.25 1.80 0.90 "角色与曲率调度`nleader/role schedule`n受力提示" $paleOrange $orange 5.45 | Out-Null
    Add-Box $Page 11.45 5.25 1.80 0.90 "参考/命令通信`n时延、丢包、偏置`n质量权重" $paleTeal $teal 5.45 | Out-Null

    Add-Box $Page 4.10 3.55 1.80 0.90 "车间相对观测`n相对位姿/距离`n连接误差" $paleTeal $teal 5.55 | Out-Null
    Add-Box $Page 6.55 3.55 1.80 0.90 "延迟补偿一致性`n远端状态预测`n质量加权融合" $paleTeal $teal 5.45 | Out-Null
    Add-Box $Page 9.00 3.55 1.80 0.90 "Koopman-MPC`n跟踪+连接+受力代价`n输入/状态约束" $paleGreen $green 5.35 | Out-Null
    Add-Box $Page 11.45 3.55 1.80 0.90 "车辆执行层`na_x,delta_f,delta_r`nu_i^{act}`nstate/response" $paleGreen $green 5.25 | Out-Null

    Add-Box $Page 4.10 1.85 1.80 0.90 "残差诊断（FDI）`nr_i/state mismatch`nfault flag" $paleRose $rose 5.45 | Out-Null
    Add-Box $Page 6.55 1.85 1.80 0.90 "容错控制（FTC）`n角色重分配`n命令修复" $paleRose $rose 5.55 | Out-Null
    Add-Box $Page 9.00 1.85 1.80 0.90 "安全滤波（PPC）`n误差边界收紧`n货物受力保护" $paleRose $rose 5.35 | Out-Null
    Add-Box $Page 11.45 1.85 1.80 0.90 "在线证书监测与回退`nLyapunov 裕度`nISS/UUB 日志" $palePurple $purple 5.25 | Out-Null

    foreach ($y in @(6.95, 5.25, 3.55, 1.85)) {
        $c = if ($y -eq 6.95) { $blue } elseif ($y -eq 5.25) { $orange } elseif ($y -eq 3.55) { $teal } else { $rose }
        Add-Line $Page 5.00 $y 5.65 $y $c $true $false 0.95 "" | Out-Null
        Add-Line $Page 7.45 $y 8.10 $y $c $true $false 0.95 "" | Out-Null
        Add-Line $Page 9.90 $y 10.55 $y $c $true $false 0.95 "" | Out-Null
    }

    Add-PathLine $Page @(@(9.00,6.50),@(9.00,6.22),@(12.80,6.22),@(12.80,3.96),@(9.90,3.96),@(9.90,3.55)) $blue $true 0.78 "模型/算子"
    Add-PathLine $Page @(@(11.45,4.80),@(11.45,4.22),@(10.10,4.22),@(10.10,3.98)) $orange $true 0.82 "ref/cmd"
    Add-PathLine $Page @(@(9.00,3.10),@(9.00,2.55),@(9.00,2.30)) $green $true 0.82 "候选控制"
    Add-PathLine $Page @(@(11.45,3.10),@(11.45,2.62),@(4.10,2.62),@(4.10,2.30)) $rose $true 0.72 "状态残差/响应误差"
    Add-PathLine $Page @(@(9.95,1.85),@(10.34,1.85),@(10.34,3.10),@(11.05,3.10)) $green $true 0.82 "安全控制"
    Add-PathLine $Page @(@(11.45,3.10),@(11.45,2.76),@(12.70,2.76),@(12.70,5.25),@(12.35,5.25)) $teal $true 0.75 "feedback/replan"
    Add-PathLine $Page @(@(2.66,1.85),@(2.92,1.85),@(2.92,1.25),@(9.00,1.25),@(9.00,1.40)) $green $true 0.72 "保护信号"

    Add-ReviewLegendV2 $Page 13.05 0.82 "framework"
    Add-TextBox $Page 8.0 0.24 14.6 0.25 "图意：框架图区分候选控制与状态残差两条安全输入；上层到下层为 ref/cmd，下层到上层为 feedback/replan，安全层输出安全控制、回退决策和证据日志。" 5.75 $ink $false "1" | Out-Null
}

function Add-NewSignalFlow {
    param($Page)
    Setup-Page $Page "NR-KDCC review-clean control flow v2"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $green = "RGB(100,145,74)"
    $purple = "RGB(126,104,164)"
    $paleBlue = "RGB(237,243,251)"
    $paleTeal = "RGB(232,247,246)"
    $paleOrange = "RGB(255,247,235)"
    $paleRose = "RGB(253,239,240)"
    $paleGreen = "RGB(242,248,238)"
    $palePurple = "RGB(245,242,250)"

    Add-TextBox $Page 8.0 8.60 14.9 0.34 "NR-KDCC 单周期控制流程图" 11.2 $ink $true "1" | Out-Null
    Add-TextBox $Page 8.0 8.27 14.8 0.22 "主链按 u_i^\star -> u_i^{recv} -> u_i^c -> PPC guard -> cert? -> selector -> u_i^{act} 展开；外部故障只改变 actuator/plant 响应，FDI 由残差闭环推断。" 6.05 $blue $false "1" | Out-Null

    Add-TextBox $Page 2.75 7.58 3.90 0.18 "状态感知与 Koopman 预测" 6.0 $blue $true "1" | Out-Null
    Add-TextBox $Page 7.25 7.58 4.60 0.18 "MPC 优化与通信接收" 6.0 $green $true "1" | Out-Null
    Add-TextBox $Page 12.45 7.58 4.40 0.18 "安全过滤、证书检查与执行" 6.0 $rose $true "1" | Out-Null

    $y = 6.72
    Add-SignalBlock $Page 0.70 $y 0.98 0.42 "x_i, q_i^c, r_ref" $paleBlue $blue 5.0 | Out-Null
    Add-SignalBlock $Page 1.72 $y 0.92 0.42 "观测融合" $paleBlue $blue 5.5 | Out-Null
    Add-SignalBlock $Page 2.84 $y 1.00 0.42 "Koopman`n预测" $paleBlue $blue 5.0 | Out-Null
    Add-SignalBlock $Page 3.98 $y 1.08 0.42 "4WS参考生成`n质量门控" $paleOrange $orange 4.9 | Out-Null
    Add-SignalBlock $Page 5.10 $y 0.92 0.42 "MPC优化" $paleGreen $green 5.5 | Out-Null
    Add-SignalBlock $Page 6.13 $y 0.86 0.42 "u_i^\star" $paleGreen $green 5.0 | Out-Null
    Add-SignalBlock $Page 7.13 $y 0.92 0.42 "命令通信" $paleTeal $teal 5.4 | Out-Null
    Add-SignalBlock $Page 8.13 $y 0.88 0.42 "u_i^{recv}" $paleTeal $teal 4.9 | Out-Null
    Add-SignalBlock $Page 9.15 $y 0.92 0.42 "候选控制`nu_i^c" $paleOrange $orange 5.0 | Out-Null
    Add-SignalBlock $Page 10.28 $y 1.00 0.42 "安全滤波`nPPC guard" $paleRose $rose 5.0 | Out-Null
    Add-Diamond $Page 11.42 $y 0.70 0.52 "cert?" $palePurple $purple | Out-Null
    Add-SignalBlock $Page 12.48 $y 0.88 0.42 "安全仲裁`nselector" $palePurple $purple 5.0 | Out-Null
    Add-SignalBlock $Page 13.50 $y 0.88 0.42 "u_i^{act}" $paleGreen $green 4.9 | Out-Null
    Add-SignalBlock $Page 14.58 $y 1.00 0.42 "执行器/车辆`nactuator/plant" $paleBlue $blue 4.9 | Out-Null

    $xs = @(1.14,2.22,3.34,4.48,5.56,6.51,7.59,8.52,9.61,10.78,11.77,12.92,13.89)
    foreach ($i in 0..12) {
        $color = if ($i -le 2) { $blue } elseif ($i -le 3) { $orange } elseif ($i -le 5) { $green } elseif ($i -le 7) { $teal } elseif ($i -eq 8) { $orange } elseif ($i -le 10) { $rose } else { $green }
        Add-Line $Page $xs[$i] $y ($xs[$i] + 0.28) $y $color $true $false 0.95 "" | Out-Null
    }

    Add-SignalBlock $Page 14.58 7.58 1.06 0.36 "外部故障/退化" $paleRose $rose 5.1 | Out-Null
    Add-Line $Page 14.58 7.40 14.58 6.94 $rose $true $true 0.85 "作用于 actuator/plant" | Out-Null

    Add-SignalBlock $Page 1.45 4.80 1.05 0.42 "残差生成`nr_i" $paleRose $rose 5.2 | Out-Null
    Add-SignalBlock $Page 2.70 4.80 0.95 0.42 "FDI诊断" $paleRose $rose 5.4 | Out-Null
    Add-Diamond $Page 3.88 4.80 0.70 0.52 "fault?" $paleRose $rose | Out-Null
    Add-SignalBlock $Page 5.10 4.80 1.24 0.42 "FTC命令修复`n/约束修正" $paleRose $rose 4.8 | Out-Null
    Add-SignalBlock $Page 11.42 4.80 1.08 0.42 "投影/收紧`nu_i^{safe}" $paleRose $rose 4.8 | Out-Null
    Add-SignalBlock $Page 12.70 4.80 1.08 0.42 "受力超限`nfallback" $paleRose $rose 4.8 | Out-Null

    Add-Line $Page 1.98 4.80 2.22 4.80 $rose $true $false 0.95 "" | Out-Null
    Add-Line $Page 3.18 4.80 3.53 4.80 $rose $true $false 0.95 "" | Out-Null
    Add-Line $Page 4.23 4.80 4.57 4.80 $rose $true $false 0.95 "" | Out-Null
    Add-TextBox $Page 4.42 5.02 0.34 0.14 "yes" 5.0 $rose $false "1" | Out-Null
    Add-PathLine $Page @(@(5.10,5.02),@(5.10,6.51)) $rose $true 0.82 "约束/命令修正"
    Add-PathLine $Page @(@(3.88,4.54),@(3.88,4.25),@(10.28,4.25),@(10.28,6.51)) $green $true 0.78 "no"

    Add-PathLine $Page @(@(11.42,6.46),@(11.42,5.78),@(11.42,5.02)) $rose $true 0.80 "fail"
    Add-PathLine $Page @(@(11.42,5.02),@(11.42,5.54),@(12.48,5.54),@(12.48,6.51)) $green $true 0.82 "feasible u_i^{safe}"
    Add-Line $Page 11.96 4.80 12.16 4.80 $rose $true $true 0.82 "infeasible/force" | Out-Null
    Add-PathLine $Page @(@(12.70,5.02),@(12.70,5.82),@(12.48,5.82),@(12.48,6.51)) $rose $true 0.82 "fallback"
    Add-TextBox $Page 11.98 6.96 0.36 0.14 "pass" 5.0 $green $false "1" | Out-Null

    $bus = $Page.DrawRectangle(1.45, 1.34, 14.55, 1.90)
    $bus.Text = "monitoring / logging bus: trajectory / connection / force / certificate / timing logs"
    Set-BaseStyle $bus "RGB(248,250,251)" $ink $ink 0.95 6.8 $false "1"
    Set-CellFormula $bus "FillTransparency" "6%"

    Add-PathLine $Page @(@(14.58,6.51),@(14.58,2.05),@(1.45,2.05),@(1.45,4.58)) $rose $true 0.72 "response/residual"
    Add-PathLine $Page @(@(14.58,6.51),@(14.58,1.90)) $ink $true 0.65 "log"
    Add-PathLine $Page @(@(2.84,6.51),@(2.84,5.34),@(1.45,5.34),@(1.45,5.02)) $blue $true 0.68 "predicted response"
    Add-PathLine $Page @(@(11.42,6.46),@(11.42,2.58),@(7.90,2.58),@(7.90,1.90)) $purple $true 0.70 "certificate margin"
    Add-ReviewLegendV2 $Page 2.50 0.62 "flow"
    Add-TextBox $Page 8.0 0.18 14.6 0.24 "图意：u_i^c 是接收后候选控制；u_i^{safe} 可行时直接进 selector，不可行或受力超限才触发 fallback；残差由预测响应和实际响应对照得到。" 5.60 $ink $false "1" | Out-Null
}

function Add-HighlightLabel {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Text, [double]$FontSize = 9.0)
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = $Text
    Set-BaseStyle $s "RGB(255,250,62)" "RGB(238,116,43)" "RGB(0,35,145)" 0.95 $FontSize $true "1"
    Set-CellFormula $s "Rounding" "0.00 in"
    return $s
}

function Add-ReferencePanel {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Fill, [string]$Line)
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = ""
    Set-CellFormula $s "FillForegnd" $Fill
    Set-CellFormula $s "FillTransparency" "4%"
    Set-CellFormula $s "LineColor" $Line
    Set-CellFormula $s "LineWeight" "2.0 pt"
    Set-CellFormula $s "Rounding" "0.16 in"
    return $s
}

function Add-OperatorBlock {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Text, [string]$Fill, [string]$Line, [double]$Angle = 0)
    $s = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $s.Text = $Text
    Set-BaseStyle $s $Fill $Line "RGB(37,54,79)" 1.15 9.0 $true "1"
    Set-CellFormula $s "Rounding" "0.08 in"
    if ([Math]::Abs($Angle) -gt 1e-9) {
        Set-CellFormula $s "Angle" ("{0} deg" -f $Angle)
        Set-CellFormula $s "TxtAngle" ("{0} deg" -f (-1 * $Angle))
    }
    return $s
}

function Add-SumNode {
    param($Page, [double]$X, [double]$Y, [string]$Text = "+")
    $s = $Page.DrawOval($X - 0.18, $Y - 0.18, $X + 0.18, $Y + 0.18)
    $s.Text = $Text
    Set-BaseStyle $s "RGB(255,255,255)" "RGB(37,54,79)" "RGB(37,54,79)" 1.1 8.5 $true "1"
    return $s
}

function Add-CoopTransportSketch {
    param($Page, [double]$X, [double]$Y, [double]$W, [double]$H, [string]$Caption)
    $box = $Page.DrawRectangle($X - $W / 2, $Y - $H / 2, $X + $W / 2, $Y + $H / 2)
    $box.Text = ""
    Set-BaseStyle $box "RGB(255,255,255)" "RGB(128,130,133)" "RGB(37,54,79)" 1.6 6.0 $false "1"
    Set-CellFormula $box "Rounding" "0.08 in"
    $payload = $Page.DrawRectangle($X - $W * 0.27, $Y - $H * 0.07, $X + $W * 0.27, $Y + $H * 0.07)
    $payload.Text = "load"
    Set-BaseStyle $payload "RGB(244,241,251)" "RGB(126,104,164)" "RGB(37,54,79)" 0.65 5.0 $false "1"
    $vehicles = @(
        @{X=$X-$W*0.32;Y=$Y+$H*0.28;A=-20;L="V1"},
        @{X=$X+$W*0.32;Y=$Y+$H*0.28;A=20;L="V2"},
        @{X=$X-$W*0.32;Y=$Y-$H*0.28;A=20;L="V3"},
        @{X=$X+$W*0.32;Y=$Y-$H*0.28;A=-20;L="V4"}
    )
    foreach ($v in $vehicles) {
        Add-VehicleGlyph $Page $v.X $v.Y "RGB(226,72,88)" 0.58 $v.A | Out-Null
        Add-Line $Page $v.X $v.Y $X $Y "RGB(47,156,149)" $false $false 0.55 "" | Out-Null
    }
    Add-TextBox $Page $X ($Y - $H / 2 - 0.18) ($W + 0.18) 0.20 $Caption 7.0 "RGB(37,54,79)" $false "1" | Out-Null
}

function Add-NewSignalFlow {
    param($Page)
    Setup-Page $Page "NR-KDCC reference-style closed-loop flow"

    $ink = "RGB(37,54,79)"
    $blue = "RGB(65,105,165)"
    $teal = "RGB(47,156,149)"
    $orange = "RGB(230,138,53)"
    $rose = "RGB(201,93,99)"
    $green = "RGB(82,140,76)"
    $purple = "RGB(126,104,164)"
    $gray = "RGB(128,130,133)"
    $paleYellow = "RGB(255,253,214)"
    $paleGreen = "RGB(223,239,216)"
    $paleBlue = "RGB(226,241,250)"
    $paleRose = "RGB(253,239,240)"
    $palePurple = "RGB(246,242,251)"

    Add-HighlightLabel $Page 2.40 8.50 3.95 0.34 "NR-KDCC 嵌入式闭环控制流程" 8.8 | Out-Null

    Add-CoopTransportSketch $Page 1.72 6.78 2.25 1.45 "Nominal cooperative transport"
    Add-Line $Page 2.92 6.78 3.60 6.78 "RGB(60,145,205)" $true $false 3.0 "" | Out-Null
    Add-TextBox $Page 3.26 6.35 1.20 0.34 "input-output`ndataset" 7.0 $ink $false "1" | Out-Null

    Add-HighlightLabel $Page 4.92 8.18 1.35 0.28 "离线训练模块" 7.0 | Out-Null
    Add-HighlightLabel $Page 6.42 8.10 2.25 0.30 "Offline training block" 8.0 | Out-Null
    Add-ReferencePanel $Page 8.00 6.92 8.15 1.50 $paleYellow $gray | Out-Null
    Add-TextBox $Page 8.00 6.22 5.80 0.24 "Nominal bilinear Koopman learning with IRSP projection" 7.0 $ink $false "1" | Out-Null
    Add-TextBox $Page 4.42 6.92 0.55 0.20 "x_k,u_k" 6.8 $ink $false "1" | Out-Null
    Add-Line $Page 4.72 6.92 5.05 6.92 $ink $true $false 0.95 "" | Out-Null
    Add-OperatorBlock $Page 5.55 6.92 0.72 0.72 "phi" $paleBlue $blue -8 | Out-Null
    Add-TextBox $Page 5.95 7.12 0.55 0.18 "z_k" 6.0 $ink $false "1" | Out-Null
    Add-Line $Page 5.92 6.92 6.28 6.92 $ink $true $false 0.95 "" | Out-Null
    Add-OperatorBlock $Page 6.95 6.92 0.92 0.72 "A,B,N_l" "RGB(218,145,194)" "RGB(83,43,78)" 0 | Out-Null
    Add-TextBox $Page 7.55 7.12 0.62 0.18 "z_{k+1}" 6.0 $ink $false "1" | Out-Null
    Add-Line $Page 7.42 6.92 7.78 6.92 $ink $true $false 0.95 "" | Out-Null
    Add-OperatorBlock $Page 8.38 6.92 0.72 0.72 "C" "RGB(127,143,204)" "RGB(55,62,120)" 8 | Out-Null
    Add-TextBox $Page 8.94 7.12 0.74 0.18 "xhat_{k+1}" 5.8 $ink $false "1" | Out-Null
    Add-Line $Page 8.74 6.92 9.42 6.92 $ink $true $false 0.95 "" | Out-Null
    Add-SignalBlock $Page 10.25 6.92 1.25 0.42 "训练损失`nrollout验证" "RGB(255,255,255)" $blue 5.4 | Out-Null

    Add-Line $Page 8.00 6.08 8.00 5.46 "RGB(60,145,205)" $true $false 3.0 "" | Out-Null
    Add-TextBox $Page 9.32 5.70 2.58 0.42 "model matrices (A,B,N_l,C)`nlifting function phi, PPC/ISS bounds" 7.2 $ink $false "0" | Out-Null

    Add-HighlightLabel $Page 1.62 5.38 1.58 0.28 "在线闭环模块" 7.0 | Out-Null
    Add-HighlightLabel $Page 3.85 5.22 2.65 0.30 "Online adaptation/control block" 8.0 | Out-Null
    Add-ReferencePanel $Page 8.00 3.05 14.45 4.45 $paleGreen $gray | Out-Null

    Add-SignalBlock $Page 1.80 3.72 1.10 0.42 "lifting`nphi" $paleBlue $blue 6.0 | Out-Null
    Add-TextBox $Page 0.80 3.72 0.60 0.18 "x_{i,k}^{obs}" 5.8 $ink $false "1" | Out-Null
    Add-Line $Page 1.10 3.72 1.33 3.72 $ink $true $false 0.85 "" | Out-Null
    Add-TextBox $Page 2.48 3.72 0.70 0.18 "z_{i,k}^{obs}" 5.8 $ink $false "1" | Out-Null
    Add-Line $Page 2.33 3.72 2.90 3.72 $ink $true $false 0.85 "" | Out-Null

    Add-SumNode $Page 3.22 3.72 "+" | Out-Null
    Add-TextBox $Page 3.20 3.20 0.90 0.28 "sensor`nnoise" 6.2 $ink $false "1" | Out-Null
    Add-Line $Page 3.22 3.18 3.22 3.54 $ink $true $false 0.85 "" | Out-Null
    Add-Line $Page 3.40 3.72 4.02 3.72 $ink $true $false 0.85 "x_{i,k}^{obs}" | Out-Null

    Add-CoopTransportSketch $Page 5.00 3.62 2.20 1.32 "System with delay/fault/noise"
    Add-SumNode $Page 6.60 3.72 "+" | Out-Null
    Add-TextBox $Page 6.58 3.18 1.10 0.30 "input`ndisturbance" 6.2 $ink $false "1" | Out-Null
    Add-Line $Page 6.60 3.18 6.60 3.54 $ink $true $false 0.85 "" | Out-Null
    Add-Line $Page 6.42 3.72 6.05 3.72 $ink $true $false 0.85 "" | Out-Null

    Add-SignalBlock $Page 8.00 3.72 1.50 0.60 "Delay-compensated`nKoopman-MPC" "RGB(255,255,255)" $green 6.2 | Out-Null
    Add-SignalBlock $Page 9.95 3.72 1.34 0.60 "PPC/cert`nselector" "RGB(255,255,255)" $purple 6.2 | Out-Null
    Add-SignalBlock $Page 11.75 3.72 1.24 0.60 "u_i^{act}" "RGB(255,255,255)" $green 6.4 | Out-Null
    Add-Line $Page 8.75 3.72 9.28 3.72 $green $true $false 1.0 "u_i^c" | Out-Null
    Add-Line $Page 10.62 3.72 11.13 3.72 $green $true $false 1.0 "" | Out-Null
    Add-Line $Page 11.13 3.72 6.78 3.72 $ink $true $false 0.95 "u_k" | Out-Null

    Add-SignalBlock $Page 2.12 4.78 2.20 0.82 "FDI/FTC online module`nr_i, q_i^c -> fault flag`nconstraint/command repair" "RGB(255,255,255)" $rose 5.8 | Out-Null
    Add-SignalBlock $Page 9.10 4.82 2.00 0.82 "Update model / bounds`nA <- A + Delta A`nB <- B + Delta B" "RGB(255,255,255)" $green 5.8 | Out-Null
    Add-Line $Page 3.22 4.78 8.10 4.82 $ink $true $false 1.0 "Delta A, Delta B, Delta constraints" | Out-Null
    Add-PathLine $Page @(@(9.10,4.41),@(9.10,4.08),@(8.00,4.08),@(8.00,4.02)) $green $true 0.95 "A,B,N_l,bounds"
    Add-PathLine $Page @(@(2.12,4.36),@(2.12,4.12),@(8.00,4.12),@(8.00,4.02)) $rose $true 0.85 "FTC flag"

    Add-PathLine $Page @(@(5.00,2.96),@(5.00,2.20),@(1.80,2.20),@(1.80,3.51)) $ink $true 0.85 "x_{i,k+1}^{obs}"
    Add-PathLine $Page @(@(5.00,4.28),@(5.00,4.95),@(2.12,4.95),@(2.12,5.19)) $rose $true 0.85 "response residual"
    Add-PathLine $Page @(@(2.84,6.56),@(2.84,5.60),@(1.10,5.60),@(1.10,4.78)) $blue $true 0.75 "predicted response"
    Add-PathLine $Page @(@(9.95,4.02),@(9.95,4.34),@(9.10,4.34),@(9.10,4.41)) $purple $true 0.75 "certificate margin"
    Add-PathLine $Page @(@(8.00,6.08),@(8.00,5.24),@(9.10,5.24),@(9.10,5.23)) $blue $true 0.80 "offline model"
    Add-Line $Page 8.00 3.42 8.00 3.08 $orange $true $false 0.85 "r_ref" | Out-Null
    Add-TextBox $Page 8.00 2.88 1.55 0.24 "4WS reference + quality gate" 5.8 $orange $false "1" | Out-Null

    Add-TextBox $Page 8.00 0.34 14.4 0.24 "图意：该图按参考样式展示离线 Koopman 训练 -> 在线模型/约束修正 -> MPC/PPC/selector 闭环。残差由预测响应与实际响应对照得到，故障不作为 FDI 的直接输入。" 6.0 $ink $false "1" | Out-Null
}

function Draw-Framework {
    param($Page)
    Add-NewFramework $Page
}

function Draw-Flow {
    param($Page)
    Add-NewSignalFlow $Page
}

function Export-Page {
    param($Page, [string]$BasePath)
    try { $Page.Export("$BasePath.png") } catch {}
    try { $Page.Export("$BasePath.svg") } catch {}
    try { $Page.Export("$BasePath.pdf") } catch {}
}

New-OutputDir $OutputDir

$visio = $null
try {
    $visio = New-Object -ComObject Visio.Application
    $visio.Visible = $false
    try { $visio.AlertResponse = 7 } catch {}

    $combinedPath = Join-Path $OutputDir "NRKDCC_nature_framework_flow_route_visio_editable.vsdx"
    $doc = $visio.Documents.Add("")
    $page1 = $visio.ActivePage
    Draw-Framework $page1
    $page2 = $doc.Pages.Add()
    Draw-Flow $page2
    $page3 = $doc.Pages.Add()
    Draw-TechnicalRoute $page3
    $doc.SaveAs($combinedPath)
    Export-Page $page1 (Join-Path $OutputDir "NRKDCC_framework_nature_style")
    Export-Page $page2 (Join-Path $OutputDir "NRKDCC_control_flow_nature_style")
    Export-Page $page3 (Join-Path $OutputDir "NRKDCC_technical_route_reference_style")
    $doc.Close()

    New-VisioDoc $visio (Join-Path $OutputDir "NRKDCC_framework_nature_style_editable.vsdx") ${function:Draw-Framework}
    New-VisioDoc $visio (Join-Path $OutputDir "NRKDCC_control_flow_nature_style_editable.vsdx") ${function:Draw-Flow}
    New-VisioDoc $visio (Join-Path $OutputDir "NRKDCC_technical_route_reference_style_editable.vsdx") ${function:Draw-TechnicalRoute}

    $readme = @"
# NR-KDCC review-clean Visio figures

生成文件：

- NRKDCC_nature_framework_flow_route_visio_editable.vsdx：三页 Visio 源文件，第 1 页为四层总体框架图，第 2 页为信号流式控制流程图，第 3 页为论文技术路线/论证链图。
- NRKDCC_framework_nature_style_editable.vsdx：单独的总体框架图 Visio 源文件。
- NRKDCC_control_flow_nature_style_editable.vsdx：单独的在线控制流程图 Visio 源文件。
- NRKDCC_technical_route_reference_style_editable.vsdx：单独的论文技术路线图 Visio 源文件。
- NRKDCC_framework_nature_style.png / .svg：总体框架图预览与投稿用矢量导出。
- NRKDCC_control_flow_nature_style.png / .svg：控制流程图预览与投稿用矢量导出。
- NRKDCC_technical_route_reference_style.png / .svg：技术路线图预览与投稿用矢量导出。

编辑说明：

- .vsdx 文件中的模块框、箭头、标签和车辆--载荷示意均为 Visio 原生形状，可直接移动、改色、改文字。
- 所有包含多个要点的模块均采用“外层模块框 + 内部小要点框”结构；内部每个小框也是 Visio 原生形状，可单独编辑。
- 当前框架图按离线层、上层、下层、安全层组织，并包含四车 4WS 协同搬运示意与单车动力学示意。
- 当前框架图删除右侧大空总线，改为四层之间的短反馈/回退箭头，并加入图内颜色与线型图例。
- 当前框架图左下安全层示意不再使用外层截图式边框，且将原来的安全控制圆形节点改为“保护信号融合”，并接入安全滤波链路，避免和下层执行控制混淆。
- 当前控制流程图已按参考图重画为“上方离线训练块 + 下方在线适应/闭环控制块”的结构。
- 离线训练块展示 nominal system 数据生成、lifting phi、双线性 Koopman 算子 A,B,N_l、输出矩阵 C、训练/rollout 验证，并向在线块下发模型矩阵、lifting 函数和 PPC/ISS 边界。
- 在线闭环块展示 lifting、系统响应、传感器噪声、输入扰动、FDI/FTC 在线模块、模型/约束更新、delay-compensated Koopman-MPC、PPC/cert selector 与执行控制 u_i^{act}。
- 残差通道同时接收 Koopman predicted response 与 actuator/plant response，避免残差来源不明；故障不作为 FDI 的直接输入。
- 框架图中候选控制采用绿色正常控制链路，红色仅表示故障、残差和安全诊断链路。
- 外部故障/退化只作用到通信/执行器/车辆系统，FDI 仅通过 residual/state mismatch/control response 推断故障，避免“使用真实故障标签”的误解。
- 底部反馈合并为 monitoring/logging bus，文本压缩为 trajectory / connection / force / certificate / timing logs，只保留必要反馈线；跨层线、反馈线和回退线尽量绕开模块块体，同一条折线只在末尾保留箭头。
- 第 3 页按照用户参考图的“虚线大章节块 + 小模块框 + 方向箭头”组织，用于展示论文逻辑而不是控制时序。
- 当前风格采用 Nature 控制类论文常见的浅底、少色、分层机制、实线主链路和虚线跨层/保护回路。
- 配色避免大面积纯黑：深蓝灰用于文字，蓝色用于模型/车辆执行，橙色用于上层协调，青色用于通信与感知，玫红用于安全保护。
"@
    Set-Content -LiteralPath (Join-Path $OutputDir "README_zh.md") -Value $readme -Encoding UTF8
    Write-Output "Generated Visio diagrams in: $OutputDir"
} finally {
    if ($visio -ne $null) {
        try { $visio.Quit() } catch {}
        try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($visio) | Out-Null } catch {}
    }
}

