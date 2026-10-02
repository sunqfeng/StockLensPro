# -*- coding: utf-8 -*-
"""
均线放量策略。
条件：
    1. 5日均线上穿20日均线。
    2. 今日成交量大于20日均量的1.5倍。
"""

from strategies.base import BaseStrategy, RecommendResult


class MaVolumeStrategy(BaseStrategy):
    strategy_code = "MA_VOLUME"
    strategy_name = "均线金叉放量"

    def run(self) -> list[RecommendResult]:
        symbols = self.engine.get_local_symbols(self.trade_date)
        results: list[RecommendResult] = []
        limit = int(getattr(self.strategy_config, "kline_limit", 260))

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol, self.trade_date, limit)
                if len(df) < 21:
                    continue

                df["ma5"] = df["close"].rolling(5).mean()
                df["ma20"] = df["close"].rolling(20).mean()
                df["vol_ma20"] = df["volume"].rolling(20).mean()

                last = df.iloc[-1]
                prev = df.iloc[-2]

                golden_cross = prev["ma5"] < prev["ma20"] and last["ma5"] > last["ma20"]
                volume_surge = last["volume"] > last["vol_ma20"] * 1.5

                if golden_cross and volume_surge:
                    reason = (
                        f"5日均线 {last['ma5']:.3f} 上穿20日均线 {last['ma20']:.3f}；"
                        f"今日成交量 {last['volume']:.0f} 大于20日均量 {last['vol_ma20']:.0f} 的1.5倍。"
                    )
                    results.append(self.build_result(symbol, reason, 82.0))
            except Exception as exc:
                print(f"[WARN] {symbol} {self.strategy_name} 计算失败：{exc}")

        print(f"[INFO] {self.strategy_name} 选出 {len(results)} 只股票")
        return results
