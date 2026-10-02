# -*- coding: utf-8 -*-
"""
RPS 极强动量突破策略。
逻辑：
    1. 计算每只股票过去 N 日涨幅。
    2. 对全市场做横向百分位排名。
    3. 筛选 RPS >= 阈值的强势股。
    4. 当前收盘价接近 N 日最高价，认为处于强势突破区。
"""

from strategies.base import BaseStrategy, RecommendResult


class RpsBreakoutStrategy(BaseStrategy):
    strategy_code = "RPS_BREAKOUT"
    strategy_name = "RPS强势突破"

    def run(self) -> list[RecommendResult]:
        period = int(getattr(self.strategy_config, "rps_period", 120))
        threshold = float(getattr(self.strategy_config, "rps_threshold", 90.0))
        limit_days = max(period + 20, int(getattr(self.strategy_config, "kline_limit", 260)))

        try:
            df = self.engine.get_all_daily_for_rps(self.trade_date, limit_days)
        except Exception as exc:
            print(f"[ERROR] {self.strategy_name} 读取全市场行情失败：{exc}")
            return []

        if df.empty:
            print(f"[INFO] {self.strategy_name} 无行情数据")
            return []

        df = df.sort_values(["symbol", "date"]).copy()

        # 计算过去 period 日涨幅。
        df["close_shift"] = df.groupby("symbol")["close"].shift(period)
        df["pct_change"] = (df["close"] - df["close_shift"]) / df["close_shift"]

        latest_date = df["date"].max()
        latest_df = df[df["date"] == latest_date].copy()
        latest_df = latest_df.dropna(subset=["pct_change"])

        if latest_df.empty:
            print(f"[INFO] {self.strategy_name} 可计算RPS的数据为空")
            return []

        # RPS 横向排名。
        latest_df["rps"] = latest_df["pct_change"].rank(pct=True) * 100
        strong_df = latest_df[latest_df["rps"] >= threshold].copy()

        if strong_df.empty:
            print(f"[INFO] {self.strategy_name} 没有达到RPS阈值的股票")
            return []

        # 计算 period 日内最高价。
        # 不用 groupby().rolling()，直接用日期区间过滤 + groupby().max()，快几十倍。
        all_dates = sorted(df["date"].unique())
        cutoff_idx = max(0, len(all_dates) - period)
        cutoff_date = all_dates[cutoff_idx]

        roll_high = (
            df[df["date"] >= cutoff_date]
            .groupby("symbol")["high"]
            .max()
            .reset_index()
        )
        roll_high.columns = ["symbol", "roll_high"]

        strong_df = strong_df.merge(roll_high, on="symbol", how="left")
        strong_df = strong_df.dropna(subset=["roll_high"])

        selected = strong_df[strong_df["close"] >= strong_df["roll_high"] * 0.90].copy()

        results: list[RecommendResult] = []
        for _, row in selected.iterrows():
            symbol = str(row["symbol"]).zfill(6)
            reason = (
                f"过去{period}日涨幅 {row['pct_change'] * 100:.2f}%；"
                f"RPS {row['rps']:.2f}，达到阈值 {threshold:.2f}；"
                f"当前收盘价 {row['close']:.3f} 接近{period}日高点 {row['roll_high']:.3f}。"
            )
            results.append(self.build_result(symbol, reason, min(95.0, float(row["rps"]))))

        print(f"[INFO] {self.strategy_name} 选出 {len(results)} 只股票")
        return results
