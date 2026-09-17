# -*- coding: utf-8 -*-
"""
把 paper_v4_results / paper_v4/results 的实验结果与全部已生成图片导出为 Word 文档。

- 只读既有 JSON/MD/PNG，不修改任何仿真数据、冻结协议或历史裁决。
- 图片全部嵌入，每张图配「图注（来源与单位）」+「解读」+「边界」三部分说明。
- 运行：E:\\anaconda\\python.exe revision_2026\\paper_v4\\tools\\export_results_docx.py
"""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

REV = r"D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026"
BASE = os.path.join(REV, "paper_v4_results")
OUT = os.path.join(BASE, "实验结果汇总_20260915.docx")

CJK_BODY = "宋体"
CJK_HEAD = "微软雅黑"
WIDE = 16.0      # 多面板宽图
MID = 13.5       # 中等宽度
NARROW = 11.5

_fig_no = [0]


# ----------------------------------------------------------------------------- 基础工具
def style_run(run, size=10.5, bold=False, italic=False, color=None, cjk=CJK_BODY, latin="Times New Roman"):
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.name = latin
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), cjk)
    rFonts.set(qn('w:ascii'), latin)
    rFonts.set(qn('w:hAnsi'), latin)
    if color is not None:
        run.font.color.rgb = color
    return run


def para(doc, text="", size=10.5, bold=False, italic=False, align=None, space_after=6,
         color=None, cjk=CJK_BODY, latin="Times New Roman", indent=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if indent is not None:
        p.paragraph_format.left_indent = Cm(indent)
    if text:
        style_run(p.add_run(text), size=size, bold=bold, italic=italic, color=color,
                  cjk=cjk, latin=latin)
    return p


def heading(doc, text, level=1):
    sizes = {1: 16, 2: 13.5, 3: 12, 4: 11}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else (10 if level == 2 else 8))
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    style_run(p.add_run(text), size=sizes.get(level, 11), bold=True,
              color=RGBColor(0x1F, 0x38, 0x64), cjk=CJK_HEAD, latin=CJK_HEAD)
    return p


def bullets(doc, items, size=10.5, style="List Bullet"):
    for it in items:
        p = doc.add_paragraph(style=style)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Cm(0.75)
        style_run(p.add_run(it), size=size)


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hexcolor)
    tcPr.append(shd)


def set_cell(cell, text, size=9, bold=False, align=None, color=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.space_before = Pt(1)
    if align is not None:
        p.alignment = align
    style_run(p.add_run(str(text)), size=size, bold=bold, color=color)


def add_table(doc, header, rows, widths=None, size=9, caption=None):
    if caption:
        para(doc, caption, size=9.5, bold=True, space_after=3)
    t = doc.add_table(rows=1, cols=len(header))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, h in enumerate(header):
        set_cell(t.rows[0].cells[i], h, size=size, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
        shade(t.rows[0].cells[i], 'DEEAF6')
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            set_cell(cells[i], v, size=size)
    if widths:
        for r in t.rows:
            for i, w in enumerate(widths):
                if i < len(r.cells):
                    r.cells[i].width = Cm(w)
    para(doc, "", size=6, space_after=6)
    return t


def add_figure(doc, rel, title, caption, read, limit, width=WIDE):
    """插入一张图：图 + 编号标题 + 图注 + 解读 + 边界。"""
    _fig_no[0] += 1
    n = _fig_no[0]
    path = os.path.join(BASE, rel.replace('/', os.sep))
    if not os.path.isfile(path):
        para(doc, "[缺图] " + rel, size=9, color=RGBColor(0xC0, 0x00, 0x00))
        return n, False
    doc.add_picture(path, width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.space_after = Pt(3)
    para(doc, "图 %d　%s" % (n, title), size=10.5, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)
    raw = caption[3:] if caption.startswith("来源：") else caption
    para(doc, "图注与来源：" + raw, size=9, italic=True,
         color=RGBColor(0x59, 0x59, 0x59), space_after=3)
    if read:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.4)
        style_run(p.add_run("解读："), size=9.5, bold=True)
        style_run(p.add_run("　".join(read) if isinstance(read, list) else read), size=9.5)
    if limit:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.left_indent = Cm(0.4)
        style_run(p.add_run("边界："), size=9.5, bold=True, color=RGBColor(0xA0, 0x30, 0x00))
        style_run(p.add_run("　".join(limit) if isinstance(limit, list) else limit),
                  size=9.5, color=RGBColor(0x80, 0x30, 0x00))
    return n, True


def add_footer_page_numbers(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style_run(p.add_run("第 "), size=9)
    fld = OxmlElement('w:fldSimple')
    fld.set(qn('w:instr'), 'PAGE')
    p._p.append(fld)
    style_run(p.add_run(" 页 / 共 "), size=9)
    fld2 = OxmlElement('w:fldSimple')
    fld2.set(qn('w:instr'), 'NUMPAGES')
    p._p.append(fld2)
    style_run(p.add_run(" 页"), size=9)


# ----------------------------------------------------------------------------- 文档骨架
doc = Document()
sec = doc.sections[0]
sec.page_width = Cm(21.0)
sec.page_height = Cm(29.7)
sec.left_margin = Cm(2.2)
sec.right_margin = Cm(2.2)
sec.top_margin = Cm(2.2)
sec.bottom_margin = Cm(2.0)
add_footer_page_numbers(sec)

st = doc.styles['Normal']
st.font.name = "Times New Roman"
st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn('w:eastAsia'), CJK_BODY)

cp = doc.core_properties
cp.title = "四车协同运输 · Adaptive Koopman 论文修订 v4 实验结果汇总"
cp.author = "paper_v4 实验证据整理"
cp.comments = "由 paper_v4_results 与 paper_v4/results 的 JSON/MD/PNG 证据整理，未修改任何仿真数据或裁决。"

# ------------------------------------------------------------------ 封面与使用说明
para(doc, "四车协同运输 · Adaptive Koopman 论文修订 v4", size=13, bold=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2, cjk=CJK_HEAD, latin=CJK_HEAD)
para(doc, "实验结果汇总（含全部图表与解读）", size=20, bold=True,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10, cjk=CJK_HEAD, latin=CJK_HEAD)
para(doc, "版本：POST-R3-DRAFT-20260915", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
para(doc, "图片：%d 张（全部已生成 PNG，均内嵌于本文档）" % 40, size=11,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
para(doc, "整理依据：各 run 目录内的 metrics.json / status.json / 独立审计 JSON / 比较 JSON / "
          "figure_manifest.json / README.md，以及 experiment.md、exp_status.md、exp_solution.md、"
          "experiment_execution_2026091{3,4,5}.md、protocol/后续实验详细任务书_20260915.md",
     size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x59, 0x59, 0x59), space_after=12)

heading(doc, "目录", 2)
for t in [
    "0. 使用说明（数据来源、状态三分法、阅读规则）",
    "1. 研究主线与实验目标",
    "2. 方法名称对照（全部使用英文原称）",
    "3. 实验阶段与当前状态总览",
    "4. 结果与图表分阶段说明",
    "　　4.1 E00 源码身份、数据角色与输入时间语义",
    "　　4.2 E01 几何、100 m 诊断与数值分辨率",
    "　　4.3 E01 真实回头弯硬门失败线",
    "　　4.4 R1 离线构形与内力归因",
    "　　4.5 R2b / R2c 候选选择与完整回头弯开发选优",
    "　　4.6 R3 旧候选数值配对 FAIL",
    "　　4.7 R3 诊断与根因定位",
    "　　4.8 U1—U3 身份重建与计算成本",
    "　　4.9 R4-B 串并行等价性补证",
    "　　4.10 R4-C 时间身份 → 有力窗口 → 完整路线 → 决定性配对 PASS",
    "　　4.11 C0 接口资格与 R4-P1-2ms（进行中）",
    "5. 关键数字总表",
    "6. 失败、负结果与工程问题清单",
    "7. 结论边界：现在能写什么、不能写什么",
    "8. 下一步（已冻结的顺序与门）",
    "附录 A　paper_v4 之前的 Koopman 预测阶段（2026-09-02 — 09-08）",
    "附录 B　其余图表版本（被替代版本、QA 前后版本、只读冒烟版本）",
    "附录 C　图片文件索引",
]:
    para(doc, t, size=10.5, space_after=2, indent=0.3)

doc.add_page_break()

heading(doc, "0. 使用说明", 1)
para(doc, "0.1 两个结果目录")
add_table(doc,
          ["目录", "绝对路径", "内容"],
          [["早期结果目录", r"…\revision_2026\paper_v4_results",
            "20260909 批次：E00_01—E00_04、E01 几何 / 100 m / 回头弯、R1；共 28 个 run 目录、7 张 PNG"],
           ["主结果目录", r"…\revision_2026\paper_v4\results",
            "20260910—20260915 批次：R2B、R2C、R3、QP 诊断、R4-B、R4-C、C0、R4-P1；共 30 张 PNG、15 个 SVG"]],
          widths=[2.6, 5.6, 8.4], size=9.5)
para(doc, "任务书规定的正式输出根目录是 paper_v4_results（experiment.md 第 12.2 节 $TaskResultRoot）。"
          "后续批次实际落在 paper_v4\\results，本文档按实际位置引用，不做移动或改写。"
          "两个目录的 PNG 合计 37 张，另加 analysis 目录 3 张，共 40 张，全部内嵌。", size=10, space_after=8)

para(doc, "0.2 状态必须分开登记", size=11, bold=True, space_after=3)
add_table(doc,
          ["状态", "含义"],
          [["execution_status", "是否完整跑完（COMPLETED / RUNNING / FAILED / INTERRUPTED / TIMEOUT_INCOMPLETE）"],
           ["science_status", "是否通过预登记的科学门（PASS / FAIL / PARTIAL / NOT_RUN）"],
           ["figure_status", "图是否生成并完成视觉 QA（PASS / MISSING）"]],
          widths=[3.6, 13.0], size=9.5)
para(doc, "程序 exit=0、文件存在、图已生成，都不能替代科学验收。", size=10, space_after=8)

para(doc, "0.3 阅读与引用规则（继承任务书第 0 节）", size=11, bold=True, space_after=3)
bullets(doc, [
    "旧文档、旧代码、旧数据和失败记录保留，不追认通过。",
    "失败与负结果照实保留，不得为提高通过率修改阈值、删晚段、换终点或增加第三套权重。",
    "开发集上的选优（如 λ=2）只属于开发选优，不构成独立或统计显著的优越性证明。",
    "图内一律使用方法的英文全名，不使用内部代号。",
    "未完成项一律标 NOT_RUN / SOURCE_PENDING / RESOURCE_PENDING，不填默认成功。",
])
doc.add_page_break()

# ------------------------------------------------------------------ 1 研究主线
heading(doc, "1. 研究主线与实验目标", 1)
para(doc, "研究主线：在同一可信四车—货物模型、同一合法信息和同一运输任务下，验证「预测改进」是否能够改善"
          "通信受限时的状态估计、跟踪和连接受力，并说明代价与适用范围。任务书明确：不能预设改进模型在所有工况获胜，"
          "也不能把正确建模、普通瞬时转动中心（ICR）分配本身包装成核心创新。", space_after=8)

heading(doc, "1.1 被控对象与信息边界", 3)
bullets(doc, [
    "状态：30 维物理状态 X=[p1,ψ1,vx1,vy1,r1,…,p4,ψ4,vx4,vy4,r4,pc,ψc,vxc,vyc,rc]；另有实际转向 δ_act∈R⁴ "
    "与连接器历史状态作为植物附加状态。",
    "预测状态：47 维（G0 货物运动 3 维、G1 相对位置 / 姿态 16 维、G2 相对速度 12 维、G3 四点连接形变 / 相对速度 16 维）。",
    "物理命令：w=[a1,δ1^req,…,a4,δ4^req]∈R⁸；控制器内部 11 维请求 u11。",
    "执行器：τδ=0.12 s、转角速率上限 1.2 rad/s、转角上限 15°（仿真假设，非实测标定）。",
    "合法信息：每辆车只能用自己的测量、已收到且带原时间戳的邻车包、已收到的上层包和本地历史；"
    "货物测量由协调节点获取后再经链路发送。",
])

heading(doc, "1.2 三条主路线与诊断路线", 3)
add_table(doc,
          ["路线", "冻结几何 / 时间", "事件点"],
          [["连续正弦路线", "y=0.82·sin(2πq/60+0.18)，q∈[0,100] m", "第一个完整非起始曲率峰附近"],
           ["单移线", "25 m 后 3.5 m 五次多项式换道，终点 q=100 m", "进入、最大曲率、退出"],
           ["真实回头弯", "24 m 入口直线＋半径 11.5 m 半圆＋≥24 m 出口直线，两端曲率连续过渡", "弯道进入、中部、退出"],
           ["100 m 诊断", "1 m/s 起以 0.25 m/s² 加速至 30 m；前轮 +5° / 后轮 −2.5° 持续 5 s 后反向 5 s；余程减速至 0.7 m/s",
            "第一阶跃前 0.1 s 注入网络诊断"]],
          widths=[2.4, 10.0, 4.2], size=9.5)
para(doc, "实际冻结的回头弯参考：过渡段 11 m 版本，路线总长 95.1283155163 m，"
          "相对理想瞬时 11.5 m 半圆的最大径向偏离 5.48636 m——这一偏离必须在论文图中同时画出理想几何，"
          "不能只标「相同 11.5 m 回头弯」。", size=10, space_after=8)

heading(doc, "1.3 核心比较网格与科学门", 3)
para(doc, "同一已验收分层架构下 3 种预测模型 × 网络保护开关 = 6 个核心方法；在其上做时延单开关（E06）、"
          "共同误差界（E07）、强基线（E08）、混合网络压力（E09）、观测 / 在线适应 2×2（E10）、"
          "故障诊断与容错（E11）、逐模块消融（E12）、敏感性与计算预算（E13）、适用域（E14）、"
          "独立验证（E15）、理论补证（E16）、审稿逐点回复（E17）。", space_after=6)
bullets(doc, [
    "6 项控制主假设 H1—H6，按路线分层、整族有放回成对 bootstrap 10000 次，同时报告原 95% CI 与 "
    "Bonferroni 99.1667% 区间。",
    "收益声明要求点改善 ≥ 5% 且校正 CI 下界 > 0，并通过 42 项非劣化护栏。",
    "数值分辨率门：峰值相对差 ≤ 2%、冲量向量相对差 ≤ 2%、终态货物位置 ≤ 1 mm、航向 ≤ 0.01°。",
])
doc.add_page_break()

# ------------------------------------------------------------------ 2 方法名称
heading(doc, "2. 方法名称对照（全部使用英文原称）", 1)
add_table(doc,
          ["内部键", "英文全称（原称）", "中文说明"],
          [["P0", "Physical Model Predictive Control", "耦合物理模型预测控制"],
           ["P0N", "Network-Protected Physical Model Predictive Control", "带网络保护的耦合物理模型预测控制"],
           ["K0", "Fixed Linear Koopman Model Predictive Control", "固定线性 Koopman 模型预测控制"],
           ["K0N", "Network-Protected Fixed Linear Koopman Model Predictive Control",
            "带网络保护的固定线性 Koopman 模型预测控制"],
           ["K1", "Guarded Residual Koopman Model Predictive Control", "固定保护残差 Koopman 模型预测控制"],
           ["K1N", "Network-Protected Guarded Residual Koopman Model Predictive Control",
            "带网络保护的固定保护残差 Koopman 模型预测控制"],
           ["—", "Distributed Physical Model Predictive Control", "无在线上层的分布式物理模型预测控制"],
           ["—", "Hierarchical Distributed Physical Model Predictive Control", "有在线上层的分层分布式物理模型预测控制"]],
          widths=[1.6, 9.0, 6.0], size=9.5, caption="表 2-1　六个核心方法键与架构方法")

add_table(doc,
          ["英文全称（原称）", "中文说明"],
          [["Guarded Residual Koopman Model Predictive Control without State Time Alignment",
            "仅关闭状态时间对齐的保护残差 Koopman MPC"],
           ["Tube-Based Robust Model Predictive Control", "管状鲁棒模型预测控制"],
           ["Affine Output-Feedback Robust Model Predictive Control", "仿射因果输出反馈鲁棒模型预测控制"],
           ["Packet-Buffered Predictive Control", "缓存预测控制"],
           ["Observer-Augmented Guarded Residual Koopman Model Predictive Control", "观测增强的保护残差 Koopman MPC"],
           ["Causally Bias-Adaptive Guarded Residual Koopman Model Predictive Control", "因果偏置适应的保护残差 Koopman MPC"],
           ["Oracle Fault-Aware Model Predictive Control", "已知故障上界（Oracle）容错 MPC"],
           ["Fault-Diagnosis-Based Fault-Tolerant Model Predictive Control", "实际检测与容错 MPC"],
           ["Network-Resilient Cooperative Transport Control", "完整框架"],
           ["Centralized Full-State Physical Model Predictive Control",
            "集中全状态物理 MPC（诊断上界；本文档多数闭环结果属于此方法）"],
           ["Adaptive Koopman Estimation Method（AKE-M）",
            "原稿自适应 Koopman 方法；尚未恢复提交版原文与源码，不得用任意「AKE」控制器冒充复现"]],
          widths=[10.6, 6.0], size=9, caption="表 2-2　消融、基线与鲁棒方法")

add_table(doc,
          ["代号", "含义", "绝对参数"],
          [["参数点 P0", "名义参数（1.0 倍）",
            "载荷质量 2000 kg；连接器刚度 30000 N/m、阻尼 3500 N·s/m、空程 0.002 m；摩擦系数 μ=0.9；"
            "货物 5.0×2.0 m、重心高 1.2 m；车辆 1200 kg、横摆惯量 1800 kg·m²"],
           ["参数点 P1", "轻载高摩擦", "载荷质量 1800 kg（0.9 倍）、连接器 28500 N/m、阻尼 3325 N·s/m、"
                                    "空程 0.0019 m、μ=0.95、货物转动惯量 4350 kg·m²"],
           ["参数点 P2", "重载低摩擦", "载荷质量 2200 kg（1.1 倍）、连接器 31500 N/m、阻尼 3675 N·s/m、"
                                    "空程 0.0021 m、μ=0.80、货物转动惯量 5316.6667 kg·m²"],
           ["λ（lambda_internal）", "MPC 内部力代价权重倍率", "λ=1 / λ=2（λ=2 为开发选定者）"],
           ["EXP-R3-unfrozen-v1", "候选身份", "每个预测步重算动力学雅可比、中心差分尺度 1、8 进程、λ=2；"
                                            "相对旧候选唯一登记的结构变化"]],
          widths=[3.2, 3.0, 10.4], size=9,
          caption="表 2-3　参数点与算法代号（P0/P1/P2 在参数点语境与方法键语境下同名，须加限定词）")
doc.add_page_break()

# ------------------------------------------------------------------ 3 总览
heading(doc, "3. 实验阶段与当前状态总览", 1)
add_table(doc,
          ["阶段", "内容", "当前状态"],
          [["E00", "源码身份、数据角色、命令语义与原公式核对", "PARTIAL（formal_allowed=false）"],
           ["E01", "植物、ICR、执行器、连接受力与数值分辨率",
            "PARTIAL / FAIL（100 m 子门 PASS；真实回头弯硬门 FAIL；plant_gate 未通过）"],
           ["E02", "冻结预测复现、接口闭合、历史基线补证", "NOT_RUN"],
           ["E03", "真正物理 MPC、分布式信息、网络时序", "部分工程已有，正式资格未完成"],
           ["E04", "无在线上层 / 有在线上层架构比较", "NOT_RUN"],
           ["E05", "3 预测模型 × 网络保护开关核心比较", "NOT_RUN（接口与门未齐）"],
           ["E06 / E07", "时延补偿单开关、共同误差界", "NOT_RUN"],
           ["E08 / E09", "强基线、混合网络压力", "NOT_RUN（来源资格 SOURCE_PENDING）"],
           ["E10—E12", "观测 / 适应、故障容错、逐模块消融", "NOT_RUN"],
           ["E13 / E14", "参数敏感性、计算预算、适用域", "开发诊断部分已有"],
           ["E15", "独立物理验证与真实网络 / 硬件", "RESOURCE_PENDING"],
           ["E16", "公式 22、连续域证书、递归可行性", "反例已实算；完整证明未完成"],
           ["E17", "审稿逐点回复、图表、文稿", "22 项意见均 OPEN / NOT_RUN / 各类 PENDING"],
           ["R1", "失败边界修复＋离线构形 / 内力归因", "R0 / R1 PASS"],
           ["R2a / R2b / R2c", "真实物理 MPC 身份与完整回头弯开发选优", "PASS（λ=2 为开发选定者）"],
           ["R3", "冻结开发选定者的数值配对", "旧候选 FAIL（保留）；新候选 EXP-R4-C 恢复链 PASS"],
           ["R4", "其余两参数点三步长（6 条）", "C0 资格 PASS；R4-P1-2ms RUNNING；其余 5 条 BLOCKED"],
           ["R5", "合法信息接口转接（2 条）", "NOT_RUN（等待 R4 总 PASS）"],
           ["C0", "新旧 runner / 报告 / 协议身份迁移", "PASS_C0_R4_READY"],
           ["C3", "执行器更新间隔九短片段", "NOT_RUN"],
           ["C4", "原 E01 逐项缺口核销", "部分完成"]],
          widths=[2.2, 7.4, 7.0], size=8.5)
doc.add_page_break()

# ------------------------------------------------------------------ 4 结果
heading(doc, "4. 结果与图表分阶段说明", 1)

# 4.1 E00
heading(doc, "4.1 E00 源码身份、数据角色与输入时间语义（2026-09-09）", 2)
para(doc, "批次：20260909_E00_01 / 02 / 03 / 04。总门 gates/E00.json = PARTIAL、formal_allowed=false："
          "plant_source_identity=PASS，actuator / data_role / input_time / submission 均 SOURCE_PENDING。"
          "protocol/methods.json = NOT_RUN、methods=[]；review/review_matrix.json 登记 22 项唯一审稿意见编号"
          "（AE-1、AE-2、R1-1…R1-6、R2-1…R2-7、R3-1…R3-7），全部为 NOT_RUN 且 evidence=[]。", space_after=6)
add_table(doc,
          ["对象", "身份 / 结果"],
          [["主机 / Python", "DESKTOP-9IUUGEO；3.11.14（Anaconda）"],
           ["冻结植物入口", "four_vehicle_common.py = 6d7a2092…bca80"],
           ["事件积分器", "event_substep.py = 9aa0e8bd…d77c"],
           ["当前错误比较控制器", "paper_v3/src/controllers.py = c504bb09…c797"],
           ["静态物理测试", "5 项通过；最大归一化残差 1.5325941567668805e-14（门槛 1e-8）；plant_gate=NOT_RUN"],
           ["mandatory 套件", "PASS，但 scope = 「guard utility tests only; full experiment mandatory suite "
                            "NOT_IMPLEMENTED」；6 项通过；legacy_recorder_proven=false"],
           ["历史数据审计", "97 个源码 SHA 全匹配；672 条 manifest / 14842 条访问账本全部映射；"
                        "denied=[]、unmapped=[]；跨角色族重叠 = []"],
           ["三个 checkpoint", "repeat0 seed997100 γ=0.75 / repeat1 seed997200 γ=0.5 / repeat2 seed997300 γ=0.5"],
           ["normalization / S0", "DD408EB0…487CC7 / 4F0B403E…6CCF07（registered_match=true）"],
           ["确认盲性", "NOT_PROVEN_BY_SINGLE_RUN_LEDGER（仍 PARTIAL）"],
           ["输入时间语义", "raw_pulse_row=2、cache_pulse_row=1、state_replay_max_abs=0.0；"
                        "11 列控制映射已核实；不能判为未来命令泄漏"]],
          widths=[3.6, 13.0], size=9, caption="表 4-1　E00 已核实身份与结果")
para(doc, "E16 子项（counterexamples.json）实算完成：基础块已超界时返回 NOT_CERTIFIABLE_BY_THIS_BOUND（γ=null），"
          "而不是把 γ 截到 0 后宣称成功；非正规算例 A=[[0.9,10],[0,0.9]] 谱半径 0.9 但 2-范数 10.080354318352214；"
          "切换算例 A1、A2 各自谱半径 0.5，乘积谱半径 4.48606797749979。"
          "submitted_formula_match=SOURCE_PENDING、full_closed_loop_proof=NOT_RUN。", size=10, space_after=8)

# 4.2 E01 100m
heading(doc, "4.2 E01 几何、100 m 诊断与数值分辨率（2026-09-09）", 2)
para(doc, "几何：旧质心切线分配的最大后轴残差 0.1363955907 m/s，不满足后轴无侧滑；新增稳态参考修正后"
          "最大残差 8.3267e-17 m/s（9 个测试点）。转向过渡 20 s / 2001 点诊断：位置差分与解析速度最大误差 "
          "6.9579e-10 m/s，后轴 / 前轴 / 锚点残差 1.94e-16 / 1.11e-16 / 1.33e-15 m/s，最大请求轮角 12.8557°、"
          "采样转角速率 0.22137 rad/s。", space_after=6)
para(doc, "100 m 批次的证据完整性经历三次修正：100M03（9 条 PASS 但未存 Fz / 轮胎利用率 / 真实子步 → 降级 "
          "PILOT_EVIDENCE_INCOMPLETE）、100M04（补存子步，但 raw 时间标签错位且多跑一个 20 ms 区间 → 继续降级）、"
          "100M05（时间语义改为起点 / 终点双列，区间数改为 ⌈T/20ms⌉，9 条 PASS → 100 m 数值分辨率子门 PASS）。", space_after=6)
add_table(doc,
          ["参数点", "1 ms → 0.5 ms 峰值相对差", "冲量向量相对差", "终态位置", "终态航向", "裁决"],
          [["P0", "9.5153e-7（0.0000952%）", "2.1502e-5", "9.447e-9 m", "6.104e-9°", "PASS"],
           ["P1", "1.4295e-6", "1.0173e-5", "1.359e-8 m", "1.082e-8°", "PASS"],
           ["P2", "2.3645e-6", "1.0005e-5", "1.379e-9 m", "3.402e-10°", "PASS"]],
          widths=[2.0, 4.4, 3.2, 2.6, 2.4, 2.0], size=9,
          caption="表 4-2　100M05 决定性 1 ms → 0.5 ms 配对（注册上限 2% / 2% / 1 mm / 0.01°）")

add_figure(doc, "20260909_E01_100M05/figure_100m_P0_0p5ms.png",
           "100 m 诊断六面板（参数点 P0，最大植物积分步 0.5 ms）",
           "来源：paper_v4_results/20260909_E01_100M05/P0_0.5ms（metrics.json、raw.npz、substeps.npz）；"
           "场景 100m_diagnostic；P0 = 载荷 1.0 / 连接器 1.0 / μ=0.9；34.78 s、1739 个 20 ms 区间、69609 个真实子步；"
           "力曲线未平滑（raw / substep 原始峰值）。",
           ["面板给出加速—前虚拟 +5° / 后 −2.5° 阶跃—反向阶跃—制动四段的轨迹、误差、四点力、请求与实际转角、"
            "约束与求解耗时证据。",
            "实测：实际货物路径 102.81025 m（不是严格直线 100 m）；最大四点力范数 1540.95 N；"
            "最大纵向 / 横向拉开载荷代理 131.97 N / 218.92 N；最小支承 4077.38 N；"
            "最大轮胎原始利用率 0.2374；作用—反作用残差 0，内力投影残差 3.10e-16，时间闭合 0。"],
           ["这是数值分辨率与证据完整性图，不是控制性能、实时性或材料安全图。",
            "100 m 只是 E01 计划 27 条诊断轨迹中的 9 条子集；plant_gate 仍为 NOT_RUN / PARTIAL。"],
           width=WIDE)

add_figure(doc, "20260909_E01_100M05/figure_convergence_100m.png",
           "100 m 数值收敛门（三参数点 × 两档配对）",
           "来源：paper_v4_results/20260909_E01_100M05/convergence_100m.json；"
           "门限 峰值相对差 ≤ 2%、冲量向量相对差 ≤ 2%、终态位置 ≤ 1 mm、终态航向 ≤ 0.01°；"
           "近零策略：连接器冲量向量范数使用 1 N·s 分母下限。",
           ["6 组配对全部低于注册线；决定性 1→0.5 ms 的三参数点峰值相对差为 9.52e-7 / 1.43e-6 / 2.36e-6，"
            "比 2% 门小 4—6 个数量级。",
            "2→1 ms 配对作为诊断对照报告，不套用注册门。"],
           ["门通过只说明该批次在 2 / 1 / 0.5 ms 之间已进入数值收敛区间，不等于跟踪精度优秀，"
            "也不证明「执行器—植物联合连续极限」（执行器仍按 2 ms 离散更新）。"],
           width=MID)

add_figure(doc, "20260909_E01_100M05/figure_connector_directions_100m.png",
           "100 m 四点连接力方向与拉伸载荷代理",
           "来源：paper_v4_results/20260909_E01_100M05/P0_0.5ms 子步力数据；单位 N；方向 θ=atan2(Fy,Fx)。",
           ["用于说明「整体净力为零」不等于「货物没有受拉」：净合力 / 净力矩与四点内力零空间投影必须分开画。",
            "本图同时给出左右（T_LR）与前后（T_FR）拉伸载荷代理，为后续回头弯失败归因提供同一口径。"],
           ["刚体货物平面模型只能说明拉伸载荷或潜在受拉趋势；没有材料、结构应力与破坏准则时不得称为「撕裂」。",
            "零力附近方向不稳定，应标 NO_DIRECTION，不画随机跳角。"],
           width=WIDE)
doc.add_page_break()

# 4.3 hairpin
heading(doc, "4.3 E01 真实回头弯硬门失败线（2026-09-09）", 2)
para(doc, "几何冻结：2 m 过渡使偏置四车目标转角超 15° 被排除；11 m 过渡被冻结，路线总长 95.1283155163 m，"
          "相对理想瞬时半圆最大径向偏离 5.48636 m（必须在论文中披露）。转向过渡区短程验证 HS01—HS04 全部 PASS"
          "（13 s / 26 m 与 18 s / 36 m），HS04 请求饱和 0、目标几何残差 2.22e-16 m/s。", space_after=6)
add_table(doc,
          ["输入器", "状态", "触发进度", "积分时长", "最大点力", "横向拉开代理", "最大速度误差",
           "最大航向误差", "请求饱和", "轮胎原始利用率"],
          [["纯前馈、无共同速度（HAIRPIN01/P0_2ms）", "FAIL STOP_ULTIMATE_FORCE", "75.92 m", "37.946 s",
            "15001.955 N", "15019.573 N", "1.3355 m/s", "22.811°", "0", "0.999802"],
           ["共同速度 P＋货物航向 / 横摆反馈（HR01）", "FAIL STOP_ULTIMATE_FORCE", "50.836 m", "25.418 s",
            "15001.214 N", "12886.649 N", "0.7058 m/s", "11.632°", "188", "1.082632"],
           ["仅共同速度 P（HR02）", "FAIL STOP_ULTIMATE_FORCE", "81.72 m", "40.860 s",
            "15001.652 N", "14601.078 N", "0.7581 m/s", "3.549°", "0", "0.997916"]],
          widths=[3.6, 2.4, 1.8, 1.7, 1.9, 1.9, 1.6, 1.5, 1.2, 1.6], size=8,
          caption="表 4-3　三条失败全部命中未改动的 15 kN 极限停止（FAIL，证据保留）")

add_figure(doc, "20260909_E01_HFAIL01/hairpin_failures.png",
           "真实回头弯三次硬停止对比（三列分别为三种输入器）",
           "来源：paper_v4_results/20260909_E01_HFAIL01/failure_comparison.json、"
           "HAIRPIN01/P0_2ms、HR01、HR02 的 metrics.json 与 substeps.npz；"
           "每列自上而下为四点连接力（N，红色虚线 = 15 kN 停止线）、货物体纵向速度（m/s）、"
           "货物航向误差（deg）、纵 / 横向拉开载荷代理（N）；曲线来自未平滑子步数据。",
           ["三条曲线都在前部连接点力与横向拉开代理持续上升后触发 15 kN 停止（75.92 / 50.836 / 81.72 m）。",
            "仅共同速度组（右列）失败时请求饱和为 0、目标 / 请求几何残差约 1e-16 m/s、"
            "最大航向误差仅 3.549°，仍然失败——因此「请求不符合阿克曼几何」不是此次失败的充分解释。",
            "共同速度＋航向反馈组（中列）反而更早失败，并记录 188 次不可行目标，该结构已被反证。"],
           ["只证明「冻结植物在该纯前馈 / 简单速度补偿输入器下不能完成回头弯」，"
            "不等于连接器力律错误，也不代表物理不可控。",
            "三条旧失败的末端时间标 FINAL_STATE_TIME_UNCERTAIN；失败边界存在已接受段遗漏"
            "（substeps 14995.128 N / raw 端点 15001.652 N / metrics 14997.301 N 三者不一致），已登记 R0 修复。",
            "HAIRPIN01 与 HR01/HR02 的 complete_registered_trajectory=true 只表示「请求全程走完」，"
            "不能作为完成证明——状态定义需拆成 requested_full_trajectory 与 trajectory_completed。"],
           width=WIDE)

# 4.4 R1
heading(doc, "4.4 R1 离线构形与内力归因（2026-09-09，只读）", 2)
para(doc, "批次：R1_01（空目录）、R1_02（空目录）、R1_03（唯一有效报告）。范围：只重算既有三条失败轨迹和 "
          "100 m 名义轨迹，没有运行新动力学；三条旧失败末端统一标 FINAL_STATE_TIME_UNCERTAIN。", space_after=6)
add_table(doc,
          ["轨迹", "最大构形误差 e_g", "最大相对速度", "最大内力", "最大轮胎利用率",
           "差动加速度绝对值最大", "±0.8 m/s² 越界"],
          [["original_input", "0.6228 m", "0.11644 m/s", "20916.54 N", "0.99980", "0.08556", "0"],
           ["heading_repair", "0.6727 m", "0.18401 m/s", "19465.65 N", "1.08263", "0.54687", "0"],
           ["common_speed_repair", "0.5800 m", "0.08688 m/s", "21259.19 N", "0.99792", "0.03000", "0"],
           ["100m_nominal", "0.07645 m", "0.37241 m/s", "2342.65 N", "0.23356", "0.42557", "0"]],
          widths=[3.2, 2.6, 2.4, 2.2, 2.2, 2.2, 1.8], size=9,
          caption="表 4-4　R1 逐轨迹最大量（离线重算，无新动力学）")

add_figure(doc, "20260909_R1_03/failure_timeline.png",
           "R1 失败时间线：四组诊断量的 20% 持续阈值越过顺序",
           "来源：paper_v4_results/20260909_R1_03（summary.json、relative_motion.csv、"
           "force_decomposition.csv，各 6953 行）；阈值 = 20% 幅度且持续 1 s 的诊断线，不是材料阈值；"
           "纵轴为诊断量（构形 m、相对速度 m/s、内力 N、轮胎利用率），横轴为时间 s。",
           ["三条回头弯失败的时序一致：相对运动先越线，持续内力上升在后"
            "（original 13.52→31.22 s、heading_repair 14.38→20.16 s、common_speed 13.34→33.14 s）；"
            "100 m 名义轨迹的顺序相反（构形 12.20 s 最先）。",
            "该时序支持「需要显式构形 / 内力控制」的判断，并解释了为何仅减小航向误差不足以解除内部拉伸。"],
           ["阈值越过顺序只是定位线索，不构成因果证明。",
            "图表不能用于宣称 15 kN 附近的连续时间峰值已收敛（末端时间不确定，已单独阴影标注）。"],
           width=WIDE)
doc.add_page_break()

# 4.5 R2b/R2c
heading(doc, "4.5 R2b / R2c 候选选择与完整回头弯开发选优（2026-09-10 / 11）", 2)
para(doc, "方法身份：Centralized Full-State Physical Model Predictive Control（集中全状态物理模型预测控制，"
          "离线诊断上界），N=20、控制周期 20 ms、执行器 2 ms、冻结参考 95.1283155 m。", space_after=6)
add_table(doc,
          ["批次", "说明", "状态"],
          [["20260910_R2B_COMPARE01", "18 s 入弯短试，把短片段排序误写为 R3 选择", "保留为错误分析版本"],
           ["20260910_R2B_COMPARE02", "修正后仅给出 R2c 顺序 lambda2, lambda1，selected_for_r3=null", "PASS"],
           ["20260910_R2C_ANALYZER_SMOKE01 / 02", "分析器只读冒烟，两个 copy 指标完全相同", "PASS"],
           ["20260910_R2C_COMPARE01", "比较器错误地要求两候选都 PASS", "FAIL（保留）"],
           ["20260911_R2C_COMPARE02", "修正为「只有两者都失败才停止」", "PASS，selected_for_r3 = lambda2"]],
          widths=[5.0, 8.4, 3.2], size=9, caption="表 4-5　R2b / R2c 批次与裁决")
add_table(doc,
          ["候选", "资格", "失败检查", "点力峰值", "预测点力峰值", "内力峰值", "货物位置 RMSE",
           "货物航向 RMSE", "最大构形误差", "轮胎利用率", "最小支承", "实际 / 参考路程",
           "平均 / P95 / 最大求解", "墙钟"],
          [["λ=1", "FAIL", "request_steering_bound（请求转角 15.0054157° > 15°）",
            "358.861345 N", "636.095247 N", "320.906730 N", "0.260528 m", "0.848559°", "0.013854 m",
            "0.072837", "4675.590 N", "95.883548 / 95.128316 m", "3.118 / 3.218 / 4.386 s", "7682.283 s"],
           ["λ=2", "PASS", "—", "345.882087 N", "621.912453 N", "312.087919 N", "0.258509 m", "0.848671°",
            "0.013488 m", "0.054235", "4675.573 N", "95.813880 / 95.128316 m", "2.980 / 3.220 / 4.981 s",
            "7343.339 s"]],
          widths=[1.3, 1.1, 3.0, 1.8, 1.8, 1.8, 1.5, 1.4, 1.5, 1.2, 1.5, 2.4, 2.2, 1.4], size=7.5,
          caption="表 4-6　R2c 两条完整回头弯路线实测（λ=1 因请求转角越界被淘汰）")

add_figure(doc, "../paper_v4/results/20260911_R2C_COMPARE02/r2c_paths.png",
           "完整回头弯：实际冻结参考与理想几何对比（两条候选）",
           "来源：paper_v4/results/20260911_R2C_COMPARE02（comparison.json、raw.npz）；"
           "横 / 纵坐标 m；黑虚线 = 冻结 11 m 过渡参考，蓝 / 橙实线 = λ1 / λ2 实际货物轨迹，"
           "灰点线 = 理想瞬时 11.5 m 半圆。",
           ["两条候选都完成了 95.1283155 m 冻结参考（实际货物路径 95.883548 / 95.813880 m）。",
            "图中直观显示实际冻结参考相对理想半圆存在明显偏离（最大径向差 5.48636 m）——"
            "这是为了让 15° 四车目标转角可行而做的几何妥协，必须在论文中披露。"],
           ["虚线（实际冻结参考）与点线（理想几何）没有混称为同一路线；改变过渡长度或半径需要新协议。",
            "该图只证明两条候选都跑完全程，不构成跟踪精度或受力优势结论。"],
           width=MID)

add_figure(doc, "../paper_v4/results/20260911_R2C_COMPARE02/r2c_comparison.png",
           "R2c 候选指标对比（含资格判定）",
           "来源：paper_v4/results/20260911_R2C_COMPARE02/comparison.md 与 comparison.json；"
           "单位为各指标原生单位（N、m、deg、1、s）。",
           ["λ1 请求转角峰值 15.0054157°，超出 15° 硬界 0.0054157°，资格 FAIL；其实际执行器角 14.9980547° "
            "不改变裁决。λ2 请求峰值 15.0000000° 通过，成为唯一 R3 候选。",
            "λ2 在点力峰值（345.88 N vs 358.86 N）、内力峰值（312.09 N vs 320.91 N）、轮胎利用率"
            "（0.0542 vs 0.0728）上更低，但差异属同批开发数据范围内。"],
           ["越界量级与 OSQP 求解容差一致，但不能据此自动豁免；处理为淘汰、不重跑、不事后裁剪。",
            "该选择仅来自同批开发数据，不构成独立或统计显著的优越性证明。"],
           width=WIDE)
doc.add_page_break()

# 4.6 R3
heading(doc, "4.6 R3 旧候选数值配对 FAIL（2026-09-11）", 2)
para(doc, "两条完整路线单条审计均 PASS（2379 周期、47.58 s、95.1283155163 m），但决定性 1 ms → 0.5 ms 配对 FAIL："
          "峰值相对差 0.889827%（通过 2% 门）、冲量向量 0.0456931%（通过 2% 门）、"
          "终态货物位置差 7.026279 mm（超过 1 mm 门）、终态航向差 0.013079743°（超过 0.01° 门）。"
          "力峰与冲量通过不允许抵消位姿失败。", space_after=6)
add_table(doc,
          ["项", "1 ms", "0.5 ms"],
          [["周期 / 时长 / 参考", "2379 / 47.58 s / 95.1283155 m", "2379 / 47.58 s / 95.1283155 m"],
           ["实际货物路径", "95.823031 m", "95.816101 m"],
           ["最大点力 / 最大内力范数", "343.844869 N / 309.964362 N", "346.931963 N / 313.241417 N"],
           ["最大轮胎利用率 / 最小支承", "0.084366 / 4675.573138 N", "0.090711 / 4675.573042 N"],
           ["最大构形误差", "0.013375987 m", "0.013486148 m"],
           ["货物位置 RMSE / 最大位置误差", "0.258457 m / 0.691428 m", "0.258685 m / 0.688858 m"],
           ["货物航向 RMSE", "0.847279°", "0.848292°"],
           ["求解 均值 / P95 / 最大（超 5 s 步数）",
            "3.108966 / 3.515841 / 5.246189 s（2 步）", "2.935452 / 3.034259 / 3.545605 s（0 步）"],
           ["墙钟", "7893.887 s", "7899.363 s"]],
          widths=[4.6, 6.0, 6.0], size=9, caption="表 4-7　R3 两条完整路线单条结果（单条审计均 PASS）")

add_figure(doc, "../paper_v4/results/20260911_R3_COMPARE01/r3_convergence.png",
           "R3 注册数值门：旧候选 1 ms → 0.5 ms（FAIL）",
           "来源：paper_v4/results/20260911_R3_COMPARE01/r3_convergence.json（status = FAIL，保留不覆盖）；"
           "四个面板分别为四点力峰最大相对差（%）、冲量向量最大相对差（%）、终态位置差（mm）、终态航向差（deg）；"
           "红色虚线 = 注册上限（2% / 2% / 1 mm / 0.01°）。",
           ["上排两个力相关指标远低于 2% 门；下排位姿指标明显越过注册线——位置 7.026279 mm（约 7 倍门限）、"
            "航向 0.013079743°（约 1.3 倍门限）。",
            "图中同时给出 2→1 ms 诊断点，可见两档差值随步长细化并未单调收敛到门内，说明该失败与晚段闭环分叉有关。"],
           ["必须区分两类数字：0.5 ms 对参考的货物位置 RMSE ≈ 0.258685 m（跟踪误差）与 7.026279 mm"
            "（两次仿真的相互差异）不能混为一谈。",
            "该 FAIL 已被 2026-09-15 的 EXP-R4-C 恢复链解决，但本文件与旧裁决继续保留，不被覆盖。"],
           width=WIDE)
doc.add_page_break()

# 4.7 R3 diag
heading(doc, "4.7 R3 诊断与根因定位（2026-09-11，只读，不出新动力学）", 2)
para(doc, "第一批 R3A 冻结输入短窗（42.00—44.50 s，125 个 20 ms 区间，不重求 MPC）判定为 PASS_BRANCH_A："
          "1 ms 与 0.5 ms 的终态位置差 1.7878e-10 m、航向差 2.7557e-9°、点力峰值相对差 0.0822070%、"
          "冲量相对差 0.000602301%，全部远低于门槛；自重放最大状态绝对差 3.28e-9（1 ms）与 0.0（0.5 ms）。"
          "结论：植物积分误差不是全程 R3 失败的主因，问题在闭环重求解的控制映射敏感性。", space_after=6)
add_table(doc,
          ["诊断", "结论"],
          [["QP_SENS02", "同一 QP 重复求解 3 次逐位一致，非线性复核 PASS → 无证据支持随机求解漂移或热启动是根因"],
           ["QP_TOL03", "两个登记容差候选通过诊断，首控制相对基准最大变化范数 0；未证明闭环改善"],
           ["QP_FD01", "4 个登记试验，默认 QP 逐位回归 PASS；单点结果不是闭环收敛证明"],
           ["R3_DIAG02", "同 tick 只读差异定位（DIAGNOSTIC_ONLY），见下图"]],
          widths=[2.8, 13.8], size=9, caption="表 4-8　QP 数值敏感性诊断（全部为单点 / 只读）")

add_figure(doc, "../paper_v4/results/20260911_R3_DIAG02/r3_divergence.png",
           "R3 同 tick 差异定位（DIAGNOSTIC_ONLY）",
           "来源：paper_v4/results/20260911_R3_DIAG02/r3_divergence.json；2379 个采样点、时间栅格完全一致、"
           "初始货物位姿差为 0；纵轴为位置差（mm）与航向差（deg），横轴为时间 s。",
           ["位置差在 42.90 s 首次超过 1 mm，航向差在 44.20 s 首次超过 0.01°；请求加速度差在 42.58 s 首次超过 "
            "0.01 m/s²，请求转角差在 36.44 s 首次超过 0.01°。",
            "最大同 tick 请求转角差 2.243402° @43.06 s、请求加速度差 0.594908 m/s² @43.12 s、"
            "逐点力差 56.2579 N @43.04 s。"],
           ["同 tick 指令差非零说明这是闭环数值敏感性问题，不是「相同冻结输入下只比较积分器」的试验。",
            "它本身不能在优化器与植物之间确定根因；R3A 已排除积分器为主因，但 QP 条件数、约束切换、"
            "有限差分敏感性与冻结雅可比等候选均尚未独立确认。"],
           width=WIDE)
doc.add_page_break()

# 4.8 U1-U3
heading(doc, "4.8 U1—U3 身份重建与计算成本（2026-09-13）", 2)
add_table(doc,
          ["批次", "结果", "裁决"],
          [["U1 IDENTITY01", "15 项候选 / 协议 / runner / controller / batch / 递归 plant 身份与只读物理重审全通过；"
                          "原 UNFROZEN_FULL01/status.json 保持 FAILED 未修改",
            "PASS_RECONSTRUCTED_IDENTITY"],
           ["U2 QP_COST01", "四点矩阵逐位回归、QP 求解与非线性复核 PASS；逐步雅可比两点总计 34.818888 / "
                         "32.300863 s，动力学线性化占 QP 构建 94.16% / 94.98%，OSQP 求解约 0.01 s",
            "PASS_DIAGNOSTIC，预算门 FAIL（均值 33.559876 s > 5 s）"],
           ["U3 PARALLEL_EQ01（8 进程）", "P/q/A/l/u/u_nom 与首控制逐位一致、非线性复核 PASS；单步总计 14.151784 s",
            "FAIL（超预算 183.04%）"],
           ["U3 PARALLEL_EQ02（16 进程）", "同上逐位一致；单步总计 14.684687 s", "FAIL（超预算 193.69%）"]],
          widths=[3.4, 9.6, 3.6], size=9, caption="表 4-9　U1—U3 身份、成本与并行等价性")
para(doc, "source_identity=false 的直接原因已定位：src/paper_v4_core/r2c_analyze.py 第 138—139 行把 runner SHA "
          "硬编码为旧值 da2a33b6…ff82，而新批次实际为 a0ba3123…5728。依赖「小工程错误最多修复两轮」与预算硬门，"
          "U4 停止：新 1 / 0.5 ms 完整 R3、R4、R5 均未启动。", size=10, space_after=8)

# 4.9 R4B
heading(doc, "4.9 R4-B 串并行等价性补证（2026-09-13）", 2)
add_table(doc,
          ["批次", "状态", "周期 / 子步 / solver", "墙钟", "峰值力", "内力", "轮胎利用率",
           "最小支承", "构形误差"],
          [["B2B_SERIAL01", "INTERRUPTED_INCOMPLETE", "45/125（第 46 条已求解未施加）", "—", "—", "—", "—", "—", "—"],
           ["B2B_SERIAL02", "COMPLETED", "125 / 1250 / 125", "3922.794941 s", "0.0", "0.0",
            "0.0052276379", "4905 N", "0.0035738138 m"],
           ["B2B_PARALLEL01", "COMPLETED", "125 / 1250 / 125", "1797.407461 s", "0.0", "0.0",
            "0.0052276379", "4905 N", "0.0035738138 m"]],
          widths=[2.6, 2.6, 2.6, 2.2, 1.4, 1.4, 1.8, 1.6, 1.8], size=8.5,
          caption="表 4-10　B2b 短窗闭环（42.00—44.50 s，125 周期，2 ms）")
para(doc, "串并行所有非墙钟 raw、全部 substeps、QP problem hashes 和首控制逐位一致，加速比 2.182474；"
          "并行平均墙钟 14.379260 s / 周期，约为 20 ms 控制周期的 719 倍，仍 FAIL_ORIGINAL_5S_BUDGET。"
          "正式比较 window_equivalence.json = FAIL（exit 20）：分析器用严格 time_s > 42.0 切片，"
          "而源边界实际保存为 42.00000000000001，多取上一边界；按整数周期对齐后全部非时间字段逐位一致，"
          "仅 raw 15 行 / substeps 150 行的 time_s 不同，最大差 7.105427357601002e-15 s。"
          "按第 22.3 节「浮点差异不得自动放宽」裁决 STOP_B3_NEEDS_INDEPENDENT_REVIEW。", size=10, space_after=6)

add_figure(doc, "../paper_v4/analysis/b2b_latest_review_20260913/01_equivalence_and_cost.png",
           "B2b 串并行等价性、源时间差与墙钟成本",
           "来源：paper_v4/analysis/b2b_latest_review_20260913（analysis.json、figure_manifest.json）；"
           "源文件为 SERIAL02 / PARALLEL01 / UNFROZEN_FULL01-2ms 的 raw.npz 与 substeps.npz；"
           "纵轴分别为物理差（原生单位）、时间残差（fs 量级）与墙钟（s）。",
           ["串并行物理差为精确零；与源时间戳的差异集中在飞秒（fs）量级（最大 7.1054e-15 s）；"
            "串行 3922.79 s vs 并行 1797.41 s，加速 2.18247 倍，两窗合计仍在冻结两小时预算内。"],
           ["本分析是本地独立诊断（原始正式 FAIL 不变），只覆盖该 2.5 s 短窗；"
            "窗口连接力为零，不能替代有力阶段的等价证据。"],
           width=WIDE)

add_figure(doc, "../paper_v4/analysis/b2b_latest_review_20260913/02_window_physics.png",
           "B2b 短窗轨迹、构形误差、连接力与逐步耗时",
           "来源同上；轨迹单位 m，构形误差单位 m，连接力单位 N（未平滑），耗时单位 s。",
           ["串并行轨迹完全重合；本窗连接力恒为 0 N，构形误差约 3.57 mm；逐步耗时呈周期性，"
            "与每 20 ms 求解一次 MPC 一致。"],
           ["零力是窗口数据的真实值，不是脱离、无接触或记录器故障的证据，也未经力律与间隙状态独立解释。",
            "该窗位于 42—44.5 s 晚段，不能代表整条路线（整程最大点力 288.06 N 出现在 27.154 s）。"],
           width=WIDE)

add_figure(doc, "../paper_v4/analysis/b2b_latest_review_20260913/03_window_controls.png",
           "B2b 请求转角、轮胎利用率与支承载荷",
           "来源同上；转角单位 deg，轮胎利用率无量纲（1），支承单位 N；显示串行曲线，"
           "并行物理 / 控制数组已独立校验与串行逐位一致。",
           ["请求转角在本窗内变化平稳；轮胎利用率约 0.0052，最小支承 4905 N，说明该窗口载荷远低于工作界。"],
           ["低载荷窗口的等价性不能外推到高载荷 / 出弯阶段；有力阶段等价由 26.66—27.66 s 窗口单独补证（见 4.10）。"],
           width=WIDE)
doc.add_page_break()

# 4.10 R4C
heading(doc, "4.10 R4-C 时间身份 → 有力窗口 → 完整路线 → 决定性配对 PASS（2026-09-14 / 15）", 2)
para(doc, "这是目前唯一一条通过的完整路线数值收敛链。时间身份 v1（TIME_IDENTITY01）因历史源 solver 缺少未记录的 "
          "problem_hashes 在裁决前停止，失败保留；v2 明确该字段为 NOT_APPLICABLE，协议 SHA256 = 77e98747…b50c0，"
          "状态 PASS_NEW_TIME_IDENTITY_CONTRACT：三方 raw / substeps / solver 时间严格单调、唯一映射登记整数 tick，"
          "最大浮点表示误差 7.105427357601002e-15 s，低于事前固定 32ε 界（1.8957e-13 s），9 项正 / 负例全 PASS。"
          "旧 B2b 正式 FAIL 保持不变。", space_after=6)

add_figure(doc, "../paper_v4/results/20260914_R4C_TIME_IDENTITY02/time_identity_audit.png",
           "EXP-R4-C 时间身份独立重审",
           "来源：paper_v4/results/20260914_R4C_TIME_IDENTITY02（time_identity_report.json、figure_manifest.json）；"
           "纵轴为时间戳表示误差（s，对数或放大量级）与登记 32ε 界；横轴为三点三方时间流。",
           ["所有时间戳都能唯一归属到登记的整数 tick，表示误差比 32ε 界小约 50 倍；"
            "全部非时间物理量仍保持逐位比较，9 项正 / 负例通过。"],
           ["该裁决只释放有力窗口登记；它不覆盖旧 EXP-R4-B 的正式 FAIL，也不放宽任何物理门。"],
           width=WIDE)

para(doc, "有力窗口登记：冻结 2 ms 源中全程最大点力首次出现于 connector0、t=27.154 s，值 288.0596665626036 N；"
          "按规则把 1 s 窗口中心对齐到最近 20 ms tick，登记 26.66—27.66 s（初态 tick 1333、50 周期、500 子步），"
          "不另选更有利窗口。协议 v1 / v2 各因一个 SHA 手工录入错误被身份门在 QP 构造前拒绝（零 QP / 动力学消耗）；"
          "v3 协议 SHA256 = 09fbd10b…42d6，12 项身份零不匹配。", size=10, space_after=6)

add_figure(doc, "../paper_v4/results/20260914_R4C_FORCE_QP01/force_qp_preflight_qa.png",
           "有力窗口 QP 预检（QA 修正版）",
           "来源：paper_v4/results/20260914_R4C_FORCE_QP01（force_qp_report.json、qp_arrays.npz、"
           "figure_qa_correction.json）；比较对象为同一登记起点的串行与 8 进程 QP；"
           "纵轴为矩阵 / 边界 / 首控制差异与耗时（s）。",
           ["状态恢复完整：P、q、A、l、u、u_nom 与首控制逐位一致，串 / 并非线性复核均 PASS；"
            "六组差异均为 0。串行构建 36.444446 s，8 进程构建 13.940386 s。"],
           ["首版图对相等无穷边界计算 inf−inf 产生 NaN，导致零差异面板空白；原图保留，本图仅为后处理修正，"
            "未重跑 QP。",
            "仍保留 FAIL_ORIGINAL_5S_BUDGET / OFFLINE_ONLY：预检通过不代表实时性。"],
           width=WIDE)

add_table(doc,
          ["批次", "状态", "周期 / 子步 / solver", "墙钟", "峰值点力", "最大内力",
           "轮胎利用率", "最小支承", "构形误差"],
          [["R4C_FORCE_SERIAL01", "COMPLETED", "50 / 500 / 50", "1550.584120 s", "288.0596665626036 N",
            "176.987239 N", "0.045657", "4690.5808 N", "0.012997624 m"],
           ["R4C_FORCE_PARALLEL01", "COMPLETED", "50 / 500 / 50", "702.142416 s", "288.0596665626036 N",
            "176.987239 N", "0.045657", "4690.5808 N", "0.012997624 m"]],
          widths=[3.4, 2.2, 2.4, 2.2, 2.6, 2.0, 1.6, 1.8, 1.8], size=8.5,
          caption="表 4-11　有力窗口闭环：登记峰值被精确复现")

add_figure(doc, "../paper_v4/results/20260914_R4C_FORCE_SERIAL01/figures/force_window_diagnostics_qa.png",
           "有力窗口单条诊断：Centralized Full-State Physical Model Predictive Control（串行）",
           "来源：paper_v4/results/20260914_R4C_FORCE_SERIAL01（metrics.json、figures/figure_manifest.json）；"
           "方法全名标注为 Centralized Full-State Physical Model Predictive Control (serial)；"
           "工况 26.66—27.66 s 登记有力窗口、单次确定性仿真；力曲线未平滑；"
           "面板含货物 X/Y（m）、构形误差（mm）、点力范数（N）、请求 / 实际转角（deg）、"
           "优化墙钟（s）、轮胎利用率（1）与支承（N）。",
           ["50 / 50 周期、500 / 500 子步、50 条 solver 完成，stderr 为空；与冻结 2 ms 源按整数 tick 对齐后"
            "全部非时间物理量逐位一致，峰值点力精确复现 288.0596665626036 N。"],
           ["本条只证明该实现完成了登记窗口；串并行等价性要等配对比较（本图 science_status = "
            "RUN_COMPLETED_SINGLE_IMPLEMENTATION_ONLY_COMPARISON_PENDING）。",
            "原 5 s 离线优化预算仍然失败。"],
           width=WIDE)

add_figure(doc, "../paper_v4/results/20260914_R4C_FORCE_PARALLEL01/figures/force_window_diagnostics_qa.png",
           "有力窗口单条诊断：Centralized Full-State Physical Model Predictive Control（8 进程）",
           "来源：paper_v4/results/20260914_R4C_FORCE_PARALLEL01（同上结构与单位）。",
           ["50 / 500 / 50 完成，墙钟 702.142416 s，相对串行 1550.584120 s 加速 2.208361 倍；"
            "物理量与串行逐位一致。"],
           ["单条图只证明本条运行完成；等价性由下方配对图给出。"],
           width=WIDE)

add_figure(doc, "../paper_v4/results/20260914_R4C_FORCE_COMPARE01/figures/force_window_equivalence.png",
           "有力窗口串并行配对：PASS_FORCE_WINDOW_EQUIVALENCE",
           "来源：paper_v4/results/20260914_R4C_FORCE_COMPARE01（force_window_equivalence.json、"
           "budget_review.json）；比较串行、8 进程与冻结源三方；"
           "面板含货物 XY（m）、raw 物理差（原生单位）、未平滑 2 ms 力峰（N）、实际转角（deg）、"
           "时间残差（fs）、优化墙钟（s）。",
           ["15 项检查全 true：串 / 并及与源的全部非时间物理数组逐位一致、substeps 逐位一致、"
            "QP 哈希与三方首控制逐位一致、9 组时间流全部通过 32ε 合同（最大误差 3.5527e-15 s）。",
            "并行实测 14.04284832 s / 周期，2379 周期外推 9.279982 h，相对 12 h 门名义余量 2.720018 h（22.67%），"
            "据此只释放完整 1 ms 协议准备。"],
           ["该比较只能释放 12 h 预算复核，不是完整路线精度或收敛结论。",
            "外推不是完工保证；原 5 s/步预算继续 FAIL。"],
           width=WIDE)

add_table(doc,
          ["项", "完整 1 ms（R4C_FULL_1MS01）", "完整 0.5 ms（R4C_FULL_0P5MS01）"],
          [["状态 / 周期", "COMPLETED / 2379 of 2379", "COMPLETED / 2379 of 2379"],
           ["参考 / 时长", "95.1283155163 m / 47.58 s", "95.1283155163 m / 47.58 s"],
           ["墙钟（是否触及 12 h 截止）", "33308.693095 s（9.2524 h），否", "33601.870952 s（9.3339 h），否"],
           ["实际货物路径", "95.379401 m", "95.379410 m"],
           ["最大点力 / 最大预测点力", "288.059652 N / 288.058037 N", "288.059651 N / 288.058036 N"],
           ["最大内力范数", "180.164761 N", "180.164761 N"],
           ["最大轮胎利用率 / 最小支承", "0.0499304 / 4677.137644 N", "0.0499304 / 4677.137561 N"],
           ["最大构形误差", "0.0129976244 m", "0.0129976246 m"],
           ["货物位置 RMSE / 最大位置误差", "0.255770897 m / 0.679060093 m", "0.255770194 m / 0.679056796 m"],
           ["货物航向 RMSE", "0.903907°", "0.903913°"],
           ["最大请求 / 实际转角", "15.000000° / 14.998566°", "15.000000° / 14.998566°"],
           ["求解 均值 / P95 / 最大（超 5 s 步数）",
            "13.727750 / 14.584679 / 19.616598 s（2379 / 2379）",
            "13.585393 / 13.937637 / 18.299252 s（2379 / 2379）"],
           ["独立审计", "22 项全 PASS", "22 项全 PASS"]],
          widths=[4.4, 6.2, 6.2], size=8.5,
          caption="表 4-12　EXP-R4-C 完整路线单条结果（同一候选 EXP-R3-unfrozen-v1）")

add_figure(doc, "../paper_v4/results/20260914_R4C_FULL_1MS01/figures/full_route_1ms_diagnostics.png",
           "完整路线六面板：1 ms Plant Maximum Integration Step",
           "来源：paper_v4/results/20260914_R4C_FULL_1MS01（metrics.json、single_run_audit.json、"
           "figures/figure_manifest.json）；方法全名 Centralized Full-State Physical Model Predictive Control；"
           "信息边界 = 集中全仿真状态、离线诊断上界；单次确定性仿真；力峰未平滑；"
           "字段单位：XY m、位置误差 m、航向误差 deg、力 N、转角 deg、墙钟 s、轮胎利用率 1、支承 N。",
           ["2379 / 2379 周期完成，早于 12 h 截止且 stderr 为空；独立 single_run_audit.json 的 22 项完整性、"
            "求解 / 非线性、受力、轮胎、支承、请求 / 实际转角、源身份与指标复算全部 PASS。",
            "路线 / 参考轨迹、跟踪误差、未平滑力峰、转角界、优化耗时、轮胎利用率与支承全部可读。"],
           ["单条通过不等于数值收敛（需 0.5 ms 与配对比较），也不代表实时性：2379 步全部超过原 5 s 预算，"
            "均值 13.72775 s。",
            "该结果是集中全状态离线诊断，不支持分布式或通信鲁棒主张。"],
           width=WIDE)

add_figure(doc, "../paper_v4/results/20260914_R4C_FULL_0P5MS01/figures/full_route_0.5ms_diagnostics.png",
           "完整路线六面板：0.5 ms Plant Maximum Integration Step",
           "来源：paper_v4/results/20260914_R4C_FULL_0P5MS01（同上结构与单位）。",
           ["2379 / 2379 周期完成，墙钟 9.3339 h，未触及 07:48:23 截止；22 项独立审计全 PASS；"
            "峰值点力 288.059651 N、最大内力 180.164761 N、最大轮胎利用率 0.0499304、最小支承 4677.138 N、"
            "最大构形误差 12.9976 mm；位置 / 航向 RMSE 0.255770 m / 0.903913°。"],
           ["跟踪误差不能因数值门通过而隐藏；2379 步仍全部超过 5 s 预算（均值 13.585393 s），"
            "仍是离线集中全状态诊断。"],
           width=WIDE)

add_figure(doc, "../paper_v4/results/20260915_R4C_FULL_COMPARE01/figures/full_route_pair_diagnostics.png",
           "完整路线配对诊断：1 ms 与 0.5 ms 的轨迹、差值、受力、冲量、输入与耗时",
           "来源：paper_v4/results/20260915_R4C_FULL_COMPARE01（r3_convergence.json、figures/figure_manifest.json，"
           "状态 PASS）；方法全名 Centralized Full-State Physical Model Predictive Control；"
           "字段单位：XY m、位置 mm、航向 deg、力 N、冲量 N·s、转角 deg、墙钟 s。",
           ["左上：两条轨迹几乎完全重合；右上：同 tick 位置差与航向差全程远低于门限（虚线为终态门参考）。",
            "左下：未平滑最大点力两条几乎重合，峰值 288.0597 N；中右：四个连接器的冲量向量范数对比一致。",
            "下排：闭环输入分叉在约 42 s 之后放大（最大请求转角差约 1.2°），与 R3_DIAG02 的晚段控制分叉定位一致；"
            "优化墙钟箱线远高于原 5 s 预算线。"],
           ["该图说明两条不同积分步长的闭环确实在晚段出现输入分叉，但四项注册数值门仍然通过。",
            "「通过数值门」不等于「实现实时控制」（5 s 预算线在图中明显被超越），也不代表 Koopman 或通信优势。"],
           width=WIDE)

add_figure(doc, "../paper_v4/results/20260915_R4C_FULL_COMPARE01/figures/r3_registered_gates.png",
           "EXP-R4-C 决定性数值分辨率四门：PASS",
           "来源：paper_v4/results/20260915_R4C_FULL_COMPARE01/r3_convergence.json；"
           "四个面板分别为四点力峰最大相对差（%）、冲量向量最大相对差（%）、终态位置差（mm）、终态航向差（deg）；"
           "每组左柱 = 观测值，右柱 = 注册上限（2% / 2% / 1 mm / 0.01°）。",
           ["观测值全部远低于注册上限：峰值相对差 4.5892936e-8（0.0000045893%）、冲量向量 3.2463998e-6"
            "（0.0003246400%）、终点位置 8.7018595e-6 m（0.00870186 mm）、终点航向 4.1915693e-5°。",
            "证据身份 12 项全部 true，含 coarse/fine 审计 PASS、同任务书父 SHA、同计算身份与同控制时间栅格。"],
           ["该 PASS 只证明同一集中全状态候选在 1 / 0.5 ms 最大植物积分步下满足登记的数值分辨率与单条物理 / "
            "证据门。",
            "不证明 Koopman、通信鲁棒、分布式、实时或材料安全优势；旧 R3 与 B2b 失败文件继续保留。"],
           width=WIDE)
doc.add_page_break()

# 4.11 C0
heading(doc, "4.11 C0 接口资格与 R4-P1-2ms（2026-09-15，进行中）", 2)
para(doc, "C0 经历三轮：C0_01 通过后复查发现长 runner 未锁定 C0 报告与图表 manifest（加父报告状态 / SHA、"
          "图表状态 / SHA 门后重跑）；C0_02 之后的正式预检把 Python 元组与 JSON 数组误判为绝对参数不同"
          "（仅统一身份序列化表示，未改任何参数数值、模型或阈值）；C0_03 全量重跑通过，"
          "正式协议 SHA256 = 3b12c8cb…64ef，状态 PASS_C0_R4_READY。", space_after=6)
add_table(doc,
          ["组", "状态构造", "四点力（N）", "串行构建", "8 进程构建"],
          [["P1 初始", "同参数初始化状态", "0 / 0 / 0 / 0", "35.242283 s", "13.978472 s"],
           ["P1 有力", "同参数状态 + 车辆 1 世界 x 偏移 +0.03 m", "800.85 / 0 / 0 / 0", "35.626563 s", "13.634458 s"],
           ["P2 初始", "同参数初始化状态", "0 / 0 / 0 / 0", "35.420044 s", "16.319176 s"],
           ["P2 有力", "同参数状态 + 车辆 1 世界 x 偏移 +0.03 m", "878.85 / 0 / 0 / 0", "34.955160 s", "14.088655 s"]],
          widths=[2.0, 6.2, 3.2, 2.6, 2.6], size=9,
          caption="表 4-13　C0 四组固定 QP 回归（矩阵逐位一致、首控制逐位一致、非线性复核 PASS）")
para(doc, "10 项负例全部在建输出前拒绝：旧冻结雅可比候选（ALGORITHM_IDENTITY_MISMATCH）、错误父 R3 报告"
          "（PARENT_R3_NOT_PASS）、缺候选字段（CANDIDATE_MISMATCH）、错误参数 / 错误步长 / 重复输出"
          "（RUN_MANIFEST_MATRIX_MISMATCH）、错误协议源 SHA（SOURCE_IDENTITY_MISMATCH:experiment.md）、"
          "未过图表门（PARENT_FIGURE_NOT_PASS）、已存在输出目录（REFUSING_EXISTING_OUTPUT）、"
          "存在活动 run（ACTIVE_RUN_PRESENT）。", size=10, space_after=6)

add_figure(doc, "../paper_v4/results/20260915_POST_R3_C0_03/c0_contract_coverage.png",
           "POST-R3 C0 迁移与负例合同覆盖：PASS_C0_R4_READY",
           "来源：paper_v4/results/20260915_POST_R3_C0_03（c0_report.json、figure_manifest.json，"
           "协议 SHA256 = 3b12c8cb…64ef）；横轴为判定结果（左 FAIL / 右 PASS 或已拒绝）；"
           "纵轴逐条列出 5 项正向检查、10 项负例与参数 / 清单检查。",
           ["15 个条目全部落在 PASS / rejected 侧：positive_contract、all_negative_cases_rejected、"
            "all_fixed_qp_checks_pass、run_manifest_six_unique_rows、absolute_parameter_tables_registered 均为 true；"
            "10 个负例覆盖候选身份、父报告、参数、步长、协议 SHA、图表门、输出目录与活动 run。"],
           ["C0 是接口资格门，不是科学结果：它只释放 R4-P1-2ms，且保留 FAIL_ORIGINAL_5S_BUDGET / OFFLINE_ONLY。",
            "C0_01 与 C0_02 保留为被替代的工程证据（见附录 B）。"],
           width=WIDE)

heading(doc, "R4-P1-2ms：当前正在运行的首个长单元", 3)
add_table(doc,
          ["项", "值"],
          [["协议", "protocol/R4_P1_2MS_20260915.json，SHA-256 = e41b6633…1dd5"],
           ["固定候选", "EXP-R3-unfrozen-v1（逐步更新雅可比、中心差分步长 1、8 进程、λ=2）"],
           ["结果目录", "results/20260915_R4_P1_2MS01"],
           ["启动", "2026-09-15 10:00:08，PID 27780"],
           ["绝对截止", "2026-09-15 21:53:02"],
           ["最后检查点", "completed_ticks = 525 / 2379，time_s = 10.5，reference_distance_m = 21.0，"
                       "写入时间 2026-09-15 12:02:47；进程存活、stderr 为空、已保存 solver 条目与非线性复核 PASS"],
           ["当前裁决", "C0_PASS / R4_P1_2MS_RUNNING / R4_P1_1MS_AND_LATER_BLOCKED"]],
          widths=[3.0, 13.6], size=9.5)
para(doc, "运行中状态不等于科学 PASS；必须等待单条完成、独立 21 / 22 项审计、六面板 PNG / SVG 生成及视觉 QA "
          "全部通过后，才允许冻结下一单元。", size=10, space_after=8)
doc.add_page_break()

# ------------------------------------------------------------------ 5 数字总表
heading(doc, "5. 关键数字总表", 1)
heading(doc, "5.1 同一 Centralized Full-State Physical Model Predictive Control 的完整路线结果", 3)
add_table(doc,
          ["批次", "参数点", "最大植物步", "加载方式", "最大点力 (N)", "最大内力 (N)",
           "最大构形误差 (m)", "轮胎利用率", "最小支承 (N)", "位置 RMSE (m)", "航向 RMSE (°)",
           "求解均值 (s)", "墙钟 (h)"],
          [["R2C_L1_01", "P0", "2 ms", "冻结雅可比", "358.861345", "320.906730", "0.013854411", "0.072837",
            "4675.5896", "—", "—", "—", "2.13"],
           ["R2C_L2_01", "P0", "2 ms", "冻结雅可比", "345.882087", "312.087919", "0.013488169", "0.054235",
            "4675.5730", "0.258509", "0.848671", "2.979847", "2.04"],
           ["R3_02/1ms", "P0", "1 ms", "冻结雅可比", "343.844869", "309.964362", "0.013375987", "0.084366",
            "4675.5731", "0.258457", "0.847279", "3.108966", "2.19"],
           ["R3_02/0.5ms", "P0", "0.5 ms", "冻结雅可比", "346.931963", "313.241417", "0.013486148", "0.090711",
            "4675.5730", "0.258685", "0.848292", "2.935452", "2.19"],
           ["UNFROZEN_FULL01/2ms", "P0", "2 ms", "逐步雅可比", "288.059667", "180.164760", "0.012997624",
            "0.049930", "4677.1375", "0.255770", "0.903910", "32.635780", "21.66"],
           ["R4C_FULL_1MS01", "P0", "1 ms", "逐步雅可比 + parallel8", "288.059652", "180.164761",
            "0.012997624", "0.049930", "4677.1376", "0.255771", "0.903907", "13.727750", "9.2524"],
           ["R4C_FULL_0P5MS01", "P0", "0.5 ms", "逐步雅可比 + parallel8", "288.059651", "180.164761",
            "0.012997624", "0.049930", "4677.1376", "0.255770", "0.903913", "13.585393", "9.3339"]],
          widths=[3.0, 1.1, 1.3, 2.6, 1.9, 1.8, 1.7, 1.3, 1.6, 1.5, 1.4, 1.6, 1.2], size=7.5)
para(doc, "全部为集中全状态离线诊断；没有任何一条达到 20 ms 实时性（原 5 s/步预算全部 FAIL）。", size=9.5, space_after=8)

heading(doc, "5.2 数值收敛门汇总", 3)
add_table(doc,
          ["比较", "峰值相对差", "冲量向量相对差", "终态位置差", "终态航向差", "裁决"],
          [["100 m P0 1→0.5 ms", "9.5153e-7", "2.1502e-5", "9.447e-9 m", "6.104e-9°", "PASS"],
           ["100 m P1 1→0.5 ms", "1.4295e-6", "1.0173e-5", "1.359e-8 m", "1.082e-8°", "PASS"],
           ["100 m P2 1→0.5 ms", "2.3645e-6", "1.0005e-5", "1.379e-9 m", "3.402e-10°", "PASS"],
           ["回头弯 R3A 冻结输入 1→0.5 ms", "8.2207e-4", "6.0230e-6", "1.7878e-10 m", "2.7557e-9°", "PASS_BRANCH_A"],
           ["回头弯旧候选 1→0.5 ms", "8.8983e-3", "4.5693e-4", "7.026279e-3 m", "0.013079743°", "FAIL"],
           ["回头弯 EXP-R4-C 1→0.5 ms", "4.5893e-8", "3.2464e-6", "8.7019e-6 m", "4.1916e-5°", "PASS"],
           ["注册上限", "2%", "2%", "1 mm", "0.01°", "—"]],
          widths=[5.0, 2.4, 2.8, 2.4, 2.4, 2.0], size=9)

heading(doc, "5.3 计算成本与预算", 3)
add_table(doc,
          ["项", "实测", "门", "裁决"],
          [["冻结雅可比单步（QP 构建＋求解＋复核）", "4.158—4.270 s", "≤ 5 s", "PASS"],
           ["逐步雅可比串行单步（均值）", "33.559876 s", "≤ 5 s", "FAIL"],
           ["逐步雅可比 8 进程单步", "14.151784 s", "≤ 5 s", "FAIL"],
           ["逐步雅可比 16 进程单步", "14.684687 s", "≤ 5 s", "FAIL"],
           ["完整 1 ms 求解均值", "13.727750 s", "≤ 20 ms 实时 / ≤ 5 s", "FAIL"],
           ["完整 0.5 ms 求解均值", "13.585393 s", "同上", "FAIL"],
           ["完整 1 ms / 0.5 ms 墙钟", "9.2524 h / 9.3339 h", "≤ 12 h", "PASS"],
           ["8 进程相对串行加速", "2.182—2.208 倍", "—", "记录"],
           ["瓶颈定位", "动力学线性化占 QP 构建 94%—95%；OSQP 求解约 0.01 s", "—", "记录"]],
          widths=[4.6, 5.6, 4.2, 2.2], size=9)

heading(doc, "5.4 参考几何", 3)
add_table(doc,
          ["项", "值"],
          [["冻结回头弯路线总长 / 过渡段 / 半径", "95.1283155163 m / 11 m / 11.5 m"],
           ["最大曲率", "0.0869565 1/m"],
           ["相对理想瞬时半圆最大径向偏离", "5.48636 m"],
           ["航向改变 π 误差", "1.034e-12 rad"],
           ["参考速度", "2 m/s"],
           ["100 m 诊断 P0 实际货物路径", "102.81025 m"]],
          widths=[7.0, 9.6], size=9.5)
doc.add_page_break()

# ------------------------------------------------------------------ 6 失败清单
heading(doc, "6. 失败、负结果与工程问题清单", 1)
heading(doc, "6.1 科学 / 物理失败（保留，不追认）", 3)
add_table(doc,
          ["编号", "事实", "性质"],
          [["F1", "真实回头弯三条输入器全部 15 kN 硬停止（75.92 / 50.836 / 81.72 m）", "物理 / 控制能力失败"],
           ["F2", "旧候选回头弯 1→0.5 ms 终态位置 7.026279 mm、航向 0.013079743° 超门",
            "数值收敛失败（后经 EXP-R4-C 恢复链解决）"],
           ["F3", "旧候选 2 ms 批次 status.json = FAILED（source_identity=false）",
            "工程身份失败（已由 U1 重建式重审，F3 不因此消失）"],
           ["F4", "原 5 s/步计算预算：2379 / 2379 步全部超限", "工程 / 实时性失败（保留）"],
           ["F5", "新候选航向 RMSE 相对旧候选退化约 6.51%", "负结果（必须披露）"],
           ["F6", "连接器强度来源为 numerical_legacy_unverified", "来源缺口"],
           ["F7", "提交版论文来源、确认池盲性、完整 mandatory suite", "E00 PARTIAL"]],
          widths=[1.6, 9.6, 5.4], size=9)

heading(doc, "6.2 工程过程问题与修复效果", 3)
add_table(doc,
          ["问题", "处理", "效果"],
          [["前台会话回收长 Python 进程（SERIAL01 45/125 中断）",
            "隐藏后台＋独立 stdout/stderr＋进程内绝对截止＋15 s 存活探针",
            "SERIAL02 / PARALLEL01 及后续长任务完整完成"],
           ["分析器严格 time_s > 42.0 边界误取", "保留正式 FAIL，另做整数 tick 对齐诊断",
            "确认全部非时间字段逐位一致，仅时间戳差 7.1054e-15 s"],
           ["历史源 solver 无 problem_hashes", "v1 失败保留，v2 登记 NOT_APPLICABLE",
            "时间身份与物理身份分离验证 PASS"],
           ["有力窗口协议两个 SHA 手工录入错误", "身份门在 QP 构造前拒绝，两轮内冻结 v3 并程序化核对 12 项",
            "零不匹配，未浪费 QP / 动力学预算"],
           ["QP 图 inf−inf 产生 NaN", "保留原图，仅后处理生成 _qa 版", "六组差异 0 可见，未重跑 QP"],
           ["单条图无标签面板出现空图例框", "保留首图，只修改后处理图例选择", "串 / 并 / 完整路线 _qa 版均通过打开检查"],
           ["重复进程检查把 PowerShell 自身误判为目标", "筛选限定为 Python 进程", "只启动一个 parallel8 进程"],
           ["绘图脚本把 COMPLETED 与 PASS 误作同一枚举；直接执行时缺 src 导入路径",
            "分别核对状态、显式加入只读源码路径，确认空目录后删除重试", "六面板 PNG/SVG 交付门关闭，未重跑仿真"],
           ["比较器 numpy.bool_ 不能 JSON 序列化；空父字段比较无证据意义",
            "显式转 Python bool，改为父任务书 SHA＋共享计算源码身份核对", "独立比较重跑 PASS，无需重跑约 18.59 h 动力学"],
           ["C0 报告 / 图表未锁定；元组 vs JSON 数组误判", "加入父报告 / 图表 SHA 门；仅统一身份序列化",
            "C0_03 全量通过，释放且只释放 R4-P1-2ms"]],
          widths=[5.0, 6.4, 5.2], size=8.5)

heading(doc, "6.3 必须保留的边界声明", 3)
bullets(doc, [
    "连接力为零的 B2b 窗口不能替代有力阶段等价证据。",
    "集中全状态诊断上界不能进入分布式 H1—H6 主比较。",
    "仿真数值不能称为实测、HIL 或材料安全证明；刚体平面模型只能说明「拉伸载荷 / 潜在受拉趋势」，"
    "不能判定「撕裂」。",
    "数值收敛 PASS 不代表实时性、Koopman 贡献或通信鲁棒性 PASS。",
])
doc.add_page_break()

# ------------------------------------------------------------------ 7 结论边界
heading(doc, "7. 结论边界：现在能写什么、不能写什么", 1)
heading(doc, "7.1 现在可以写（有证据）", 3)
for i, t in enumerate([
    "冻结四车—货物植物在 100 m 阶跃激励下，三参数点 × 三档最大植物积分步的数值分辨率子门 PASS"
    "（最差 1→0.5 ms 峰值相对差 2.3645e-6）。",
    "集中全状态物理模型预测控制在名义参数下能完成 95.1283155163 m 冻结回头弯参考（2379 周期 / 47.58 s）。",
    "EXP-R4-C 恢复链已 PASS：同一候选 EXP-R3-unfrozen-v1 的 1 ms 与 0.5 ms 完整路线在峰值（4.5893e-8）、"
    "冲量（3.2464e-6）、终点位置（8.7019e-6 m）、终点航向（4.1916e-5°）四项注册门上全部通过，"
    "且两条单条审计 22 项全 PASS。",
    "逐步雅可比候选在单个名义 2 ms 开发工况下降低连接力：点力峰值 345.882087 → 288.059667 N（−16.72%），"
    "内部力范数 312.087919 → 180.164760 N（−42.27%）。",
    "代价与退化同时存在：航向 RMSE 0.848671° → 0.903910°（+6.51%），平均单步求解 2.98 → 32.64 s（约 10.95 倍）。",
    "串行与 8 进程实现在 QP 层与短窗闭环层逐位等价（B2a 四点、B2b 短窗、有力窗口 9 组时间流 32ε 内、"
    "登记峰值精确复现）。",
    "真实回头弯失败的定位结论：请求几何 / Ackermann 残差约 1e-16 m/s 且请求无饱和时仍失败，"
    "说明「请求不符合阿克曼」不是充分解释；三条失败均表现为前部连接点力与横向拉开代理持续上升。",
    "C0 接口资格 PASS，10 项负例在建输出前被拒绝。",
]):
    para(doc, "（%d）%s" % (i + 1, t), size=10, space_after=4, indent=0.3)

heading(doc, "7.2 现在不能写（缺证据）", 3)
for t in [
    "Koopman 预测创新（固定线性 / 可训练 lift / 双线性 / 保护残差 / 三专家）已被验证有独立收益 —— E02 未完成。",
    "网络中断 / 丢包 / 时延下本方法有优势 —— E06 / E09 未运行。",
    "已实现实时控制 —— 5 s/步与 20 ms 周期均 FAIL。",
    "分布式 / 通信受限架构已验证 —— 现有闭环全部为集中全状态诊断上界。",
    "完整 plant_gate / E01 通过 —— 100 m 只是 27 条计划中的 9 条子集。",
    "货物「撕裂」减少或材料安全 —— 无材料强度 / 台架数据。",
    "已补齐独立物理验证或 HIL / 实测 —— E15 为 RESOURCE_PENDING。",
    "22 项审稿意见已关闭 —— 全部为 OPEN / NOT_RUN / 各类 PENDING。",
]:
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(3)
    style_run(p.add_run("✗　" + t), size=10)

doc.add_page_break()

# ------------------------------------------------------------------ 8 下一步
heading(doc, "8. 下一步（已冻结的顺序与门）", 1)
add_table(doc,
          ["顺序", "工作", "门与预算"],
          [["1", "完成 R4-P1-2ms（运行中）",
            "单条结束 → 独立审计＋六面板 PNG/SVG＋视觉 QA；任一门失败即停止，不启动 P1-1ms"],
           ["2", "C1/R4 六条：P1 与 P2 各 2 / 1 / 0.5 ms",
            "每条 ≤ 12 h，六条总动态上限 72 h；P1 失败不继续 P2；每参数点独立数值比较"],
           ["3", "C2/R5 两条：P0、同候选 2 ms，无噪声复现后基础噪声 seed 5105",
            "单条 ≤ 12 h，总 24 h；只证明合法信息接口转接，不称已验证分布式 / 通信保护"],
           ["4", "C3 执行器九短片段＋C4 物理门核销",
            "九片段总 ≤ 2 h；逐项匹配原 E01 证据，旧输入器与新候选不得混算"],
           ["5", "K/E02 预测资格与状态闭合",
            "预测门未过则保留合格基础预测器推进允许分支，不包装为主创新"],
           ["6", "M/N/B：真实多步约束优化与合法信息 → 六方法核心比较、时延单开关、共同误差界 → 强基线 / 混合网络",
            "每阶段先建机器可读 run_manifest，检查唯一键、配对齐全、角色合法、数量符合"],
           ["7", "A/S/V/T/W：观测 / 适应 / 故障 / 消融、敏感性 / 适用域、独立验证、理论、论文与 22 项意见回复",
            "E15 无设备保持 RESOURCE_PENDING；E16 无法证明则收缩主张"]],
          widths=[1.3, 7.2, 8.1], size=9)
para(doc, "逐实验出图制度（强制）：每个 run 输出 figures/，含 PNG（建议 300 dpi）＋ SVG 矢量版、可重绘脚本、"
          "figure_manifest.json、中文 figures/README.md；science_status 与 figure_status 分列；"
          "只完成 JSON 而缺图不能标交付完成；失败 / 超时也须输出已接受段的诊断图或状态 / 覆盖矩阵。", size=10, space_after=8)
para(doc, "当前总状态：C0_PASS；R4_P1_2MS_RUNNING（截止 2026-09-15 21:53:02）；R4_P1_1MS_AND_LATER_BLOCKED；"
          "EXP_R4C_RECOVERY_PASS；R3_NUMERICAL_PAIR_PASS；ORIGINAL_5S_BUDGET_FAIL_RETAINED；"
          "E00_PARTIAL / E01_PARTIAL / E02_NOT_RUN / R5_NOT_STARTED。",
     size=10, bold=True, space_after=8)

doc.add_page_break()

# ------------------------------------------------------------------ 附录 A
heading(doc, "附录 A　paper_v4 之前的 Koopman 预测阶段（2026-09-02 — 09-08）", 1)
para(doc, "来源声明：本附录不是 paper_v4_results 内的产物，而是从工作日志 paper_v4/koopman_work_log.md、"
          "paper_v4/logs/{koopman_work_log.md, exp_status.md, exp_solution.md, 20260911_*.md, 20260911_E00/*} "
          "与 inputs/experiment_EXP-R{1,2,4,R4B}_*.md 中提取的历史摘要（数值为日志逐字引用，属二手整理，"
          "未从原始 npz/CSV 重算）。列出它是为了说明当前 K1/K1N 的冻结权重从何而来，以及哪些预测侧尝试已得负结论。",
     size=10, space_after=8)
heading(doc, "A.1 主线结论", 3)
bullets(doc, [
    "固定线性 11 维输入（control11）明显优于旧 7 维输入：真纯线性 11-over-7 的 20 步改善 D7 +74.0%（1 步 +67.2%）、"
    "D9 合并 +48.0%、D5 +16.6%、D2 +7.3%、D4 +4.6%、D10/D11 +9.3/+15.0%；但 D1 −3.8%、D0 −1.2%（退化）。",
    "7 维旧输入存在不可恢复的接口缺陷：control7 只用 requested 转角列，四车加速度偏置从未进入 control7"
    "（D7 差分最大 0.2281 m/s²、活跃 83.3%；D9A 0.1728 m/s²）→ KR0 = INPUT_CONTRACT_BLOCKED（exit 21）。",
    "保护残差系列多轮止步于「最差工况退化」门：KFIX F4 BLOCKED（macro MH16 +20.08% 但 scenario_degradation 失败，"
    "真实最差工况为 D1）；SB4 BLOCKED（SB16EQ +18.57%、SB16UP +18.88%，双臂失败）；"
    "KG G5 无组通过全部门，selected=null，T2 外层 20 步 +19.5111%（CI95 [17.3943%, 21.7516%]）"
    "但 1 步退化 D2 7.0132%、D7 10.6122%、D8 3.8719%、D9 3.7544%，D5 一步最大误差统计退化 25.5711%；"
    "GPU batch1 20 步含力解码 median 4.09095 ms / P99 4.76159 ms（超 1/2 ms 门）。",
    "PAPER-Q1 正式预测门 = K1 NEGATIVE_RESULT（exit 20，科学门失败）：三个 repeat 合并 20 步改善 "
    "14.369673% / 17.778392% / 13.555056%，5/5 折为正，family bootstrap 95% CI = [14.258225%, 16.196400%]，"
    "40 步新增发散 0/15；但完整质量门仅 14/15 —— repeat1/fold0 的 D1 一步 J 退化 4.301699%、"
    "D2 一步 J 退化 6.361436%。勘误：这两个数为分母下限 0.02 的保护口径，普通相对增长为 17.4126% / 12.6594%。"
    "因此 K2/K3/C0/C1/B0/N0/A0/E0 全部停止。",
    "代码审计（KC-AUDIT-20260905 = PARTIAL/REPAIR_REQUIRED）发现两处实现不合规：kc3_diagnose.py 的一步中间 "
    "gamma 点实际按 γ² 缩放；refine_loss.py::residual_loss 调四组 smooth_rmse 而非注释所写的加权 MSE"
    "（3 组旧课程标 NONCONFORMING_RMSE_CURRICULUM）。fold0 inner 纯线性 M20 = 0.1015493688103903，"
    "三 seed 下降率 −0.487754% / −0.377865% / −0.742152%，55 项保护均未过。",
    "v3w 部署与冻结权重来源：19 项测试全通过（15.45 s）；真实 fold0 956 个拟合窗口；输入还原误差 0；"
    "连接力恒等式最大误差 9.379e-13 N、系统内力恒等式最大误差 4.547e-13 N；45 点校准提名 adaptive_guard、"
    "calibrated=true，内层 20 步改善率中位数 16.522299919738145%。后台 run 20260905_221832_KC_BG02 即任务书"
    "第 5.6 节引用的冻结模型来源（repeat 0/1/2 对应 γ = 0.75 / 0.50 / 0.50，训练种子 997100 / 997200 / 997300）。",
    "KR-A = short_guard_enabled=true：冻结物理 / 连接器 109 项通过，正式 run 墙钟 11.453 秒，"
    "45/45 校准单元 stats 最大差 1.1102e-16，330 状态、两 policy 共 660 门记录，DEV_SEEN 外层回放 60 次。",
], size=10)
heading(doc, "A.2 已统一登记为无效的历史闭环批次（不追认）", 3)
para(doc, "CTRL-MATH-AUDIT（2026-09-08，只读）确认旧 ABL 三批实际控制器以固定反馈增益产生输入，"
          "未加载 Koopman 权重、未执行多步预测优化，并存在发送时间戳错位、突发丢包转移概率写反、"
          "回头弯参考不真实、旧积分配置、回退模式无正常退出等问题。", size=10, space_after=4)
add_table(doc,
          ["9 月 7 日批次", "记录数", "完成数", "登记"],
          [["ABL-CORE", "4860", "2766", "INVALID_FOR_REGISTERED_COMPARISON"],
           ["ABL-DELAY", "900", "180", "INVALID_FOR_REGISTERED_COMPARISON"],
           ["ABL-COMMON", "360", "0", "INVALID_FOR_REGISTERED_COMPARISON"]],
          widths=[4.0, 2.6, 2.6, 6.4], size=9.5)
para(doc, "原始峰值记录 C_6C0770CC7DEAE9E1/K1N.npz = 2840.5910810123128 N，与 CSV 一致，"
          "但不据此宣布 Koopman / 管状 MPC / 时延补偿有效或无效。", size=10, space_after=6)
heading(doc, "A.3 与本汇总正文的关系", 3)
bullets(doc, [
    "上述负结论解释了为什么 experiment.md 第 5.6 节把冻结模型固定为 "
    "koopman_predict_v3w_results\\runs\\20260905_221832_KC_BG02\\formal\\repeat{0,1,2}\\fold0\\fixed_guard\\train\\best.pt，"
    "并把保护残差方法降级为「有界补证」而非主创新。",
    "E02（预测资格）至今 NOT_RUN；预测侧的任何优势声明在本次汇总时点仍缺证据。",
    "本附录的数值不得与 paper_v4 的 20260909—20260915 批次混合统计或合并成同一数据集。",
], size=10)

doc.add_page_break()

# ------------------------------------------------------------------ 附录 B
heading(doc, "附录 B　其余图表版本（被替代版本、QA 前后版本、只读冒烟版本）", 1)
para(doc, "以下图片为被替代版本、只读冒烟版本或 QA 前后版本，保留以供追溯；科学裁决以正文所述及 QA 版本为准。", size=10, space_after=8)

add_figure(doc, "20260909_E01_100M03/figure_100m_P0_0p5ms.png",
           "100 m 六面板（100M03，证据不完整版）",
           "来源：paper_v4_results/20260909_E01_100M03（本版本未保存 Fz、轮胎利用率与真实子步数组）；单位同正文图。",
           ["该批 9 条均 PASS 且数值结论可复算，但交付证据不完整，因此降级为 PILOT_EVIDENCE_INCOMPLETE，"
            "不计作完整 E01 交付。"],
           ["这是被 100M04 / 100M05 取代的版本；不得用错位标签或缺失字段制作论文图。"],
           width=WIDE)
add_figure(doc, "20260909_E01_100M03/figure_convergence_100m.png",
           "100 m 收敛门（100M03，证据不完整版）",
           "来源：paper_v4_results/20260909_E01_100M03/convergence_100m.json；此版本无 evidence_audits 块。",
           ["可见 6 组配对同样低于注册门，与 100M05 的峰值差完全一致（如 P2 1→0.5 ms 均为 2.3645e-6）。"],
           ["缺少逐条证据审计块，故不作为正式交付证据。"],
           width=MID)

add_figure(doc, "../paper_v4/results/20260910_R2B_COMPARE01/r2b_comparison.png",
           "R2b 候选指标（首版，语义错误版本）",
           "来源：paper_v4/results/20260910_R2B_COMPARE01（comparison.json）；指标单位同表 4-6。",
           ["首版把 18 s 短片段的排序误写为 R3 选择；数值本身与修正版一致。"],
           ["该目录保留为错误分析版本，selected_for_r3 已由 COMPARE02 恢复为 null。"],
           width=WIDE)
add_figure(doc, "../paper_v4/results/20260910_R2B_COMPARE01/r2b_paths.png",
           "R2b 候选轨迹（首版）",
           "来源同上；横 / 纵坐标 m。",
           ["两条候选的 36 m 入弯片段轨迹几乎重合。"],
           ["短片段不覆盖回头弯主体与出弯段，不能据此判断完整路线可行性。"],
           width=MID)
add_figure(doc, "../paper_v4/results/20260910_R2B_COMPARE02/r2b_comparison.png",
           "R2b 候选指标（语义修正版）",
           "来源：paper_v4/results/20260910_R2B_COMPARE02；本次为有效比较版本。",
           ["λ=2 内力峰值比 λ=1 低约 0.60%（202.616392 N vs 203.839616 N），仅用于确定 R2c 运行顺序。"],
           ["开发选优不是独立收益证明；个别求解超过 5 s 说明当时尚非实时实现。"],
           width=WIDE)
add_figure(doc, "../paper_v4/results/20260910_R2B_COMPARE02/r2b_paths.png",
           "R2b 候选轨迹（语义修正版）",
           "来源同上。",
           ["与首版图形一致；修正只发生在比较逻辑层，未改物理或数值。"],
           ["同上：仅覆盖 18 s 入弯片段。"],
           width=MID)

add_figure(doc, "../paper_v4/results/20260910_R2C_ANALYZER_SMOKE01/r2c_comparison.png",
           "R2c 分析器只读冒烟指标（第一次）",
           "来源：paper_v4/results/20260910_R2C_ANALYZER_SMOKE01；两个 copy 候选指标完全相同。",
           ["用于验证比较器与绘图链路可用；点力峰值 345.882087 N、内力 312.087919 N、构形误差 13.488 mm。"],
           ["冒烟结果不能作为 R3 候选选择的科学依据。"],
           width=WIDE)
add_figure(doc, "../paper_v4/results/20260910_R2C_ANALYZER_SMOKE01/r2c_paths.png",
           "R2c 分析器只读冒烟轨迹（第一次）",
           "来源同上。",
           ["轨迹覆盖完整回头弯，含实际冻结参考与理想半圆对比。"],
           ["仅为冒烟复算，未新增动力学。"],
           width=MID)
add_figure(doc, "../paper_v4/results/20260910_R2C_ANALYZER_SMOKE02/r2c_comparison.png",
           "R2c 分析器只读冒烟指标（第二次）",
           "来源：paper_v4/results/20260910_R2C_ANALYZER_SMOKE02。",
           ["第二次冒烟用于确认结果可复现；与第一次逐项一致。"],
           ["同上：不能作为候选选择依据。"],
           width=WIDE)
add_figure(doc, "../paper_v4/results/20260910_R2C_ANALYZER_SMOKE02/r2c_paths.png",
           "R2c 分析器只读冒烟轨迹（第二次）",
           "来源同上。",
           ["与第一次图形一致，支持链路确定性。"],
           ["仅为冒烟复算。"],
           width=MID)

add_figure(doc, "../paper_v4/results/20260910_R2C_COMPARE01/r2c_comparison.png",
           "R2c 失败分析版指标（比较器逻辑错误，保留）",
           "来源：paper_v4/results/20260910_R2C_COMPARE01（comparison.md，状态 FAIL）。",
           ["该版比较器错误地要求两个候选都 PASS，与任务书「两者均失败才停止」冲突，因此总体判定 FAIL。"],
           ["保留为失败分析版本；逐项硬门与数值未变，有效裁决见 COMPARE02。"],
           width=WIDE)
add_figure(doc, "../paper_v4/results/20260910_R2C_COMPARE01/r2c_paths.png",
           "R2c 失败分析版轨迹",
           "来源同上。",
           ["λ1 与 λ2 的完整轨迹均存在且几乎重合。"],
           ["图形本身不含资格判定；λ1 的淘汰依据是请求转角 15.0054157° > 15°。"],
           width=MID)

add_figure(doc, "../paper_v4/results/20260911_R3_DIAG01/r3_divergence.png",
           "R3 同 tick 差异定位（首版 DIAG01）",
           "来源：paper_v4/results/20260911_R3_DIAG01/r3_divergence.json；作图时出现空 legend 警告，数值有效。",
           ["首版已定位晚段差异放大的现象；因显示代码问题另建 DIAG02，未覆盖本目录。"],
           ["属诊断图，不改变 R3 正式 FAIL 裁决。"],
           width=WIDE)

add_figure(doc, "../paper_v4/results/20260914_R4C_FORCE_QP01/force_qp_preflight.png",
           "有力窗口 QP 预检（原版，含 NaN 空面板）",
           "来源：paper_v4/results/20260914_R4C_FORCE_QP01/force_qp_preflight.png（原图保留）。",
           ["原图对相等无穷边界计算 inf−inf 产生 NaN，导致零差异面板空白，视觉上无法确认「差异为 0」。"],
           ["仅后处理生成了 _qa 版；未重跑 QP，科学裁决与数值不变。"],
           width=WIDE)

add_figure(doc, "../paper_v4/results/20260914_R4C_FORCE_SERIAL01/figures/force_window_diagnostics.png",
           "有力窗口单条诊断（串行，原版，含空图例框）",
           "来源：paper_v4/results/20260914_R4C_FORCE_SERIAL01/figures/force_window_diagnostics.png。",
           ["原图在无标签的构形误差面板调用了 legend，出现空图例框，其余面板正常。"],
           ["保留原图；修正版 _qa 只删除空框，未重算仿真数据。"],
           width=WIDE)
add_figure(doc, "../paper_v4/results/20260914_R4C_FORCE_PARALLEL01/figures/force_window_diagnostics.png",
           "有力窗口单条诊断（8 进程，原版，含空图例框）",
           "来源：paper_v4/results/20260914_R4C_FORCE_PARALLEL01/figures/force_window_diagnostics.png。",
           ["同上，仅绘图后处理问题。"],
           ["修正版 _qa 为正式引用版本。"],
           width=WIDE)

add_figure(doc, "../paper_v4/results/20260915_POST_R3_C0_01/c0_contract_coverage.png",
           "C0 合同覆盖（C0_01，被替代）",
           "来源：paper_v4/results/20260915_POST_R3_C0_01（协议 SHA256 = d870c8d9…f11456）。",
           ["本轮已显示全部正向检查与负例通过，但复查发现长任务 runner 未显式锁定 C0 报告与图表 manifest。"],
           ["保留为被替代的工程证据；C0_01 的通过不能作为 R4 释放依据。"],
           width=WIDE)
add_figure(doc, "../paper_v4/results/20260915_POST_R3_C0_02/c0_contract_coverage.png",
           "C0 合同覆盖（C0_02，被替代）",
           "来源：paper_v4/results/20260915_POST_R3_C0_02（协议 SHA256 = ca798094…1e7adf）。",
           ["之后正式 R4 预检把 Python 元组与 JSON 数组误判为绝对参数不同（ABSOLUTE_PARAMETER_IDENTITY_MISMATCH），"
            "仅统一身份序列化表示，未改任何参数数值、模型或阈值。"],
           ["保留为被替代的工程证据；错误协议在创建输出前退出。"],
           width=WIDE)

# ------------------------------------------------------------------ 附录 C
doc.add_page_break()
heading(doc, "附录 C　图片文件索引", 1)
para(doc, "下列 40 张 PNG 全部已内嵌于本文档（正文 24 张 + 附录 B 16 张）；"
          "主结果目录另有 15 个同名 SVG 矢量版。路径以 paper_v4_results 为基准。", size=10, space_after=6)
add_table(doc,
          ["#", "相对路径", "所属实验"],
          [["1", "20260909_E01_100M05/figure_100m_P0_0p5ms.png", "E01 100 m"],
           ["2", "20260909_E01_100M05/figure_convergence_100m.png", "E01 100 m"],
           ["3", "20260909_E01_100M05/figure_connector_directions_100m.png", "E01 100 m"],
           ["4", "20260909_E01_HFAIL01/hairpin_failures.png", "E01 回头弯"],
           ["5", "20260909_R1_03/failure_timeline.png", "R1"],
           ["6", "20260909_E01_100M03/figure_100m_P0_0p5ms.png", "E01 100 m（不完整版）"],
           ["7", "20260909_E01_100M03/figure_convergence_100m.png", "E01 100 m（不完整版）"],
           ["8", "../paper_v4/results/20260910_R2B_COMPARE01/r2b_comparison.png", "R2b 首版"],
           ["9", "../paper_v4/results/20260910_R2B_COMPARE01/r2b_paths.png", "R2b 首版"],
           ["10", "../paper_v4/results/20260910_R2B_COMPARE02/r2b_comparison.png", "R2b 修正版"],
           ["11", "../paper_v4/results/20260910_R2B_COMPARE02/r2b_paths.png", "R2b 修正版"],
           ["12", "../paper_v4/results/20260910_R2C_ANALYZER_SMOKE01/r2c_comparison.png", "R2c 冒烟"],
           ["13", "../paper_v4/results/20260910_R2C_ANALYZER_SMOKE01/r2c_paths.png", "R2c 冒烟"],
           ["14", "../paper_v4/results/20260910_R2C_ANALYZER_SMOKE02/r2c_comparison.png", "R2c 冒烟"],
           ["15", "../paper_v4/results/20260910_R2C_ANALYZER_SMOKE02/r2c_paths.png", "R2c 冒烟"],
           ["16", "../paper_v4/results/20260910_R2C_COMPARE01/r2c_comparison.png", "R2c 失败分析版"],
           ["17", "../paper_v4/results/20260910_R2C_COMPARE01/r2c_paths.png", "R2c 失败分析版"],
           ["18", "../paper_v4/results/20260911_R2C_COMPARE02/r2c_comparison.png", "R2c 正式"],
           ["19", "../paper_v4/results/20260911_R2C_COMPARE02/r2c_paths.png", "R2c 正式"],
           ["20", "../paper_v4/results/20260911_R3_COMPARE01/r3_convergence.png", "R3（FAIL）"],
           ["21", "../paper_v4/results/20260911_R3_DIAG01/r3_divergence.png", "R3 诊断首版"],
           ["22", "../paper_v4/results/20260911_R3_DIAG02/r3_divergence.png", "R3 诊断修正版"],
           ["23", "../paper_v4/analysis/b2b_latest_review_20260913/01_equivalence_and_cost.png", "R4-B B2b"],
           ["24", "../paper_v4/analysis/b2b_latest_review_20260913/02_window_physics.png", "R4-B B2b"],
           ["25", "../paper_v4/analysis/b2b_latest_review_20260913/03_window_controls.png", "R4-B B2b"],
           ["26", "../paper_v4/results/20260914_R4C_TIME_IDENTITY02/time_identity_audit.png", "R4-C 时间身份"],
           ["27", "../paper_v4/results/20260914_R4C_FORCE_QP01/force_qp_preflight_qa.png", "R4-C QP（QA）"],
           ["28", "../paper_v4/results/20260914_R4C_FORCE_QP01/force_qp_preflight.png", "R4-C QP（原版）"],
           ["29", "../paper_v4/results/20260914_R4C_FORCE_SERIAL01/figures/force_window_diagnostics_qa.png",
            "R4-C 有力窗口串行（QA）"],
           ["30", "../paper_v4/results/20260914_R4C_FORCE_SERIAL01/figures/force_window_diagnostics.png",
            "R4-C 有力窗口串行（原版）"],
           ["31", "../paper_v4/results/20260914_R4C_FORCE_PARALLEL01/figures/force_window_diagnostics_qa.png",
            "R4-C 有力窗口 8 进程（QA）"],
           ["32", "../paper_v4/results/20260914_R4C_FORCE_PARALLEL01/figures/force_window_diagnostics.png",
            "R4-C 有力窗口 8 进程（原版）"],
           ["33", "../paper_v4/results/20260914_R4C_FORCE_COMPARE01/figures/force_window_equivalence.png",
            "R4-C 有力窗口配对"],
           ["34", "../paper_v4/results/20260914_R4C_FULL_1MS01/figures/full_route_1ms_diagnostics.png",
            "R4-C 完整 1 ms"],
           ["35", "../paper_v4/results/20260914_R4C_FULL_0P5MS01/figures/full_route_0.5ms_diagnostics.png",
            "R4-C 完整 0.5 ms"],
           ["36", "../paper_v4/results/20260915_R4C_FULL_COMPARE01/figures/full_route_pair_diagnostics.png",
            "R4-C 决定性配对"],
           ["37", "../paper_v4/results/20260915_R4C_FULL_COMPARE01/figures/r3_registered_gates.png",
            "R4-C 四门"],
           ["38", "../paper_v4/results/20260915_POST_R3_C0_01/c0_contract_coverage.png", "C0（被替代）"],
           ["39", "../paper_v4/results/20260915_POST_R3_C0_02/c0_contract_coverage.png", "C0（被替代）"],
           ["40", "../paper_v4/results/20260915_POST_R3_C0_03/c0_contract_coverage.png", "C0 正式"]],
          widths=[1.0, 11.6, 4.0], size=5.5)

para(doc, "", space_after=6)
para(doc, "未出图的批次（诚实登记）：U1/U2/U3 成本与并行等价、B2a 四点 QP 回归、R1_01/R1_02（空目录）、"
          "100M01/100M02（仅 0 字节 stdout/stderr 日志，无 run 目录、无原因记录）、R3_UNFROZEN_SMOKE01、"
          "E01_G01/G02/G03/D01/S01/S02/S03/HS01—HS04/HR00（仅 JSON/npz）。"
          "任务书第 25.3—25.4 节已把这些类型纳入「必须出图」映射，属历史缺图，"
          "需按规则从原始数据后处理补齐或登记缺图原因。", size=9.5, color=RGBColor(0x80, 0x30, 0x00), space_after=8)

para(doc, "本文档由项目既有 JSON / MD / PNG 证据整理而成，未修改任何仿真数据、冻结协议或历史裁决。"
          "所有裁决文字均引用原始文件字段值；失败与负结果照实保留。"
          "附录 A 为工作日志二手整理，已单独标注来源与不确定性。",
     size=9.5, italic=True, color=RGBColor(0x59, 0x59, 0x59), space_after=4)

doc.save(OUT)
print("SAVED:", OUT)
print("figures embedded:", _fig_no[0])
