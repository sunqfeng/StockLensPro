# -*- coding: utf-8 -*-
"""
涨停洗盘策略。
条件：
    1. 昨日涨停。
    2. 今日收阴。
    3. 今日成交量大于昨日2倍。
    4. 今日最低价不破昨日收盘价。
"""

from strategies.base import BaseStrategy, RecommendResult


class LimitUpShakeoutStrategy(BaseStrategy):
    strategy_code = "LIMIT_UP_SHAKEOUT"
    strategy_name = "涨停洗盘"

    _MIN_BARS = 3

    def run(self) -> list[RecommendResult]:
        symbols = self.engine.get_local_symbols(self.trade_date)
        results: list[RecommendResult] = []
        limit = int(getattr(self.strategy_config, "kline_limit", 260))

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol, self.trade_date, limit)
                if len(df) < self._MIN_BARS:
                    continue

                prev2 = df.iloc[-3]
                prev1 = df.iloc[-2]
                today = df.iloc[-1]

                limit_up_yesterday = prev1["close"] >= prev2["close"] * 1.095
                bearish_today = today["close"] < today["open"]
                volume_surge = today["volume"] > prev1["volume"] * 2.0
                support_hold = today["low"] >= prev1["close"]

                if limit_up_yesterday and bearish_today and volume_surge and support_hold:
                    reason = (
                        f"昨日收盘价 {prev1['close']:.3f} 较前日 {prev2['close']:.3f} 接近涨停；"
                        f"今日收阴且成交量 {today['volume']:.0f} 超昨日 {prev1['volume']:.0f} 的2倍；"
                        f"今日最低价 {today['low']:.3f} 未跌破昨日收盘价 {prev1['close']:.3f}。"
                    )
                    results.append(self.build_result(symbol, reason, 81.0))
            except Exception as exc:
                print(f"[WARN] {symbol} {self.strategy_name} 计算失败：{exc}")

        print(f"[INFO] {self.strategy_name} 选出 {len(results)} 只股票")
        return results
