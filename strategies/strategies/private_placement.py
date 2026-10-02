# -*- coding: utf-8 -*-
"""
定向增发公告策略。

说明：
    这个策略不依赖你的 stock_daily 选股，而是通过 akshare 拉取东方财富定增数据。
    如果你暂时不想联网或没有安装 akshare，可以不运行这个策略。
"""

from datetime import datetime, timedelta

import pandas as pd

from strategies.base import BaseStrategy, RecommendResult


class PrivatePlacementStrategy(BaseStrategy):
    strategy_code = "PRIVATE_PLACEMENT"
    strategy_name = "定向增发公告"

    def run(self) -> list[RecommendResult]:
        try:
            import akshare as ak
            df = ak.stock_qbzf_em()
        except Exception as exc:
            print(f"[WARN] {self.strategy_name} 获取 akshare 定增数据失败：{exc}")
            return []

        if df is None or df.empty:
            print(f"[INFO] {self.strategy_name} 无定增数据")
            return []

        if "发行方式" not in df.columns or "发行日期" not in df.columns or "股票代码" not in df.columns:
            print(f"[WARN] {self.strategy_name} akshare 返回字段不符合预期")
            return []

        df = df[df["发行方式"] == "定向增发"].copy()
        if df.empty:
            return []

        lookback_days = int(getattr(self.strategy_config, "private_placement_lookback_days", 7))
        trade_dt = pd.to_datetime(self.trade_date, errors="coerce")
        if pd.isna(trade_dt):
            trade_dt = pd.Timestamp(datetime.today().date())

        cutoff = trade_dt.date() - timedelta(days=lookback_days)

        df["发行日期"] = pd.to_datetime(df["发行日期"], errors="coerce")
        df = df.dropna(subset=["发行日期"])
        df = df[df["发行日期"].dt.date >= cutoff]
        df = df.sort_values("发行日期", ascending=False)

        symbols = df["股票代码"].astype(str).str.extract(r"(\d{6})")[0].dropna().tolist()

        seen = set()
        results: list[RecommendResult] = []
        for symbol in symbols:
            symbol = str(symbol).zfill(6)
            if symbol in seen:
                continue
            seen.add(symbol)
            reason = f"最近{lookback_days}天内出现定向增发公告，属于事件驱动观察标的。"
            results.append(self.build_result(symbol, reason, 75.0))

        print(f"[INFO] {self.strategy_name} 选出 {len(results)} 只股票")
        return results
