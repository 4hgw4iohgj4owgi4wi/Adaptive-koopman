// Node-oriented editable pro deck builder.
// Run this after editing SLIDES, SOURCES, and layout functions.
// The init script installs a sibling node_modules/@oai/artifact-tool package link
// and package.json with type=module for shell-run eval builders. Run with the
// Node executable from Codex workspace dependencies or the platform-appropriate
// command emitted by the init script.
// Do not use pnpm exec from the repo root or any Node binary whose module
// lookup cannot resolve the builder's sibling node_modules/@oai/artifact-tool.

const fs = await import("node:fs/promises");
const path = await import("node:path");
const { Presentation, PresentationFile } = await import("@oai/artifact-tool");

const W = 1280;
const H = 720;

const DECK_ID = "tf12-history-report";
const OUT_DIR = "D:\\LEARNING\\ZNN\\ZNN\\Adaptive-koopman\\Adaptive-koopman-main\\paper_dcn_tf12_draft\\history_modification_report\\output";
const REF_DIR = "D:\\LEARNING\\ZNN\\ZNN\\Adaptive-koopman\\Adaptive-koopman-main\\paper_dcn_tf12_draft\\history_modification_report";
const SCRATCH_DIR = path.resolve(process.env.PPTX_SCRATCH_DIR || path.join("tmp", "slides", DECK_ID));
const PREVIEW_DIR = path.join(SCRATCH_DIR, "preview");
const VERIFICATION_DIR = path.join(SCRATCH_DIR, "verification");
const INSPECT_PATH = path.join(SCRATCH_DIR, "inspect.ndjson");
const MAX_RENDER_VERIFY_LOOPS = 3;

const INK = "#101214";
const GRAPHITE = "#30363A";
const MUTED = "#687076";
const PAPER = "#F7F4ED";
const PAPER_96 = "#F7F4EDF5";
const WHITE = "#FFFFFF";
const ACCENT = "#27C47D";
const ACCENT_DARK = "#116B49";
const GOLD = "#D7A83D";
const CORAL = "#E86F5B";
const TRANSPARENT = "#00000000";

const TITLE_FACE = "Poppins";
const BODY_FACE = "Lato";
const MONO_FACE = "Aptos Mono";

const FALLBACK_PLATE_DATA_URL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=";

const SOURCES = {
  timeline:
    "Local notebooks and runtime files in Adaptive-koopman-main dated 2026-04-03 to 2026-04-22, including tf3.ipynb, tf11_A2_pre.ipynb, tf11_A1_pre.ipynb, tf12_pre.ipynb, tf11_a1_runtime.py, and tf12_runtime.py.",
  manuscript:
    "paper_dcn_tf12_draft/manuscript_zh_word_export.md, especially the contribution mapping, module comparison table, and A1 baseline-vs-TF12 result table.",
  report:
    "paper_dcn_tf12_draft/history_modification_report/tf12_improvements_history.md reconstructed from local artifacts because the workspace is not a git repository.",
};

const SLIDES = [
  {
    "type": "cover",
    "kicker": "TF12 HISTORY REPORT",
    "title": "TF12 改进说明与\n历史修改汇报",
    "subtitle": "从 Adaptive Koopman baseline 到抗网络退化协同运输控制的完整升级路径",
    "moment": "从单体鲁棒控制到协同运输网络韧性",
    "notes": "开场先交代工作定位：这不是简单的版本号迭代，而是研究对象、控制栈和评价体系的完整升级。",
    "sources": [
      "timeline",
      "report"
    ]
  },
  {
    "type": "cards",
    "kicker": "WORK POSITIONING",
    "title": "这项工作到底改了什么",
    "subtitle": "真正的变化不是从 TF11 变成 TF12，\n而是把 baseline 的适应性 Koopman 控制扩展成协同搬运与网络韧性闭环。",
    "cards": [
      [
        "问题升级",
        "研究对象从单体非线性系统变成四车刚性载荷协同运输，任务目标从单车跟踪扩展到团队一致性与载荷平顺性。"
      ],
      [
        "缺口识别",
        "baseline 解决的是模型失配，但没有显式解决多车协同中的通信时延、丢包、约束退化和安全回退。"
      ],
      [
        "TF12 定义",
        "TF12 保留 Adaptive Koopman 内核，同时新增通信质量感知一致性、时延补偿、约束收紧和退化回退。"
      ]
    ],
    "notes": "这一页要把口径钉死：TF12 与 baseline 的差别，核心在网络韧性和任务化建模，而不是换个版本号。",
    "sources": [
      "report",
      "manuscript"
    ]
  },
  {
    "type": "timeline",
    "kicker": "VERSION TIMELINE",
    "title": "tf3 到 tf12 的四阶段演进",
    "subtitle": "从原型验证、工程整合，到协同搬运成型和网络韧性增强。",
    "phases": [
      [
        "04-03 至 04-13",
        "原型验证期",
        "tf3 到 tf6：把 baseline 的 Koopman 学习迁移到车辆 Frenet 跟踪任务，先解决“模型能否学、控制能否跑”。"
      ],
      [
        "04-14 至 04-16",
        "工程整合期",
        "tf7 到 tf10：加入全局配置、训练测试统一和论文图产出链路，开始从试验稿转向可复现实验工程。"
      ],
      [
        "04-17 至 04-20",
        "协同搬运成型期",
        "tf11：建立四车刚性载荷团队模型，出现 A2 paper-like 控制栈，并形成 A1 任务化 baseline。"
      ],
      [
        "04-20 至 04-22",
        "网络韧性提升期",
        "tf12：新增通信质量感知一致性、时延补偿、约束收紧、退化回退和通信诊断，形成投稿主线。"
      ]
    ],
    "notes": "这一页建议按阶段讲，不要逐个 notebook 念名字。每个阶段都强调“解决了什么新问题”。",
    "sources": [
      "timeline",
      "report"
    ]
  },
  {
    "type": "grid",
    "kicker": "CHANGE MAP",
    "title": "相对于 baseline 的六类实质性改动",
    "subtitle": "TF12 的主要增量不是单一算法点，\n而是一条完整的任务化升级链。",
    "gridCards": [
      [
        "研究对象",
        "从单体系统扩展到四车刚性载荷协同运输。"
      ],
      [
        "团队建模",
        "从单车状态扩展为载荷中心 Frenet 团队模型。"
      ],
      [
        "任务数据",
        "离线训练数据改为服务于协同搬运的团队级数据。"
      ],
      [
        "学习内核",
        "保留 Adaptive Koopman 思想，但任务化为车辆团队双线性升维。"
      ],
      [
        "控制闭环",
        "新增通信质量感知一致性、时延补偿、约束收紧、退化回退。"
      ],
      [
        "评价体系",
        "从单一跟踪误差扩展到连接一致性、载荷受力和计算时间。"
      ]
    ],
    "notes": "这一页是整场汇报的总导航，后面各页都在展开这六点。",
    "sources": [
      "report",
      "manuscript"
    ]
  },
  {
    "type": "grid",
    "kicker": "MODEL & DATA",
    "title": "建模与离线学习的关键升级",
    "subtitle": "这一部分回答：\n为什么 TF12 不是拿四辆车并排跑四个单车控制器。",
    "gridCards": [
      [
        "载荷中心状态",
        "团队中心状态统一描述路径推进、横向偏差、航向误差和速度状态。"
      ],
      [
        "角点映射",
        "先建团队中心模型，再映射到四个角点车辆，而不是独立建四套车。"
      ],
      [
        "柔性连接",
        "显式跟踪 Δs、Δe_y、Δψ 等连接偏差，使车辆拉扯进入模型和约束。"
      ],
      [
        "团队级数据集",
        "720 条轨迹、1400 个快照、5 组运行配置，覆盖 1 车到 4 车变化模式。"
      ],
      [
        "双线性升维",
        "保留 Koopman 升维与在线双线性自适应，但对象已变成协同搬运团队。"
      ],
      [
        "高置信更新",
        "在线更新只在高置信样本上触发，并做范数裁剪与稳定性投影。"
      ]
    ],
    "notes": "强调这里的升级是“任务化落地”，把 baseline 真正嵌进了协同运输系统。",
    "sources": [
      "report",
      "manuscript"
    ]
  },
  {
    "type": "grid",
    "kicker": "CONTROL STACK",
    "title": "TF12 新增的网络韧性控制栈",
    "subtitle": "这是 TF12 相对于 AKE-baseline 最关键、\n也最能支撑论文创新性的部分。",
    "gridCards": [
      [
        "通信质量感知一致性",
        "链路越差，团队融合越保守，避免多车横向控制相互冲突。"
      ],
      [
        "时延补偿",
        "延迟到达的远端状态不直接使用，而是按运动学向前预测。"
      ],
      [
        "约束收紧",
        "全局通信质量越差，输入边界越保守，降低网络退化时的激进动作。"
      ],
      [
        "退化回退",
        "通信质量低于阈值时，团队命令混入安全控制器而不是盲信名义解。"
      ],
      [
        "通信诊断",
        "显式记录通信质量、时延、丢包和收紧强度等关键闭环指标。"
      ],
      [
        "系统意义",
        "四个模块不是补丁堆叠，而是把网络状态真正接入 MPC 闭环。"
      ]
    ],
    "notes": "如果只讲一页创新点，这一页最关键。它定义了 TF12 与 baseline 的根本边界。",
    "sources": [
      "manuscript",
      "report"
    ]
  },
  {
    "type": "grid",
    "kicker": "SAFETY & ENGINEERING",
    "title": "安全保护与工程化改进",
    "subtitle": "这部分不一定是最强算法创新，但决定了系统能否稳定跑完任务。",
    "gridCards": [
      [
        "紧急稳定保护",
        "横向误差或航向误差越界时，附加稳定转角并增强制动。"
      ],
      [
        "进度监督",
        "防止路径推进回退，保证团队中心沿参考路径单调前进。"
      ],
      [
        "状态裁剪",
        "对 e_y、e_ψ、v_y、r 等关键状态限制可接受范围。"
      ],
      [
        "尾段衰减",
        "任务后段减弱协同校正，减少终点附近的互相拉拽。"
      ],
      [
        "稳定运行",
        "tf11_A1 runtime 与 tf12 runtime 已形成可复现的主实验入口。"
      ],
      [
        "论文化输出",
        "结果图、主任务指标和双语文稿已被整理成投稿和汇报可用的形式。"
      ]
    ],
    "notes": "这里要强调“工程完整性”三个字。顶会/顶刊会在意系统是否真的可运行，而不只是概念上可行。",
    "sources": [
      "timeline",
      "manuscript",
      "report"
    ]
  },
  {
    "type": "results",
    "kicker": "A1 RESULTS",
    "title": "与 AKE-baseline 的核心结果对比",
    "subtitle": "最重要的收益发生在横向稳定性、连接一致性、载荷冲击和平滑性上。",
    "notes": "结果解读要主动承认纵向 RMSE 上升 9.9%，并解释为更保守的团队协调换来了更稳的横向姿态与更小的载荷冲击。",
    "sources": [
      "manuscript",
      "report"
    ]
  },
  {
    "type": "compare",
    "kicker": "MANUSCRIPT REWRITE",
    "title": "论文写作层面的历史修改",
    "subtitle": "后期的一个重要工作，不只是补结果，而是把整篇文章改成更符合一区审稿逻辑的结构。",
    "beforeTitle": "初版主要问题",
    "beforeBullets": [
      "比较对象容易被理解成 TF12 对历史版本号，而不是对 baseline。",
      "引言没有按本文模块系统梳理相关研究，贡献-方法映射不够紧。",
      "方法部分写得像功能堆叠，缺少从系统模型到控制器的展开顺序。",
      "实验部分缺少与方法一一对应的图位和证据链。"
    ],
    "afterTitle": "重构后的改法",
    "afterBullets": [
      "把比较基线明确改成 task-aligned AKE-baseline。",
      "按 Koopman、车辆控制、协同搬运、MPC、通信韧性五条文献线重写引言。",
      "按建模、离线数据、升维学习、MPC 与安全保护重写方法部分。",
      "按离线数据、动力学学习、控制效果、单车误差、受力对比预留完整图题。"
    ],
    "notes": "这一页适合说明我不仅改了代码，也把文章重写成了真正能投的结构。",
    "sources": [
      "manuscript",
      "report"
    ]
  },
  {
    "type": "cards",
    "kicker": "REVIEWER VIEW",
    "title": "一区 top 审稿人会如何看这些修改",
    "subtitle": "最强卖点是系统创新与任务贴合度；\n最大风险是理论说明和 ablation 仍需补强。",
    "cards": [
      [
        "会认可的点",
        "问题升级真实，网络状态被显式引入控制闭环，结果又能落到载荷力和连接一致性这种任务级指标上。"
      ],
      [
        "会追问的点",
        "Koopman 理论本身的新意有限；还需要更强的 ablation、递归可行性说明和纵向误差 trade-off 解释。"
      ],
      [
        "一句话总结",
        "不是改版本号，而是把 Adaptive Koopman 扩展成协同运输网络韧性控制框架。"
      ]
    ],
    "notes": "最后用这页收口，既讲创新，也讲风险，口径会更像成熟研究汇报。",
    "sources": [
      "report",
      "manuscript"
    ]
  }
];

const inspectRecords = [];

async function pathExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function readImageBlob(imagePath) {
  const bytes = await fs.readFile(imagePath);
  if (!bytes.byteLength) {
    throw new Error(`Image file is empty: ${imagePath}`);
  }
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}

async function normalizeImageConfig(config) {
  if (!config.path) {
    return config;
  }
  const { path: imagePath, ...rest } = config;
  return {
    ...rest,
    blob: await readImageBlob(imagePath),
  };
}

async function ensureDirs() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const obsoleteFinalArtifacts = [
    "preview",
    "verification",
    "inspect.ndjson",
    ["presentation", "proto.json"].join("_"),
    ["quality", "report.json"].join("_"),
  ];
  for (const obsolete of obsoleteFinalArtifacts) {
    await fs.rm(path.join(OUT_DIR, obsolete), { recursive: true, force: true });
  }
  await fs.mkdir(SCRATCH_DIR, { recursive: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  await fs.mkdir(VERIFICATION_DIR, { recursive: true });
}

function lineConfig(fill = TRANSPARENT, width = 0) {
  return { style: "solid", fill, width };
}

function recordShape(slideNo, shape, role, shapeType, x, y, w, h) {
  if (!slideNo) return;
  inspectRecords.push({
    kind: "shape",
    slide: slideNo,
    id: shape?.id || `slide-${slideNo}-${role}-${inspectRecords.length + 1}`,
    role,
    shapeType,
    bbox: [x, y, w, h],
  });
}

function addShape(slide, geometry, x, y, w, h, fill = TRANSPARENT, line = TRANSPARENT, lineWidth = 0, meta = {}) {
  const shape = slide.shapes.add({
    geometry,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: lineConfig(line, lineWidth),
  });
  recordShape(meta.slideNo, shape, meta.role || geometry, geometry, x, y, w, h);
  return shape;
}

function normalizeText(text) {
  if (Array.isArray(text)) {
    return text.map((item) => String(item ?? "")).join("\n");
  }
  return String(text ?? "");
}

function textLineCount(text) {
  const value = normalizeText(text);
  if (!value.trim()) {
    return 0;
  }
  return Math.max(1, value.split(/\n/).length);
}

function requiredTextHeight(text, fontSize, lineHeight = 1.18, minHeight = 8) {
  const lines = textLineCount(text);
  if (lines === 0) {
    return minHeight;
  }
  return Math.max(minHeight, lines * fontSize * lineHeight);
}

function assertTextFits(text, boxHeight, fontSize, role = "text") {
  const required = requiredTextHeight(text, fontSize);
  const tolerance = Math.max(2, fontSize * 0.08);
  if (normalizeText(text).trim() && boxHeight + tolerance < required) {
    throw new Error(
      `${role} text box is too short: height=${boxHeight.toFixed(1)}, required>=${required.toFixed(1)}, ` +
        `lines=${textLineCount(text)}, fontSize=${fontSize}, text=${JSON.stringify(normalizeText(text).slice(0, 90))}`,
    );
  }
}

function wrapText(text, widthChars) {
  const normalized = normalizeText(text);
  if (!/\s/.test(normalized) && normalized.length > widthChars) {
    const chunks = [];
    for (let idx = 0; idx < normalized.length; idx += widthChars) {
      chunks.push(normalized.slice(idx, idx + widthChars));
    }
    return chunks.join("\n");
  }
  const words = normalized.split(/\s+/).filter(Boolean);
  const lines = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (next.length > widthChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) {
    lines.push(current);
  }
  return lines.join("\n");
}

function recordText(slideNo, shape, role, text, x, y, w, h) {
  const value = normalizeText(text);
  inspectRecords.push({
    kind: "textbox",
    slide: slideNo,
    id: shape?.id || `slide-${slideNo}-${role}-${inspectRecords.length + 1}`,
    role,
    text: value,
    textPreview: value.replace(/\n/g, " | ").slice(0, 180),
    textChars: value.length,
    textLines: textLineCount(value),
    bbox: [x, y, w, h],
  });
}

function recordImage(slideNo, image, role, imagePath, x, y, w, h) {
  inspectRecords.push({
    kind: "image",
    slide: slideNo,
    id: image?.id || `slide-${slideNo}-${role}-${inspectRecords.length + 1}`,
    role,
    path: imagePath,
    bbox: [x, y, w, h],
  });
}

function applyTextStyle(box, text, size, color, bold, face, align, valign, autoFit, listStyle) {
  box.text = text;
  box.text.fontSize = size;
  box.text.color = color;
  box.text.bold = Boolean(bold);
  box.text.alignment = align;
  box.text.verticalAlignment = valign;
  box.text.typeface = face;
  box.text.insets = { left: 0, right: 0, top: 0, bottom: 0 };
  if (autoFit) {
    box.text.autoFit = autoFit;
  }
  if (listStyle) {
    box.text.style = "list";
  }
}

function addText(
  slide,
  slideNo,
  text,
  x,
  y,
  w,
  h,
  {
    size = 22,
    color = INK,
    bold = false,
    face = BODY_FACE,
    align = "left",
    valign = "top",
    fill = TRANSPARENT,
    line = TRANSPARENT,
    lineWidth = 0,
    autoFit = null,
    listStyle = false,
    checkFit = true,
    role = "text",
  } = {},
) {
  if (!checkFit && textLineCount(text) > 1) {
    throw new Error("checkFit=false is only allowed for single-line headers, footers, and captions.");
  }
  if (checkFit) {
    assertTextFits(text, h, size, role);
  }
  const box = addShape(slide, "rect", x, y, w, h, fill, line, lineWidth);
  applyTextStyle(box, text, size, color, bold, face, align, valign, autoFit, listStyle);
  recordText(slideNo, box, role, text, x, y, w, h);
  return box;
}

async function addImage(slide, slideNo, config, position, role, sourcePath = null) {
  const image = slide.images.add(await normalizeImageConfig(config));
  image.position = position;
  recordImage(slideNo, image, role, sourcePath || config.path || config.uri || "inline-data-url", position.left, position.top, position.width, position.height);
  return image;
}

async function addPlate(slide, slideNo, opacityPanel = false) {
  slide.background.fill = PAPER;
  const platePath = path.join(REF_DIR, `slide-${String(slideNo).padStart(2, "0")}.png`);
  if (await pathExists(platePath)) {
    await addImage(
      slide,
      slideNo,
      { path: platePath, fit: "cover", alt: `Text-free art-direction plate for slide ${slideNo}` },
      { left: 0, top: 0, width: W, height: H },
      "art plate",
      platePath,
    );
  } else {
    await addImage(
      slide,
      slideNo,
      { dataUrl: FALLBACK_PLATE_DATA_URL, fit: "cover", alt: `Fallback blank art plate for slide ${slideNo}` },
      { left: 0, top: 0, width: W, height: H },
      "fallback art plate",
      "fallback-data-url",
    );
  }
  if (opacityPanel) {
    addShape(slide, "rect", 0, 0, W, H, "#FFFFFFB8", TRANSPARENT, 0, { slideNo, role: "plate readability overlay" });
  }
}

function addHeader(slide, slideNo, kicker, idx, total) {
  addText(slide, slideNo, String(kicker || "").toUpperCase(), 64, 34, 430, 24, {
    size: 13,
    color: ACCENT_DARK,
    bold: true,
    face: MONO_FACE,
    checkFit: false,
    role: "header",
  });
  addText(slide, slideNo, `${String(idx).padStart(2, "0")} / ${String(total).padStart(2, "0")}`, 1114, 34, 104, 24, {
    size: 13,
    color: ACCENT_DARK,
    bold: true,
    face: MONO_FACE,
    align: "right",
    checkFit: false,
    role: "header",
  });
  addShape(slide, "rect", 64, 64, 1152, 2, INK, TRANSPARENT, 0, { slideNo, role: "header rule" });
  addShape(slide, "ellipse", 57, 57, 16, 16, ACCENT, INK, 2, { slideNo, role: "header marker" });
}

function addTitleBlock(slide, slideNo, title, subtitle = null, x = 64, y = 86, w = 780, dark = false) {
  const titleColor = dark ? PAPER : INK;
  const bodyColor = dark ? PAPER : GRAPHITE;
  addText(slide, slideNo, title, x, y, w, 142, {
    size: 40,
    color: titleColor,
    bold: true,
    face: TITLE_FACE,
    role: "title",
  });
  if (subtitle) {
    addText(slide, slideNo, subtitle, x + 2, y + 148, Math.min(w, 720), 70, {
      size: 19,
      color: bodyColor,
      face: BODY_FACE,
      role: "subtitle",
    });
  }
}

function addIconBadge(slide, slideNo, x, y, accent = ACCENT, kind = "signal") {
  addShape(slide, "ellipse", x, y, 54, 54, PAPER_96, INK, 1.2, { slideNo, role: "icon badge" });
  if (kind === "flow") {
    addShape(slide, "ellipse", x + 13, y + 18, 10, 10, accent, INK, 1, { slideNo, role: "icon glyph" });
    addShape(slide, "ellipse", x + 31, y + 27, 10, 10, accent, INK, 1, { slideNo, role: "icon glyph" });
    addShape(slide, "rect", x + 22, y + 25, 19, 3, INK, TRANSPARENT, 0, { slideNo, role: "icon glyph" });
  } else if (kind === "layers") {
    addShape(slide, "roundRect", x + 13, y + 15, 26, 13, accent, INK, 1, { slideNo, role: "icon glyph" });
    addShape(slide, "roundRect", x + 18, y + 24, 26, 13, GOLD, INK, 1, { slideNo, role: "icon glyph" });
    addShape(slide, "roundRect", x + 23, y + 33, 20, 10, CORAL, INK, 1, { slideNo, role: "icon glyph" });
  } else {
    addShape(slide, "rect", x + 16, y + 29, 6, 12, accent, TRANSPARENT, 0, { slideNo, role: "icon glyph" });
    addShape(slide, "rect", x + 25, y + 21, 6, 20, accent, TRANSPARENT, 0, { slideNo, role: "icon glyph" });
    addShape(slide, "rect", x + 34, y + 14, 6, 27, accent, TRANSPARENT, 0, { slideNo, role: "icon glyph" });
  }
}

function addCard(slide, slideNo, x, y, w, h, label, body, { accent = ACCENT, fill = PAPER_96, line = INK, iconKind = "signal" } = {}) {
  if (h < 156) {
    throw new Error(`Card is too short for editable pro-deck copy: height=${h.toFixed(1)}, minimum=156.`);
  }
  addShape(slide, "roundRect", x, y, w, h, fill, line, 1.2, { slideNo, role: `card panel: ${label}` });
  addShape(slide, "rect", x, y, 8, h, accent, TRANSPARENT, 0, { slideNo, role: `card accent: ${label}` });
  addIconBadge(slide, slideNo, x + 22, y + 24, accent, iconKind);
  addText(slide, slideNo, label, x + 88, y + 22, w - 108, 28, {
    size: 15,
    color: ACCENT_DARK,
    bold: true,
    face: MONO_FACE,
    role: "card label",
  });
  const wrapped = wrapText(body, Math.max(28, Math.floor(w / 13)));
  const bodyY = y + 86;
  const bodyH = h - (bodyY - y) - 22;
  if (bodyH < 54) {
    throw new Error(`Card body area is too short: height=${bodyH.toFixed(1)}, cardHeight=${h.toFixed(1)}, label=${JSON.stringify(label)}.`);
  }
  addText(slide, slideNo, wrapped, x + 24, bodyY, w - 48, bodyH, {
    size: 17,
    color: INK,
    face: BODY_FACE,
    role: `card body: ${label}`,
  });
}

function addMetricCard(slide, slideNo, x, y, w, h, metric, label, note = null, accent = ACCENT) {
  if (h < 132) {
    throw new Error(`Metric card is too short for editable pro-deck copy: height=${h.toFixed(1)}, minimum=132.`);
  }
  addShape(slide, "roundRect", x, y, w, h, PAPER_96, INK, 1.2, { slideNo, role: `metric panel: ${label}` });
  addShape(slide, "rect", x, y, w, 7, accent, TRANSPARENT, 0, { slideNo, role: `metric accent: ${label}` });
  addText(slide, slideNo, metric, x + 22, y + 24, w - 44, 54, {
    size: 34,
    color: INK,
    bold: true,
    face: TITLE_FACE,
    role: "metric value",
  });
  addText(slide, slideNo, label, x + 24, y + 82, w - 48, 38, {
    size: 16,
    color: GRAPHITE,
    face: BODY_FACE,
    role: "metric label",
  });
  if (note) {
    addText(slide, slideNo, note, x + 24, y + h - 42, w - 48, 22, {
      size: 10,
      color: MUTED,
      face: BODY_FACE,
      role: "metric note",
    });
  }
}

function addNotes(slide, body, sourceKeys) {
  const sourceLines = (sourceKeys || []).map((key) => `- ${SOURCES[key] || key}`).join("\n");
  slide.speakerNotes.setText(`${body || ""}\n\n[Sources]\n${sourceLines}`);
}

function addReferenceCaption(slide, slideNo) {
  addText(
    slide,
    slideNo,
    "依据本地 notebook、runtime 与中文稿重建历史修改线；页面文字、结论与数字均可编辑。",
    64,
    674,
    980,
    22,
    {
      size: 10,
      color: MUTED,
      face: BODY_FACE,
      checkFit: false,
      role: "caption",
    },
  );
}

async function slideCover(presentation) {
  const slideNo = 1;
  const data = SLIDES[0];
  const slide = presentation.slides.add();
  await addPlate(slide, slideNo);
  addShape(slide, "rect", 0, 0, W, H, "#FFFFFFCC", TRANSPARENT, 0, { slideNo, role: "cover contrast overlay" });
  addShape(slide, "rect", 64, 86, 7, 455, ACCENT, TRANSPARENT, 0, { slideNo, role: "cover accent rule" });
  addText(slide, slideNo, data.kicker, 86, 88, 520, 26, {
    size: 13,
    color: ACCENT_DARK,
    bold: true,
    face: MONO_FACE,
    role: "kicker",
  });
  addText(slide, slideNo, data.title, 82, 130, 785, 184, {
    size: 48,
    color: INK,
    bold: true,
    face: TITLE_FACE,
    role: "cover title",
  });
  addText(slide, slideNo, data.subtitle, 86, 326, 610, 86, {
    size: 20,
    color: GRAPHITE,
    face: BODY_FACE,
    role: "cover subtitle",
  });
  addShape(slide, "roundRect", 86, 456, 390, 92, PAPER_96, INK, 1.2, { slideNo, role: "cover moment panel" });
  addText(slide, slideNo, data.moment || "Replace with core idea", 112, 478, 336, 40, {
    size: 23,
    color: INK,
    bold: true,
    face: TITLE_FACE,
    role: "cover moment",
  });
  addReferenceCaption(slide, slideNo);
  addNotes(slide, data.notes, data.sources);
}

async function slideCards(presentation, idx) {
  const data = SLIDES[idx - 1];
  const slide = presentation.slides.add();
  await addPlate(slide, idx);
  addShape(slide, "rect", 0, 0, W, H, "#FFFFFFB8", TRANSPARENT, 0, { slideNo: idx, role: "content contrast overlay" });
  addHeader(slide, idx, data.kicker, idx, SLIDES.length);
  addTitleBlock(slide, idx, data.title, data.subtitle, 64, 86, 760);
  const cards = data.cards?.length
    ? data.cards
    : [
        ["Replace", "Add a specific, sourced point for this slide."],
        ["Author", "Use native PowerPoint chart objects for charts; use deterministic geometry for cards and callouts."],
        ["Verify", "Render previews, inspect them at readable size, and fix actionable layout issues within 3 total render loops."],
      ];
  const cols = Math.min(3, cards.length);
  const cardW = (1114 - (cols - 1) * 24) / cols;
  const iconKinds = ["signal", "flow", "layers"];
  for (let cardIdx = 0; cardIdx < cols; cardIdx += 1) {
    const [label, body] = cards[cardIdx];
    const x = 84 + cardIdx * (cardW + 24);
    addCard(slide, idx, x, 426, cardW, 176, label, body, { iconKind: iconKinds[cardIdx % iconKinds.length] });
  }
  addReferenceCaption(slide, idx);
  addNotes(slide, data.notes, data.sources);
}

async function slideMetrics(presentation, idx) {
  const data = SLIDES[idx - 1];
  const slide = presentation.slides.add();
  await addPlate(slide, idx);
  addShape(slide, "rect", 0, 0, W, H, "#FFFFFFBD", TRANSPARENT, 0, { slideNo: idx, role: "metrics contrast overlay" });
  addHeader(slide, idx, data.kicker, idx, SLIDES.length);
  addTitleBlock(slide, idx, data.title, data.subtitle, 64, 86, 700);
  const metrics = data.metrics || [
    ["00", "Replace metric", "Source"],
    ["00", "Replace metric", "Source"],
    ["00", "Replace metric", "Source"],
  ];
  const accents = [ACCENT, GOLD, CORAL];
  for (let metricIdx = 0; metricIdx < Math.min(3, metrics.length); metricIdx += 1) {
    const [metric, label, note] = metrics[metricIdx];
    addMetricCard(slide, idx, 92 + metricIdx * 370, 404, 330, 174, metric, label, note, accents[metricIdx % accents.length]);
  }
  addReferenceCaption(slide, idx);
  addNotes(slide, data.notes, data.sources);
}

function bulletize(items, widthChars = 30) {
  return (items || [])
    .map((item) => {
      const wrapped = wrapText(item, widthChars);
      return `• ${wrapped.replace(/\n/g, "\n  ")}`;
    })
    .join("\n");
}

function addBulletPanel(slide, slideNo, x, y, w, h, title, items, accent = ACCENT, bodySize = 17) {
  addShape(slide, "roundRect", x, y, w, h, PAPER_96, INK, 1.2, { slideNo, role: `bullet panel: ${title}` });
  addShape(slide, "rect", x, y, 8, h, accent, TRANSPARENT, 0, { slideNo, role: `bullet accent: ${title}` });
  addText(slide, slideNo, title, x + 24, y + 22, w - 48, 28, {
    size: 15,
    color: ACCENT_DARK,
    bold: true,
    face: MONO_FACE,
    role: "bullet panel title",
  });
  addText(slide, slideNo, bulletize(items, Math.max(24, Math.floor(w / 14))), x + 24, y + 64, w - 48, h - 88, {
    size: bodySize,
    color: INK,
    face: BODY_FACE,
    role: "bullet panel body",
  });
}

async function slideTimeline(presentation, idx) {
  const data = SLIDES[idx - 1];
  const slide = presentation.slides.add();
  await addPlate(slide, idx);
  addShape(slide, "rect", 0, 0, W, H, "#FFFFFFB6", TRANSPARENT, 0, { slideNo: idx, role: "timeline contrast overlay" });
  addHeader(slide, idx, data.kicker, idx, SLIDES.length);
  addTitleBlock(slide, idx, data.title, data.subtitle, 64, 86, 900);
  const phases = data.phases || [];
  const cardW = 272;
  const cardH = 212;
  const gap = 20;
  const y = 348;
  phases.forEach((phase, phaseIdx) => {
    const [date, title, body] = phase;
    const x = 64 + phaseIdx * (cardW + gap);
    addShape(slide, "roundRect", x, y, cardW, cardH, PAPER_96, INK, 1.2, { slideNo: idx, role: `timeline panel: ${title}` });
    addShape(slide, "rect", x, y, cardW, 10, phaseIdx % 2 === 0 ? ACCENT : GOLD, TRANSPARENT, 0, {
      slideNo: idx,
      role: `timeline accent: ${title}`,
    });
    addText(slide, idx, date, x + 22, y + 22, cardW - 44, 24, {
      size: 13,
      color: ACCENT_DARK,
      bold: true,
      face: MONO_FACE,
      role: "timeline date",
    });
    addText(slide, idx, title, x + 22, y + 54, cardW - 44, 34, {
      size: 24,
      color: INK,
      bold: true,
      face: TITLE_FACE,
      role: "timeline title",
    });
    addText(slide, idx, wrapText(body, 23), x + 22, y + 98, cardW - 44, 92, {
      size: 16,
      color: GRAPHITE,
      face: BODY_FACE,
      role: "timeline body",
    });
    if (phaseIdx < phases.length - 1) {
      addShape(slide, "rect", x + cardW + 4, y + 102, 12, 6, ACCENT_DARK, TRANSPARENT, 0, {
        slideNo: idx,
        role: "timeline connector",
      });
      addShape(slide, "rightArrow", x + cardW + 2, y + 90, 20, 30, ACCENT_DARK, TRANSPARENT, 0, {
        slideNo: idx,
        role: "timeline connector arrow",
      });
    }
  });
  addReferenceCaption(slide, idx);
  addNotes(slide, data.notes, data.sources);
}

async function slideGrid(presentation, idx) {
  const data = SLIDES[idx - 1];
  const slide = presentation.slides.add();
  await addPlate(slide, idx);
  addShape(slide, "rect", 0, 0, W, H, "#FFFFFFB8", TRANSPARENT, 0, { slideNo: idx, role: "grid contrast overlay" });
  addHeader(slide, idx, data.kicker, idx, SLIDES.length);
  addTitleBlock(slide, idx, data.title, data.subtitle, 64, 86, 900);
  const cards = data.gridCards || [];
  const cols = 3;
  const cardW = 344;
  const cardH = 166;
  const x0 = 76;
  const y0 = 308;
  const gapX = 24;
  const gapY = 18;
  const iconKinds = ["signal", "flow", "layers"];
  cards.slice(0, 6).forEach((card, cardIdx) => {
    const [label, body] = card;
    const row = Math.floor(cardIdx / cols);
    const col = cardIdx % cols;
    const x = x0 + col * (cardW + gapX);
    const y = y0 + row * (cardH + gapY);
    addCard(slide, idx, x, y, cardW, cardH, label, body, { iconKind: iconKinds[col % iconKinds.length] });
  });
  addReferenceCaption(slide, idx);
  addNotes(slide, data.notes, data.sources);
}

async function slideResults(presentation, idx) {
  const data = SLIDES[idx - 1];
  const slide = presentation.slides.add();
  await addPlate(slide, idx);
  addShape(slide, "rect", 0, 0, W, H, "#FFFFFFBA", TRANSPARENT, 0, { slideNo: idx, role: "results contrast overlay" });
  addHeader(slide, idx, data.kicker, idx, SLIDES.length);
  addTitleBlock(slide, idx, data.title, data.subtitle, 64, 86, 920);

  addMetricCard(slide, idx, 78, 308, 296, 146, "-75.3%", "横向 RMSE 下降", "0.2075 m → 0.0513 m", ACCENT);
  addMetricCard(slide, idx, 394, 308, 296, 146, "-61.5%", "载荷横向峰值力下降", "1305.56 N → 503.04 N", GOLD);
  addMetricCard(slide, idx, 78, 472, 296, 146, "-52.7%", "连接 RMS 下降", "0.00510 → 0.00241", CORAL);
  addMetricCard(slide, idx, 394, 472, 296, 146, "-18.4%", "平均单步耗时下降", "0.2661 s → 0.2170 s", ACCENT_DARK);

  addShape(slide, "roundRect", 718, 308, 486, 146, PAPER_96, INK, 1.2, { slideNo: idx, role: "result summary panel" });
  addShape(slide, "rect", 718, 308, 8, 146, ACCENT, TRANSPARENT, 0, { slideNo: idx, role: "result summary accent" });
  addText(slide, idx, "闭环可靠性", 742, 330, 160, 24, {
    size: 15,
    color: ACCENT_DARK,
    bold: true,
    face: MONO_FACE,
    role: "summary label",
  });
  addText(slide, idx, "100% / 100%", 742, 360, 210, 48, {
    size: 36,
    color: INK,
    bold: true,
    face: TITLE_FACE,
    role: "summary metric",
  });
  addText(slide, idx, "全路径完成率 / 求解成功率", 742, 412, 240, 22, {
    size: 15,
    color: GRAPHITE,
    face: BODY_FACE,
    role: "summary note",
  });
  addText(slide, idx, "失败次数", 1010, 360, 94, 24, {
    size: 14,
    color: ACCENT_DARK,
    bold: true,
    face: MONO_FACE,
    role: "failure label",
  });
  addText(slide, idx, "1 → 0", 1010, 386, 150, 34, {
    size: 28,
    color: INK,
    bold: true,
    face: TITLE_FACE,
    role: "failure metric",
  });

  addBulletPanel(
    slide,
    idx,
    718,
    472,
    486,
    146,
    "结果解读",
    [
      "收益集中在横向稳定性、连接一致性和载荷横向冲击抑制。",
      "TF12 用更保守的推进换取更稳的团队协同，因此纵向 RMSE 上升 9.9% 需要解释为 trade-off。",
    ],
    GOLD,
    14,
  );

  addReferenceCaption(slide, idx);
  addNotes(slide, data.notes, data.sources);
}

async function slideCompare(presentation, idx) {
  const data = SLIDES[idx - 1];
  const slide = presentation.slides.add();
  await addPlate(slide, idx);
  addShape(slide, "rect", 0, 0, W, H, "#FFFFFFBC", TRANSPARENT, 0, { slideNo: idx, role: "compare contrast overlay" });
  addHeader(slide, idx, data.kicker, idx, SLIDES.length);
  addTitleBlock(slide, idx, data.title, data.subtitle, 64, 86, 940);
  addBulletPanel(slide, idx, 74, 308, 540, 296, data.beforeTitle, data.beforeBullets, CORAL);
  addBulletPanel(slide, idx, 666, 308, 540, 296, data.afterTitle, data.afterBullets, ACCENT);
  addShape(slide, "roundRect", 74, 622, 1132, 34, PAPER_96, INK, 1.2, { slideNo: idx, role: "compare footer panel" });
  addText(slide, idx, "结论：后期最大的修改不只是补图补字，而是把文章重构成“问题缺口 - 方法模块 - baseline 对比 - 图证链”的投稿逻辑。", 94, 630, 1092, 18, {
    size: 13,
    color: INK,
    face: BODY_FACE,
    role: "compare footer",
    checkFit: false,
  });
  addReferenceCaption(slide, idx);
  addNotes(slide, data.notes, data.sources);
}

async function createDeck() {
  await ensureDirs();
  if (!SLIDES.length) {
    throw new Error("SLIDES must contain at least one slide.");
  }
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });
  for (let idx = 1; idx <= SLIDES.length; idx += 1) {
    const data = SLIDES[idx - 1];
    if ((data.type || "").toLowerCase() === "cover") {
      await slideCover(presentation);
    } else if ((data.type || "").toLowerCase() === "timeline") {
      await slideTimeline(presentation, idx);
    } else if ((data.type || "").toLowerCase() === "grid") {
      await slideGrid(presentation, idx);
    } else if ((data.type || "").toLowerCase() === "results") {
      await slideResults(presentation, idx);
    } else if ((data.type || "").toLowerCase() === "compare") {
      await slideCompare(presentation, idx);
    } else if (data.metrics) {
      await slideMetrics(presentation, idx);
    } else {
      await slideCards(presentation, idx);
    }
  }
  return presentation;
}

async function saveBlobToFile(blob, filePath) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  await fs.writeFile(filePath, bytes);
}

async function writeInspectArtifact(presentation) {
  inspectRecords.unshift({
    kind: "deck",
    id: DECK_ID,
    slideCount: presentation.slides.count,
    slideSize: { width: W, height: H },
  });
  presentation.slides.items.forEach((slide, index) => {
    inspectRecords.splice(index + 1, 0, {
      kind: "slide",
      slide: index + 1,
      id: slide?.id || `slide-${index + 1}`,
    });
  });
  const lines = inspectRecords.map((record) => JSON.stringify(record)).join("\n") + "\n";
  await fs.writeFile(INSPECT_PATH, lines, "utf8");
}

async function currentRenderLoopCount() {
  const logPath = path.join(VERIFICATION_DIR, "render_verify_loops.ndjson");
  if (!(await pathExists(logPath))) return 0;
  const previous = await fs.readFile(logPath, "utf8");
  return previous.split(/\r?\n/).filter((line) => line.trim()).length;
}

async function nextRenderLoopNumber() {
  return (await currentRenderLoopCount()) + 1;
}

async function appendRenderVerifyLoop(presentation, previewPaths, pptxPath) {
  const logPath = path.join(VERIFICATION_DIR, "render_verify_loops.ndjson");
  const priorCount = await currentRenderLoopCount();
  const record = {
    kind: "render_verify_loop",
    deckId: DECK_ID,
    loop: priorCount + 1,
    maxLoops: MAX_RENDER_VERIFY_LOOPS,
    capReached: priorCount + 1 >= MAX_RENDER_VERIFY_LOOPS,
    timestamp: new Date().toISOString(),
    slideCount: presentation.slides.count,
    previewCount: previewPaths.length,
    previewDir: PREVIEW_DIR,
    inspectPath: INSPECT_PATH,
    pptxPath,
  };
  await fs.appendFile(logPath, JSON.stringify(record) + "\n", "utf8");
  return record;
}

async function verifyAndExport(presentation) {
  await ensureDirs();
  const nextLoop = await nextRenderLoopNumber();
  if (nextLoop > MAX_RENDER_VERIFY_LOOPS) {
    throw new Error(
      `Render/verify/fix loop cap reached: ${MAX_RENDER_VERIFY_LOOPS} total renders are allowed. ` +
        "Do not rerender; note any remaining visual issues in the final response.",
    );
  }
  await writeInspectArtifact(presentation);
  const previewPaths = [];
  for (let idx = 0; idx < presentation.slides.items.length; idx += 1) {
    const slide = presentation.slides.items[idx];
    const preview = await presentation.export({ slide, format: "png", scale: 1 });
    const previewPath = path.join(PREVIEW_DIR, `slide-${String(idx + 1).padStart(2, "0")}.png`);
    await saveBlobToFile(preview, previewPath);
    previewPaths.push(previewPath);
  }
  const pptxBlob = await PresentationFile.exportPptx(presentation);
  const pptxPath = path.join(OUT_DIR, "output.pptx");
  await pptxBlob.save(pptxPath);
  const loopRecord = await appendRenderVerifyLoop(presentation, previewPaths, pptxPath);
  return { pptxPath, loopRecord };
}

const presentation = await createDeck();
const result = await verifyAndExport(presentation);
console.log(result.pptxPath);
