# -*- coding: utf-8 -*-
"""
趋势回踩 + 行业主线 策略（第二轮优化版）。

核心逻辑：
    1. 行业评分：按细分行业计算涨跌幅、站上均线比例、强弱度，选出主线行业
    2. 趋势过滤：均线多头排列（close > ma20 > ma60, ma5 > ma10 > ma20）
    3. 回踩过滤：最近 N 日最低价触及 10 日线附近 + 缩量回踩
    4. 市值分层：小中盘（30-100亿）和中大盘（100-500亿）不同换手率/PE 标准
    5. 财务底线：利润同比、收入同比、ROE 最低要求
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import pandas as pd

from strategies.base import BaseStrategy, RecommendResult


# ============================================================
# 策略参数配置（自包含，不依赖 config.py）
# ============================================================
@dataclass
class TrendPullbackConfig:
    """趋势回踩策略参数，可在这里直接调参。"""

    # 行业层
    top_industry_limit: int = 20
    min_industry_stock_count: int = 3

    # 个股基础过滤
    min_listing_days: int = 250
    min_pct_20d: float = 8.0
    max_bias_ma10: float = 12.0
    ma10_touch_ratio: float = 1.05
    min_turnover: float = 1e8
    max_vol_ratio_5d: float = 3.0
    max_today_drop_pct: float = -2.0

    # 缩量回踩
    touch_vol_ratio_threshold: float = 0.85
    touch_window_days: int = 3

    # 市值分层（单位：亿）
    min_float_market_cap: float = 30.0
    max_float_market_cap: float = 500.0
    small_mid_cap_upper: float = 100.0
    large_cap_upper: float = 500.0

    # 分层换手率
    small_mid_min_turnover_rate: float = 2.0
    small_mid_max_turnover_rate: float = 20.0
    large_cap_min_turnover_rate: float = 1.0
    large_cap_max_turnover_rate: float = 12.0

    # 分层 PE(TTM)
    small_mid_max_pe_ttm: float = 120.0
    large_cap_max_pe_ttm: float = 65.0

    # 财务底线
    min_profit_yoy_pct: float = -10.0
    min_revenue_yoy_pct: float = -10.0
    min_roe_pct: float = 0.0

    # 结果控制
    top_result_limit: int = 30


# ============================================================
# 工具函数
# ============================================================

def _fill_ma_if_missing(df: pd.DataFrame) -> pd.DataFrame:
    """数据库均线为空时，用 rolling 回退计算。"""
    df = df.sort_values(["stock_code", "trade_date"]).copy()
    for ma_col, window_size in [("ma5", 5), ("ma10", 10), ("ma20", 20), ("ma60", 60)]:
        if ma_col not in df.columns:
            df[ma_col] = None
        calc = (
            df.groupby("stock_code")["close_price"]
            .transform(lambda s: s.rolling(window=window_size, min_periods=window_size).mean())
        )
        df[ma_col] = df[ma_col].where(df[ma_col].notna(), calc)
    return df


def _classify_cap_bucket(market_cap: float, cfg: TrendPullbackConfig) -> str:
    """根据流通市值（亿）判断所属市值层。"""
    if pd.isna(market_cap):
        return "OTHER"
    if cfg.min_float_market_cap <= market_cap < cfg.small_mid_cap_upper:
        return "SMALL_MID"
    if cfg.small_mid_cap_upper <= market_cap <= cfg.large_cap_upper:
        return "LARGE"
    return "OTHER"


def _build_reason(row: pd.Series) -> str:
    """根据选股结果行组装推荐理由。"""
    parts = [
        "策略筛选：趋势回踩 + 行业主线",
        f"股票名称：{row.get('stock_name', '')}",
        f"所属行业：{row.get('sub_industry', '')}",
    ]
    for key, label in [
        ("total_score", "总分"), ("industry_score", "行业分"),
        ("trend_score", "趋势分"), ("pullback_score", "回踩分"),
        ("quality_score", "质量分"),
    ]:
        val = row.get(key)
        if pd.notna(val):
            parts.append(f"{label}：{float(val):.2f}")

    for key, label in [
        ("pct_5d", "5日涨幅"), ("pct_10d", "10日涨幅"), ("pct_20d", "20日涨幅"),
        ("bias_ma10", "距10日线偏离"), ("vol_ratio_5d", "5日量比"),
        ("touch_vol_ratio", "回踩量比"),
    ]:
        val = row.get(key)
        if pd.notna(val):
            parts.append(f"{label}：{float(val):.2f}%")

    close_price = row.get("close_price")
    if pd.notna(close_price):
        parts.append(f"推荐价格：{float(close_price):.2f}")

    short_term = row.get("short_term_pattern", "")
    if isinstance(short_term, str) and short_term.strip():
        parts.append(f"短期形态：{short_term}")
    tip = row.get("recent_indicator_tip", "")
    if isinstance(tip, str) and tip.strip():
        parts.append(f"指标提示：{tip}")

    return "；".join(parts)


# ============================================================
# 格式化输出（中文展示）
# ============================================================

def _print_industry_result(df: pd.DataFrame, top_n: int = 20) -> None:
    """打印行业评分排名。"""
    if df.empty:
        print("没有行业结果可展示。")
        return

    disp = df.copy()
    for col in ["avg_pct_5d", "avg_pct_10d", "avg_pct_20d", "avg_strength", "avg_activity", "industry_score"]:
        if col in disp.columns:
            disp[col] = pd.to_numeric(disp[col], errors="coerce")

    disp = disp.rename(columns={
        "sub_industry": "细分行业", "stock_count": "股票数",
        "avg_pct_5d": "5日均涨幅%", "avg_pct_10d": "10日均涨幅%",
        "avg_pct_20d": "20日均涨幅%", "above_ma20_ratio": "站上MA20占比",
        "strong_stock_ratio": "强势股占比", "avg_strength": "平均强弱度%",
        "avg_activity": "平均活跃度", "industry_score": "行业总分",
    }).fillna("--")

    pd.set_option("display.unicode.east_asian_width", True)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", None)
    print(f"\n===== 最强行业（前{min(top_n, len(disp))}名） =====")
    print(disp.head(top_n).to_string(index=False))


def _print_stock_result(df: pd.DataFrame, top_n: int = 30) -> None:
    """打印个股选股结果。"""
    if df.empty:
        print("未选出符合条件的股票。")
        return

    disp = df.copy()
    if "trade_date" in disp.columns:
        disp["trade_date"] = pd.to_datetime(disp["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    disp = disp.rename(columns={
        "trade_date": "交易日期", "stock_code": "股票代码", "stock_name": "股票名称",
        "sub_industry": "细分行业", "close_price": "收盘价",
        "ma5": "5日线", "ma10": "10日线", "ma20": "20日线",
        "change_percent": "今日涨跌幅%", "turnover_rate_pct": "换手率%",
        "float_market_cap": "流通市值(亿)", "pct_5d": "5日涨幅%",
        "pct_10d": "10日涨幅%", "pct_20d": "20日涨幅%",
        "bias_ma10": "距10日线偏离%", "vol_ratio_5d": "量比(5日)",
        "touch_vol_ratio": "回踩量比", "strength_pct": "强弱度%",
        "activity": "活跃度", "industry_score": "行业分",
        "trend_score": "趋势分", "pullback_score": "回踩分",
        "quality_score": "质量分", "pattern_bonus": "形态加分",
        "total_score": "总分", "short_term_pattern": "短期形态",
        "recent_indicator_tip": "指标提示",
    }).fillna("--")

    pd.set_option("display.unicode.east_asian_width", True)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", None)
    print(f"\n===== 选股结果（前{min(top_n, len(disp))}名） =====")
    print(disp.head(top_n).to_string(index=False))

    # # 保存 CSV
    # csv_file = "selected_stocks_trend_pullback_v2.csv"
    # disp.to_csv(csv_file, index=False, encoding="utf-8-sig")
    # print(f"\n结果已保存到文件：{csv_file}")


# ============================================================
# 策略类
# ============================================================

class TrendPullbackV2Strategy(BaseStrategy):
    """趋势回踩 + 行业主线 策略（第二轮优化版）。"""

    strategy_code = "TREND_PULLBACK_V2"
    strategy_name = "趋势回踩 + 行业主线"

    def __init__(self, engine, strategy_config, trade_date: str, batch_no: str) -> None:
        super().__init__(engine, strategy_config, trade_date, batch_no)
        # 使用自包含的策略参数，可从 strategy_config 中按名字覆盖
        self.cfg = TrendPullbackConfig()
        self._apply_strategy_config_overrides()

    def _apply_strategy_config_overrides(self) -> None:
        """如果 strategy_config 中有同名属性，则覆盖默认值。"""
        sc = self.strategy_config
        for field_name in self.cfg.__dataclass_fields__:
            if hasattr(sc, field_name):
                setattr(self.cfg, field_name, getattr(sc, field_name))

    # ---- run -------------------------------------------------
    def run(self) -> list[RecommendResult]:
        cfg = self.cfg
        engine = self.engine

        # 1. 获取最近 60 个交易日
        recent_dates = self._query_recent_trade_dates(60)
        if len(recent_dates) < 20:
            print("最近交易日不足 20 天，无法计算。")
            return []

        latest_date = recent_dates[0]
        d5 = recent_dates[4]
        d10 = recent_dates[9]
        d20 = recent_dates[19]
        print("最新交易日：", latest_date)

        # 2. 加载数据
        daily_df = self._load_daily_data(recent_dates)
        full_df = self._load_full_info()
        if daily_df.empty or full_df.empty:
            print("数据为空，退出。")
            return []

        print(f"日线数据：{len(daily_df)} 行，综合信息：{len(full_df)} 行")

        # 3. 类型转换
        daily_df = self._cast_daily_types(daily_df)
        full_df = self._cast_full_info_types(full_df)
        daily_df = _fill_ma_if_missing(daily_df)

        # 4. 合并 & 过滤次新
        df = daily_df.merge(full_df, on="stock_code", how="inner")
        print("合并后行数：", len(df))
        latest_date_ts = pd.to_datetime(latest_date)
        df = df[df["listing_date"].notna()]
        df = df[(latest_date_ts - df["listing_date"]).dt.days >= cfg.min_listing_days]
        print("过滤次新股后行数：", len(df))

        # 5. 取关键日期数据
        latest_df = df[df["trade_date"] == pd.to_datetime(latest_date)].copy()
        latest_df = self._merge_date_snapshots(latest_df, df, latest_date, d5, d10, d20, recent_dates, cfg)
        print("最新日股票数：", len(latest_df))

        # 6. 计算指标
        latest_df = self._calc_indicators(latest_df, cfg)
        print("计算指标完成")

        # 7. 行业评分
        industry_perf = self._score_industries(latest_df, cfg)
        top_industry = industry_perf.head(cfg.top_industry_limit)[["sub_industry", "industry_score"]]
        _print_industry_result(industry_perf, cfg.top_industry_limit)
        latest_df = latest_df.merge(top_industry, on="sub_industry", how="inner")
        print("强行业内股票数：", len(latest_df))

        # 8. 个股过滤
        result = self._filter_stocks(latest_df, cfg)
        print("条件过滤后股票数：", len(result))

        if result.empty:
            print("未选出符合条件的股票。")
            return []

        # 9. 评分 & 排序
        result = self._score_stocks(result)

        # 10. 构建结果
        top_n = cfg.top_result_limit
        selected = result.head(top_n)

        results: list[RecommendResult] = []
        for _, row in selected.iterrows():
            stock_code = str(row["stock_code"]).zfill(6)
            reason = _build_reason(row)
            score = float(row["total_score"]) if pd.notna(row["total_score"]) else 80.0
            results.append(self.build_result(stock_code, reason, score))

        print(f"\n[INFO] {self.strategy_name} 选出 {len(results)} 只股票")

        # 11. 打印 & 保存
        display_cols = [
            "trade_date", "stock_code", "stock_name", "sub_industry",
            "close_price", "ma5", "ma10", "ma20",
            "change_percent", "turnover_rate_pct", "float_market_cap",
            "pct_5d", "pct_10d", "pct_20d", "bias_ma10",
            "vol_ratio_5d", "touch_vol_ratio", "strength_pct", "activity",
            "industry_score", "trend_score", "pullback_score",
            "quality_score", "pattern_bonus", "total_score",
            "short_term_pattern", "recent_indicator_tip",
        ]
        _print_stock_result(selected[display_cols].copy(), top_n)
        return results

    # ---- 数据库查询 -------------------------------------------

    def _query_recent_trade_dates(self, limit_days: int) -> list:
        sql = f"""
            SELECT trade_date FROM stock_daily
            GROUP BY trade_date ORDER BY trade_date DESC LIMIT {int(limit_days)}
        """
        df = self.engine.read_sql(sql)
        return [str(d)[:10] for d in df["trade_date"].tolist()] if not df.empty else []

    def _load_daily_data(self, recent_dates: list) -> pd.DataFrame:
        if not recent_dates:
            return pd.DataFrame()
        date_str = ",".join([f"'{d}'" for d in recent_dates])
        sql = f"""
            SELECT stock_code, trade_date, open_price, high_price, low_price,
                   close_price, volume, turnover, change_percent,
                   ma5, ma10, ma20, ma60
            FROM stock_daily WHERE trade_date IN ({date_str})
        """
        return self.engine.read_sql(sql)

    def _load_full_info(self) -> pd.DataFrame:
        sql = """
            SELECT stock_code, stock_name, sub_industry, listing_date,
                   turnover_rate_pct, float_market_cap, strength_pct, activity,
                   profit_yoy_pct, revenue_yoy_pct, roe_pct, pe_ttm, pb_ratio,
                   recent_indicator_tip, short_term_pattern, mid_term_pattern,
                   long_term_pattern, distance_ma5_pct
            FROM stock_full_info
            WHERE stock_name IS NOT NULL AND stock_name <> ''
              AND sub_industry IS NOT NULL AND sub_industry <> ''
              AND stock_name NOT LIKE '%%ST%%' AND stock_name NOT LIKE '%%*ST%%'
        """
        return self.engine.read_sql(sql)

    # ---- 类型转换 ---------------------------------------------

    @staticmethod
    def _cast_daily_types(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        for col in ["open_price", "high_price", "low_price", "close_price",
                     "volume", "turnover", "change_percent",
                     "ma5", "ma10", "ma20", "ma60"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    @staticmethod
    def _cast_full_info_types(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["listing_date"] = pd.to_datetime(df["listing_date"], errors="coerce")
        for col in ["turnover_rate_pct", "float_market_cap", "strength_pct",
                     "activity", "profit_yoy_pct", "revenue_yoy_pct",
                     "roe_pct", "pe_ttm", "pb_ratio", "distance_ma5_pct"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    # ---- 日期快照合并 -----------------------------------------

    @staticmethod
    def _merge_date_snapshots(latest_df, df, latest_date, d5, d10, d20, recent_dates, cfg):
        d5_df = df[df["trade_date"] == pd.to_datetime(d5)][["stock_code", "close_price"]].rename(
            columns={"close_price": "close_5d_ago"})
        d10_df = df[df["trade_date"] == pd.to_datetime(d10)][["stock_code", "close_price"]].rename(
            columns={"close_price": "close_10d_ago"})
        d20_df = df[df["trade_date"] == pd.to_datetime(d20)][["stock_code", "close_price"]].rename(
            columns={"close_price": "close_20d_ago"})

        recent3 = list(pd.to_datetime(recent_dates[:cfg.touch_window_days]))
        recent5 = list(pd.to_datetime(recent_dates[:5]))

        low_3d = (df[df["trade_date"].isin(recent3)].groupby("stock_code", as_index=False)["low_price"]
                  .min().rename(columns={"low_price": "low_3d_min"}))
        avg_vol_5d = (df[df["trade_date"].isin(recent5)].groupby("stock_code", as_index=False)["volume"]
                      .mean().rename(columns={"volume": "avg_vol_5d"}))
        touch_vol = (df[df["trade_date"].isin(recent3)].groupby("stock_code", as_index=False)["volume"]
                     .min().rename(columns={"volume": "touch_day_volume"}))

        latest_df = latest_df.merge(d5_df, on="stock_code", how="left")
        latest_df = latest_df.merge(d10_df, on="stock_code", how="left")
        latest_df = latest_df.merge(d20_df, on="stock_code", how="left")
        latest_df = latest_df.merge(low_3d, on="stock_code", how="left")
        latest_df = latest_df.merge(avg_vol_5d, on="stock_code", how="left")
        latest_df = latest_df.merge(touch_vol, on="stock_code", how="left")
        return latest_df

    # ---- 指标计算 ---------------------------------------------

    @staticmethod
    def _calc_indicators(df: pd.DataFrame, cfg: TrendPullbackConfig) -> pd.DataFrame:
        df = df.copy()
        df["pct_5d"] = (df["close_price"] - df["close_5d_ago"]) / df["close_5d_ago"] * 100
        df["pct_10d"] = (df["close_price"] - df["close_10d_ago"]) / df["close_10d_ago"] * 100
        df["pct_20d"] = (df["close_price"] - df["close_20d_ago"]) / df["close_20d_ago"] * 100
        df["bias_ma10"] = (df["close_price"] - df["ma10"]) / df["ma10"] * 100
        df["vol_ratio_5d"] = df["volume"] / df["avg_vol_5d"]
        df["touch_vol_ratio"] = df["touch_day_volume"] / df["avg_vol_5d"]
        df["above_ma20_flag"] = (df["close_price"] > df["ma20"]).astype(int)
        df["strong_stock_flag"] = (df["pct_20d"] >= cfg.min_pct_20d).astype(int)
        df["touch_ma10_flag"] = (
            df["low_3d_min"].notna() & df["ma10"].notna() &
            (df["low_3d_min"] <= df["ma10"] * cfg.ma10_touch_ratio)
        ).astype(int)
        df["shrink_touch_flag"] = (
            df["touch_vol_ratio"].notna() &
            (df["touch_vol_ratio"] <= cfg.touch_vol_ratio_threshold)
        ).astype(int)
        df["cap_bucket"] = df["float_market_cap"].apply(lambda x: _classify_cap_bucket(x, cfg))
        return df

    # ---- 行业评分 ---------------------------------------------

    @staticmethod
    def _score_industries(df: pd.DataFrame, cfg: TrendPullbackConfig) -> pd.DataFrame:
        perf = (
            df.groupby("sub_industry", as_index=False)
            .agg(
                stock_count=("stock_code", "count"),
                avg_pct_5d=("pct_5d", "mean"),
                avg_pct_10d=("pct_10d", "mean"),
                avg_pct_20d=("pct_20d", "mean"),
                above_ma20_ratio=("above_ma20_flag", "mean"),
                strong_stock_ratio=("strong_stock_flag", "mean"),
                avg_strength=("strength_pct", "mean"),
                avg_activity=("activity", "mean"),
            )
        )
        perf = perf[perf["stock_count"] >= cfg.min_industry_stock_count].copy()
        perf["industry_score"] = (
            perf["avg_pct_5d"].fillna(0) * 0.30 +
            perf["avg_pct_10d"].fillna(0) * 0.25 +
            perf["avg_pct_20d"].fillna(0) * 0.15 +
            perf["above_ma20_ratio"].fillna(0) * 100 * 0.15 +
            perf["strong_stock_ratio"].fillna(0) * 100 * 0.10 +
            perf["avg_strength"].fillna(0) * 0.04 +
            perf["avg_activity"].fillna(0) * 0.001
        )
        return perf.sort_values(["industry_score", "stock_count", "avg_pct_5d"],
                                ascending=[False, False, False])

    # ---- 个股过滤 ---------------------------------------------

    @staticmethod
    def _filter_stocks(df: pd.DataFrame, cfg: TrendPullbackConfig) -> pd.DataFrame:
        r = df.copy()
        print("\n开始个股过滤，初始股票数：", len(r))

        # 关键空值
        r = r[r["close_price"].notna() & r["ma5"].notna() & r["ma10"].notna() &
              r["ma20"].notna() & r["ma60"].notna() & r["turnover"].notna() &
              r["turnover_rate_pct"].notna() & r["float_market_cap"].notna()]
        print("过滤关键空值后：", len(r))

        # 市值区间
        r = r[r["cap_bucket"] != "OTHER"]
        print("市值区间过滤后：", len(r))

        # 均线多头排列
        r = r[r["close_price"] > r["ma20"]]
        print("close > ma20 后：", len(r))
        r = r[r["ma5"] > r["ma10"]]
        print("ma5 > ma10 后：", len(r))
        r = r[r["ma10"] > r["ma20"]]
        print("ma10 > ma20 后：", len(r))
        r = r[r["ma20"] > r["ma60"]]
        print("ma20 > ma60 后：", len(r))

        # 20日涨幅
        r = r[r["close_20d_ago"].notna()]
        r = r[r["pct_20d"] >= cfg.min_pct_20d]
        print("20日涨幅 >= 阈值 后：", len(r))

        # 距10日线偏离
        r = r[r["ma10"].notna() & (r["ma10"] > 0)]
        r = r[r["bias_ma10"].abs() <= cfg.max_bias_ma10]
        print("bias_ma10 过滤后：", len(r))

        # 回踩 + 缩量
        r = r[r["touch_ma10_flag"] == 1]
        print("回踩10日线后：", len(r))
        r = r[r["shrink_touch_flag"] == 1]
        print("缩量回踩过滤后：", len(r))

        # 重新站上 ma10
        r = r[r["close_price"] >= r["ma10"]]
        print("站上 ma10 后：", len(r))

        # 今日跌幅
        r = r[r["change_percent"].notna()]
        r = r[r["change_percent"] > cfg.max_today_drop_pct]
        print("今日跌幅过滤后：", len(r))

        # 成交额
        r = r[r["turnover"] >= cfg.min_turnover]
        print("成交额过滤后：", len(r))

        # 分层换手率
        sm = r["cap_bucket"] == "SMALL_MID"
        lg = r["cap_bucket"] == "LARGE"
        r = r[(sm & (r["turnover_rate_pct"] >= cfg.small_mid_min_turnover_rate) &
                  (r["turnover_rate_pct"] <= cfg.small_mid_max_turnover_rate)) |
               (lg & (r["turnover_rate_pct"] >= cfg.large_cap_min_turnover_rate) &
                  (r["turnover_rate_pct"] <= cfg.large_cap_max_turnover_rate))]
        print("分层换手率过滤后：", len(r))

        # 量比
        r = r[r["avg_vol_5d"].notna() & (r["avg_vol_5d"] > 0)]
        r = r[r["vol_ratio_5d"].notna() & (r["vol_ratio_5d"] <= cfg.max_vol_ratio_5d)]
        print("量比过滤后：", len(r))

        # 分层 PE
        sm = r["cap_bucket"] == "SMALL_MID"
        lg = r["cap_bucket"] == "LARGE"
        r = r[(sm & (r["pe_ttm"].isna() |
                      ((r["pe_ttm"] > 0) & (r["pe_ttm"] <= cfg.small_mid_max_pe_ttm)))) |
               (lg & (r["pe_ttm"].isna() |
                      ((r["pe_ttm"] > 0) & (r["pe_ttm"] <= cfg.large_cap_max_pe_ttm))))]
        print("分层 PE 过滤后：", len(r))

        # 财务底线
        r = r[r["profit_yoy_pct"].fillna(0) >= cfg.min_profit_yoy_pct]
        print("利润同比过滤后：", len(r))
        r = r[r["revenue_yoy_pct"].fillna(0) >= cfg.min_revenue_yoy_pct]
        print("收入同比过滤后：", len(r))
        r = r[r["roe_pct"].fillna(0) >= cfg.min_roe_pct]
        print("ROE 过滤后：", len(r))

        return r

    # ---- 评分 -------------------------------------------------

    @staticmethod
    def _score_stocks(df: pd.DataFrame) -> pd.DataFrame:
        r = df.copy()

        r["trend_score"] = (
            (r["close_price"] > r["ma20"]).astype(int) * 20 +
            (r["ma5"] > r["ma10"]).astype(int) * 15 +
            (r["ma10"] > r["ma20"]).astype(int) * 15 +
            r["pct_20d"].clip(upper=30).fillna(0)
        )

        r["pullback_score"] = (
            (r["touch_ma10_flag"] == 1).astype(int) * 20 +
            (r["shrink_touch_flag"] == 1).astype(int) * 20 +
            (r["close_price"] >= r["ma10"]).astype(int) * 15 +
            (r["vol_ratio_5d"] <= 1.0).astype(int) * 10 +
            ((r["vol_ratio_5d"] > 1.0) & (r["vol_ratio_5d"] <= 1.2)).astype(int) * 5 +
            (r["change_percent"] > 0).astype(int) * 10 +
            (r["change_percent"] <= 0).astype(int) * 5
        )

        r["quality_score"] = (
            r["strength_pct"].fillna(0).clip(lower=0, upper=30) * 0.40 +
            r["activity"].fillna(0).clip(lower=0, upper=5000) * 0.001 +
            r["roe_pct"].fillna(0).clip(lower=0, upper=20) * 0.30 +
            r["profit_yoy_pct"].fillna(0).clip(lower=-10, upper=50) * 0.15 +
            r["revenue_yoy_pct"].fillna(0).clip(lower=-10, upper=30) * 0.15
        )

        r["pattern_bonus"] = 0.0
        r.loc[r["short_term_pattern"].fillna("").str.contains("多头排列", na=False), "pattern_bonus"] += 5.0
        r.loc[r["recent_indicator_tip"].fillna("").str.contains("跌破BOLL下轨", na=False), "pattern_bonus"] -= 5.0

        r["total_score"] = (
            r["industry_score"].fillna(0) * 0.30 +
            r["trend_score"].fillna(0) * 0.28 +
            r["pullback_score"].fillna(0) * 0.22 +
            r["quality_score"].fillna(0) * 0.20 +
            r["pattern_bonus"].fillna(0)
        )

        return r.sort_values(["total_score", "industry_score", "pct_20d", "strength_pct"],
                             ascending=[False, False, False, False])
