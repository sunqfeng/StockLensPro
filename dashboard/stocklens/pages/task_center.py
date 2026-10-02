# -*- coding: utf-8 -*-
"""任务中心 — 独立重建（tc- 命名空间，不依赖旧 task-admin 样式）。"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

import streamlit as st

from stocklens.tasks import (
    STRATEGY_OPTIONS,
    add_custom_task,
    get_task_command,
    list_recent_runs,
    list_tasks,
    read_run_status,
    remove_task_from_schedule,
    start_task,
)

# ---------------------------------------------------------------------------
# 设计 token + 组件样式（自包含，优先级高于历史样式）
# ---------------------------------------------------------------------------

TC_CSS = r"""
<style>
/* =========================================================
   Task Center layout — Ant Design Pro / console density
   8px spacing system · dark tokens · layout only
   ========================================================= */
:root {
  --tc-bg: #0d0f14;
  --tc-surface: #161a23;
  --tc-elevated: #1e232e;
  --tc-border: rgba(255,255,255,0.08);
  --tc-border-strong: rgba(255,255,255,0.12);
  --tc-text: #E8E8ED;
  --tc-text-2: #8B8D98;
  --tc-text-3: #6B7280;
  --tc-primary: #10B981;
  --tc-primary-fg: #06281c;
  --tc-danger-fg: #FCA5A5;
  --tc-s1: 4px;
  --tc-s2: 8px;
  --tc-s3: 16px;
  --tc-s4: 24px;
  --tc-s5: 32px;
  --tc-radius: 8px;
  --tc-shadow: 0 4px 16px rgba(0,0,0,0.28);
  --tc-font: "Microsoft YaHei","PingFang SC","Noto Sans SC","Segoe UI",sans-serif;
  --tc-mono: "JetBrains Mono",Consolas,"Courier New",monospace;
  --tc-ctrl-h: 32px;
}

/* Root density: tighter vertical stack */
.tc-root {
  font-family: var(--tc-font) !important;
  color: var(--tc-text) !important;
  max-width: 100% !important;
}
.tc-root [data-testid="stVerticalBlock"] {
  gap: 8px !important;
}
.tc-root, .tc-root p, .tc-root label, .tc-root span, .tc-root div {
  font-synthesis: none !important;
  text-shadow: none !important;
}

/* ---- Title row: compact ---- */
.tc-title {
  margin: 0 !important;
  font-size: 15px !important;
  font-weight: 700 !important;
  color: #E0E0E5 !important;
  line-height: 1.3 !important;
}
.tc-title-bar {
  width: 32px;
  height: 2px;
  margin-top: 6px;
  border-radius: 999px;
  background: var(--tc-primary);
}
.tc-root [data-testid="stHorizontalBlock"]:first-child {
  margin-bottom: 8px !important;
}

/* ---- Cards unified ---- */
.tc-card {
  background: var(--tc-surface) !important;
  border: 1px solid var(--tc-border) !important;
  border-radius: var(--tc-radius) !important;
  box-shadow: var(--tc-shadow) !important;
  padding: 16px !important;
  margin: 0 0 16px 0 !important;
}
.tc-card-flush {
  padding: 0 !important;
  overflow: hidden !important;
  margin-bottom: 16px !important;
}
.tc-section {
  font-size: 13px !important;
  font-weight: 700 !important;
  color: #E0E0E5 !important;
  margin: 0 0 12px 0 !important;
  padding-bottom: 8px !important;
  border-bottom: 1px solid var(--tc-border) !important;
}

/* ---- Field labels ---- */
.tc-label {
  font-size: 11px !important;
  font-weight: 600 !important;
  color: var(--tc-text-2) !important;
  letter-spacing: 0.04em !important;
  text-transform: uppercase !important;
  margin: 0 0 6px 0 !important;
  line-height: 16px !important;
  min-height: 16px !important;
}
.tc-label-strong { color: #C4C6D0 !important; }
.tc-gap-8 { height: 8px !important; margin: 0 !important; padding: 0 !important; }
.tc-gap-12 { height: 8px !important; margin: 0 !important; padding: 0 !important; }

/* ---- Controls: unified height 32px ---- */
.tc-root .stTextInput input,
.tc-root .stTextArea textarea,
.tc-root .stDateInput input,
.tc-root .stNumberInput input,
.tc-root .stNumberInput [data-baseweb="input"],
.tc-root div[data-baseweb="select"] > div {
  background: var(--tc-bg) !important;
  border: 1px solid var(--tc-border-strong) !important;
  border-radius: var(--tc-radius) !important;
  color: var(--tc-text) !important;
  min-height: var(--tc-ctrl-h) !important;
  height: var(--tc-ctrl-h) !important;
  font-size: 13px !important;
  font-family: var(--tc-font) !important;
  box-shadow: none !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}
.tc-root .stTextArea textarea {
  height: auto !important;
  min-height: 72px !important;
}
.tc-root .stTextInput input:focus,
.tc-root .stTextArea textarea:focus,
.tc-root div[data-baseweb="select"] > div:focus-within {
  border-color: rgba(16,185,129,0.55) !important;
  box-shadow: 0 0 0 2px rgba(16,185,129,0.12) !important;
}
.tc-root input::placeholder,
.tc-root textarea::placeholder {
  color: var(--tc-text-3) !important;
  opacity: 1 !important;
}
.tc-root .stCaption,
.tc-root [data-testid="stCaptionContainer"] {
  color: var(--tc-text-2) !important;
  font-size: 12px !important;
}
.tc-root .stCheckbox label {
  color: var(--tc-text) !important;
  font-size: 13px !important;
}

/* Toolbar: denser card, aligned controls */
.tc-card .stHorizontalBlock,
.tc-root .tc-card [data-testid="stHorizontalBlock"] {
  gap: 12px !important;
  align-items: flex-end !important;
}
.tc-root .stButton > button {
  min-height: var(--tc-ctrl-h) !important;
  height: var(--tc-ctrl-h) !important;
  border-radius: var(--tc-radius) !important;
  font-size: 13px !important;
  padding: 0 16px !important;
  width: 100% !important;
}

/* Primary / secondary buttons */
.tc-root .stButton > button[kind="primary"],
.tc-root .stButton > button[data-testid="baseButton-primary"] {
  background: var(--tc-primary) !important;
  color: var(--tc-primary-fg) !important;
  border: 1px solid rgba(16,185,129,0.55) !important;
  font-weight: 700 !important;
  box-shadow: none !important;
}
.tc-root .stButton > button[kind="secondary"],
.tc-root .stButton > button[data-testid="baseButton-secondary"],
.tc-root .stButton > button:not([kind="primary"]) {
  background: transparent !important;
  color: var(--tc-text) !important;
  border: 1px solid var(--tc-border-strong) !important;
  font-weight: 600 !important;
  box-shadow: none !important;
}
.tc-root .stButton > button:hover { filter: brightness(1.08); }
.tc-root .stButton > button:focus-visible {
  outline: 2px solid var(--tc-primary) !important;
  outline-offset: 2px !important;
}
.tc-root .stButton > button:disabled {
  opacity: 0.45 !important;
  cursor: not-allowed !important;
}

/* Button markers */
[data-testid="stElementContainer"]:has(.tc-btn-primary) + [data-testid="stElementContainer"] button,
[data-testid="stVerticalBlock"]:has(.tc-btn-primary) .stButton button {
  background: var(--tc-primary) !important;
  color: var(--tc-primary-fg) !important;
  border: 1px solid rgba(16,185,129,0.55) !important;
  font-weight: 700 !important;
}
[data-testid="stElementContainer"]:has(.tc-btn-danger) + [data-testid="stElementContainer"] button,
[data-testid="stVerticalBlock"]:has(.tc-btn-danger) .stButton button {
  color: var(--tc-danger-fg) !important;
  background: rgba(239,68,68,0.12) !important;
  border: 1px solid rgba(239,68,68,0.40) !important;
}
[data-testid="stElementContainer"]:has(.tc-btn-danger) + [data-testid="stElementContainer"] button:hover {
  background: rgba(239,68,68,0.22) !important;
}
.tc-btn-primary, .tc-btn-secondary, .tc-btn-danger {
  display: none !important;
  height: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* ---- Table: console density ---- */
.tc-table .tc-th {
  font-size: 12px !important;
  font-weight: 600 !important;
  color: #9CA3AF !important;
  letter-spacing: 0.04em !important;
  line-height: 1.4 !important;
  padding: 0 8px !important;
  margin: 0 !important;
  white-space: nowrap !important;
}
.tc-table [data-testid="stHorizontalBlock"]:first-of-type {
  background: rgba(255,255,255,0.05) !important;
  border-bottom: 1px solid var(--tc-border) !important;
  margin: 0 !important;
  padding: 0 16px !important;
  gap: 8px !important;
  min-height: 40px !important;
  align-items: center !important;
}
.tc-table [data-testid="stHorizontalBlock"]:first-of-type [data-testid="stColumn"] {
  padding-top: 10px !important;
  padding-bottom: 10px !important;
  border: none !important;
  background: transparent !important;
  display: flex !important;
  align-items: center !important;
}
.tc-table [data-testid="stHorizontalBlock"]:not(:first-of-type) {
  margin: 0 !important;
  padding: 0 16px !important;
  border-bottom: 1px solid rgba(255,255,255,0.06) !important;
  gap: 8px !important;
  transition: background 0.12s ease;
  min-height: 64px !important;
}
.tc-table [data-testid="stHorizontalBlock"]:not(:first-of-type):last-of-type {
  border-bottom: none !important;
}
.tc-table [data-testid="stHorizontalBlock"]:not(:first-of-type):hover {
  background: rgba(255,255,255,0.03) !important;
}
.tc-table [data-testid="stHorizontalBlock"]:not(:first-of-type) [data-testid="stColumn"] {
  padding-top: 12px !important;
  padding-bottom: 12px !important;
  border: none !important;
  display: flex !important;
  align-items: center !important;
  color: var(--tc-text) !important;
  min-width: 0 !important;
}

.tc-td {
  color: var(--tc-text) !important;
  font-size: 13px !important;
  line-height: 1.5 !important;
  padding: 0 8px !important;
  max-width: 100%;
  min-width: 0;
}
.tc-td-id {
  color: var(--tc-text-2) !important;
  font-family: var(--tc-mono) !important;
  font-variant-numeric: tabular-nums;
  text-align: center !important;
  width: 100%;
  font-size: 12px !important;
}
.tc-td-muted {
  color: #C4C6D0 !important;
  font-size: 12px !important;
  line-height: 1.4 !important;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 8px !important;
  max-width: 100%;
}
.tc-td-mono {
  color: #C4C6D0 !important;
  font-size: 12px !important;
  line-height: 1.4 !important;
  font-family: var(--tc-mono) !important;
  font-variant-numeric: tabular-nums;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 8px !important;
  max-width: 100%;
}

/* Description hierarchy: title / body / action */
.tc-desc {
  max-width: 100%;
  min-width: 0;
  width: 100%;
  padding: 0 8px !important;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.tc-desc-name {
  color: var(--tc-text) !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  line-height: 1.4 !important;
  margin: 0 !important;
}
.tc-desc-sub {
  margin: 0 !important;
  color: var(--tc-text-2) !important;
  font-size: 12px !important;
  line-height: 1.5 !important;
}
.tc-desc.is-clamped .tc-desc-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tc-desc.is-clamped .tc-desc-sub {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  white-space: normal;
  word-break: break-word;
}
.tc-desc.is-expanded .tc-desc-name,
.tc-desc.is-expanded .tc-desc-sub {
  white-space: normal;
  overflow: visible;
  display: block;
  -webkit-line-clamp: unset;
}
/* expand btn compact, secondary look */
.tc-table [data-testid="stColumn"] .stButton > button {
  min-height: 28px !important;
  height: 28px !important;
  padding: 0 10px !important;
  font-size: 12px !important;
  margin-top: 6px !important;
  width: auto !important;
}

/* Action column buttons tighter */
.tc-table [data-testid="stColumn"]:last-child [data-testid="stHorizontalBlock"] {
  gap: 8px !important;
  min-height: auto !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
}
.tc-table [data-testid="stColumn"]:last-child [data-testid="stHorizontalBlock"] [data-testid="stColumn"] {
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}
.tc-table [data-testid="stColumn"]:last-child .stButton > button {
  width: 100% !important;
  margin-top: 0 !important;
  min-height: 28px !important;
  height: 28px !important;
  font-size: 12px !important;
}

/* Badges */
.tc-badge {
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  padding: 2px 8px !important;
  border-radius: 999px !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  font-family: var(--tc-mono);
  border: 1px solid transparent;
}
.tc-badge.running,
.tc-badge.success {
  color: #6EE7B7 !important;
  background: rgba(16,185,129,0.16) !important;
  border-color: rgba(16,185,129,0.35) !important;
}
.tc-badge.failed {
  color: #FCA5A5 !important;
  background: rgba(239,68,68,0.16) !important;
  border-color: rgba(239,68,68,0.35) !important;
}
.tc-badge.queued {
  color: #9CA3AF !important;
  background: rgba(107,114,128,0.20) !important;
  border-color: rgba(156,163,175,0.30) !important;
}

/* Empty */
.tc-empty {
  padding: 32px 16px !important;
  text-align: center;
}
.tc-empty-title {
  font-size: 14px !important;
  font-weight: 700 !important;
  color: var(--tc-text) !important;
  margin-bottom: 8px !important;
}
.tc-empty-sub {
  font-size: 12px !important;
  color: var(--tc-text-2) !important;
  line-height: 1.5 !important;
}

/* Dataframe / popover */
.tc-root [data-testid="stDataFrame"] {
  border: 1px solid var(--tc-border) !important;
  border-radius: var(--tc-radius) !important;
}
.tc-root [data-testid="stDataFrame"] thead th {
  background: var(--tc-elevated) !important;
  color: var(--tc-text-2) !important;
}
.tc-root [data-testid="stDataFrame"] tbody td {
  background: var(--tc-surface) !important;
  color: var(--tc-text) !important;
  font-family: var(--tc-mono) !important;
  font-variant-numeric: tabular-nums;
}
.tc-root div[data-baseweb="popover"] {
  background: var(--tc-elevated) !important;
  border: 1px solid var(--tc-border-strong) !important;
}
.tc-root div[data-baseweb="popover"] li { color: var(--tc-text) !important; }
.tc-root div[data-baseweb="popover"] li:hover {
  background: rgba(16,185,129,0.12) !important;
}

/* Responsive: laptop / 1920 / 2560 */
@media (max-width: 1440px) {
  .tc-table [data-testid="stHorizontalBlock"]:not(:first-of-type) {
    min-height: 56px !important;
  }
  .tc-table [data-testid="stHorizontalBlock"]:not(:first-of-type) [data-testid="stColumn"] {
    padding-top: 10px !important;
    padding-bottom: 10px !important;
  }
  .tc-card { padding: 12px !important; }
}
@media (min-width: 1920px) {
  .tc-root { max-width: 100% !important; }
  .tc-table [data-testid="stHorizontalBlock"]:first-of-type,
  .tc-table [data-testid="stHorizontalBlock"]:not(:first-of-type) {
    padding-left: 20px !important;
    padding-right: 20px !important;
    gap: 12px !important;
  }
}
@media (min-width: 2560px) {
  .tc-table [data-testid="stHorizontalBlock"]:first-of-type,
  .tc-table [data-testid="stHorizontalBlock"]:not(:first-of-type) {
    padding-left: 24px !important;
    padding-right: 24px !important;
    gap: 16px !important;
  }
  .tc-desc-name { font-size: 14px !important; }
}

/* ---- Stable selectors for Streamlit 1.5x DOM ---- */
/* Markdown markers are not layout containers in Streamlit. Keep them as
   selector hooks but remove their own boxes from the visual flow. */
[data-testid="stElementContainer"]:has(.control-panel),
[data-testid="stElementContainer"]:has(.tc-root),
[data-testid="stElementContainer"]:has(.tc-card),
[data-testid="stElementContainer"]:has(.tc-btn-primary),
[data-testid="stElementContainer"]:has(.tc-btn-secondary),
[data-testid="stElementContainer"]:has(.tc-btn-danger),
[data-testid="stElementContainer"]:has(.tc-gap-8),
[data-testid="stElementContainer"]:has(.tc-gap-12) {
  display: none !important;
}

/* Actual outer shell: sidebar and content start on the same baseline. */
[data-testid="stMainBlockContainer"]
> [data-testid="stVerticalBlock"]
> [data-testid="stLayoutWrapper"]
> [data-testid="stHorizontalBlock"]
> [data-testid="stColumn"]:first-child {
  align-self: flex-start !important;
  position: sticky !important;
  top: 8px !important;
  padding: 16px !important;
  background: var(--tc-surface) !important;
  border: 1px solid var(--tc-border) !important;
  border-radius: var(--tc-radius) !important;
  box-shadow: var(--tc-shadow) !important;
}

/* Search toolbar card, using content rather than generated class names. */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(6)):not(:has(> [data-testid="stColumn"]:nth-child(7))) {
  display: grid !important;
  grid-template-columns: minmax(128px,.9fr) minmax(120px,.8fr) minmax(240px,1.55fr) minmax(220px,1.35fr) minmax(150px,.9fr) 88px !important;
  align-items: end !important;
  gap: 16px !important;
  padding: 16px !important;
  margin: 8px 0 16px !important;
  background: var(--tc-surface) !important;
  border: 1px solid var(--tc-border) !important;
  border-radius: var(--tc-radius) !important;
  box-shadow: var(--tc-shadow) !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(6)):not(:has(> [data-testid="stColumn"]:nth-child(7))) > [data-testid="stColumn"] {
  width: auto !important;
  min-width: 0 !important;
  flex: none !important;
}

/* Real table rows: the marker cannot wrap widgets, so target row content. */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-th),
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id) {
  display: grid !important;
  grid-template-columns: 36px minmax(320px,2.5fr) minmax(110px,1.15fr) minmax(170px,1.55fr) minmax(92px,.9fr) minmax(76px,.7fr) minmax(200px,1.55fr) !important;
  gap: 12px !important;
  margin: 0 !important;
  padding: 0 16px !important;
  border-left: 1px solid var(--tc-border) !important;
  border-right: 1px solid var(--tc-border) !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-th) {
  min-height: 40px !important;
  align-items: center !important;
  background: var(--tc-elevated) !important;
  border-top: 1px solid var(--tc-border) !important;
  border-bottom: 1px solid var(--tc-border) !important;
  border-radius: var(--tc-radius) var(--tc-radius) 0 0 !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id) {
  min-height: 68px !important;
  align-items: center !important;
  background: var(--tc-surface) !important;
  border-bottom: 1px solid var(--tc-border) !important;
  border-radius: 0 0 var(--tc-radius) var(--tc-radius) !important;
  box-shadow: var(--tc-shadow) !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-th) > [data-testid="stColumn"],
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id) > [data-testid="stColumn"] {
  width: auto !important;
  min-width: 0 !important;
  flex: none !important;
  padding: 10px 4px !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id) > [data-testid="stColumn"]:last-child [data-testid="stHorizontalBlock"] {
  display: grid !important;
  grid-template-columns: repeat(3, minmax(52px,1fr)) !important;
  gap: 8px !important;
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id) > [data-testid="stColumn"]:last-child [data-testid="stColumn"] {
  width: auto !important;
  min-width: 0 !important;
  padding: 0 !important;
}

@media (max-width: 1500px) {
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(6)):not(:has(> [data-testid="stColumn"]:nth-child(7))) {
    grid-template-columns: repeat(3, minmax(0,1fr)) !important;
    gap: 12px !important;
  }
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-th),
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id) {
    grid-template-columns: 32px minmax(280px,2.35fr) minmax(94px,1fr) minmax(140px,1.35fr) 82px 72px minmax(180px,1.4fr) !important;
    gap: 8px !important;
    padding-left: 12px !important;
    padding-right: 12px !important;
  }
}

/* =========================================================
   Streamlit DOM bridge
   Markdown markers do not wrap following widgets, therefore layout rules
   below intentionally apply page-wide while this page's CSS is mounted.
   ========================================================= */

/* Use the available canvas and keep the shell on one 8px grid. */
.block-container {
  max-width: none !important;
  width: 100% !important;
  padding: 8px 16px 24px !important;
}
section.main [data-testid="stHorizontalBlock"] {
  gap: 16px !important;
}
.tide-header-v2 {
  padding: 8px 16px !important;
  margin: 0 0 8px !important;
  min-height: 0 !important;
}
.tide-header-inner { min-height: 40px !important; }
.tide-logo-mark { width: 32px !important; height: 32px !important; }
.tide-brand { gap: 12px !important; }
.tide-subtitle-v2 { margin-top: 2px !important; line-height: 1.3 !important; }

/* The marker nodes are visual hooks only. */
[data-testid="stElementContainer"]:has(> .tc-root),
[data-testid="stElementContainer"]:has(> .tc-card),
[data-testid="stElementContainer"]:has(> .tc-card.tc-card-flush) {
  height: 0 !important;
  min-height: 0 !important;
  margin: 0 !important;
  overflow: hidden !important;
}

/* Consistent task-page rhythm and control dimensions. */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:not(:first-child),
.block-container > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"]:not(:first-child) {
  margin-top: 0 !important;
}
.stTextInput input,
.stDateInput input,
.stNumberInput input,
.stNumberInput [data-baseweb="input"],
div[data-baseweb="select"] > div {
  height: var(--tc-ctrl-h) !important;
  min-height: var(--tc-ctrl-h) !important;
  border-radius: var(--tc-radius) !important;
  background: var(--tc-bg) !important;
  border: 1px solid var(--tc-border-strong) !important;
  color: var(--tc-text) !important;
  font-size: 13px !important;
  box-shadow: none !important;
}
.stTextInput input:focus,
.stDateInput input:focus,
.stNumberInput input:focus,
div[data-baseweb="select"] > div:focus-within {
  border-color: rgba(16,185,129,.55) !important;
  box-shadow: 0 0 0 2px rgba(16,185,129,.12) !important;
}

/* Default task-page button is neutral; semantic markers override it. */
.stButton > button {
  width: 100% !important;
  height: var(--tc-ctrl-h) !important;
  min-height: var(--tc-ctrl-h) !important;
  padding: 0 14px !important;
  border-radius: var(--tc-radius) !important;
  background: rgba(255,255,255,.035) !important;
  border: 1px solid var(--tc-border-strong) !important;
  color: #D1D5DB !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  text-transform: none !important;
  box-shadow: none !important;
}
.stButton > button:hover {
  background: rgba(255,255,255,.07) !important;
  border-color: rgba(255,255,255,.20) !important;
  transform: none !important;
}
[data-testid="stElementContainer"]:has(.tc-btn-primary) + [data-testid="stElementContainer"] .stButton > button {
  background: var(--tc-primary) !important;
  border-color: rgba(16,185,129,.62) !important;
  color: var(--tc-primary-fg) !important;
  font-weight: 700 !important;
}
[data-testid="stElementContainer"]:has(.tc-btn-secondary) + [data-testid="stElementContainer"] .stButton > button {
  background: rgba(255,255,255,.035) !important;
  border-color: var(--tc-border-strong) !important;
  color: #D1D5DB !important;
}
[data-testid="stElementContainer"]:has(.tc-btn-danger) + [data-testid="stElementContainer"] .stButton > button {
  background: rgba(239,68,68,.10) !important;
  border-color: rgba(239,68,68,.42) !important;
  color: var(--tc-danger-fg) !important;
}
[data-testid="stElementContainer"]:has(.tc-btn-danger) + [data-testid="stElementContainer"] .stButton > button:hover {
  background: rgba(239,68,68,.18) !important;
  border-color: rgba(239,68,68,.62) !important;
}

/* Toolbar behaves as a compact responsive search grid. */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(6)):not(:has(> [data-testid="stColumn"]:nth-child(7))) {
  align-items: end !important;
  gap: 16px !important;
  padding: 16px !important;
  margin: 8px 0 16px !important;
  background: var(--tc-surface) !important;
  border: 1px solid var(--tc-border) !important;
  border-radius: var(--tc-radius) !important;
  box-shadow: var(--tc-shadow) !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(6)):not(:has(> [data-testid="stColumn"]:nth-child(7))) [data-testid="stColumn"] {
  min-width: 0 !important;
}

/* Page-size control stays compact instead of spanning the content canvas. */
[data-testid="stSelectbox"]:has([aria-label="每页记录数"]) {
  width: min(240px, 100%) !important;
  margin: 0 0 8px auto !important;
}

/* Table surface, spacing and readable description hierarchy. */
.tc-table ~ [data-testid="stHorizontalBlock"],
[data-testid="stElementContainer"]:has(.tc-table) ~ [data-testid="stHorizontalBlock"] {
  border-bottom: 1px solid rgba(255,255,255,.06) !important;
}
.tc-th { color: #9CA3AF !important; font-size: 12px !important; font-weight: 600 !important; }
.tc-td, .tc-desc { min-width: 0 !important; }
.tc-desc { gap: 4px !important; padding: 0 4px !important; }
.tc-desc-name { color: var(--tc-text) !important; font-size: 13px !important; font-weight: 700 !important; line-height: 1.4 !important; }
.tc-desc-sub { color: var(--tc-text-2) !important; font-size: 12px !important; line-height: 1.5 !important; }
.tc-td-muted, .tc-td-mono {
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
  font-size: 12px !important;
}

@media (max-width: 1366px) {
  .block-container { padding-left: 12px !important; padding-right: 12px !important; }
  section.main [data-testid="stHorizontalBlock"] { gap: 12px !important; }
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(6)):not(:has(> [data-testid="stColumn"]:nth-child(7))) {
    gap: 8px !important;
    padding: 12px !important;
  }
  .tc-table .tc-desc-sub { -webkit-line-clamp: 1 !important; }
}
@media (min-width: 1920px) {
  .block-container { padding-left: 24px !important; padding-right: 24px !important; }
}
@media (min-width: 2560px) {
  .block-container { padding-left: 32px !important; padding-right: 32px !important; }
}

/* Task description cell: compact hierarchy, not a nested action card. */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"]:nth-child(2) {
  align-self: stretch !important;
  display: flex !important;
  align-items: center !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"]:nth-child(2) > [data-testid="stVerticalBlock"] {
  gap: 2px !important;
  justify-content: center !important;
  position: relative !important;
  width: 100% !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"]:nth-child(2) .tc-desc {
  gap: 3px !important;
  padding: 0 !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"]:nth-child(2) .tc-desc-name {
  font-size: 13px !important;
  line-height: 18px !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"]:nth-child(2) .tc-desc-sub {
  font-size: 12px !important;
  line-height: 17px !important;
  color: #9CA3AF !important;
  display: block !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
  padding-right: 42px !important;
  -webkit-line-clamp: unset !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"] {
  padding-top: 8px !important;
  padding-bottom: 8px !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"]:nth-child(2) > [data-testid="stVerticalBlock"]
> [data-testid="stElementContainer"]:has(.stButton) {
  position: absolute !important;
  right: 0 !important;
  bottom: 0 !important;
  width: auto !important;
  z-index: 2 !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"]:nth-child(2) .stButton > button {
  width: auto !important;
  height: 20px !important;
  min-height: 20px !important;
  margin: 1px 0 0 !important;
  padding: 0 !important;
  border: 0 !important;
  border-radius: 3px !important;
  background: transparent !important;
  color: #67E8F9 !important;
  font-size: 11px !important;
  font-weight: 600 !important;
  box-shadow: none !important;
}
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(7)):has(.tc-td-id)
> [data-testid="stColumn"]:nth-child(2) .stButton > button:hover {
  color: #A5F3FC !important;
  background: rgba(61,220,255,.06) !important;
}
</style>

"""

STATUS_LABELS = {
    "QUEUED": "等待",
    "RUNNING": "运行中",
    "SUCCESS": "成功",
    "FAILED": "失败",
}
STATUS_CLASS = {
    "QUEUED": "queued",
    "RUNNING": "running",
    "SUCCESS": "success",
    "FAILED": "failed",
}

COL_SPEC = [0.35, 2.5, 1.15, 1.55, 0.9, 0.7, 1.55]
HEADERS = ["#", "任务描述", "调度类型", "运行模式", "负责人", "状态", "操作"]


def _apply_tc_styles():
    st.markdown(TC_CSS, unsafe_allow_html=True)


def _format_command(command):
    return " ".join(str(item) for item in command)


def _read_log_tail(path, max_chars=6000):
    log_path = Path(path)
    if not log_path.exists():
        return ""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return text if len(text) <= max_chars else text[-max_chars:]


def _handler_name(task):
    command = list(task.base_command)
    if not command:
        return "-"
    if len(command) >= 2 and str(command[0]).endswith(("python", "python3")):
        return Path(command[1]).name
    return Path(command[0]).name


def _latest_run_by_task():
    latest = {}
    for run in list_recent_runs(limit=200):
        task_id = run.get("task_id")
        if task_id and task_id not in latest:
            latest[task_id] = run
    return latest


def _task_status(task, latest_runs):
    latest_run = latest_runs.get(task.task_id)
    if not latest_run:
        return "QUEUED"
    code = (latest_run.get("status") or "QUEUED").upper()
    return code if code in STATUS_CLASS else "QUEUED"


def _badge(status_code: str):
    label = html.escape(STATUS_LABELS.get(status_code, status_code))
    cls = STATUS_CLASS.get(status_code, "queued")
    st.markdown(f'<span class="tc-badge {cls}">{label}</span>', unsafe_allow_html=True)


def _label(text: str, strong: bool = False):
    cls = "tc-label tc-label-strong" if strong else "tc-label"
    st.markdown(f'<div class="{cls}">{html.escape(text)}</div>', unsafe_allow_html=True)


def _btn_marker(kind: str):
    """kind: primary | secondary | danger"""
    st.markdown(f'<div class="tc-btn-{kind}"></div>', unsafe_allow_html=True)


def _start_simple_task(task):
    command = get_task_command(task.task_id)
    run_id = start_task(task.task_id, command)
    st.toast("启动成功")
    st.session_state["selected_task_run_id"] = run_id
    st.rerun()


def _render_toolbar(tasks, latest_runs):
    st.markdown('<div class="tc-card">', unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns([1.0, 0.9, 1.7, 1.45, 1.0, 0.68])

    categories = ["全部"] + sorted({t.category for t in tasks})
    with c1:
        _label("执行器")
        category = st.selectbox(
            "执行器", categories, label_visibility="collapsed", key="tc_f_cat"
        )
    with c2:
        _label("状态")
        status_filter = st.selectbox(
            "状态",
            ["全部", "RUNNING", "SUCCESS", "FAILED", "QUEUED"],
            format_func=lambda v: "全部" if v == "全部" else STATUS_LABELS.get(v, v),
            label_visibility="collapsed",
            key="tc_f_status",
        )
    with c3:
        _label("任务搜索")
        desc_kw = st.text_input(
            "任务搜索",
            placeholder="搜索任务名称 / 描述…",
            label_visibility="collapsed",
            key="tc_f_desc",
        )
    with c4:
        _label("JobHandler")
        handler_kw = st.text_input(
            "JobHandler",
            placeholder="脚本名或 JobHandler…",
            label_visibility="collapsed",
            key="tc_f_handler",
        )
    with c5:
        _label("负责人")
        owner_kw = st.text_input(
            "负责人",
            placeholder="负责人…",
            label_visibility="collapsed",
            key="tc_f_owner",
        )
    with c6:
        _label("\u00a0")
        st.button("搜索", type="primary", key="tc_f_search")

    st.markdown("</div>", unsafe_allow_html=True)

    out = []
    for task in tasks:
        status = _task_status(task, latest_runs)
        if category != "全部" and task.category != category:
            continue
        if status_filter != "全部" and status != status_filter:
            continue
        blob_name = (task.name or "").lower()
        blob_desc = (task.description or "").lower()
        if desc_kw and desc_kw.lower() not in blob_name and desc_kw.lower() not in blob_desc:
            continue
        if handler_kw and handler_kw.lower() not in _handler_name(task).lower():
            continue
        if owner_kw and owner_kw.lower() not in (task.owner or "").lower():
            continue
        out.append(task)
    return out


def _render_table(tasks, latest_runs):
    st.markdown('<div class="tc-card tc-card-flush tc-table">', unsafe_allow_html=True)

    if not tasks:
        st.markdown(
            """
<div class="tc-empty">
  <div class="tc-empty-title">暂无任务</div>
  <div class="tc-empty-sub">调整上方筛选条件，或点击右上角「新增」创建任务</div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    header = st.columns(COL_SPEC)
    for col, title in zip(header, HEADERS):
        col.markdown(f'<div class="tc-th">{title}</div>', unsafe_allow_html=True)

    for index, task in enumerate(tasks, start=1):
        status = _task_status(task, latest_runs)
        row = st.columns(COL_SPEC)

        row[0].markdown(
            f'<div class="tc-td tc-td-id">{index}</div>', unsafe_allow_html=True
        )

        name_raw = str(task.name or "-")
        desc_raw = str(task.description or "-")
        name = html.escape(name_raw)
        desc = html.escape(desc_raw)
        tip = html.escape(f"{name_raw} — {desc_raw}")
        long_desc = len(desc_raw) > 36
        exp_key = f"tc_desc_exp_{task.task_id}"
        expanded = bool(st.session_state.get(exp_key, False))
        clamp = "is-expanded" if expanded else "is-clamped"
        with row[1]:
            st.markdown(
                f'<div class="tc-desc {clamp}" title="{tip}">'
                f'<div class="tc-desc-name">{name}</div>'
                f'<div class="tc-desc-sub">{desc}</div></div>',
                unsafe_allow_html=True,
            )
            if long_desc:
                label = "收起" if expanded else "展开"
                if st.button(label, key=f"tc_desc_btn_{task.task_id}", type="secondary"):
                    st.session_state[exp_key] = not expanded
                    st.rerun()

        row[2].markdown(
            f'<div class="tc-td tc-td-muted" title="{html.escape(str(task.category or "-"))}">'
            f"{html.escape(str(task.category or '-'))}</div>",
            unsafe_allow_html=True,
        )
        handler = f"BEAN: {_handler_name(task)}"
        row[3].markdown(
            f'<div class="tc-td tc-td-mono" title="{html.escape(handler)}">{html.escape(handler)}</div>',
            unsafe_allow_html=True,
        )
        row[4].markdown(
            f'<div class="tc-td tc-td-muted" title="{html.escape(str(task.owner or "-"))}">'
            f"{html.escape(str(task.owner or '-'))}</div>",
            unsafe_allow_html=True,
        )
        with row[5]:
            _badge(status)
        with row[6]:
            a, b, c = st.columns(3)
            with a:
                _btn_marker("primary")
                if st.button("启动", type="primary", key=f"tc_start_{task.task_id}"):
                    st.session_state["selected_task_id"] = task.task_id
                    st.session_state["selected_task_action"] = "start"
                    st.rerun()
            with b:
                _btn_marker("secondary")
                if st.button("日志", type="secondary", key=f"tc_log_{task.task_id}"):
                    st.session_state["selected_task_id"] = task.task_id
                    st.session_state["selected_task_action"] = "log"
                    st.rerun()
            with c:
                _btn_marker("danger")
                if st.button("删除", type="secondary", key=f"tc_del_{task.task_id}"):
                    st.session_state["selected_task_id"] = task.task_id
                    st.session_state["selected_task_action"] = "delete"
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def _render_strategy_panel(task):
    st.markdown('<div class="tc-section">运行参数</div>', unsafe_allow_html=True)
    with st.form("tc_strategy_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            _label("交易日", strong=True)
            use_trade_date = st.checkbox("指定交易日", value=False)
            st.markdown('<div class="tc-gap-8"></div>', unsafe_allow_html=True)
            trade_date = st.date_input(
                "交易日",
                value=date.today(),
                disabled=not use_trade_date,
                label_visibility="collapsed",
            )
        with c2:
            _label("策略")
            strategy = st.selectbox(
                "策略", STRATEGY_OPTIONS, index=0, label_visibility="collapsed"
            )
        with c3:
            _label("批次号")
            batch_no = st.text_input(
                "批次号",
                placeholder="为空则自动生成",
                label_visibility="collapsed",
            )
        submitted = st.form_submit_button("启动任务", type="primary")

    if submitted:
        params = {
            "trade_date": str(trade_date) if use_trade_date else None,
            "strategy": strategy,
            "batch_no": (batch_no or "").strip() or None,
        }
        command = get_task_command(task.task_id, **params)
        run_id = start_task(task.task_id, command, params=params)
        st.success(f"启动成功：{run_id}")
        st.session_state["selected_task_run_id"] = run_id
        st.rerun()


def _render_tech_panel(task):
    st.markdown('<div class="tc-section">运行参数</div>', unsafe_allow_html=True)
    with st.form("tc_tech_form"):
        _label("评分范围", strong=True)
        mode = st.radio(
            "评分范围",
            ["最近N天", "指定日期", "指定批次"],
            horizontal=True,
            label_visibility="collapsed",
        )
        st.markdown('<div class="tc-gap-12"></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            _label("最近天数")
            days = st.number_input(
                "最近天数",
                min_value=1,
                max_value=30,
                value=1,
                step=1,
                disabled=mode != "最近N天",
                label_visibility="collapsed",
            )
        with c2:
            _label("评分日期")
            score_date = st.date_input(
                "评分日期",
                value=date.today(),
                disabled=mode != "指定日期",
                label_visibility="collapsed",
            )
        with c3:
            _label("推荐批次号")
            batch_no = st.text_input(
                "推荐批次号",
                disabled=mode != "指定批次",
                placeholder="输入批次号…",
                label_visibility="collapsed",
            )
        submitted = st.form_submit_button("启动任务", type="primary")

    if submitted:
        params = {
            "mode": mode,
            "days": int(days),
            "score_date": str(score_date) if mode == "指定日期" else None,
            "batch_no": (batch_no or "").strip() or None,
        }
        command = get_task_command(task.task_id, **params)
        run_id = start_task(task.task_id, command, params=params)
        st.success(f"启动成功：{run_id}")
        st.session_state["selected_task_run_id"] = run_id
        st.rerun()


def _render_action_panel(tasks):
    selected_id = st.session_state.get("selected_task_id")
    action = st.session_state.get("selected_task_action")
    if not selected_id or not action:
        return

    task = next((t for t in tasks if t.task_id == selected_id), None)
    if not task:
        return

    st.markdown('<div class="tc-card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="tc-section">{html.escape(task.name)} · {html.escape(action)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"任务ID：{task.task_id} ｜ 工作目录：{task.cwd}")
    st.code(_format_command(task.base_command), language="bash")

    if action == "start":
        if task.task_id == "run_strategy":
            _render_strategy_panel(task)
        elif task.task_id == "tech_score":
            _render_tech_panel(task)
        else:
            _btn_marker("primary")
            if st.button("确认启动", type="primary", key=f"tc_confirm_start_{task.task_id}"):
                _start_simple_task(task)

    elif action == "delete":
        st.warning("只会从任务中心调度列表移除记录，不会删除服务器脚本代码。")
        confirm = st.checkbox("确认从调度列表移除该任务", key=f"tc_del_confirm_{task.task_id}")
        _btn_marker("danger")
        if st.button("确认移除", type="secondary", key=f"tc_del_ok_{task.task_id}"):
            if not confirm:
                st.warning("请先勾选确认。")
            else:
                remove_type = remove_task_from_schedule(task.task_id)
                msg = "已从调度列表移除。"
                if remove_type == "builtin":
                    msg = "已隐藏内置任务；服务器脚本代码没有删除。"
                st.success(msg)
                st.session_state.pop("selected_task_id", None)
                st.session_state.pop("selected_task_action", None)
                st.rerun()

    elif action == "log":
        _render_logs(task.task_id)

    st.markdown("</div>", unsafe_allow_html=True)


def _render_logs(task_id=None):
    runs = list_recent_runs(limit=200)
    if task_id:
        runs = [r for r in runs if r.get("task_id") == task_id]

    if not runs:
        st.info("暂无执行记录。")
        return

    rows = []
    for run in runs[:30]:
        rows.append(
            {
                "运行编号": run.get("run_id"),
                "任务": run.get("task_name"),
                "状态": STATUS_LABELS.get(run.get("status"), run.get("status")),
                "开始时间": run.get("started_at"),
                "结束时间": run.get("finished_at"),
                "返回码": run.get("return_code"),
            }
        )
    st.dataframe(rows, width="stretch", hide_index=True)

    run_options = [r["run_id"] for r in runs if r.get("run_id")]
    if not run_options:
        st.info("暂无可查看的运行日志。")
        return

    scope = task_id or "all"
    selected_run_id = st.selectbox(
        "查看运行日志", run_options, key=f"tc_log_select_{scope}"
    )
    selected_run = read_run_status(selected_run_id)
    if not selected_run:
        st.warning("没有读取到该运行记录。")
        return

    st.code(_format_command(selected_run.get("command", [])), language="bash")
    t1, t2 = st.tabs(["标准输出", "错误输出"])
    with t1:
        st.code(_read_log_tail(selected_run.get("stdout_path", "")) or "暂无标准输出。")
    with t2:
        st.code(_read_log_tail(selected_run.get("stderr_path", "")) or "暂无错误输出。")


def _render_add_form():
    if "show_add_task" not in st.session_state:
        st.session_state["show_add_task"] = False

    show = st.checkbox("显示新增任务表单", key="show_add_task")
    if not show:
        return

    st.markdown('<div class="tc-card">', unsafe_allow_html=True)
    st.markdown('<div class="tc-section">新增任务</div>', unsafe_allow_html=True)
    with st.form("tc_add_task_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            _label("任务描述")
            name = st.text_input(
                "任务描述",
                placeholder="例如：同步资金流数据",
                label_visibility="collapsed",
            )
        with c2:
            _label("执行器")
            category = st.text_input(
                "执行器", value="自定义任务", label_visibility="collapsed"
            )
        with c3:
            _label("负责人")
            owner = st.text_input("负责人", value="admin", label_visibility="collapsed")

        _label("工作目录")
        cwd = st.text_input(
            "工作目录",
            value="/srv/python",
            help="必须在 /srv 目录下",
            label_visibility="collapsed",
        )
        _label("JobHandler / 执行命令")
        command_text = st.text_input(
            "命令",
            placeholder="/path/to/python script.py --arg value",
            label_visibility="collapsed",
        )
        _label("说明")
        description = st.text_area("说明", height=70, label_visibility="collapsed")
        _label("执行影响")
        impact = st.text_area("执行影响", height=70, label_visibility="collapsed")
        submitted = st.form_submit_button("保存", type="primary")

    if submitted:
        try:
            task = add_custom_task(
                name=name,
                category=category,
                description=description,
                cwd=cwd,
                command_text=command_text,
                impact=impact,
                owner=owner,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"新增成功：{task.name}")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render_task_center_page():
    """任务中心入口（由 app.py 调用）。"""
    _apply_tc_styles()
    st.markdown('<div class="tc-root">', unsafe_allow_html=True)

    # Header
    h1, h2 = st.columns([0.92, 0.08])
    with h1:
        st.markdown(
            '<div class="tc-title">任务管理</div><div class="tc-title-bar"></div>',
            unsafe_allow_html=True,
        )
    with h2:
        _btn_marker("primary")
        if st.button("新增", type="primary", key="tc_header_add"):
            st.session_state["show_add_task"] = not st.session_state.get(
                "show_add_task", False
            )
            st.rerun()

    st.markdown('<div class="tc-gap-12"></div>', unsafe_allow_html=True)
    _render_add_form()

    latest_runs = _latest_run_by_task()
    tasks = list_tasks()
    filtered = _render_toolbar(tasks, latest_runs)

    _label("每页记录数")
    page_size = st.selectbox(
        "每页记录数",
        [10, 20, 50],
        index=0,
        format_func=lambda n: f"每页 {n} 条",
        label_visibility="collapsed",
        key="tc_page_size",
    )
    page_tasks = filtered[: int(page_size)]
    _render_table(page_tasks, latest_runs)
    st.caption(f"共 {len(filtered)} 条 · 当前展示 {len(page_tasks)} 条")

    _render_action_panel(tasks)

    st.markdown('<div class="tc-gap-12"></div>', unsafe_allow_html=True)
    show_logs = st.checkbox("查看全部执行记录", value=False, key="tc_show_all_logs")
    if show_logs:
        st.markdown('<div class="tc-card">', unsafe_allow_html=True)
        st.markdown('<div class="tc-section">全部执行记录</div>', unsafe_allow_html=True)
        _render_logs()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
