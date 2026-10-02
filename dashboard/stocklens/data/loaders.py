import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, text

from stocklens.db import get_engine
from stocklens.data.hot_stock_loaders import (
    attach_latest_hot_rank,
    load_latest_hot_rank_lookup,
)


# ==========================================================
# 5. 查询基础数据
# ==========================================================
@st.cache_data(ttl=300)
def load_date_range():
    """
    查询推荐日期范围。
    """
    engine = get_engine()
    sql = text("""
        SELECT
            MIN(recommend_date) AS min_date,
            MAX(recommend_date) AS max_date
        FROM stock_recommend_record
    """)
    df = pd.read_sql(sql, engine)

    if df.empty or pd.isna(df.loc[0, "min_date"]):
        return None, None

    return df.loc[0, "min_date"], df.loc[0, "max_date"]


@st.cache_data(ttl=300)
def load_batch_list(start_date, end_date):
    """
    查询推荐批次号。
    """
    engine = get_engine()
    sql = text("""
        SELECT DISTINCT recommend_batch_no
        FROM stock_recommend_record
        WHERE recommend_date BETWEEN :start_date AND :end_date
        ORDER BY recommend_batch_no DESC
    """)

    df = pd.read_sql(
        sql,
        engine,
        params={
            "start_date": start_date,
            "end_date": end_date,
        },
    )

    return df["recommend_batch_no"].dropna().tolist()


# ==========================================================
# 6. 查询统计数据
# ==========================================================
@st.cache_data(ttl=300)
def load_strategy_stats(start_date, end_date, group_type, selected_batch, selected_status, recommendation_ids=None):
    """
    按维度统计推荐成功率和涨幅。

    成功判断：
    pct_Nd > 0 视为上涨成功。
    """
    engine = get_engine()

    if group_type == "按策略":
        select_group = """
            r.strategy_name AS `推荐策略`
        """
        group_by = """
            r.strategy_name
        """
    elif group_type == "按策略 + 行业":
        select_group = """
            r.strategy_name AS `推荐策略`,
            IFNULL(r.industry, '未分类') AS `所属行业`
        """
        group_by = """
            r.strategy_name,
            IFNULL(r.industry, '未分类')
        """
    elif group_type == "按推荐日期 + 策略":
        select_group = """
            r.recommend_date AS `推荐日期`,
            r.strategy_name AS `推荐策略`
        """
        group_by = """
            r.recommend_date,
            r.strategy_name
        """
    else:
        select_group = """
            r.recommend_date AS `推荐日期`,
            r.strategy_name AS `推荐策略`,
            IFNULL(r.industry, '未分类') AS `所属行业`
        """
        group_by = """
            r.recommend_date,
            r.strategy_name,
            IFNULL(r.industry, '未分类')
        """

    extra_where = ""
    params = {
        "start_date": start_date,
        "end_date": end_date,
    }

    if selected_batch != "全部":
        extra_where += " AND r.recommend_batch_no = :selected_batch "
        params["selected_batch"] = selected_batch

    if selected_status != "全部":
        extra_where += " AND r.status = :selected_status "
        params["selected_status"] = selected_status

    if recommendation_ids is not None:
        extra_where += " AND r.id IN :recommendation_ids "
        params["recommendation_ids"] = tuple(recommendation_ids)

    sql = text(f"""
        SELECT
            {select_group},

            COUNT(*) AS `推荐总数`,

            COUNT(t.pct_1d) AS `已有1日数据数量`,
            SUM(CASE WHEN t.pct_1d > 0 THEN 1 ELSE 0 END) AS `1日上涨数量`,
            SUM(CASE WHEN t.pct_1d IS NOT NULL AND t.pct_1d <= 0 THEN 1 ELSE 0 END) AS `1日未上涨数量`,
            ROUND(
                SUM(CASE WHEN t.pct_1d > 0 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(t.pct_1d), 0) * 100,
                2
            ) AS `1日成功率%`,
            ROUND(AVG(t.pct_1d), 2) AS `1日平均涨幅%`,

            COUNT(t.pct_3d) AS `已有3日数据数量`,
            SUM(CASE WHEN t.pct_3d > 0 THEN 1 ELSE 0 END) AS `3日上涨数量`,
            SUM(CASE WHEN t.pct_3d IS NOT NULL AND t.pct_3d <= 0 THEN 1 ELSE 0 END) AS `3日未上涨数量`,
            ROUND(
                SUM(CASE WHEN t.pct_3d > 0 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(t.pct_3d), 0) * 100,
                2
            ) AS `3日成功率%`,
            ROUND(AVG(t.pct_3d), 2) AS `3日平均涨幅%`,

            COUNT(t.pct_5d) AS `已有5日数据数量`,
            SUM(CASE WHEN t.pct_5d > 0 THEN 1 ELSE 0 END) AS `5日上涨数量`,
            SUM(CASE WHEN t.pct_5d IS NOT NULL AND t.pct_5d <= 0 THEN 1 ELSE 0 END) AS `5日未上涨数量`,
            ROUND(
                SUM(CASE WHEN t.pct_5d > 0 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(t.pct_5d), 0) * 100,
                2
            ) AS `5日成功率%`,
            ROUND(AVG(t.pct_5d), 2) AS `5日平均涨幅%`,

            COUNT(t.pct_10d) AS `已有10日数据数量`,
            SUM(CASE WHEN t.pct_10d > 0 THEN 1 ELSE 0 END) AS `10日上涨数量`,
            SUM(CASE WHEN t.pct_10d IS NOT NULL AND t.pct_10d <= 0 THEN 1 ELSE 0 END) AS `10日未上涨数量`,
            ROUND(
                SUM(CASE WHEN t.pct_10d > 0 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(t.pct_10d), 0) * 100,
                2
            ) AS `10日成功率%`,
            ROUND(AVG(t.pct_10d), 2) AS `10日平均涨幅%`,

            COUNT(t.pct_20d) AS `已有20日数据数量`,
            SUM(CASE WHEN t.pct_20d > 0 THEN 1 ELSE 0 END) AS `20日上涨数量`,
            SUM(CASE WHEN t.pct_20d IS NOT NULL AND t.pct_20d <= 0 THEN 1 ELSE 0 END) AS `20日未上涨数量`,
            ROUND(
                SUM(CASE WHEN t.pct_20d > 0 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(t.pct_20d), 0) * 100,
                2
            ) AS `20日成功率%`,
            ROUND(AVG(t.pct_20d), 2) AS `20日平均涨幅%`,

            ROUND(AVG(t.max_pct_20d), 2) AS `20日内平均最大涨幅%`,
            ROUND(AVG(t.max_drawdown_20d), 2) AS `20日内平均最大回撤%`

        FROM stock_recommend_record r
        LEFT JOIN stock_recommend_track t
            ON t.recommend_id = r.id
        WHERE
            r.recommend_date BETWEEN :start_date AND :end_date
            {extra_where}
        GROUP BY
            {group_by}
    """)

    if recommendation_ids is not None:
        sql = sql.bindparams(bindparam("recommendation_ids", expanding=True))
    return pd.read_sql(sql, engine, params=params)


# ==========================================================
# 7. 查询单只股票明细
# ==========================================================
@st.cache_data(ttl=300)
def load_detail_data(start_date, end_date, selected_batch, selected_status, recommendation_ids=None):
    """
    查询单只股票推荐后的具体表现。

    注意：
    这里完全按照你的表结构来查询，不使用 current_price/current_return。
    使用 LEFT JOIN，推荐了但还没生成跟踪记录的股票也会展示。
    """
    engine = get_engine()

    extra_where = ""
    params = {
        "start_date": start_date,
        "end_date": end_date,
    }

    if selected_batch != "全部":
        extra_where += " AND r.recommend_batch_no = :selected_batch "
        params["selected_batch"] = selected_batch

    if selected_status != "全部":
        extra_where += " AND r.status = :selected_status "
        params["selected_status"] = selected_status

    if recommendation_ids is not None:
        extra_where += " AND r.id IN :recommendation_ids "
        params["recommendation_ids"] = tuple(recommendation_ids)

    sql = text(f"""
        SELECT
            r.recommend_batch_no AS `推荐批次号`,
            r.recommend_date AS `推荐日期`,
            r.strategy_name AS `推荐策略`,
            IFNULL(r.industry, '未分类') AS `所属行业`,

            r.stock_code AS `股票代码`,
            r.stock_name AS `股票名称`,
            r.recommend_price AS `推荐价格`,
            r.recommend_score AS `推荐分数`,

            t.close_price_1d AS `1日收盘价`,
            t.pct_1d AS `1日涨幅%`,

            t.close_price_3d AS `3日收盘价`,
            t.pct_3d AS `3日涨幅%`,

            t.close_price_5d AS `5日收盘价`,
            t.pct_5d AS `5日涨幅%`,

            t.close_price_10d AS `10日收盘价`,
            t.pct_10d AS `10日涨幅%`,

            t.close_price_20d AS `20日收盘价`,
            t.pct_20d AS `20日涨幅%`,

            t.max_price_20d AS `20日内最高价`,
            t.max_pct_20d AS `20日内最大涨幅%`,
            t.min_price_20d AS `20日内最低价`,
            t.max_drawdown_20d AS `20日内最大回撤%`,

            t.success_flag AS `是否成功`,
            t.success_rule AS `成功规则`,

            r.status AS `推荐状态`,
            r.reason AS `推荐理由`,

            t.update_time AS `跟踪更新时间`

        FROM stock_recommend_record r
        LEFT JOIN stock_recommend_track t
            ON t.recommend_id = r.id
        WHERE
            r.recommend_date BETWEEN :start_date AND :end_date
            {extra_where}
        ORDER BY
            r.recommend_date DESC,
            r.strategy_name,
            IFNULL(r.industry, '未分类'),
            r.stock_code
    """)

    if recommendation_ids is not None:
        sql = sql.bindparams(bindparam("recommendation_ids", expanding=True))
    detail = pd.read_sql(sql, engine, params=params)
    hot_metadata, hot_ranks = load_latest_hot_rank_lookup()
    return attach_latest_hot_rank(
        detail,
        hot_ranks,
        captured_at=hot_metadata.get("captured_at"),
        observation_cutoff=hot_metadata.get("observation_cutoff", 100),
    )


@st.cache_data(ttl=300)
def load_tech_score_data(start_date, end_date, selected_batch, selected_status):
    """
    查询当前推荐股票的技术评分。

    使用推荐记录作为主表，LEFT JOIN 技术评分表；即使暂时没有评分记录，
    推荐股票也会出现在结果中，便于发现评分缺口。
    """
    engine = get_engine()

    extra_where = ""
    params = {
        "start_date": start_date,
        "end_date": end_date,
    }

    if selected_batch != "全部":
        extra_where += " AND r.recommend_batch_no = :selected_batch "
        params["selected_batch"] = selected_batch

    if selected_status != "全部":
        extra_where += " AND r.status = :selected_status "
        params["selected_status"] = selected_status

    sql = text(f"""
        SELECT
            r.recommend_batch_no AS `推荐批次号`,
            r.recommend_date AS `推荐日期`,
            r.strategy_name AS `推荐策略`,
            IFNULL(r.industry, '未分类') AS `所属行业`,
            r.stock_code AS `股票代码`,
            r.stock_name AS `股票名称`,
            r.recommend_price AS `推荐价格`,
            r.recommend_score AS `推荐分数`,
            r.status AS `推荐状态`,

            s.trade_date AS `评分交易日`,
            s.close_price AS `评分收盘价`,
            s.technical_score AS `技术综合分`,
            s.technical_level AS `技术等级`,
            s.trend_score AS `趋势分`,
            s.position_score AS `位置分`,
            s.momentum_score AS `动量分`,
            s.volume_score AS `量能分`,
            s.risk_score AS `风险分`,
            s.score_model AS `评分模型`,
            s.score_version AS `评分版本`,

            s.ma5 AS `MA5`,
            s.ma10 AS `MA10`,
            s.ma20 AS `MA20`,
            s.ma60 AS `MA60`,
            s.rsi_14 AS `RSI14`,
            s.macd AS `MACD`,
            s.macd_signal AS `MACD信号线`,
            s.macd_hist AS `MACD柱`,
            s.adx_14 AS `ADX14`,
            s.plus_di_14 AS `+DI14`,
            s.minus_di_14 AS `-DI14`,
            s.atr_14 AS `ATR14`,
            s.change_percent AS `当日涨跌幅%`,
            s.amplitude_5d AS `5日振幅%`,
            s.bias_ma20 AS `MA20乖离率%`,
            s.close_position_20 AS `20日收盘位置%`,
            s.volume_ratio_5 AS `5日量比`,
            s.volume_ratio_10 AS `10日量比`,
            s.upper_shadow_ratio AS `上影线比例`,

            s.signal_tag AS `信号标签`,
            s.risk_level AS `风险等级`,
            s.trade_advice AS `交易建议`,
            s.score_reason AS `评分原因`,
            s.risk_warning AS `风险提示`,
            s.update_time AS `评分更新时间`

        FROM stock_recommend_record r
        LEFT JOIN stock_recommend_tech_score s
            ON s.recommend_id = r.id
        WHERE
            r.recommend_date BETWEEN :start_date AND :end_date
            {extra_where}
        ORDER BY
            r.recommend_date DESC,
            s.technical_score DESC,
            r.strategy_name,
            r.stock_code
    """)

    tech_scores = pd.read_sql(sql, engine, params=params)
    hot_metadata, hot_ranks = load_latest_hot_rank_lookup()
    return attach_latest_hot_rank(
        tech_scores,
        hot_ranks,
        captured_at=hot_metadata.get("captured_at"),
        observation_cutoff=hot_metadata.get("observation_cutoff", 100),
    )


@st.cache_data(ttl=300)
def load_sector_hot_data(min_stock_count=5):
    """
    计算近期热门板块/行业。

    主线使用 stock_daily 最近 10 个交易日行情，辅助叠加最近 7 天推荐热度
    和技术评分，避免只看单日涨跌造成误判。
    """
    engine = get_engine()

    sql = text("""
        WITH recent_dates AS (
            SELECT DISTINCT trade_date
            FROM stock_daily
            ORDER BY trade_date DESC
            LIMIT 10
        ),
        recent_5_dates AS (
            SELECT DISTINCT trade_date
            FROM stock_daily
            ORDER BY trade_date DESC
            LIMIT 5
        ),
        daily_industry AS (
            SELECT
                COALESCE(b.sub_industry, '未分类') AS industry,
                d.stock_code,
                d.trade_date,
                d.change_percent,
                d.turnover_rate
            FROM stock_daily d
            JOIN recent_dates rd
                ON rd.trade_date = d.trade_date
            LEFT JOIN stock_basic_info b
                ON b.stock_code = d.stock_code
            WHERE b.sub_industry IS NOT NULL
        ),
        market_stats AS (
            SELECT
                industry,
                COUNT(DISTINCT stock_code) AS stock_count,
                ROUND(
                    AVG(
                        CASE
                            WHEN trade_date >= (SELECT MIN(trade_date) FROM recent_5_dates)
                            THEN change_percent
                        END
                    ),
                    2
                ) AS avg_5td_change,
                ROUND(AVG(change_percent), 2) AS avg_10td_change,
                ROUND(AVG(turnover_rate), 2) AS avg_turnover_rate,
                ROUND(
                    SUM(CASE WHEN change_percent > 0 THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0) * 100,
                    2
                ) AS up_ratio
            FROM daily_industry
            GROUP BY industry
        ),
        rec_stats AS (
            SELECT
                COALESCE(r.industry, '未分类') AS industry,
                COUNT(*) AS recommend_count_7d,
                COUNT(DISTINCT r.stock_code) AS recommend_stock_count_7d,
                ROUND(AVG(r.recommend_score), 2) AS avg_recommend_score,
                ROUND(AVG(s.technical_score), 2) AS avg_technical_score
            FROM stock_recommend_record r
            LEFT JOIN stock_recommend_tech_score s
                ON s.recommend_id = r.id
            WHERE r.recommend_date >= DATE_SUB(
                (SELECT MAX(recommend_date) FROM stock_recommend_record),
                INTERVAL 7 DAY
            )
            GROUP BY COALESCE(r.industry, '未分类')
        )
        SELECT
            m.industry AS `板块行业`,
            m.stock_count AS `成分股数`,
            m.avg_5td_change AS `近5交易日均涨幅%`,
            m.avg_10td_change AS `近10交易日均涨幅%`,
            m.avg_turnover_rate AS `平均换手率%`,
            m.up_ratio AS `上涨占比%`,
            COALESCE(r.recommend_count_7d, 0) AS `近7日推荐次数`,
            COALESCE(r.recommend_stock_count_7d, 0) AS `近7日推荐股票数`,
            r.avg_recommend_score AS `平均推荐分`,
            r.avg_technical_score AS `平均技术分`,
            ROUND(
                COALESCE(m.avg_5td_change, 0) * 0.42
                + COALESCE(m.avg_10td_change, 0) * 0.18
                + COALESCE(m.up_ratio, 0) * 0.025
                + LEAST(COALESCE(m.avg_turnover_rate, 0), 15) * 0.12
                + LEAST(COALESCE(r.recommend_count_7d, 0), 100) * 0.035
                + COALESCE(r.avg_technical_score, 0) * 0.025,
                2
            ) AS `板块热度分`
        FROM market_stats m
        LEFT JOIN rec_stats r
            ON r.industry = m.industry
        WHERE m.stock_count >= :min_stock_count
        ORDER BY `板块热度分` DESC
    """)

    return pd.read_sql(sql, engine, params={"min_stock_count": min_stock_count})


# ==========================================================
# 8. 数值类型统一处理
# ==========================================================
def normalize_numeric_columns(df):
    """
    将统计结果中的数值字段统一转换为 float。

    用途：
    解决 Plotly Express 宽表多列画图时的字段类型不一致问题。
    """
    numeric_cols = [
        "推荐总数",

        "已有1日数据数量",
        "1日上涨数量",
        "1日未上涨数量",
        "1日成功率%",
        "1日平均涨幅%",

        "已有3日数据数量",
        "3日上涨数量",
        "3日未上涨数量",
        "3日成功率%",
        "3日平均涨幅%",

        "已有5日数据数量",
        "5日上涨数量",
        "5日未上涨数量",
        "5日成功率%",
        "5日平均涨幅%",

        "已有10日数据数量",
        "10日上涨数量",
        "10日未上涨数量",
        "10日成功率%",
        "10日平均涨幅%",

        "已有20日数据数量",
        "20日上涨数量",
        "20日未上涨数量",
        "20日成功率%",
        "20日平均涨幅%",

        "20日内平均最大涨幅%",
        "20日内平均最大回撤%",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def normalize_detail_numeric_columns(df):
    """
    将明细表中的价格、涨幅、分数字段统一转换为数值。
    """
    numeric_cols = [
        "推荐价格",
        "推荐分数",

        "1日收盘价",
        "1日涨幅%",
        "3日收盘价",
        "3日涨幅%",
        "5日收盘价",
        "5日涨幅%",
        "10日收盘价",
        "10日涨幅%",
        "20日收盘价",
        "20日涨幅%",

        "20日内最高价",
        "20日内最大涨幅%",
        "20日内最低价",
        "20日内最大回撤%",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def normalize_tech_score_numeric_columns(df):
    """
    将技术评分表中的价格、评分、指标字段统一转换为数值。
    """
    numeric_cols = [
        "推荐价格",
        "推荐分数",
        "评分收盘价",
        "技术综合分",
        "趋势分",
        "位置分",
        "动量分",
        "量能分",
        "风险分",
        "MA5",
        "MA10",
        "MA20",
        "MA60",
        "RSI14",
        "MACD",
        "MACD信号线",
        "MACD柱",
        "ADX14",
        "+DI14",
        "-DI14",
        "ATR14",
        "当日涨跌幅%",
        "5日振幅%",
        "MA20乖离率%",
        "20日收盘位置%",
        "5日量比",
        "10日量比",
        "上影线比例",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def normalize_sector_hot_numeric_columns(df):
    """
    将板块热度表中的涨幅、推荐、评分字段统一转换为数值。
    """
    numeric_cols = [
        "成分股数",
        "近5交易日均涨幅%",
        "近10交易日均涨幅%",
        "平均换手率%",
        "上涨占比%",
        "近7日推荐次数",
        "近7日推荐股票数",
        "平均推荐分",
        "平均技术分",
        "板块热度分",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df
