"""读取已冻结的新算法候选快照；无快照时绝不退回原推荐。"""
import json
import os
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
import pandas as pd
from sqlalchemy import text

from stocklens.db import get_engine
from stocklens.config import PROJECT_DIR, configured_path

ALGORITHM_VERSION = "candidate-v1.2"
ALGORITHM_EFFECTIVE_DATE = date(2026, 10, 2)
SNAPSHOT_DIR = configured_path('STOCKLENS_SHADOW_DIR',
    configured_path('STOCKLENS_STRATEGY_DIR', PROJECT_DIR.parent / 'strategies') / 'outputs' / 'recommendation_shadow')


def read_optimized_ids(start_date, end_date, selected_batch, directory=SNAPSHOT_DIR):
    start, end = str(start_date)[:10], str(end_date)[:10]
    accepted = set()
    info = dict(evaluated_records=0, evaluated_batches=[], replayed=False, issues=[])
    for path in sorted(Path(directory).glob(f"*_{ALGORITHM_VERSION}.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload["version"] != ALGORITHM_VERSION:
                continue
            day = str(date.fromisoformat(payload["data_cutoff"]))
            batch = payload["batch_no"]
            if not start <= day <= end or (selected_batch != "全部" and batch != selected_batch):
                continue
            candidates = set()
            records = payload["records"]
            for row in records:
                if str(row["recommend_date"])[:10] != day or row["recommend_batch_no"] != batch:
                    raise ValueError("记录与快照日期/批次不一致")
                if type(row["id"]) is not int or row["id"] <= 0:
                    raise ValueError("推荐ID无效")
                if row["decision"] == "候选保留":
                    candidates.add(row["id"])
            accepted.update(candidates)
            info["evaluated_records"] += len(records)
            info["evaluated_batches"].append((day,batch))
            info["replayed"] |= payload.get("mode") != "前向影子"
        except (OSError, ValueError, KeyError, TypeError):
            info["issues"].append(path.name)
    return tuple(sorted(accepted)), info


@st.cache_data(ttl=60,show_spinner=False)
def load_optimized_ids(start_date,end_date,selected_batch):
    return read_optimized_ids(start_date,end_date,selected_batch)


@st.cache_data(ttl=60, show_spinner=False)
def load_display_ids(start_date, end_date, selected_batch):
    """保留生效日前的全部历史；生效日起只使用冻结的新规则保留结果。"""
    start, end = str(start_date)[:10], str(end_date)[:10]
    cutoff = ALGORITHM_EFFECTIVE_DATE.isoformat()
    historical = set()
    if start < cutoff:
        params = dict(start_date=start, end_date=min(
            end, (ALGORITHM_EFFECTIVE_DATE - timedelta(days=1)).isoformat()))
        batch_where = ""
        if selected_batch != "全部":
            batch_where = " AND recommend_batch_no = :selected_batch"
            params["selected_batch"] = selected_batch
        rows = pd.read_sql(text(
            "SELECT id FROM stock_recommend_record "
            "WHERE recommend_date BETWEEN :start_date AND :end_date" + batch_where),
            get_engine(), params=params)
        historical.update(int(value) for value in rows["id"])
    accepted = ()
    info = dict(evaluated_records=0, evaluated_batches=[], replayed=False, issues=[])
    if end >= cutoff:
        accepted, info = read_optimized_ids(max(start, cutoff), end, selected_batch)
    info["historical_records"] = len(historical)
    info["optimized_records"] = len(accepted)
    return tuple(sorted(historical.union(accepted))), info
