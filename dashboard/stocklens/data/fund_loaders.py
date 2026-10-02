import pandas as pd
import streamlit as st
from sqlalchemy import text

from stocklens.db import get_engine


@st.cache_data(ttl=600)
def load_fund_report_overview():
    """查询基金持仓报告期覆盖情况。

    这里读取股票维度汇总表，避免每次页面打开都扫描数百万条持仓明细。
    """
    engine = get_engine()
    sql = text("""
        SELECT
            report_date AS `报告期`,
            COUNT(*) AS `持仓明细数`,
            SUM(COALESCE(holding_fund_count, 0)) AS `覆盖基金数`,
            COUNT(DISTINCT stock_code) AS `覆盖股票数`,
            MAX(updated_at) AS `最近更新时间`
        FROM stock_fund_hold_summary
        GROUP BY report_date
        ORDER BY report_date DESC
    """)
    return pd.read_sql(sql, engine)


def choose_latest_complete_report(report_df, min_fund_count=3000):
    """选择最新完整报告期。"""
    if report_df.empty:
        return None

    complete_df = report_df[report_df["覆盖基金数"] >= int(min_fund_count)].copy()
    if complete_df.empty:
        return report_df.iloc[0]["报告期"]
    return complete_df.iloc[0]["报告期"]


@st.cache_data(ttl=600)
def load_fund_stock_ranking(report_date, keyword="", min_fund_count=1, min_hold_value=0.0, limit=100):
    """查询指定报告期的股票维度基金持仓排行。"""
    engine = get_engine()
    extra_where = ""
    params = {
        "report_date": report_date,
        "min_fund_count": int(min_fund_count),
        "min_hold_value": float(min_hold_value),
        "limit": int(limit),
    }

    if keyword:
        extra_where = " AND (s.stock_code LIKE :keyword OR s.stock_name LIKE :keyword) "
        params["keyword"] = f"%{keyword}%"

    sql = text(f"""
        SELECT
            s.report_date AS `报告期`,
            s.stock_code AS `股票代码`,
            s.stock_name AS `股票名称`,
            s.holding_fund_count AS `持有基金数`,
            ROUND(COALESCE(s.total_hold_value, 0), 2) AS `合计持仓市值`,
            ROUND(COALESCE(s.total_hold_shares, 0), 2) AS `合计持股数`,
            s.change_type AS `持股变化`,
            s.change_shares AS `持股变动数值`,
            s.change_ratio AS `持股变动比例%`,
            s.rank_no AS `排名`,
            s.updated_at AS `最近更新时间`
        FROM stock_fund_hold_summary s
        WHERE s.report_date = :report_date
          {extra_where}
          AND s.holding_fund_count >= :min_fund_count
          AND COALESCE(s.total_hold_value, 0) >= :min_hold_value
        ORDER BY `持有基金数` DESC, `合计持仓市值` DESC
        LIMIT :limit
    """)
    return pd.read_sql(sql, engine, params=params)


@st.cache_data(ttl=600)
def load_fund_industry_ranking(report_date, min_fund_count=1, min_hold_value=0.0, limit=50):
    """查询指定报告期的基金持仓行业维度排行。"""
    engine = get_engine()
    sql = text("""
        SELECT
            s.report_date AS `报告期`,
            COALESCE(NULLIF(i.sub_industry, ''), '未分类') AS `板块/行业`,
            COUNT(*) AS `覆盖股票数`,
            SUM(COALESCE(s.holding_fund_count, 0)) AS `基金持仓次数`,
            ROUND(SUM(COALESCE(s.total_hold_value, 0)), 2) AS `合计持仓市值`,
            ROUND(SUM(COALESCE(s.total_hold_shares, 0)), 2) AS `合计持股数`,
            ROUND(AVG(COALESCE(s.holding_fund_count, 0)), 2) AS `单股平均持有基金数`,
            MAX(s.updated_at) AS `最近更新时间`
        FROM stock_fund_hold_summary s
        LEFT JOIN stock_full_info i ON i.stock_code = s.stock_code
        WHERE s.report_date = :report_date
          AND s.holding_fund_count >= :min_fund_count
        GROUP BY s.report_date, COALESCE(NULLIF(i.sub_industry, ''), '未分类')
        HAVING SUM(COALESCE(s.total_hold_value, 0)) >= :min_hold_value
        ORDER BY `基金持仓次数` DESC, `合计持仓市值` DESC
        LIMIT :limit
    """)
    return pd.read_sql(sql, engine, params={
        "report_date": report_date,
        "min_fund_count": int(min_fund_count),
        "min_hold_value": float(min_hold_value),
        "limit": int(limit),
    })


@st.cache_data(ttl=3600)
def load_fund_sector_options():
    """查询股票基础表中的可选板块/行业列表。"""
    engine = get_engine()
    sql = text("""
        SELECT
            sub_industry AS `板块`,
            COUNT(*) AS `股票数`
        FROM stock_full_info
        WHERE sub_industry IS NOT NULL
          AND sub_industry <> ''
        GROUP BY sub_industry
        ORDER BY sub_industry
    """)
    return pd.read_sql(sql, engine)


@st.cache_data(ttl=600)
def load_sector_fund_exposure(report_date, sector_name, min_nav_ratio=0.0):
    """查询指定报告期持有某个板块股票的基金。"""
    if not report_date or not sector_name:
        return pd.DataFrame()

    engine = get_engine()
    sql = text("""
        SELECT
            h.fund_code AS `基金代码`,
            COALESCE(h.fund_name, b.fund_name, h.fund_code) AS `基金名称`,
            COUNT(DISTINCT h.stock_code) AS `板块持仓股票数`,
            ROUND(SUM(COALESCE(h.hold_value, 0)), 2) AS `板块持仓市值`,
            ROUND(SUM(COALESCE(h.nav_ratio, 0)), 4) AS `板块净值占比%`
        FROM fund_stock_holdings h
        JOIN stock_full_info i ON i.stock_code = h.stock_code
        LEFT JOIN fund_basic b ON b.fund_code = h.fund_code
        WHERE h.report_date = :report_date
          AND i.sub_industry = :sector_name
        GROUP BY h.fund_code, COALESCE(h.fund_name, b.fund_name, h.fund_code)
        HAVING SUM(COALESCE(h.nav_ratio, 0)) >= :min_nav_ratio
    """)
    return pd.read_sql(sql, engine, params={
        "report_date": report_date,
        "sector_name": sector_name,
        "min_nav_ratio": float(min_nav_ratio),
    })


@st.cache_data(ttl=1800)
def load_fund_return_ranking(
    period_col="近1月",
    keyword="",
    limit=100,
    report_date=None,
    sector_name="",
    min_sector_nav_ratio=0.0,
):
    """查询开放基金收益排行。"""
    valid_periods = {"近1周", "近1月", "近1年"}
    if period_col not in valid_periods:
        period_col = "近1月"

    try:
        import akshare as ak

        rank_df = ak.fund_open_fund_rank_em(symbol="全部")
    except Exception as exc:
        return pd.DataFrame(), str(exc)

    if rank_df is None or rank_df.empty:
        return pd.DataFrame(), None

    frame = rank_df.copy()
    frame["基金代码"] = frame["基金代码"].astype(str).str.zfill(6)

    sector_df = pd.DataFrame()
    if sector_name:
        sector_df = load_sector_fund_exposure(report_date, sector_name, min_sector_nav_ratio)
        if sector_df.empty:
            return pd.DataFrame(), None
        sector_df["基金代码"] = sector_df["基金代码"].astype(str).str.zfill(6)
        frame = frame[frame["基金代码"].isin(set(sector_df["基金代码"]))].copy()

    if keyword:
        keyword_text = str(keyword).strip()
        frame = frame[
            frame["基金代码"].astype(str).str.contains(keyword_text, na=False)
            | frame["基金简称"].astype(str).str.contains(keyword_text, na=False)
        ].copy()

    numeric_cols = ["单位净值", "累计净值", "日增长率", "近1周", "近1月", "近1年"]
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    frame = frame.dropna(subset=[period_col]).sort_values(period_col, ascending=False).head(int(limit)).copy()
    if not sector_df.empty and not frame.empty:
        frame = frame.merge(
            sector_df[["基金代码", "板块持仓股票数", "板块持仓市值", "板块净值占比%"]],
            on="基金代码",
            how="left",
        )
    frame.insert(0, "排行", range(1, len(frame) + 1))

    display_cols = [
        "排行",
        "基金代码",
        "基金简称",
        "日期",
        "单位净值",
        "累计净值",
        "日增长率",
        "近1周",
        "近1月",
        "近1年",
        "板块持仓股票数",
        "板块持仓市值",
        "板块净值占比%",
    ]
    return frame[[col for col in display_cols if col in frame.columns]].reset_index(drop=True), None


@st.cache_data(ttl=600)
def load_fund_holding_industry_weights(report_date, fund_code, top_n=4):
    """查询单只基金在指定报告期的持仓行业占比。"""
    if not fund_code:
        return pd.DataFrame(), {}

    clean_code = str(fund_code).strip().zfill(6)
    engine = get_engine()

    def _query(target_report_date=None):
        report_filter = "AND h.report_date = :report_date" if target_report_date else ""
        params = {"fund_code": clean_code}
        if target_report_date:
            params["report_date"] = target_report_date

        sql = text(f"""
            SELECT
                h.report_date AS `报告期`,
                h.fund_code AS `基金代码`,
                COALESCE(h.fund_name, b.fund_name, h.fund_code) AS `基金名称`,
                COALESCE(NULLIF(i.sub_industry, ''), '未分类') AS `板块/行业`,
                COUNT(*) AS `持仓股票数`,
                ROUND(SUM(COALESCE(h.hold_value, 0)), 2) AS `持仓市值`,
                ROUND(SUM(COALESCE(h.nav_ratio, 0)), 4) AS `净值占比合计%`
            FROM fund_stock_holdings h
            LEFT JOIN fund_basic b ON b.fund_code = h.fund_code
            LEFT JOIN stock_full_info i ON i.stock_code = h.stock_code
            WHERE h.fund_code = :fund_code
              {report_filter}
            GROUP BY h.report_date, h.fund_code, COALESCE(h.fund_name, b.fund_name, h.fund_code),
                     COALESCE(NULLIF(i.sub_industry, ''), '未分类')
            ORDER BY h.report_date DESC, `持仓市值` DESC, `净值占比合计%` DESC
        """)
        return pd.read_sql(sql, engine, params=params)

    weights_df = _query(report_date)
    if weights_df.empty:
        weights_df = _query()

    if weights_df.empty:
        return pd.DataFrame(), {"基金代码": clean_code}

    latest_report = weights_df.iloc[0]["报告期"]
    weights_df = weights_df[weights_df["报告期"] == latest_report].copy()
    fund_name = weights_df.iloc[0]["基金名称"]

    total_value = float(weights_df["持仓市值"].fillna(0).sum())
    total_nav_ratio = float(weights_df["净值占比合计%"].fillna(0).sum())
    if total_value > 0:
        weights_df["占比%"] = weights_df["持仓市值"] / total_value * 100
        basis = "持仓市值"
    elif total_nav_ratio > 0:
        weights_df["占比%"] = weights_df["净值占比合计%"] / total_nav_ratio * 100
        basis = "净值占比"
    else:
        weights_df["占比%"] = 0
        basis = "无可用权重"

    weights_df = weights_df.sort_values("占比%", ascending=False).reset_index(drop=True)
    top_df = weights_df.head(int(top_n)).copy()
    other_df = weights_df.iloc[int(top_n):].copy()

    if not other_df.empty:
        other_row = {
            "报告期": latest_report,
            "基金代码": clean_code,
            "基金名称": fund_name,
            "板块/行业": "其他",
            "持仓股票数": int(other_df["持仓股票数"].sum()),
            "持仓市值": round(float(other_df["持仓市值"].sum()), 2),
            "净值占比合计%": round(float(other_df["净值占比合计%"].sum()), 4),
            "占比%": round(float(other_df["占比%"].sum()), 2),
        }
        top_df = pd.concat([top_df, pd.DataFrame([other_row])], ignore_index=True)

    top_df["占比%"] = top_df["占比%"].round(2)
    meta = {
        "基金代码": clean_code,
        "基金名称": fund_name,
        "报告期": latest_report,
        "权重口径": basis,
        "行业数": int(len(weights_df)),
    }
    return top_df.reset_index(drop=True), meta


@st.cache_data(ttl=600)
def load_stock_fund_holders(report_date, stock_code, limit=300):
    """查询某只股票在指定报告期被哪些基金持有。"""
    if not stock_code:
        return pd.DataFrame()

    engine = get_engine()
    sql = text("""
        SELECT
            h.report_date AS `报告期`,
            h.stock_code AS `股票代码`,
            h.stock_name AS `股票名称`,
            h.fund_code AS `基金代码`,
            COALESCE(h.fund_name, b.fund_name) AS `基金名称`,
            COALESCE(h.fund_type, b.fund_type) AS `基金类型`,
            h.hold_shares AS `持股数`,
            h.hold_value AS `持仓市值`,
            h.nav_ratio AS `占基金净值比例%`,
            h.quarter_label AS `季度说明`
        FROM fund_stock_holdings h
        LEFT JOIN fund_basic b ON b.fund_code = h.fund_code
        WHERE h.report_date = :report_date
          AND h.stock_code = :stock_code
        ORDER BY h.hold_value DESC, h.nav_ratio DESC
        LIMIT :limit
    """)
    return pd.read_sql(sql, engine, params={
        "report_date": report_date,
        "stock_code": str(stock_code).zfill(6),
        "limit": int(limit),
    })


@st.cache_data(ttl=600)
def load_fund_holdings_detail(report_date, fund_code):
    """查询某只基金在指定报告期的股票持仓明细。"""
    if not fund_code:
        return pd.DataFrame()

    engine = get_engine()
    sql = text("""
        SELECT
            h.report_date AS `报告期`,
            h.fund_code AS `基金代码`,
            COALESCE(h.fund_name, b.fund_name) AS `基金名称`,
            COALESCE(h.fund_type, b.fund_type) AS `基金类型`,
            h.stock_code AS `股票代码`,
            h.stock_name AS `股票名称`,
            h.hold_shares AS `持股数`,
            h.hold_value AS `持仓市值`,
            h.nav_ratio AS `占基金净值比例%`,
            h.quarter_label AS `季度说明`
        FROM fund_stock_holdings h
        LEFT JOIN fund_basic b ON b.fund_code = h.fund_code
        WHERE h.report_date = :report_date
          AND h.fund_code = :fund_code
        ORDER BY h.nav_ratio DESC, h.hold_value DESC
    """)
    return pd.read_sql(sql, engine, params={
        "report_date": report_date,
        "fund_code": str(fund_code).zfill(6),
    })


@st.cache_data(ttl=600)
def load_fund_basic_summary():
    """查询基金基础数据概览。"""
    engine = get_engine()
    sql = text("""
        SELECT
            COUNT(*) AS `基金总数`,
            SUM(CASE WHEN is_exchange_traded = 1 THEN 1 ELSE 0 END) AS `场内基金数`,
            SUM(CASE WHEN is_exchange_traded = 0 THEN 1 ELSE 0 END) AS `场外基金数`,
            COUNT(DISTINCT fund_type) AS `基金类型数`,
            MAX(updated_at) AS `最近更新时间`
        FROM fund_basic
    """)
    return pd.read_sql(sql, engine)
