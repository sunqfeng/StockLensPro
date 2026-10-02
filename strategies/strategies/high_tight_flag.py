# -*- coding: utf-8 -*-
"""
高旗形整理策略。
条件：
    1. 过去40天最高价 / 最低价 > 1.6，说明前期有强动量。
    2. 最近10天最高价 / 最低价 < 1.15，说明进入收敛整理。
    3. 最近10天最低价不低于40天最高价的80%，说明高位抗跌。
    4. 今日成交量小于过去20日均量的0.6倍，说明缩量。
"""

from strategies.base import BaseStrategy, RecommendResult


class HighTightFlagStrategy(BaseStrategy):
    strategy_code = "HIGH_TIGHT_FLAG"
    strategy_name = "高旗形整理"

    _MIN_BARS = 40

    def run(self) -> list[RecommendResult]:
        symbols = self.engine.get_local_symbols(self.trade_date)
        results: list[RecommendResult] = []
        limit = int(getattr(self.strategy_config, "kline_limit", 260))

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol, self.trade_date, limit)
                if len(df) < self._MIN_BARS:
                    continue

                tail40 = df.tail(40)
                tail10 = df.tail(10)

                high40 = tail40["high"].max()
                low40 = tail40["low"].min()
                high10 = tail10["high"].max()
                low10 = tail10["low"].min()

                if low40 <= 0 or low10 <= 0:
                    continue

                vol_ma20 = df["volume"].iloc[-21:-1].mean()
                today_volume = df["volume"].iloc[-1]

                momentum = high40 / low40 > 1.6
                consolidation = high10 / low10 < 1.15
                high_level = low10 >= high40 * 0.8
                shrink = today_volume < vol_ma20 * 0.6

                if momentum and consolidation and high_level and shrink:
                    reason = (
                        f"近40日高低比 {high40 / low40:.2f}，具备强动量；"
                        f"近10日高低比 {high10 / low10:.2f}，波动收敛；"
                        f"近10日低点不低于40日高点80%；"
                        f"今日成交量 {today_volume:.0f} 小于20日均量 {vol_ma20:.0f} 的0.6倍。"
                    )
                    results.append(self.build_result(symbol, reason, 83.0))
            except Exception as exc:
                print(f"[WARN] {symbol} {self.strategy_name} 计算失败：{exc}")

        print(f"[INFO] {self.strategy_name} 选出 {len(results)} 只股票")
        return results
