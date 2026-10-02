import re

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from stocklens.db import get_engine


def _normalize_a_share_code(value):
    if pd.isna(value):
        return pd.NA
    code = str(value).strip().upper()
    if code.endswith(".0"):
        code = code[:-2]
    match = re.search(r"(\d{6})", code)
    if match:
        return match.group(1)
    return code.zfill(6) if code.isdigit() else pd.NA


def attach_latest_hot_rank(
    recommendations,
    hot_ranks,
    *,
    captured_at,
    observation_cutoff=100,
):
    """把最近一次雪球热榜名次附加到推荐结果，不改变评分或行顺序。"""
    if "股票代码" not in recommendations.columns:
        raise ValueError("推荐结果缺少股票代码字段")

    result = recommendations.copy()
    result["_hot_stock_code"] = result["股票代码"].map(_normalize_a_share_code)

    rank_lookup = pd.DataFrame(columns=["_hot_stock_code", "_hot_rank_no"])
    if not hot_ranks.empty:
        required_columns = {"normalized_code", "rank_no"}
        missing_columns = required_columns.difference(hot_ranks.columns)
        if missing_columns:
            raise ValueError(
                "雪球热榜数据缺少字段：" + ", ".join(sorted(missing_columns))
            )
        rank_lookup = hot_ranks[["normalized_code", "rank_no"]].copy()
        rank_lookup["_hot_stock_code"] = rank_lookup["normalized_code"].map(
            _normalize_a_share_code
        )
        rank_lookup["_hot_rank_no"] = pd.to_numeric(
            rank_lookup["rank_no"], errors="coerce"
        )
        rank_lookup = (
            rank_lookup.dropna(subset=["_hot_stock_code", "_hot_rank_no"])
            .sort_values("_hot_rank_no")
            .drop_duplicates("_hot_stock_code", keep="first")
            [["_hot_stock_code", "_hot_rank_no"]]
        )

    result = result.merge(rank_lookup, on="_hot_stock_code", how="left", sort=False)
    if captured_at is None:
        result["雪球讨论热度排名"] = "暂无数据"
        result["雪球热度采集时间"] = pd.NaT
    else:
        cutoff_label = f"{int(observation_cutoff)}名外"
        result["雪球讨论热度排名"] = result["_hot_rank_no"].map(
            lambda value: (
                cutoff_label if pd.isna(value) else f"第{int(value)}名"
            )
        )
        result["雪球热度采集时间"] = captured_at

    result = result.drop(columns=["_hot_stock_code", "_hot_rank_no"])
    insert_at = result.columns.get_loc("股票名称") + 1 if "股票名称" in result else len(result.columns)
    for column in ("雪球讨论热度排名", "雪球热度采集时间"):
        values = result.pop(column)
        result.insert(insert_at, column, values)
        insert_at += 1
    return result


@st.cache_data(ttl=60, show_spinner=False)
def load_latest_hot_rank_lookup():
    """读取最近一次成功雪球快照中的A股排名；失败时返回空数据。"""
    engine = get_engine()
    try:
        with engine.connect() as connection:
            batches = pd.read_sql(
                text(
                    """
                    SELECT id, captured_at, observation_cutoff
                    FROM stock_hot_batch
                    WHERE source = 'XUEQIU' AND status = 'SUCCESS'
                    ORDER BY capture_slot DESC, id DESC
                    LIMIT 1
                    """
                ),
                connection,
            )
            if batches.empty:
                return {}, pd.DataFrame(columns=["normalized_code", "rank_no"])

            batch = batches.iloc[0]
            ranks = pd.read_sql(
                text(
                    """
                    SELECT normalized_code, rank_no
                    FROM stock_hot_snapshot
                    WHERE batch_id = :batch_id
                      AND market IN ('CN_SH', 'CN_SZ')
                      AND normalized_code IS NOT NULL
                    ORDER BY rank_no
                    """
                ),
                connection,
                params={"batch_id": int(batch["id"])},
            )
    except SQLAlchemyError:
        return {}, pd.DataFrame(columns=["normalized_code", "rank_no"])

    metadata = {
        "batch_id": int(batch["id"]),
        "captured_at": batch["captured_at"],
        "observation_cutoff": int(batch["observation_cutoff"]),
    }
    return metadata, ranks


def select_heat_change_top(data, limit=20):
    """选出热度涨跌幅绝对值最大的股票。"""
    comparable = data.dropna(subset=["heat_change_pct"]).copy()
    comparable["absolute_heat_change"] = comparable["heat_change_pct"].abs()
    return comparable.nlargest(limit, "absolute_heat_change").reset_index(drop=True)


def build_latest_comparison(latest, previous, *, top_n=50, market_data=None):
    """把最近两批榜单合并为可直接展示的排名、热度变化数据。"""
    if latest.empty:
        return latest.copy()

    current = latest.copy()
    current["rank_no"] = pd.to_numeric(current["rank_no"], errors="coerce")
    current["heat_score"] = pd.to_numeric(current["heat_score"], errors="coerce")
    current = current[current["rank_no"].between(1, top_n)].copy()

    if previous.empty:
        prior = pd.DataFrame(
            columns=["external_symbol", "previous_rank", "previous_heat"]
        )
    else:
        prior = previous[["external_symbol", "rank_no", "heat_score"]].copy()
        prior = prior.rename(
            columns={"rank_no": "previous_rank", "heat_score": "previous_heat"}
        )
        prior["previous_rank"] = pd.to_numeric(
            prior["previous_rank"], errors="coerce"
        )
        prior["previous_heat"] = pd.to_numeric(
            prior["previous_heat"], errors="coerce"
        )

    result = current.merge(prior, on="external_symbol", how="left")
    detail_columns = ["latest_price", "price_trade_date", "sector_name"]
    if (
        market_data is not None
        and not market_data.empty
        and "normalized_code" in result.columns
    ):
        details = market_data[
            ["normalized_code", *detail_columns]
        ].drop_duplicates("normalized_code")
        result = result.merge(details, on="normalized_code", how="left")
    else:
        for column in detail_columns:
            result[column] = pd.NA
    result["rank_change"] = result["previous_rank"] - result["rank_no"]
    result["heat_change"] = result["heat_score"] - result["previous_heat"]
    valid_previous_heat = result["previous_heat"].where(
        result["previous_heat"] != 0
    )
    result["heat_change_pct"] = (
        result["heat_change"] / valid_previous_heat * 100
    )
    result["change_direction"] = "持平"
    result.loc[result["heat_change"] > 0, "change_direction"] = "上升"
    result.loc[result["heat_change"] < 0, "change_direction"] = "下降"
    result.loc[result["previous_rank"].isna(), "change_direction"] = "新上榜"
    return result.sort_values("rank_no").reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False)
def load_hot_stock_dashboard(top_n=50):
    """读取最近两次成功快照，返回批次信息和Top N对比结果。"""
    top_n = min(max(int(top_n), 1), 50)
    engine = get_engine()

    with engine.connect() as connection:
        batches = pd.read_sql(
            text(
                """
                SELECT id, capture_slot, captured_at, item_count
                FROM stock_hot_batch
                WHERE source = 'XUEQIU' AND status = 'SUCCESS'
                ORDER BY capture_slot DESC, id DESC
                LIMIT 2
                """
            ),
            connection,
        )
        if batches.empty:
            return {}, pd.DataFrame()

        latest_batch_id = int(batches.iloc[0]["id"])
        latest = pd.read_sql(
            text(
                """
                SELECT rank_no, external_symbol, normalized_code, stock_name,
                       market, heat_score, quote_change_pct, topic
                FROM stock_hot_snapshot
                WHERE batch_id = :batch_id AND rank_no <= :top_n
                ORDER BY rank_no
                """
            ),
            connection,
            params={"batch_id": latest_batch_id, "top_n": top_n},
        )
        market_data = pd.read_sql(
            text(
                """
                SELECT s.normalized_code,
                       d.close_price AS latest_price,
                       d.trade_date AS price_trade_date,
                       b.sub_industry AS sector_name
                FROM stock_hot_snapshot s
                LEFT JOIN stock_basic_info b
                    ON b.stock_code = s.normalized_code
                LEFT JOIN stock_daily d
                    ON d.stock_code = s.normalized_code
                   AND d.trade_date = (
                       SELECT MAX(d2.trade_date)
                       FROM stock_daily d2
                       WHERE d2.stock_code = s.normalized_code
                   )
                WHERE s.batch_id = :batch_id
                  AND s.market IN ('CN_SH', 'CN_SZ')
                  AND s.normalized_code IS NOT NULL
                """
            ),
            connection,
            params={"batch_id": latest_batch_id},
        )

        previous = pd.DataFrame()
        if len(batches) > 1:
            previous = pd.read_sql(
                text(
                    """
                    SELECT rank_no, external_symbol, heat_score
                    FROM stock_hot_snapshot
                    WHERE batch_id = :batch_id
                    """
                ),
                connection,
                params={"batch_id": int(batches.iloc[1]["id"])},
            )

    metadata = {
        "batch_id": latest_batch_id,
        "capture_slot": batches.iloc[0]["capture_slot"],
        "captured_at": batches.iloc[0]["captured_at"],
        "item_count": int(batches.iloc[0]["item_count"]),
        "previous_capture_slot": (
            batches.iloc[1]["capture_slot"] if len(batches) > 1 else None
        ),
    }
    return metadata, build_latest_comparison(
        latest,
        previous,
        top_n=top_n,
        market_data=market_data,
    )
