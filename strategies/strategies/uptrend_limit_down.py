# -*- coding: utf-8 -*-
"""
上升趋势跌停策略。
条件：
    1. 昨日20日均线大于昨日60日均线，说明仍处于上升趋势。
    2. 今日接近跌停。
    3. 今日成交量大于20日均量的2倍。
"""

import pandas as pd

from strategies.base import BaseStrategy, RecommendResult


class UptrendLimitDownStrategy(BaseStrategy):
    strategy_code = "UPTREND_LIMIT_DOWN"
    strategy_name = "上升趋势放量跌停"

    _MIN_BARS = 60

    def run(self) -> list[RecommendResult]:
        symbols = self.engine.get_local_symbols(self.trade_date)
        results: list[RecommendResult] = []
        limit = int(getattr(self.strategy_config, "kline_limit", 260))

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol, self.trade_date, limit)
                if len(df) < self._MIN_BARS:
                    continue

                df["ma20"] = df["close"].rolling(20).mean()
                df["ma60"] = df["close"].rolling(60).mean()
                df["vol_ma20"] = df["volume"].rolling(20).mean()

                prev = df.iloc[-2]
                today = df.iloc[-1]

                if pd.isna(prev["ma20"]) or pd.isna(prev["ma60"]) or pd.isna(today["vol_ma20"]):
                    continue

                uptrend = prev["ma20"] > prev["ma60"]
                limit_down = today["close"] <= prev["close"] * 0.905
                volume_surge = today["volume"] > today["vol_ma20"] * 2.0

                if uptrend and limit_down and volume_surge:
                    reason = (
                        f"昨日MA20 {prev['ma20']:.3f} 大于MA60 {prev['ma60']:.3f}，仍处于上升趋势；"
                        f"今日收盘价 {today['close']:.3f} 接近跌停；"
                        f"今日成交量 {today['volume']:.0f} 大于20日均量 {today['vol_ma20']:.0f} 的2倍。"
                    )
                    results.append(self.build_result(symbol, reason, 78.0))
            except Exception as exc:
                print(f"[WARN] {symbol} {self.strategy_name} 计算失败：{exc}")

        print(f"[INFO] {self.strategy_name} 选出 {len(results)} 只股票")
        return results
