# -*- coding: utf-8 -*-
"""
海龟20日突破策略。验收自 Sequoia-X 的 TurtleTradeStrategy。核心条件：
    1. 今日收盘价突破前 20 个交易日最高价。
    2. 今日成交额大于配置门槛，默认 1 亿。
    3. 今日为实体阳线。
    4. 今日收盘价大于昨日收盘价，避免假阳线。
"""

import pandas as pd

from strategies.base import BaseStrategy, RecommendResult


class TurtleTradeStrategy(BaseStrategy):
    strategy_code = "TURTLE_TRADE"
    strategy_name = "海龟20日突破"

    _MIN_BARS = 21

    def run(self) -> list[RecommendResult]:
        symbols = self.engine.get_local_symbols(self.trade_date)
        results: list[RecommendResult] = []
        limit = int(getattr(self.strategy_config, "kline_limit", 260))
        turnover_min = float(getattr(self.strategy_config, "turtle_turnover_min", 100_000_000))

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol, self.trade_date, limit)
                if len(df) < self._MIN_BARS:
                    continue

                df["high_20"] = df["high"].shift(1).rolling(20).max()
                last = df.iloc[-1]
                prev = df.iloc[-2]

                if pd.isna(last["high_20"]):
                    continue

                breakout = last["close"] > last["high_20"]
                liquid = last["turnover"] > turnover_min
                is_yang = last["close"] > last["open"]
                is_up = last["close"] > prev["close"]

                if breakout and liquid and is_yang and is_up:
                    reason = (
                        f"收盘价 {last['close']:.3f} 突破前20日高点 {last['high_20']:.3f}；"
                        f"成交额 {last['turnover']:.0f} 大于门槛 {turnover_min:.0f}；"
                        f"当日阳线且收盘价高于昨日收盘价。"
                    )
                    results.append(self.build_result(symbol, reason, 85.0))
            except Exception as exc:
                print(f"[WARN] {symbol} {self.strategy_name} 计算失败：{exc}")

        print(f"[INFO] {self.strategy_name} 选出 {len(results)} 只股票")
        return results
