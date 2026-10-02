import streamlit as st
import streamlit.components.v1 as components


# UI-only: Bloomberg / Wind / 同花顺 style terminal shell
# A-share: 红涨绿跌. Numbers use monospace. Density high, not cramped.

STYLE_CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    /* Design tokens — 统一深色规范 */
    --term-bg-0: #0d0f14;          /* 主背景 */
    --term-bg-1: #161a23;          /* 卡片/表格 */
    --term-bg-2: #1e232e;          /* 再高一级 */
    --term-panel: #161a23;
    --term-panel-2: #1e232e;
    --term-border: #2a3140;
    --term-border-hi: #3a4356;
    --term-text: #E8E8ED;          /* 主文字 */
    --term-text-2: #8B8D98;        /* 次要文字 */
    --term-text-3: #6B6D78;
    --term-cyan: #3DDCFF;
    --term-blue: #4C8DFF;
    --term-amber: #F0B429;
    --term-up: #F6465D;            /* 红涨 */
    --term-down: #0ECB81;          /* 绿跌 / 主操作绿 */
    --term-flat: #8B8D98;
    --term-primary: #10B981;       /* 主要操作 */
    --term-danger: #EF4444;        /* 危险操作 */
    --term-radius: 10px;
    --term-radius-sm: 6px;
    --term-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
    --term-font-ui: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", "Segoe UI", Inter, sans-serif;
    --term-font-num: "JetBrains Mono", "SF Mono", Consolas, "Courier New", monospace;
}

/* ---------- Base ---------- */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: #0d0f14 !important;
    color: var(--term-text);
    font-family: var(--term-font-ui) !important;
    font-synthesis: none !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
}

.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    background:
        radial-gradient(ellipse at 0% 0%, rgba(61, 220, 255, 0.05), transparent 42%),
        radial-gradient(ellipse at 100% 0%, rgba(246, 70, 93, 0.04), transparent 36%),
        linear-gradient(180deg, #0B0E11 0%, #0E1218 100%);
}

.block-container {
    /* 给 fixed 顶线留一点视觉余量 */
    /* padding-top for fixed accent */
    position: relative;
    z-index: 1;
    max-width: 1920px !important;
    padding: 12px 16px 24px 16px !important;
}
/* main two-column layout density */
section.main [data-testid="stHorizontalBlock"] {
    gap: 16px !important;
}


.stApp p, .stApp label,
.stMarkdown, .stMarkdown p, [data-testid="stMarkdownContainer"] {
    color: var(--term-text);
    font-family: var(--term-font-ui);
    font-synthesis: none !important;
    text-shadow: none !important;
}
/* Do not force color on every div/span — can double-paint Streamlit internals */
.stApp div, .stApp span {
    font-synthesis: none !important;
}

[data-testid="stVerticalBlock"] { gap: 0.55rem; }
[data-testid="column"] { min-width: 0; }

/* denser streamlit widgets */
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
    letter-spacing: 0.2px;
}

/* Hide chrome */
section[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
#MainMenu, footer,
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: #0B0E11; }
::-webkit-scrollbar-thumb {
    background: #2A3340;
    border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover { background: #3A4656; }

/* Number mono utility */
.num, .kpi-value, .fund-industry-pct,
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * {
    font-family: var(--term-font-num) !important;
    font-variant-numeric: tabular-nums lining-nums;
    letter-spacing: -0.02em;
}

.num-up, .text-up { color: var(--term-up) !important; }
.num-down, .text-down { color: var(--term-down) !important; }
.num-flat, .text-flat { color: var(--term-flat) !important; }

/* ---------- Header (terminal bar) ---------- */
/* 品牌渐变线：固定贴视口顶部，滚动时仍可见 */
.tide-top-accent {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    height: 2px !important;
    z-index: 10000 !important;
    pointer-events: none !important;
    background: linear-gradient(
        90deg,
        var(--term-up) 0%,
        var(--term-cyan) 45%,
        var(--term-down) 100%
    ) !important;
}

.tide-header-v2,
.main-title {
    position: relative;
    overflow: hidden;
    padding: 10px 16px 10px 16px;
    margin: 4px 0 12px 0;
    border-radius: 8px;
    background: linear-gradient(180deg, #161C26 0%, #12171F 100%);
    border: 1px solid var(--term-border);
    box-shadow: 0 4px 16px rgba(0,0,0,0.28);
}

/* 卡片内顶线弱化（品牌线已 fixed） */
.tide-header-v2::before,
.main-title::before {
    content: "";
    position: absolute;
    left: 0; top: 0; right: 0;
    height: 1px;
    opacity: 0.35;
    background: linear-gradient(90deg, var(--term-up) 0%, var(--term-cyan) 45%, var(--term-down) 100%);
}

.tide-header-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}

.tide-brand {
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0;
}

.tide-logo-mark {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 700;
    color: #0B0E11;
    background: linear-gradient(145deg, #5EE7FF 0%, #3DDCFF 45%, #4C8DFF 100%);
    box-shadow: 0 0 0 1px rgba(61, 220, 255, 0.25), 0 6px 14px rgba(0,0,0,0.35);
    flex-shrink: 0;
    font-family: var(--term-font-ui);
}

.tide-title-v2,
.main-title h1 {
    margin: 0;
    font-size: clamp(18px, 1.5vw, 22px);
    line-height: 1.25;
    font-weight: 700;
    letter-spacing: 0.3px;
    color: #F3F7FC !important;
    background: none !important;
}

.tide-subtitle-v2,
.main-title p {
    margin: 4px 0 0 0;
    color: var(--term-text-2) !important;
    font-size: 12px;
    line-height: 1.4;
    font-weight: 500;
}

.tide-header-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
}

/* 基础 chip */
.tide-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    color: #C8F7FF !important;
    background: rgba(61, 220, 255, 0.08);
    border: 1px solid rgba(61, 220, 255, 0.22);
    font-family: var(--term-font-num);
    white-space: nowrap;
}

/* 市场类型：静态弱化 */
.tide-chip.static {
    color: #9CA3AF !important;
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid rgba(255, 255, 255, 0.10) !important;
    font-weight: 600 !important;
}

/* 规则说明：更小、不抢焦点 */
.tide-chip.rule,
.tide-chip.soft {
    color: #8B8D98 !important;
    background: transparent !important;
    border: none !important;
    font-size: 10px !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    text-transform: none !important;
    padding: 2px 4px !important;
    font-family: var(--term-font-ui) !important;
}

/* LIVE：状态强调 */
.tide-chip.live {
    color: #6EE7B7 !important;
    background: rgba(16, 185, 129, 0.12) !important;
    border: 1px solid rgba(16, 185, 129, 0.40) !important;
    font-weight: 800 !important;
}
.tide-chip.live::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10B981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.7);
    animation: pulse-dot 1.6s ease-in-out infinite;
}


.tide-chip.live::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--term-down);
    box-shadow: 0 0 8px var(--term-down);
    animation: pulse-dot 1.6s ease-in-out infinite;
}

@keyframes pulse-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.45; transform: scale(0.85); }
}

/* ---------- Control panel ---------- */
.control-panel {
    position: sticky;
    top: 8px;
    max-height: calc(100vh - 16px);
    overflow-y: auto;
    padding: 12px 12px;
    border-radius: 8px;
    background: var(--term-panel);
    border: 1px solid var(--term-border);
    box-shadow: 0 4px 16px rgba(0,0,0,0.28);
}

.control-panel h2,
.control-panel h3 {
    margin: 0 0 8px 0 !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    color: #F3F7FC !important;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}

.control-panel h2::after,
.control-panel h3::after {
    content: "";
    display: block;
    width: 28px;
    height: 2px;
    margin-top: 6px;
    background: var(--term-cyan);
}

.control-panel label,
.control-panel p,
.control-panel span,
.control-panel [data-testid="stWidgetLabel"],
.control-panel [data-testid="stWidgetLabel"] * {
    color: var(--term-text-2) !important;
    text-shadow: none !important;
    font-size: 12px !important;
}

.control-panel [data-testid="stWidgetLabel"] {
    min-height: 18px;
    font-weight: 600 !important;
}

/* Nav radios as terminal list */
.control-panel .stRadio [role="radiogroup"] { gap: 2px !important; }
.control-panel .stRadio [role="radiogroup"] label {
    padding: 7px 8px !important;
    border-radius: 5px !important;
    border: 1px solid transparent !important;
    transition: background 0.12s ease, border-color 0.12s ease;
    font-weight: 600 !important;
    font-size: 13px !important;
}
.control-panel .stRadio [role="radiogroup"] label:hover {
    background: rgba(61, 220, 255, 0.06) !important;
    border-color: rgba(61, 220, 255, 0.14) !important;
}
.control-panel .stRadio [role="radiogroup"] label[data-checked="true"],
.control-panel .stRadio [role="radiogroup"] div[data-checked="true"] {
    background: rgba(61, 220, 255, 0.10) !important;
    border-color: rgba(61, 220, 255, 0.28) !important;
    box-shadow: inset 2px 0 0 var(--term-cyan);
}

div[role="radiogroup"] label {
    color: var(--term-text-2) !important;
    font-weight: 600 !important;
}

/* Inputs denser */
.stDateInput input,
.stNumberInput input,
div[data-baseweb="select"] > div,
.stTextInput input,
.stTextArea textarea {
    min-height: 34px !important;
    background-color: #0E131A !important;
    border: 1px solid var(--term-border) !important;
    border-radius: var(--term-radius-sm) !important;
    color: #F3F7FC !important;
    font-size: 12px !important;
    font-family: var(--term-font-num) !important;
    transition: border-color 0.12s ease, box-shadow 0.12s ease;
}

.stDateInput input:focus,
.stNumberInput input:focus,
div[data-baseweb="select"] > div:focus-within,
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: rgba(61, 220, 255, 0.55) !important;
    box-shadow: 0 0 0 2px rgba(61, 220, 255, 0.12) !important;
}

div[data-baseweb="select"] svg { color: var(--term-text-3) !important; }

/* Dropdown */
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[role="listbox"] {
    background: #121820 !important;
    background-color: #121820 !important;
    border: 1px solid var(--term-border-hi) !important;
    border-radius: 8px !important;
    box-shadow: 0 12px 32px rgba(0,0,0,0.55) !important;
    color: #E8EEF7 !important;
}

[role="listbox"] *,
[data-baseweb="menu"] *,
[data-baseweb="popover"] * {
    color: #E8EEF7 !important;
    text-shadow: none !important;
}

[role="option"],
[role="listbox"] li,
[data-baseweb="menu"] li {
    background: transparent !important;
    min-height: 30px !important;
    padding: 6px 10px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    font-family: var(--term-font-ui) !important;
    border-radius: 4px !important;
    transition: background 0.1s ease;
}

[role="option"]:hover,
[role="listbox"] li:hover,
[data-baseweb="menu"] li:hover {
    background: rgba(61, 220, 255, 0.10) !important;
}

[role="option"][aria-selected="true"],
[role="listbox"] [aria-selected="true"],
[data-baseweb="menu"] [aria-selected="true"] {
    background: rgba(61, 220, 255, 0.16) !important;
    font-weight: 700 !important;
}

/* Buttons */
.stButton > button {
    width: 100%;
    min-height: 36px;
    border-radius: 6px !important;
    border: 1px solid rgba(61, 220, 255, 0.35) !important;
    background: linear-gradient(180deg, #1E3A55 0%, #16304A 100%) !important;
    color: #E8F7FF !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06) !important;
    transition: background 0.12s ease, border-color 0.12s ease, transform 0.12s ease !important;
}

.stButton > button:hover {
    background: linear-gradient(180deg, #254A6B 0%, #1A3A58 100%) !important;
    border-color: rgba(61, 220, 255, 0.55) !important;
    transform: translateY(-1px) !important;
}

.stButton > button:active { transform: translateY(0) !important; }

/* ---------- KPI cards ---------- */
.kpi-card {
    position: relative;
    overflow: hidden;
    min-height: 108px;
    padding: 12px 14px 12px 14px;
    border-radius: var(--term-radius);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: linear-gradient(180deg, #171D27 0%, #121820 100%);
    border: 1px solid var(--term-border);
    box-shadow: var(--term-shadow);
    transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.kpi-card:hover {
    border-color: var(--term-border-hi);
    box-shadow: 0 10px 28px rgba(0,0,0,0.5);
    transform: translateY(-1px);
}

.kpi-card::after {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background: var(--term-cyan);
}

.kpi-card.purple::after { background: var(--term-amber); }
.kpi-card.green::after { background: var(--term-up); } /* accent, not "down" */
.kpi-card.up::after { background: var(--term-up); }
.kpi-card.down::after { background: var(--term-down); }

.kpi-card::before {
    content: none;
}

.kpi-icon {
    font-size: 14px;
    margin-bottom: 2px;
    opacity: 0.85;
}

.kpi-title {
    min-height: 16px;
    margin-bottom: 2px;
    font-size: 11px;
    font-weight: 700;
    color: var(--term-text-3) !important;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

.kpi-value {
    font-size: clamp(20px, 1.7vw, 26px);
    line-height: 1.15;
    font-weight: 700;
    color: #F3F7FC !important;
    font-family: var(--term-font-num) !important;
    transition: color 0.2s ease;
}

.kpi-value.up { color: var(--term-up) !important; }
.kpi-value.down { color: var(--term-down) !important; }

.kpi-sub {
    margin-top: 4px;
    min-height: 14px;
    font-size: 11px;
    font-weight: 500;
    color: var(--term-text-3) !important;
    line-height: 1.35;
}

@keyframes subtle-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.82; }
}
.kpi-card.running { animation: subtle-pulse 1.8s ease-in-out infinite; }

/* ---------- Sections / cards ---------- */
.section-title {
    margin: 12px 0 8px 0;
    padding: 6px 0 6px 10px;
    font-size: 14px;
    line-height: 1.25;
    font-weight: 700;
    color: #F3F7FC !important;
    letter-spacing: 0.3px;
    border-left: 3px solid var(--term-cyan);
    background: linear-gradient(90deg, rgba(61, 220, 255, 0.06), transparent 55%);
}

.chart-box,
.table-card,
.small-note,
[data-testid="stMetric"],
[data-testid="stExpander"] {
    border-radius: var(--term-radius) !important;
    background: var(--term-panel) !important;
    border: 1px solid var(--term-border) !important;
    box-shadow: var(--term-shadow) !important;
}

.chart-box {
    padding: 10px 12px 8px 12px;
    margin-bottom: 10px;
    min-height: 200px;
    transition: border-color 0.15s ease;
}
.chart-box:hover { border-color: var(--term-border-hi) !important; }
.chart-box [data-testid="stPlotlyChart"] {
    border-radius: 6px;
    overflow: hidden;
}

.table-card {
    padding: 8px;
    margin-bottom: 10px;
}

.small-note {
    color: var(--term-text-2) !important;
    font-size: 12px;
    line-height: 1.65;
    padding: 10px 12px;
}
.small-note *, .small-note b {
    color: var(--term-text-2) !important;
    text-shadow: none !important;
}
.small-note b { color: var(--term-text) !important; }

/* Strategy win-rate block: keep the compact dashboard rhythm without
   letting the title, filter labels and chart headings touch each other. */
.strategy-win-title {
    margin-bottom: 14px !important;
}

.strategy-win-note {
    margin-bottom: 12px !important;
    padding: 12px 14px !important;
    line-height: 1.7 !important;
}

.nav-panel {
    padding: 10px 12px;
    border-radius: var(--term-radius);
    background: var(--term-panel);
    border: 1px solid var(--term-border);
}
.nav-panel a {
    display: block;
    padding: 7px 0;
    color: var(--term-text-2) !important;
    text-decoration: none;
    font-weight: 600;
    font-size: 12px;
    border-bottom: 1px solid rgba(42, 51, 64, 0.8);
    transition: color 0.12s ease, padding-left 0.12s ease;
}
.nav-panel a:last-child { border-bottom: 0; }
.nav-panel a:hover {
    color: var(--term-cyan) !important;
    padding-left: 3px;
}

/* Metrics */
[data-testid="stMetric"] {
    min-height: 86px;
    padding: 12px 14px !important;
    transition: border-color 0.15s ease;
}
[data-testid="stMetric"]:hover { border-color: var(--term-border-hi) !important; }

[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] * {
    color: var(--term-text-3) !important;
    font-weight: 700 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * {
    color: #F3F7FC !important;
    font-weight: 700 !important;
    font-size: 22px !important;
}

[data-testid="stMetricDelta"] svg { display: none; }

/* Dataframes — terminal denser */
[data-testid="stDataFrame"] {
    border-radius: 8px !important;
    border: 1px solid var(--term-border) !important;
    box-shadow: var(--term-shadow) !important;
    overflow: hidden !important;
    min-height: 140px;
}

[data-testid="stDataFrame"] thead th {
    background: #1A222D !important;
    color: var(--term-text-2) !important;
    font-weight: 600 !important;
    font-size: 11px !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
    border-bottom: 1px solid var(--term-border-hi) !important;
    padding: 8px 8px !important;
    white-space: nowrap !important;
    font-family: var(--term-font-ui) !important;
    font-synthesis: none !important;
    text-shadow: none !important;
    -webkit-text-stroke: 0 !important;
}

[data-testid="stDataFrame"] tbody td {
    background: #10151C !important;
    color: #D5DEEA !important;
    font-size: 12px !important;
    padding: 6px 8px !important;
    border-bottom: 1px solid rgba(42, 51, 64, 0.65) !important;
    white-space: nowrap !important;
    /* 中文表体必须用中文字体；等宽字体会缺字形导致叠影 */
    font-family: var(--term-font-ui) !important;
    font-variant-numeric: tabular-nums;
    font-synthesis: none !important;
    text-shadow: none !important;
    -webkit-text-stroke: 0 !important;
    transition: background 0.1s ease;
}

[data-testid="stDataFrame"] tbody tr:nth-child(even) td {
    background: #131920 !important;
}

[data-testid="stDataFrame"] tbody tr:hover td {
    background: #1A2636 !important;
}

/* Expander / tabs / toast */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary div {
    color: #E8EEF7 !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    font-family: var(--term-font-ui) !important;
    font-synthesis: none !important;
    text-shadow: none !important;
    -webkit-text-stroke: 0 !important;
    background: transparent !important;
    letter-spacing: 0 !important;
    /* 防止 summary 内层节点叠字 */
    -webkit-text-fill-color: currentColor !important;
}
[data-testid="stExpander"] summary {
    list-style: none !important;
}
[data-testid="stExpander"] summary::-webkit-details-marker {
    display: none !important;
}
/* Streamlit expander 偶发双层 label，隐藏装饰性重复层 */
[data-testid="stExpander"] summary [data-testid="stMarkdownContainer"] p {
    margin: 0 !important;
}
[data-testid="stExpander"] [data-testid="stDataFrame"] *,
[data-testid="stDataFrame"] [role="gridcell"],
[data-testid="stDataFrame"] [role="columnheader"],
[data-testid="stDataFrame"] canvas + div,
[data-testid="stDataFrame"] .dvn-scroller,
[data-testid="stDataFrame"] .gdg-cell {
    font-family: var(--term-font-ui) !important;
    font-synthesis: none !important;
    text-shadow: none !important;
    -webkit-text-stroke: 0 !important;
}

.stTabs [data-baseweb="tab-list"] { gap: 2px; }
.stTabs [data-baseweb="tab"] {
    min-height: 32px;
    padding: 6px 12px;
    border-radius: 4px 4px 0 0;
    color: var(--term-text-3) !important;
    font-weight: 700 !important;
    font-size: 12px !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #E8EEF7 !important; }
.stTabs [aria-selected="true"] {
    color: var(--term-cyan) !important;
    border-bottom-color: var(--term-cyan) !important;
}

[data-testid="stToast"] {
    background: #141A22 !important;
    border: 1px solid var(--term-border-hi) !important;
    border-radius: 8px !important;
}

.stCheckbox label { color: var(--term-text-2) !important; font-size: 12px !important; }

/* Loading spinner accent */
[data-testid="stSpinner"] > div {
    border-top-color: var(--term-cyan) !important;
}

/* Plotly container hover lift */
[data-testid="stPlotlyChart"] {
    transition: opacity 0.15s ease;
}

/* ---------- Fund industry bars ---------- */
.fund-industry-card {
    margin: 6px 0 12px 0;
    padding: 12px 14px;
    border-radius: var(--term-radius);
    background: var(--term-panel);
    border: 1px solid var(--term-border);
    box-shadow: var(--term-shadow);
}

.fund-industry-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--term-border);
}

.fund-industry-title {
    font-size: 13px;
    font-weight: 700;
    color: #F3F7FC !important;
    letter-spacing: 0.3px;
}

.fund-industry-meta {
    font-size: 11px;
    font-weight: 500;
    color: var(--term-text-3) !important;
    font-family: var(--term-font-num);
}

.fund-industry-row {
    display: grid;
    grid-template-columns: minmax(64px, 110px) 1fr 56px;
    gap: 8px;
    align-items: center;
    margin: 6px 0;
}

.fund-industry-name {
    font-size: 12px;
    font-weight: 600;
    color: var(--term-text-2) !important;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.fund-industry-track {
    height: 7px;
    border-radius: 999px;
    background: #0E131A;
    border: 1px solid var(--term-border);
    overflow: hidden;
}

.fund-industry-bar {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #4C8DFF 0%, #3DDCFF 100%);
    transition: width 0.35s ease;
}

.fund-industry-pct {
    text-align: right;
    font-size: 12px;
    font-weight: 700;
    color: #E8EEF7 !important;
    font-family: var(--term-font-num) !important;
}


/* ---------- Task center / fund admin — DARK theme ---------- */
.task-admin-page,
.fund-page {
    padding: 16px 18px 20px 18px;
    border-radius: var(--term-radius);
    background: var(--term-bg-1) !important;
    color: var(--term-text) !important;
    border: 1px solid var(--term-border) !important;
    box-shadow: var(--term-shadow) !important;
}

.task-admin-page *,
.task-admin-page p,
.task-admin-page label,
.task-admin-page span,
.task-admin-page div,
.fund-page *,
.fund-page p,
.fund-page label,
.fund-page span,
.fund-page div {
    color: var(--term-text);
    text-shadow: none !important;
    font-synthesis: none !important;
}

/* 任务管理标题 */
.task-admin-title {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: #E0E0E5 !important;
    margin: 0 0 14px 0 !important;
    letter-spacing: 0.3px;
    line-height: 1.4;
}
.task-admin-title::after {
    content: "";
    display: block;
    width: 40px;
    height: 2px;
    margin-top: 8px;
    background: var(--term-primary);
    border-radius: 999px;
}

.task-panel-title {
    font-size: 13px !important;
    font-weight: 700 !important;
    margin: 0 0 10px 0 !important;
    color: #E0E0E5 !important;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--term-border);
    text-transform: none;
    letter-spacing: 0.2px;
}

/* 工具栏 / 搜索区 — 深色卡片，禁止白底 */
.task-toolbar {
    padding: 12px 12px 8px 12px !important;
    margin: 0 0 12px 0 !important;
    border-radius: 8px !important;
    background: var(--term-bg-2) !important;
    border: 1px solid var(--term-border) !important;
}
.task-toolbar,
.task-toolbar * {
    background-color: transparent;
}
.task-toolbar [data-testid="column"],
.task-toolbar [data-testid="stVerticalBlock"],
.task-toolbar [data-baseweb="select"] > div,
.task-toolbar .stTextInput input {
    background-color: var(--term-bg-0) !important;
}

/* 表格卡片 — 与 action-panel 统一卡片风格 */
.task-table-card,
.task-action-panel {
    margin-top: 12px !important;
    padding: 0 !important;
    border-radius: 10px !important;
    background: var(--term-bg-1) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28) !important;
    overflow: hidden !important;
}
.task-action-panel {
    padding: 14px 16px 16px 16px !important;
}

/* 表头行：略亮背景 + 弱化文字 + 底部分隔 */
.task-table-card [data-testid="stHorizontalBlock"]:first-of-type {
    background: rgba(255, 255, 255, 0.055) !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
    margin: 0 !important;
    padding: 0 10px !important;
    gap: 0.4rem !important;
}
.task-table-card [data-testid="stHorizontalBlock"]:first-of-type [data-testid="column"] {
    background: transparent !important;
    border-bottom: none !important;
    padding-top: 12px !important;
    padding-bottom: 12px !important;
}
.task-table-card .task-th {
    font-size: 12px !important;
    font-weight: 700 !important;
    color: #9CA3AF !important;
    letter-spacing: 0.2px;
    padding: 0 4px !important;
    margin: 0 !important;
    background: transparent !important;
    line-height: 1.3 !important;
}

/* 数据行 */
.task-table-card [data-testid="stHorizontalBlock"]:not(:first-of-type) {
    margin: 0 !important;
    padding: 0 10px !important;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
    transition: background 0.15s ease;
    gap: 0.4rem !important;
}
.task-table-card [data-testid="stHorizontalBlock"]:not(:first-of-type):last-of-type {
    border-bottom: none !important;
}
.task-table-card [data-testid="stHorizontalBlock"]:not(:first-of-type):hover {
    background: rgba(255, 255, 255, 0.035) !important;
}
.task-table-card [data-testid="stHorizontalBlock"]:not(:first-of-type) [data-testid="column"] {
    padding-top: 14px !important;
    padding-bottom: 14px !important;
    border-bottom: none !important;
    color: #E8E8ED !important;
    display: flex !important;
    align-items: center !important;
}

.task-td {
    color: #E8E8ED !important;
    font-size: 13px !important;
    line-height: 1.4 !important;
    padding: 0 4px !important;
}
.task-td-id {
    color: #9CA3AF !important;
    font-variant-numeric: tabular-nums;
    font-family: var(--term-font-num) !important;
}
.task-td-muted {
    color: #C4C6D0 !important;
    font-size: 12px !important;
}
.task-td-mono {
    color: #C4C6D0 !important;
    font-size: 12px !important;
    font-family: var(--term-font-num) !important;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* 描述列：默认两行截断，展开后完整显示 */
.task-desc {
    max-width: 100%;
    min-width: 0;
    width: 100%;
    padding: 0 4px !important;
    cursor: default;
}
.task-desc-name {
    color: #E8E8ED !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    line-height: 1.35 !important;
    max-width: 100%;
}
.task-desc-sub {
    margin-top: 3px;
    color: #8B8D98 !important;
    font-size: 12px !important;
    line-height: 1.45 !important;
    max-width: 100%;
}
/* 收起：标题单行 + 描述最多两行 */
.task-desc.is-clamped .task-desc-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.task-desc.is-clamped .task-desc-sub {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    white-space: normal;
    word-break: break-word;
}
/* 展开：完整多行 */
.task-desc.is-expanded .task-desc-name,
.task-desc.is-expanded .task-desc-sub {
    white-space: normal;
    overflow: visible;
    text-overflow: unset;
    display: block;
    -webkit-line-clamp: unset;
}
/* 展开按钮更轻量 */
.task-table-card [data-testid="column"] .stButton > button {
    min-height: 28px !important;
    height: 28px !important;
    padding: 0 10px !important;
    font-size: 11px !important;
    margin-top: 4px !important;
}


/* 状态 pill */
.task-status {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    min-width: 58px;
    padding: 3px 10px !important;
    border-radius: 999px !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-align: center;
    letter-spacing: 0.3px;
    font-family: var(--term-font-num);
    border: 1px solid transparent;
}
.task-status.running {
    color: #6EE7B7 !important;
    background: rgba(16, 185, 129, 0.16) !important;
    border-color: rgba(16, 185, 129, 0.35) !important;
    box-shadow: none !important;
}
.task-status.success {
    color: #6EE7B7 !important;
    background: rgba(16, 185, 129, 0.16) !important;
    border-color: rgba(16, 185, 129, 0.35) !important;
    box-shadow: none !important;
}
.task-status.failed {
    color: #FCA5A5 !important;
    background: rgba(239, 68, 68, 0.16) !important;
    border-color: rgba(239, 68, 68, 0.35) !important;
    box-shadow: none !important;
}
.task-status.queued {
    color: #9CA3AF !important;
    background: rgba(107, 114, 128, 0.2) !important;
    border-color: rgba(156, 163, 175, 0.30) !important;
    box-shadow: none !important;
}
/* 兼容旧 stop 类名（若有缓存） */
.task-status.stop {
    color: #9CA3AF !important;
    background: rgba(107, 114, 128, 0.2) !important;
    border-color: rgba(156, 163, 175, 0.30) !important;
    box-shadow: none !important;
}

/* 按钮语义化 */
.task-admin-page .stButton > button[kind="primary"],
.task-admin-page .stButton > button[data-testid="baseButton-primary"],
.fund-page .stButton > button[kind="primary"],
.fund-page .stButton > button[data-testid="baseButton-primary"] {
    color: #06281c !important;
    background: linear-gradient(180deg, #34D399 0%, #10B981 100%) !important;
    border: 1px solid rgba(16, 185, 129, 0.55) !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.18) !important;
}
.task-admin-page .stButton > button[kind="primary"]:hover,
.fund-page .stButton > button[kind="primary"]:hover {
    filter: brightness(1.06);
}

.task-admin-page .stButton > button[kind="secondary"],
.task-admin-page .stButton > button[data-testid="baseButton-secondary"],
.task-admin-page .stButton > button:not([kind="primary"]),
.fund-page .stButton > button[kind="secondary"],
.fund-page .stButton > button:not([kind="primary"]) {
    color: var(--term-text) !important;
    background: transparent !important;
    border: 1px solid var(--term-border-hi) !important;
    box-shadow: none !important;
}
.task-admin-page .stButton > button[kind="secondary"]:hover,
.task-admin-page .stButton > button:not([kind="primary"]):hover {
    background: rgba(255,255,255,0.04) !important;
    border-color: #5a6478 !important;
}

/* 按钮语义：用 marker class，不用 nth-child */
/* Streamlit 中 markdown 与 button 是兄弟容器，用 :has() 定位后一个 button */
[data-testid="stElementContainer"]:has(.btn-wrap-primary) + [data-testid="stElementContainer"] button,
div:has(> .btn-wrap-primary) + div button,
[data-testid="stVerticalBlock"]:has(.btn-wrap-primary) .stButton button {
    color: #06281c !important;
    background: linear-gradient(180deg, #34D399 0%, #10B981 100%) !important;
    border: 1px solid rgba(16, 185, 129, 0.55) !important;
    font-weight: 700 !important;
}
[data-testid="stElementContainer"]:has(.btn-wrap-secondary) + [data-testid="stElementContainer"] button,
div:has(> .btn-wrap-secondary) + div button {
    color: var(--term-text) !important;
    background: transparent !important;
    border: 1px solid var(--term-border-hi) !important;
}
[data-testid="stElementContainer"]:has(.btn-wrap-danger) + [data-testid="stElementContainer"] button,
div:has(> .btn-wrap-danger) + div button,
[data-testid="stVerticalBlock"]:has(.btn-wrap-danger) .stButton button {
    color: #FCA5A5 !important;
    background: rgba(239, 68, 68, 0.12) !important;
    border: 1px solid rgba(239, 68, 68, 0.40) !important;
}
[data-testid="stElementContainer"]:has(.btn-wrap-danger) + [data-testid="stElementContainer"] button:hover,
div:has(> .btn-wrap-danger) + div button:hover {
    background: rgba(239, 68, 68, 0.22) !important;
}
.btn-wrap {
    display: none !important; /* 仅作 CSS 标记，不占布局 */
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

/* 输入控件深色 */
.task-admin-page .stTextInput input,
.task-admin-page .stTextArea textarea,
.task-admin-page .stDateInput input,
.task-admin-page .stNumberInput input,
.task-admin-page div[data-baseweb="select"] > div,
.task-admin-page .stSelectbox > div > div,
.fund-page .stTextInput input,
.fund-page .stTextArea textarea,
.fund-page .stDateInput input,
.fund-page .stNumberInput input,
.fund-page div[data-baseweb="select"] > div {
    background-color: var(--term-bg-0) !important;
    border: 1px solid var(--term-border) !important;
    border-radius: 6px !important;
    color: var(--term-text) !important;
    font-family: var(--term-font-ui) !important;
    box-shadow: none !important;
}
.task-admin-page .stTextInput input:focus,
.task-admin-page .stTextArea textarea:focus,
.task-admin-page div[data-baseweb="select"] > div:focus-within,
.fund-page .stTextInput input:focus,
.fund-page .stTextArea textarea:focus,
.fund-page div[data-baseweb="select"] > div:focus-within {
    border-color: rgba(16, 185, 129, 0.55) !important;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.12) !important;
}

.task-admin-page div[data-baseweb="popover"],
.fund-page div[data-baseweb="popover"] {
    background-color: var(--term-bg-2) !important;
    border: 1px solid var(--term-border-hi) !important;
}
.task-admin-page div[data-baseweb="popover"] li,
.fund-page div[data-baseweb="popover"] li {
    color: var(--term-text) !important;
}
.task-admin-page div[data-baseweb="popover"] li:hover,
.fund-page div[data-baseweb="popover"] li:hover {
    background-color: rgba(16, 185, 129, 0.12) !important;
}

.task-admin-page .stCaption,
.fund-page .stCaption {
    color: var(--term-text-2) !important;
}

.task-admin-page .stCheckbox label,
.task-admin-page .stCheckbox label *,
.fund-page .stCheckbox label,
.fund-page .stCheckbox label * {
    color: var(--term-text) !important;
    -webkit-text-fill-color: var(--term-text) !important;
}

.task-admin-page [data-testid="stExpander"],
.fund-page [data-testid="stExpander"] {
    border: 1px solid var(--term-border) !important;
    background: var(--term-bg-2) !important;
    border-radius: 8px !important;
}
.task-admin-page [data-testid="stExpander"] summary,
.fund-page [data-testid="stExpander"] summary {
    color: var(--term-text) !important;
    font-weight: 600 !important;
}

.task-admin-page .stTabs [data-baseweb="tab"],
.fund-page .stTabs [data-baseweb="tab"] {
    color: var(--term-text-2) !important;
}
.task-admin-page .stTabs [aria-selected="true"],
.fund-page .stTabs [aria-selected="true"] {
    color: var(--term-primary) !important;
    border-bottom-color: var(--term-primary) !important;
}

/* DataFrame 深色 */
.task-admin-page [data-testid="stDataFrame"],
.fund-page [data-testid="stDataFrame"] {
    border: 1px solid var(--term-border) !important;
    background: var(--term-bg-1) !important;
}
.task-admin-page [data-testid="stDataFrame"] thead th,
.fund-page [data-testid="stDataFrame"] thead th {
    background: var(--term-bg-2) !important;
    color: var(--term-text-2) !important;
    border-bottom: 1px solid var(--term-border) !important;
    font-family: var(--term-font-ui) !important;
}
.task-admin-page [data-testid="stDataFrame"] tbody td,
.fund-page [data-testid="stDataFrame"] tbody td {
    background: var(--term-bg-1) !important;
    color: var(--term-text) !important;
    font-family: var(--term-font-ui) !important;
    font-variant-numeric: tabular-nums;
    font-synthesis: none !important;
    text-shadow: none !important;
}
.task-admin-page [data-testid="stDataFrame"] tbody tr:nth-child(even) td,
.fund-page [data-testid="stDataFrame"] tbody tr:nth-child(even) td {
    background: #141820 !important;
}
.task-admin-page [data-testid="stDataFrame"] tbody tr:hover td,
.fund-page [data-testid="stDataFrame"] tbody tr:hover td {
    background: var(--term-bg-2) !important;
}

.fund-page .section-title {
    color: #E0E0E5 !important;
    border-left-color: var(--term-primary);
    background: linear-gradient(90deg, rgba(16, 185, 129, 0.10), transparent 55%);
}

/* 覆盖后续 light 残留补丁 */
.task-admin-page summary,
.task-admin-page summary *,
.task-admin-page [data-testid="stExpander"] summary,
.task-admin-page [data-testid="stExpander"] summary * {
    color: var(--term-text) !important;
    -webkit-text-fill-color: var(--term-text) !important;
    background: transparent !important;
}


/* ---------- Responsive ---------- */
@media (max-width: 1280px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    .kpi-value { font-size: 20px; }
}

@media (max-width: 900px) {
    .control-panel {
        position: relative;
        top: 0;
        max-height: none;
    }
    .tide-title-v2, .main-title h1 { font-size: 18px; }
    .fund-industry-row {
        grid-template-columns: 1fr;
        gap: 3px;
    }
    .fund-industry-pct { text-align: left; }
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] * { font-size: 18px !important; }
}


/* ---- Font ghosting fix (CJK faux-bold / double paint) ---- */
.tide-title-v2, .tide-subtitle-v2, .section-title,
.kpi-title, .kpi-value, .kpi-sub, .small-note, .small-note *,
.control-panel h2, .control-panel h3, .control-panel label,
.task-admin-title, .fund-industry-title, .fund-industry-name,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] *,
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] *,
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * {
    text-shadow: none !important;
    font-synthesis: none !important;
    -webkit-text-stroke: 0 !important;
}
.kpi-value, .kpi-title, .section-title, .tide-title-v2,
.control-panel h2, .control-panel h3, .task-admin-title {
    font-weight: 700 !important;
}


/* ---- Expander + DataFrame CJK no-ghost ---- */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary *,
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] * {
    font-synthesis: none !important;
    text-shadow: none !important;
    -webkit-text-stroke: 0 transparent !important;
}
[data-testid="stDataFrame"] {
    font-family: var(--term-font-ui) !important;
}


/* Checkbox labels: no CJK ghosting */
.stCheckbox label,
.stCheckbox label p,
.stCheckbox label span,
.stCheckbox [data-testid="stMarkdownContainer"],
.stCheckbox [data-testid="stMarkdownContainer"] * {
    font-family: var(--term-font-ui) !important;
    font-weight: 600 !important;
    font-synthesis: none !important;
    text-shadow: none !important;
    -webkit-text-stroke: 0 !important;
    letter-spacing: 0 !important;
    color: var(--term-text) !important;
}


/* Chart subtitle OUTSIDE plotly — never overlaps legend */
.chart-subtitle {
    margin: 4px 0 20px 0 !important;
    padding: 0 0 10px 0 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    line-height: 1.45 !important;
    color: #C5D0E0 !important;
    font-family: var(--term-font-ui) !important;
    font-synthesis: none !important;
    text-shadow: none !important;
    border-bottom: 1px solid rgba(90, 120, 160, 0.18);
}
.chart-block {
    margin: 0 0 18px 0 !important;
    padding: 0 !important;
}
[data-testid="stPlotlyChart"] {
    margin-top: 0 !important;
    padding-top: 0 !important;
}



/* Task admin title final override */
.task-admin-page .task-admin-title {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: #E0E0E5 !important;
    -webkit-text-fill-color: #E0E0E5 !important;
}


/* 表单/工具栏字段标签 */
.field-label {
    font-size: 11px !important;
    font-weight: 700 !important;
    color: #9CA3AF !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    margin: 0 0 6px 0 !important;
    padding: 0 !important;
    line-height: 1.2 !important;
    min-height: 14px !important;
}
.field-label-primary {
    color: #C4C6D0 !important;
}
.field-stack-gap {
    height: 10px !important;
    margin: 0 !important;
    padding: 0 !important;
}
.task-action-panel .stCheckbox {
    margin-bottom: 2px !important;
}
.task-action-panel .stCheckbox label {
    font-size: 13px !important;
    color: #E8E8ED !important;
}
.task-toolbar .field-label {
    margin-bottom: 8px !important;
}
/* placeholder 更清晰一点 */
.task-admin-page input::placeholder,
.task-admin-page textarea::placeholder {
    color: #6B7280 !important;
    opacity: 1 !important;
}

</style>
"""


DATE_PICKER_ZH_SCRIPT = r"""
<script>
(() => {
    const parentWindow = window.parent;
    const document = parentWindow.document;
    const monthNames = {
        January: "1月", February: "2月", March: "3月", April: "4月",
        May: "5月", June: "6月", July: "7月", August: "8月",
        September: "9月", October: "10月", November: "11月", December: "12月"
    };
    const weekdayNames = {
        Mo: "周一", Tu: "周二", We: "周三", Th: "周四",
        Fr: "周五", Sa: "周六", Su: "周日",
        Mon: "周一", Tue: "周二", Wed: "周三", Thu: "周四",
        Fri: "周五", Sat: "周六", Sun: "周日"
    };

    function translateText(text) {
        if (weekdayNames[text]) return weekdayNames[text];
        if (monthNames[text]) return monthNames[text];

        const monthAndYear = text.match(
            /^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})$/
        );
        if (monthAndYear) {
            return `${monthAndYear[2]}年${monthNames[monthAndYear[1]]}`;
        }
        return text;
    }

    function localizeCalendar(calendar) {
        const walker = document.createTreeWalker(
            calendar,
            parentWindow.NodeFilter.SHOW_TEXT
        );
        const textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);

        textNodes.forEach((node) => {
            const original = node.nodeValue;
            const trimmed = original.trim();
            const translated = translateText(trimmed);
            if (translated !== trimmed) {
                node.nodeValue = original.replace(trimmed, translated);
            }
        });

        const ariaLabels = {
            "Previous month": "上个月",
            "Next month": "下个月",
            "Previous year": "上一年",
            "Next year": "下一年"
        };
        calendar.querySelectorAll("[aria-label]").forEach((element) => {
            const label = element.getAttribute("aria-label");
            if (ariaLabels[label]) element.setAttribute("aria-label", ariaLabels[label]);
        });
    }

    function localizeOpenCalendars() {
        document
            .querySelectorAll('[data-baseweb="calendar"]')
            .forEach(localizeCalendar);

        document.querySelectorAll('[role="listbox"]').forEach((listbox) => {
            const options = Array.from(listbox.querySelectorAll('[role="option"]'));
            const monthOptionCount = options.filter((option) =>
                monthNames[option.textContent.trim()]
            ).length;
            if (monthOptionCount < 6) return;

            options.forEach((option) => {
                const monthName = option.textContent.trim();
                if (!monthNames[monthName]) return;

                const walker = document.createTreeWalker(
                    option,
                    parentWindow.NodeFilter.SHOW_TEXT
                );
                while (walker.nextNode()) {
                    const node = walker.currentNode;
                    const trimmed = node.nodeValue.trim();
                    if (monthNames[trimmed]) {
                        node.nodeValue = node.nodeValue.replace(
                            trimmed,
                            monthNames[trimmed]
                        );
                    }
                }
            });
        });
    }

    if (parentWindow.__stocklensDatePickerZhObserver) {
        parentWindow.__stocklensDatePickerZhObserver.disconnect();
    }

    const observer = new parentWindow.MutationObserver(localizeOpenCalendars);
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true
    });
    parentWindow.__stocklensDatePickerZhObserver = observer;
    localizeOpenCalendars();
})();
</script>
"""


def apply_styles():
    st.markdown(STYLE_CSS, unsafe_allow_html=True)
    components.html(DATE_PICKER_ZH_SCRIPT, height=0, scrolling=False)
