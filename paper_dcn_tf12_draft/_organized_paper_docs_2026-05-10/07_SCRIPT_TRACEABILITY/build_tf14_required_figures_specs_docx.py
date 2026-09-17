from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "paper_dcn_tf12_draft"
OUT_DOCX = OUT_DIR / "tf14_required_figures_experiment_specs_zh_2026-05-08.docx"
SKILL_SCRIPTS = Path(
    r"C:\Users\lj\.codex\plugins\cache\openai-primary-runtime\documents\26.430.10722"
    r"\skills\documents\scripts"
)
sys.path.append(str(SKILL_SCRIPTS))
from table_geometry import apply_table_geometry, column_widths_from_weights  # noqa: E402


ACCENT = RGBColor(20, 83, 112)
MUTED = RGBColor(90, 98, 106)
HEADER_FILL = "DDEFF6"
NOTE_FILL = "F5F7F9"
WARN_FILL = "FFF3CD"


def set_east_asia_font(run, east_asia: str = "Microsoft YaHei", latin: str = "Arial"):
    run.font.name = latin
    run._element.rPr.rFonts.set(qn("w:eastAsia"), east_asia)


def set_style_font(style, size_pt=None, bold=None, color=None):
    style.font.name = "Arial"
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    if size_pt is not None:
        style.font.size = Pt(size_pt)
    if bold is not None:
        style.font.bold = bold
    if color is not None:
        style.font.color.rgb = color


def content_width_dxa(doc: Document) -> int:
    sec = doc.sections[-1]
    return int(sec.page_width.twips - sec.left_margin.twips - sec.right_margin.twips)


def shade_cell(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_text(cell, text: str, *, bold=False, color=None, size=8.2, align=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(1.5)
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    set_east_asia_font(run)
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_para(doc: Document, text: str = "", style: str | None = None, color=None, bold=False):
    p = doc.add_paragraph(style=style)
    if text:
        r = p.add_run(text)
        set_east_asia_font(r)
        r.bold = bold
        if color is not None:
            r.font.color.rgb = color
    return p


def add_bullets(doc: Document, items, size=9.2):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(item)
        set_east_asia_font(r)
        r.font.size = Pt(size)


def add_table(doc: Document, headers, rows, weights, font_size=7.8, header_size=8.2):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0]
    set_repeat_table_header(hdr)
    for idx, h in enumerate(headers):
        shade_cell(hdr.cells[idx], HEADER_FILL)
        set_cell_text(hdr.cells[idx], h, bold=True, color=ACCENT, size=header_size)
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            set_cell_text(cells[idx], str(value), size=font_size)
    total = content_width_dxa(doc)
    widths = column_widths_from_weights(weights, total_width_dxa=total)
    apply_table_geometry(table, widths, table_width_dxa=total, indent_dxa=0)
    doc.add_paragraph()
    return table


def add_note_box(doc: Document, title: str, body: str, fill: str = NOTE_FILL):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    shade_cell(cell, fill)
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(title)
    set_east_asia_font(r)
    r.bold = True
    r.font.color.rgb = ACCENT
    r.font.size = Pt(9.5)
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    r2 = p2.add_run(body)
    set_east_asia_font(r2)
    r2.font.size = Pt(8.8)
    total = content_width_dxa(doc)
    apply_table_geometry(table, [total], table_width_dxa=total, indent_dxa=0)
    doc.add_paragraph()


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r1 = paragraph.add_run("第 ")
    set_east_asia_font(r1)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r2 = paragraph.add_run()
    r2._r.append(fld_begin)
    r2._r.append(instr)
    r2._r.append(fld_end)
    r3 = paragraph.add_run(" 页")
    set_east_asia_font(r3)


def setup_doc() -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width = Inches(11)
    sec.page_height = Inches(8.5)
    sec.top_margin = Inches(0.55)
    sec.bottom_margin = Inches(0.5)
    sec.left_margin = Inches(0.55)
    sec.right_margin = Inches(0.55)

    styles = doc.styles
    set_style_font(styles["Normal"], 9.5)
    styles["Normal"].paragraph_format.line_spacing = 1.08
    styles["Normal"].paragraph_format.space_after = Pt(4)
    set_style_font(styles["Title"], 20, True, ACCENT)
    set_style_font(styles["Subtitle"], 10.5, False, MUTED)
    set_style_font(styles["Heading 1"], 13.5, True, ACCENT)
    set_style_font(styles["Heading 2"], 11.5, True, RGBColor(32, 73, 96))
    for s in ("List Bullet", "List Number"):
        set_style_font(styles[s], 9)
        styles[s].paragraph_format.left_indent = Inches(0.25)
        styles[s].paragraph_format.first_line_indent = Inches(-0.11)
        styles[s].paragraph_format.space_after = Pt(2)

    header = sec.header.paragraphs[0]
    hr = header.add_run("TF14 出图清单与实验规格 | Figure and Experiment Specification")
    set_east_asia_font(hr)
    hr.font.size = Pt(8)
    hr.font.color.rgb = MUTED
    footer = sec.footer.paragraphs[0]
    add_page_number(footer)
    for run in footer.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = MUTED
    return doc


def build_docx() -> None:
    doc = setup_doc()

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("TF14 论文出图清单与实验规格")
    set_east_asia_font(r)
    r.bold = True
    r.font.size = Pt(21)
    r.font.color.rgb = ACCENT

    sub = doc.add_paragraph(style="Subtitle")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = sub.add_run("适用于 Network-Resilient Cooperative Transport Control via Bilinear Koopman Learning and Delay-Compensated Consensus MPC 的中文稿修订")
    set_east_asia_font(sr)

    add_table(
        doc,
        ["字段", "规格"],
        [
            ["文档用途", "把主文、补充材料和待新增实验所需图一次性列清楚，后续绘图脚本、仿真实验和论文排版均按此执行。"],
            ["图件分级", "P0=主文必须有；P1=主文可选/补充材料必须有；P2=补充材料增强证据。"],
            ["当前依据", "tf14_pre.ipynb、tf14_runtime.py、control_files/tf14/*、Stage4-Stage6 已有结果与 figures 目录。"],
            ["核心原则", "每个方法模块至少有一张机制图、一张消融图、一张物理量或安全量支撑图；不能只靠平均 RMSE。"],
        ],
        [1.2, 8.8],
        font_size=8.8,
    )

    add_note_box(
        doc,
        "总判断",
        "现有 Stage5 图可以支撑部分轨迹和误差对比，results/tf14_diagnostics 可以支撑 FDI 与切换证书的机制展示；"
        "但顶刊/一区标准还缺：离线数据覆盖、Koopman 预测精度、多 seed 统计、载荷受力、连接误差、故障类型混淆矩阵、通信质量链路图、实时性 Pareto 和完整消融。"
        "下面清单按这些缺口组织。",
        WARN_FILL,
    )

    doc.add_heading("1. 全局出图规范", level=1)
    add_table(
        doc,
        ["项目", "要求"],
        [
            ["最终格式", "优先导出 PDF/SVG/EPS 矢量图；同时保存 600 dpi PNG 供 Word 检查。热力图或密集轨迹可用 600 dpi PNG/TIFF。"],
            ["尺寸", "单栏：85 mm 宽，高 55-70 mm；双栏：178 mm 宽，高 80-115 mm；机制总览/多面板图建议双栏。"],
            ["字体", "最终英文图使用 Arial 或 Helvetica；轴标签 8-9 pt，刻度 7-8 pt，图例 7.5-8.5 pt；中文内部检查图可用 Microsoft YaHei。"],
            ["线宽/标记", "主线 1.4-1.8 pt，辅助线 0.9-1.1 pt；误差带 alpha=0.18-0.25；采样点 marker 不要铺满全曲线。"],
            ["网格/背景", "白底；主网格 #E6E6E6、线宽 0.5；去掉上/右边框；不要使用深色背景和高饱和渐变。"],
            ["统计显示", "多 seed 曲线用 mean ± 95% CI 或 mean ± SEM；柱状图必须带 error bar；箱线/小提琴图保留散点。图注写 n、seed、场景、故障类型。"],
            ["事件标注", "故障开始用红色竖虚线；检测时刻用橙色虚线；切换时刻用紫色点划线；通信干扰窗口用浅橙透明带；故障窗口用浅红透明带。"],
            ["可复现文件", "每张图必须同时保存 source CSV/NPZ、plot 脚本、config JSON、PDF/PNG；命名为 fig##_slug.* 或 figS##_slug.*。"],
        ],
        [1.25, 8.75],
        font_size=8.3,
    )

    doc.add_heading("2. 统一配色表", level=1)
    add_table(
        doc,
        ["对象", "颜色/线型", "使用场景"],
        [
            ["baseline / AKE", "#6C757D 灰色，实线", "所有基线轨迹、误差、柱状图。灰色避免抢占主方法视觉中心。"],
            ["TF13 known-fault", "#0072B2 蓝色，实线或短虚线", "与上一代方法比较；强调它是强基线而不是反派。"],
            ["TF14 main", "#D55E00 橙红色，实线", "主方法核心曲线；所有主文图中保持一致。"],
            ["TF14 phase-role", "#009E73 绿色，实线", "阶段-角色增强版；只在相关图中出现，避免过度分散。"],
            ["TF14 error-match / all-solve", "#CC79A7 紫色，点划线", "精度-计算时间前沿或 TF13 对齐 preset。"],
            ["No-FDI / No-switch 消融", "#E69F00 黄色橙，虚线", "消融图，避免与主方法橙红混淆。"],
            ["Nominal / Reconfigured / Safe modes", "#0072B2 / #D55E00 / #CC79A7", "模式时间线、背景条、证书图。"],
            ["车辆 V0/V1/V2/V3", "#0072B2 / #D55E00 / #009E73 / #CC79A7", "四车误差、控制输入、轨迹；故障车额外加红色描边或阴影，不改基础色。"],
            ["Fx/Fy/Mz/Norm", "#0072B2 / #D55E00 / #009E73 / #222222", "载荷纵向力、横向力、偏航力矩、合力范数。"],
            ["安全阈值/约束边界", "#B00020 红色虚线", "残差阈值、输入饱和、连接约束、证书失效边界。"],
        ],
        [1.9, 2.3, 5.8],
        font_size=8.0,
    )

    doc.add_heading("3. 出图所需实验总表", level=1)
    add_table(
        doc,
        ["实验编号", "目的", "方法/场景设置", "必须保存变量", "支撑图"],
        [
            [
                "E0 机制绘图",
                "画系统架构、坐标系、控制闭环，不依赖仿真。",
                "使用论文最终模块：车辆模型、Koopman、MPC、通信补偿、FDI、FTC、phase-role、certificate。",
                "无；需保存 editable SVG/PPTX 源文件。",
                "F0-F1。",
            ],
            [
                "E1 离线数据与 Koopman 学习",
                "证明训练数据覆盖控制域，双线性 Koopman 比线性/无稳定投影预测更准。",
                "模型：linear Koopman、bilinear Koopman、bilinear+stable projection；seed >= 5；train/val/test 固定划分。",
                "x,u,z,train_loss,val_loss,one_step_error,multi_step_error,A/B/N norms,spectral_radius。",
                "F2-F3，S1-S4，S16。",
            ],
            [
                "E2 主鲁棒控制对比",
                "证明 TF14 相对 baseline 和 TF13 在多车协同运输中更稳。",
                "方法：baseline/AKE、TF13、TF14 main、TF14 phase-role、TF14 error-match；场景：clean、comm high、single fault、mixed fault/noise；seed 草稿 >=10，投稿 >=20。",
                "time,state,ref,control,team_center,vehicle_error,comm_diag,fault_diag,solve_time,payload_force,connection_error。",
                "F4-F7，F10，F13-F14，S9-S13，S18-S21。",
            ],
            [
                "E3 未知执行器故障诊断-切换闭环",
                "证明未知故障可被检测、辨识、切换并重分配。",
                "故障：ax degrade、steer degrade、dual degrade、severe dual、ramp、intermittent、多车故障；故障车辆和开始时刻随机化；clean/high comm 各跑一组。",
                "residual,EWMA,CUSUM,gamma_delta,gamma_a,fdi_mode,confidence,switch_mode,redistributed_delta/ax,certificate。",
                "F8-F9，F12，S6-S8，S19。",
            ],
            [
                "E4 通信退化与时延补偿",
                "突出 DCN 主题：网络质量变化如何影响一致性、约束收紧和控制降级。",
                "packet loss、delay、jitter、burst dropout、link asymmetry；比较 no-comm-aware、delay-only、quality-consensus、full TF14。",
                "q_global,q_ij,delay,loss,received_age,constraint_tightening,consensus_weight,tracking_error。",
                "F4-F6，S5，S19-S21。",
            ],
            [
                "E5 阶段-角色高曲率实验",
                "证明 phase-role 不是装饰，而是降低弯道载荷/单车峰值误差。",
                "路径：DLC、hairpin、S-curve、窄通道；方法：no phase-role、full phase-role、trim-disabled-by-role、aggressive trim。",
                "phase_label,curvature,delta_trim,ax_trim,role,vehicle_error,yaw_phase,payload_force,connection_error。",
                "F11，S14-S15。",
            ],
            [
                "E6 消融与实时预算",
                "拆分每个模块贡献，展示实时 preset 与全车求解 preset 的精度-计算折中。",
                "Ablation：no bilinear、no stable projection、no comm、no FDI、no FTC、no phase-role、no realtime decimation；runtime：decimation=1/2/5，全车求解 vs leader-first。",
                "rmse_y,rmse_s,max_y,max_s,force_peak,certificate_ok,step_time,solve_time,overrun,vehicles_solved。",
                "F13-F14，S16-S21。",
            ],
        ],
        [0.75, 1.7, 3.0, 3.0, 1.0],
        font_size=7.4,
    )

    doc.add_heading("4. 主文图清单（P0/P1）", level=1)
    main_rows = [
        [
            "F0/P1",
            "Graphical abstract：网络韧性协同运输控制闭环。说明从车辆-载荷系统、网络扰动、Koopman-MPC、FDI/FTC 到证书监控的链条。",
            "E0。无需仿真；用最终模块名，不要出现 tf12/tf13/tf14_pre 这类工程命名。",
            "双栏 178x80 mm；矢量 SVG/PDF；模块色：Koopman 蓝、MPC 深蓝、通信橙、FDI 红、certificate 绿；箭头统一 1.2 pt。",
        ],
        [
            "F1/P0",
            "系统建模图：大地坐标、Frenet 误差坐标、四车载荷连接、单车自行车模型参数。",
            "E0。基于论文模型绘制；标注 X/Y/psi、s/e_y/e_psi、l_f/l_r、C_f/C_r、连接偏置 ell_i。",
            "双栏 178x95 mm；车辆四角用 V0-V3 色；载荷浅灰 #F2F2F2；坐标轴黑色；公式只放关键变量，避免满图文字。",
        ],
        [
            "F2/P0",
            "离线数据覆盖与 Koopman 学习流程：展示训练数据覆盖控制域，并说明升维网络和 ridge 拟合。",
            "E1。输出状态/输入分布、曲率分布、train/val loss、网络结构小图。",
            "双栏多面板；直方图灰蓝；train loss 蓝、val loss 橙；所有状态单位写清楚；图注写样本数、seed、train/test split。",
        ],
        [
            "F3/P0",
            "Koopman 预测精度：linear vs bilinear vs bilinear+stable projection 的 one-step 和 multi-step 误差。",
            "E1。每个模型 >=5 seed；test trajectories 覆盖直线、DLC、hairpin；统计 per-state RMSE 和 rollout RMSE。",
            "2x2 面板；linear 灰、bilinear 蓝、stable bilinear 橙红；multi-step 横轴为 prediction horizon；误差带 95% CI。",
        ],
        [
            "F4/P0",
            "实验场景与扰动定义：DLC/hairpin/S-curve 路径、故障开始、通信退化窗口、车辆/载荷初始位置。",
            "E2-E4。生成统一 scenario map；每个场景同一坐标范围，标注故障窗口和通信窗口。",
            "双栏；路径黑线，参考速度用浅蓝渐变或下方面板；故障窗口浅红，通信窗口浅橙；不要把仿真轨迹和场景定义混在一起。",
        ],
        [
            "F5/P0",
            "主轨迹对比：team center / payload center 轨迹与参考路径，展示 baseline、TF13、TF14 main、TF14 phase-role。",
            "E2。优先选 mixed fault/noise 与 high communication 两个代表场景；完整场景放补充材料。",
            "双栏；参考路径黑虚线；baseline 灰，TF13 蓝，TF14 main 橙红，phase-role 绿；起终点加小标记；坐标单位 m。",
        ],
        [
            "F6/P0",
            "系统跟踪误差与统计：e_y、e_s 时间序列 + 多 seed RMSE/max error 汇总。",
            "E2。每方法每场景 >=10 seed；输出 mean ± CI；同时列 full path rate。",
            "双栏 2x2 或 2x3；时间序列上方标故障/通信窗口；柱状或箱线图不要只画均值；显著性可用星号但需谨慎。",
        ],
        [
            "F7/P0",
            "单车误差与角色均衡：四辆车横向/纵向/航向误差，突出故障车与支持车的误差分担。",
            "E2/E3。必须保存 per-vehicle e_y/e_s/e_psi；故障车随机时按 fault/support 重新聚合。",
            "车辆色固定 V0-V3；故障车加红色半透明背景或红色描边；推荐热力图 + 代表时间序列组合。",
        ],
        [
            "F8/P0",
            "在线 FDI 与执行器效率辨识：残差、EWMA/CUSUM、gamma_delta/gamma_a、故障类型、置信度。",
            "E3。至少展示 dual degrade 和 ramp fault；写出 detection delay、false alarm、classification accuracy。",
            "多面板纵向共享时间轴；阈值红虚线；故障开始/检测/切换三条事件线；模式用底部色带显示。",
        ],
        [
            "F9/P0",
            "切换容错与控制重分配：nominal -> reconfigured -> safe 的模式时间线，控制修正和 redistributed effort。",
            "E3。保存原 MPC 指令、补偿后指令、实际执行、支持车重分配量、输入饱和。",
            "双栏；模式色带：nominal 蓝、reconfigured 橙、safe 紫；delta 与 a_x 分开；饱和边界红虚线。",
        ],
        [
            "F10/P0",
            "载荷受力与连接安全：总合力、Fx、Fy、Mz、连接误差和峰值统计。",
            "E2/E3/E5。若当前仿真未保存 payload force，需要补写记录器；不能用轨迹误差代替载荷力学证据。",
            "Fx 蓝、Fy 橙、Mz 绿、norm 黑；安全阈值红虚线；统计图显示 peak 与 RMS；单位 N/Nm/m 必须清楚。",
        ],
        [
            "F11/P0",
            "阶段-角色调度机制：路径阶段标签、四车 delta/ax trim、yaw phase plane、角色误差差异。",
            "E5。比较 no phase-role 与 phase-role；重点看高曲率段、内外侧车辆和前后角色。",
            "阶段背景：straight 白、entry 浅蓝、core 浅橙、exit 浅绿、transition 浅灰；trim 用车辆色，alpha=0.9。",
        ],
        [
            "F12/P0",
            "Lyapunov 型证书：V_sigma、predicted upper、contraction margin、certificate_ok 与切换时刻。",
            "E3/E6。每个切换模式至少出现一次；统计 certificate_ok ratio 和 min margin。",
            "V 黑、upper 灰虚线、margin 绿/红；certificate_ok 可用底部 0/1 色带；与 F9 可合并成一个机制图。",
        ],
        [
            "F13/P0",
            "模块消融：逐一移除 bilinear、stable projection、comm-aware、FDI、FTC、phase-role、realtime scheduler。",
            "E6。每个消融 >=10 seed；指标包括 RMSE、max error、force peak、certificate_ok、full path rate。",
            "分组柱状/森林图；TF14 full 橙红加粗；坏方向统一向右或向上；不要只报告有利指标。",
        ],
        [
            "F14/P1",
            "实时性 Pareto：误差-计算时间折中，展示 realtime preset、all-vehicle solve、不同 decimation。",
            "E6。横轴 step_mean/solve_mean，纵轴 RMSE_y 或 force_peak；点大小表示 overrun ratio。",
            "散点 + 连线；实时可行区域用浅绿背景；all-solve 紫色；图注明确 Stage6 的精度提升伴随计算时间上升。",
        ],
    ]
    add_table(
        doc,
        ["编号", "图名与目的", "出图实验/数据要求", "规格与配色要求"],
        main_rows,
        [0.75, 3.0, 3.2, 3.0],
        font_size=7.2,
    )

    doc.add_heading("5. 补充材料图清单（P1/P2）", level=1)
    supp_rows = [
        ["S1/P1", "训练数据全状态分布：s,e_y,e_psi,vx,vy,r,delta,a_x,curvature。", "E1；所有训练/测试样本分开画。", "3x3 或 4x3 小面板；train 灰、test 蓝；标出控制约束边界。"],
        ["S2/P1", "Koopman 网络训练曲线：多 seed train/val loss、早停/最终 epoch。", "E1；保存每 epoch loss。", "半对数 y 轴；mean±CI；不要只给一条 seed 曲线。"],
        ["S3/P1", "每状态 one-step prediction error：按状态维度和场景拆分。", "E1；linear/bilinear/stable 三模型。", "箱线图或热力图；色条统一；单位归一化误差另附说明。"],
        ["S4/P1", "multi-step rollout 代表轨迹：x_ref、truth、prediction。", "E1；DLC 与 hairpin 各 1-2 条。", "truth 黑、prediction 各方法色；共享 horizon 横轴。"],
        ["S5/P1", "通信质量诊断：q_global、delay、loss、constraint tightening、fallback flag。", "E4；保存 comm_diag_hist。", "通信窗口浅橙；q 越低颜色越深；阈值线红虚线。"],
        ["S6/P1", "FDI 阈值调参摘要：Stage4 candidate 检测延迟、切换延迟、误报率。", "E3/Stage4；复用已有 tuning 数据但最好重跑多 seed。", "候选方法用小倍数柱状图；推荐配置加粗边框。"],
        ["S7/P1", "故障类型混淆矩阵/ROC：ax、steer、dual、severe、ramp、intermittent。", "E3；每类至少 50 次事件或足够 seed。", "混淆矩阵蓝色单色；ROC 线用故障类型色；避免彩虹色。"],
        ["S8/P1", "切换 dwell 与误报消融：不同 hold/dwell 参数下的响应和抖振。", "E3；参数网格。", "横轴 dwell/hold，纵轴 latency/false alarm；热力图用 viridis。"],
        ["S9/P1", "所有场景 team center 轨迹对比。", "E2；clean/comm/fault/mixed 全覆盖。", "每场景一个小图；统一坐标范围；主方法颜色一致。"],
        ["S10/P1", "所有场景四车轨迹对比。", "E2；四车轨迹和 payload。", "车辆色固定；baseline 与 TF14 可用不同线型避免太乱。"],
        ["S11/P1", "所有场景系统 e_y/e_s 时间序列。", "E2；各方法 mean±CI。", "共享 y 轴范围；故障/通信窗口标注一致。"],
        ["S12/P1", "所有场景单车误差。", "E2/E3；per-vehicle。", "四车色固定；fault/support 聚合另画一张。"],
        ["S13/P1", "所有场景载荷力/力矩。", "E2/E3/E5；payload_force_hist。", "Fx/Fy/Mz/Norm 固定配色；峰值统计用箱线图。"],
        ["S14/P1", "连接误差与约束余量。", "E2/E3/E5；connection_error_hist。", "连接约束边界红虚线；显示 max violation count。"],
        ["S15/P2", "输入与饱和：delta、a_x、delta_rate、a_rate。", "E2/E3；control history。", "车辆色；饱和边界红虚线；故障车标红背景。"],
        ["S16/P1", "phase-role trim 全场景：delta_trim、ax_trim、phase label。", "E5；已有 Stage5 可先用，但建议多 seed。", "阶段背景色统一；trim 不宜过粗，避免遮挡。"],
        ["S17/P2", "yaw phase plane 全场景。", "E5；e_psi-r 或 yaw-yaw_rate。", "轨迹透明度 0.75；起终点标记；高曲率段加深。"],
        ["S18/P1", "模型结构消融：linear、bilinear、stable projection、online adaptation。", "E1/E6；预测和控制指标都画。", "一张预测误差图 + 一张控制 RMSE 图；用相同方法颜色。"],
        ["S19/P1", "TF13 error-match 详细图：Stage6 每步全车求解的精度与时间代价。", "E6/Stage6；复用 stage6 metrics 并补 solve profile。", "紫色表示 all-solve；与 realtime 橙红做 Pareto 对比。"],
        ["S20/P1", "统计显著性/效应量：主要指标相对 baseline 的改善率和置信区间。", "E2/E3/E6；>=20 seed 更有说服力。", "森林图；0 改善线灰色；改善为右侧或上侧，方向统一。"],
        ["S21/P2", "失败/边界案例：极端丢包、严重双车故障、过高速度/曲率。", "E3/E4/E5；挑选代表失败和接近失败案例。", "不要美化失败；用红色标出约束违反和证书失效，说明适用边界。"],
        ["S22/P2", "运行时剖析：Koopman lifting、MPC solve、FDI、FTC、phase-role、logging 占时。", "E6；保存分模块耗时。", "堆叠条形图；模块颜色与架构图一致；显示 mean/p95。"],
    ]
    add_table(
        doc,
        ["编号", "图名", "实验/数据", "规格与配色"],
        supp_rows,
        [0.75, 3.2, 3.0, 3.1],
        font_size=7.2,
    )

    doc.add_heading("6. 已有图能否直接用", level=1)
    add_table(
        doc,
        ["已有来源", "可用图", "当前用途", "限制/需要补做"],
        [
            [
                "results/tf14_diagnostics",
                "tf14_fdi_identification.png；tf14_switch_certificate.png",
                "可作为 F8/F12 的草稿证据，说明 FDI 与切换证书链条已经有可视化基础。",
                "需要改成投稿风格：英文标签、事件线统一、故障/检测/切换时刻标注、增加多 seed 统计和故障类型分类结果。",
            ],
            [
                "tf14_stage4_fdi_fast_response_20260507",
                "tf14_stage4_fdi_tuning_summary.png",
                "可作为 S6 或方法调参补充图，支持 1 step 检测/切换和 0 误报的调参结论。",
                "不应作为主文唯一 FDI 证据；仍需 E3 的未知故障机制链和混淆矩阵。",
            ],
            [
                "tf14_stage5_phase_role_scenarios_20260507/figures",
                "team_center、four_vehicle、system_error、vehicle_error、yaw_phase、phase_role_trim、metrics_summary",
                "可作为 F5/F6/F7/F11 和 S9-S17 的初稿底图。",
                "Stage5 多数是单次或有限统计；缺 payload force、connection error、多 seed CI、统一投稿配色和部分英文排版。",
            ],
            [
                "tf14_stage6_tf13_error_match_20260508",
                "metrics CSV 与 summary",
                "可支撑 F14/S19 的实时-精度取舍叙事。",
                "当前没有完整图片；需要新增 Pareto、step time 分布、solve profile 和与 realtime preset 的同图对比。",
            ],
        ],
        [2.0, 2.8, 2.6, 3.0],
        font_size=7.4,
    )

    doc.add_heading("7. 绘图脚本与数据保存硬要求", level=1)
    add_bullets(
        doc,
        [
            "每次实验输出一个 manifest.json，记录 git hash、配置、seed、场景、方法、故障类型、通信配置、路径参数和模型文件。",
            "每张图对应一个 source CSV/NPZ，不能让绘图脚本直接从混乱的历史对象里临时扒数据；否则后续无法复现。",
            "所有时间序列统一保存 time_s，所有误差统一使用 SI 单位；横向误差 e_y、纵向误差 e_s、航向误差 e_psi 命名固定。",
            "payload_force_hist 至少包含 Fx、Fy、Mz、force_norm；connection_error_hist 至少包含每根连接的 stretch、slack、violation。",
            "FDI/FTC 数据至少包含 residual_norm、ewma、cusum、gamma_delta、gamma_a、fdi_mode、confidence、switch_mode、redistributed_delta、redistributed_ax。",
            "通信数据至少包含 q_global、q_pairwise、delay_steps、packet_loss、age、constraint_tightening_factor、fallback_flag。",
            "运行时数据至少包含 step_time、solve_time、vehicles_solved、mpc_skipped、overrun_flag、module_time_breakdown。",
            "投稿图的坐标轴、图例、caption 用英文；中文文档中可以保留中文说明，但最终 figure 文件不要中英混杂。",
        ],
        size=8.8,
    )

    doc.add_heading("8. 推荐执行顺序", level=1)
    add_table(
        doc,
        ["顺序", "任务", "原因"],
        [
            ["1", "先补 payload_force_hist、connection_error_hist、runtime breakdown 的数据记录器。", "没有这些物理量，协同运输、安全性和实时性都只能靠 RMSE 讲，证据不够硬。"],
            ["2", "重跑 E2 主对比，先 10 seed 草稿版，再 20 seed 投稿版。", "主文 F5-F7/F10/F13 大部分依赖 E2，优先级最高。"],
            ["3", "重跑 E3 未知故障套件，生成 FDI、切换、重分配、证书全链条。", "这是 TF14 相对 TF13 的最大新增点，必须用机制链证明。"],
            ["4", "重跑 E1 Koopman 预测与结构消融。", "方法开头需要证明 bilinear/stable projection 的必要性，否则审稿人会认为网络只是堆模块。"],
            ["5", "最后做 E5/E6 的 phase-role 与 realtime Pareto。", "这两部分是加分项，但要在主结果和故障闭环稳住之后再精修。"],
        ],
        [0.7, 4.2, 5.1],
        font_size=8.0,
    )

    add_note_box(
        doc,
        "最小可投稿图包",
        "如果时间紧，主文至少保留 F1、F2、F3、F5、F6、F8、F9、F10、F12、F13；"
        "补充材料至少保留 S5、S6、S7、S11、S12、S13、S14、S18、S19、S20。"
        "F0、F4、F11、F14 可以根据篇幅合并或转补充，但不建议完全删除。",
        WARN_FILL,
    )

    doc.save(OUT_DOCX)


if __name__ == "__main__":
    build_docx()
    print(OUT_DOCX)
