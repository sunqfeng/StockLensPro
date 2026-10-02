from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import text

from stocklens.db import get_engine


def build_price_history(daily, recommend_date, recommend_price, now, quote=None):
    """保留真实每日行情；只接受当天有效报价，不生成休市日价格。"""
    start = pd.Timestamp(recommend_date).normalize()
    today = pd.Timestamp(now.date())
    base = float(recommend_price)
    if not np.isfinite(base) or base <= 0:
        raise ValueError("推荐价格无效，无法计算推荐后涨跌幅。")
    frame = daily.reindex(columns=["trade_date", "close_price"]).copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    frame["close_price"] = pd.to_numeric(frame["close_price"], errors="coerce")
    frame = frame[
        frame["trade_date"].between(start, today)
        & np.isfinite(frame["close_price"]) & frame["close_price"].gt(0)
    ].drop_duplicates("trade_date", keep="last")
    frame["price_type"] = "收盘价"
    frame.loc[frame["trade_date"].eq(today), "price_type"] = "当日行情"
    if quote:
        timestamp = pd.to_datetime(quote.get("quote_time"), errors="coerce")
        price = pd.to_numeric(quote.get("close_price", float("nan")), errors="coerce")
        if price is None:
            price = float("nan")
        if pd.notna(timestamp) and timestamp.date() == now.date() and np.isfinite(price) and price > 0 and start <= today:
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert("Asia/Shanghai").tz_localize(None)
            if timestamp <= pd.Timestamp(now.replace(tzinfo=None)):
                frame = frame[~frame["trade_date"].eq(today)]
                kind = "盘中价格" if timestamp.time() < time(15) else "收盘报价"
                frame = pd.concat([frame, pd.DataFrame([{
                    "trade_date": today, "close_price": float(price),
                    "price_type": f"{kind} · {timestamp:%H:%M:%S}",
                }])], ignore_index=True)
    if start <= today and not frame["trade_date"].eq(start).any():
        frame = pd.concat([pd.DataFrame([{
            "trade_date": start, "close_price": base, "price_type": "推荐价起点",
        }]), frame], ignore_index=True)
    frame = frame.sort_values("trade_date").reset_index(drop=True)
    frame["return_pct"] = (frame["close_price"] / base - 1) * 100
    return frame


@st.cache_data(ttl=60, show_spinner=False)
def load_price_history(stock_code, recommend_date, recommend_price, today):
    """查询从推荐日至今天的所有日线，没有20日上限。"""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    daily = pd.read_sql(text("""
        SELECT trade_date, close_price FROM stock_daily
        WHERE stock_code=:code AND trade_date BETWEEN :start AND :end
        ORDER BY trade_date
    """), get_engine(), params={
        "code": str(stock_code).zfill(6), "start": recommend_date, "end": today,
    })
    quote = None
    warning = None
    # 只在可能有当日报价的时间查询；休市返回的旧报价由日期校验拒绝。
    if now.weekday() < 5 and now.time().replace(tzinfo=None) >= time(9, 15):
        try:
            from stocklens.paper_trading import fetch_quotes
            quote = fetch_quotes([str(stock_code).zfill(6)]).get(str(stock_code).zfill(6))
        except Exception:
            warning = "实时行情暂时不可用，当前展示已入库的每日价格。"
    return build_price_history(daily, recommend_date, recommend_price, now, quote), warning
