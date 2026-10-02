# -*- coding: utf-8 -*-
"""
月线突破回踩 + 日线头肩底策略。

核心思想：
    大周期（月线）确认方向，小周期（日线）确认买点。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from strategies.base import BaseStrategy, RecommendResult


@dataclass
class MonthlyBreakoutPullbackHsConfig:
    """策略参数。"""

    # 月线突破：过去 N 个月高点作为阻力，突破月需要放量。
    resistance_months: int = 8
    breakout_volume_multiplier: float = 1.3

    # 月线回踩：突破后最多 M 个月内，缩量回踩阻力位附近。
    pullback_months: int = 3
    pullback_tolerance: float = 0.06
    pullback_upper_ratio: float = 1.02
    pullback_volume_shrink: float = 0.85

    # 日线头肩底：局部极值窗口、右肩容忍、颈线突破缓冲。
    extrema_order: int = 3
    shoulder_tolerance: float = 0.05
    neckline_break_buffer: float = 0.005
    neckline_breakout_max_bars_after_right: int = 20
    signal_recent_bars: int = 5

    # 读取日 K 数量。8个月阻力 + 3个月回踩 + 日线形态，默认多给一些余量。
    daily_kline_limit: int = 520
    recommend_score: float = 88.0


class MonthlyBreakoutPullbackHsStrategy(BaseStrategy):
    """月线突破回踩 + 日线头肩底策略。"""

    strategy_code = "MONTHLY_BREAKOUT_PULLBACK_HS"
    strategy_name = "月线突破回踩 + 日线头肩底"

    def __init__(self, engine, strategy_config, trade_date: str, batch_no: str) -> None:
        super().__init__(engine, strategy_config, trade_date, batch_no)
        self.cfg = MonthlyBreakoutPullbackHsConfig()
        self._apply_strategy_config_overrides()

    def _apply_strategy_config_overrides(self) -> None:
        """允许 STRATEGY_CONFIG 用同名字段覆盖本策略默认参数。"""

        for field_name in self.cfg.__dataclass_fields__:
            if hasattr(self.strategy_config, field_name):
                setattr(self.cfg, field_name, getattr(self.strategy_config, field_name))

    def run(self) -> list[RecommendResult]:
        symbols = self.engine.get_local_symbols(self.trade_date)
        results: list[RecommendResult] = []
        base_limit = int(getattr(self.strategy_config, "kline_limit", 260))
        limit = max(base_limit, int(self.cfg.daily_kline_limit))

        for symbol in symbols:
            try:
                df = self.engine.get_ohlcv(symbol, self.trade_date, limit)
                setup = self._find_setup(df)
                if not setup:
                    continue

                reason = self._build_reason(setup)
                results.append(self.build_result(symbol, reason, self.cfg.recommend_score))
            except Exception as exc:
                print(f"[WARN] {symbol} {self.strategy_name} 计算失败：{exc}")

        print(f"[INFO] {self.strategy_name} 选出 {len(results)} 只股票")
        return results

    def _find_setup(self, daily_df: pd.DataFrame) -> Optional[dict]:
        if daily_df is None or daily_df.empty:
            return None

        daily_df = self._prepare_daily_df(daily_df)
        if daily_df.empty:
            return None

        monthly_df = self._build_monthly_df(daily_df)
        min_months = self.cfg.resistance_months + 2
        if len(monthly_df) < min_months:
            return None

        monthly_df = self._add_breakout_columns(monthly_df)
        breakout_df = monthly_df[monthly_df["is_breakout"]].copy()
        if breakout_df.empty:
            return None

        for breakout_pos in reversed([monthly_df.index.get_loc(idx) for idx in breakout_df.index]):
            for pullback in self._iter_pullbacks(monthly_df, breakout_pos):
                pattern = self._find_head_shoulders_breakout(daily_df, pullback)
                if pattern:
                    setup = {}
                    setup.update(pullback)
                    setup.update(pattern)
                    return setup

        return None

    def _prepare_daily_df(self, df: pd.DataFrame) -> pd.DataFrame:
        daily_df = df.copy()
        daily_df["date"] = pd.to_datetime(daily_df["date"], errors="coerce")
        daily_df = daily_df.dropna(subset=["date"])
        trade_dt = pd.to_datetime(self.trade_date, errors="coerce")
        if pd.notna(trade_dt):
            daily_df = daily_df[daily_df["date"] <= trade_dt]

        for col in ["open", "high", "low", "close", "volume"]:
            daily_df[col] = pd.to_numeric(daily_df[col], errors="coerce")
        daily_df = daily_df.dropna(subset=["open", "high", "low", "close", "volume"])
        return daily_df.sort_values("date").reset_index(drop=True)

    @staticmethod
    def _build_monthly_df(daily_df: pd.DataFrame) -> pd.DataFrame:
        df = daily_df.set_index("date")
        monthly = (
            df.resample("ME")
            .agg(
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
                volume=("volume", "sum"),
            )
            .dropna(subset=["open", "high", "low", "close", "volume"])
        )
        monthly["month"] = monthly.index.to_period("M").astype(str)
        monthly["month_start"] = monthly.index.to_period("M").to_timestamp()
        monthly["month_end"] = monthly.index
        return monthly.reset_index(drop=True)

    def _add_breakout_columns(self, monthly_df: pd.DataFrame) -> pd.DataFrame:
        monthly_df = monthly_df.copy()
        window = int(self.cfg.resistance_months)
        monthly_df["resistance"] = monthly_df["high"].shift(1).rolling(window).max()
        monthly_df["avg_volume_n"] = monthly_df["volume"].shift(1).rolling(window).mean()
        monthly_df["is_breakout"] = (
            monthly_df["resistance"].notna()
            & monthly_df["avg_volume_n"].notna()
            & (monthly_df["close"] > monthly_df["resistance"])
            & (monthly_df["volume"] >= monthly_df["avg_volume_n"] * self.cfg.breakout_volume_multiplier)
        )
        return monthly_df

    def _iter_pullbacks(self, monthly_df: pd.DataFrame, breakout_pos: int):
        cfg = self.cfg
        breakout = monthly_df.iloc[breakout_pos]
        resistance = float(breakout["resistance"])
        lower = resistance * (1 - cfg.pullback_tolerance)
        upper = resistance * cfg.pullback_upper_ratio

        start_pos = breakout_pos + 1
        stop_pos = min(len(monthly_df), start_pos + int(cfg.pullback_months))
        if start_pos >= stop_pos:
            return

        for low_pos in range(start_pos, stop_pos):
            window = monthly_df.iloc[start_pos : low_pos + 1]
            low_row = window.loc[window["low"].idxmin()]
            pullback_low = float(low_row["low"])
            avg_volume = float(window["volume"].mean())

            price_ok = lower <= pullback_low <= upper
            volume_ok = avg_volume <= float(breakout["volume"]) * cfg.pullback_volume_shrink
            if not (price_ok and volume_ok):
                continue

            window_start = monthly_df.iloc[start_pos]["month_start"]
            window_end = low_row["month_end"]
            trade_dt = pd.to_datetime(self.trade_date, errors="coerce")
            if pd.notna(trade_dt):
                window_end = min(window_end, trade_dt)

            yield {
                "breakout_month": breakout["month"],
                "breakout_close": float(breakout["close"]),
                "breakout_volume": float(breakout["volume"]),
                "resistance": resistance,
                "pullback_start_month": monthly_df.iloc[start_pos]["month"],
                "pullback_low_month": low_row["month"],
                "pullback_low": pullback_low,
                "pullback_avg_volume": avg_volume,
                "pullback_window_start": window_start,
                "pullback_window_end": window_end,
            }

    def _find_head_shoulders_breakout(
        self,
        daily_df: pd.DataFrame,
        pullback: dict,
    ) -> Optional[dict]:
        start = pullback["pullback_window_start"]
        end = pullback["pullback_window_end"]
        window_df = daily_df[(daily_df["date"] >= start) & (daily_df["date"] <= end)].copy()
        window_df = window_df.reset_index(drop=True)

        order = int(self.cfg.extrema_order)
        if len(window_df) < order * 2 + 8:
            return None

        lows = self._find_local_extrema(window_df, "low", order, find_low=True)
        highs = self._find_local_extrema(window_df, "high", order, find_low=False)
        if len(lows) < 3:
            return None

        for pos in range(len(lows) - 2):
            left = lows[pos]
            head = lows[pos + 1]
            right = lows[pos + 2]
            if not self._is_valid_head_shoulders(left, head, right):
                continue

            neckline = self._find_neckline(window_df, highs, left["idx"], right["idx"])
            if not neckline:
                continue

            threshold = neckline["value"] * (1 + self.cfg.neckline_break_buffer)
            # 三个低点必须形成于回踩窗口内；突破确认可以发生在窗口结束后。
            after_right = daily_df[daily_df["date"] > right["date"]]
            after_right = after_right.head(int(self.cfg.neckline_breakout_max_bars_after_right))
            confirmed = after_right[after_right["close"] > threshold]
            if confirmed.empty:
                continue

            signal = confirmed.iloc[0]
            signal_date = str(signal["date"].date())
            bars_since_signal = self._bars_since_signal(daily_df, signal["date"])
            if bars_since_signal is None or bars_since_signal > int(self.cfg.signal_recent_bars):
                continue

            return {
                "left_shoulder_date": str(left["date"].date()),
                "left_shoulder_low": float(left["value"]),
                "head_date": str(head["date"].date()),
                "head_low": float(head["value"]),
                "right_shoulder_date": str(right["date"].date()),
                "right_shoulder_low": float(right["value"]),
                "neckline_date": str(neckline["date"].date()),
                "neckline": float(neckline["value"]),
                "signal_date": signal_date,
                "signal_close": float(signal["close"]),
                "bars_since_signal": int(bars_since_signal),
            }

        return None

    @staticmethod
    def _bars_since_signal(daily_df: pd.DataFrame, signal_date) -> Optional[int]:
        dates = daily_df["date"].reset_index(drop=True)
        matched = dates[dates == signal_date]
        if matched.empty:
            return None
        return int(len(dates) - 1 - matched.index[-1])

    @staticmethod
    def _find_local_extrema(df: pd.DataFrame, col: str, order: int, find_low: bool) -> list[dict]:
        extrema: list[dict] = []
        values = df[col].tolist()
        for idx in range(order, len(df) - order):
            center = values[idx]
            left = values[idx - order : idx]
            right = values[idx + 1 : idx + order + 1]
            if find_low:
                ok = all(center < value for value in left + right)
            else:
                ok = all(center > value for value in left + right)
            if ok:
                extrema.append({
                    "idx": idx,
                    "date": df.loc[idx, "date"],
                    "value": float(center),
                })
        return extrema

    def _is_valid_head_shoulders(self, left: dict, head: dict, right: dict) -> bool:
        head_is_lowest = head["value"] < left["value"] and head["value"] < right["value"]
        right_not_too_low = right["value"] >= left["value"] * (1 - self.cfg.shoulder_tolerance)
        return head_is_lowest and right_not_too_low

    @staticmethod
    def _find_neckline(
        window_df: pd.DataFrame,
        highs: list[dict],
        left_idx: int,
        right_idx: int,
    ) -> Optional[dict]:
        between_highs = [
            item for item in highs
            if left_idx < item["idx"] < right_idx
        ]
        if between_highs:
            return max(between_highs, key=lambda item: item["value"])

        between = window_df[(window_df.index > left_idx) & (window_df.index < right_idx)]
        if between.empty:
            return None
        max_idx = between["high"].idxmax()
        return {
            "idx": int(max_idx),
            "date": window_df.loc[max_idx, "date"],
            "value": float(window_df.loc[max_idx, "high"]),
        }

    @staticmethod
    def _build_reason(setup: dict) -> str:
        volume_ratio = setup["pullback_avg_volume"] / setup["breakout_volume"]
        neckline_ratio = (setup["signal_close"] - setup["neckline"]) / setup["neckline"] * 100
        return (
            "多周期共振：月线突破阻力后缩量回踩，日线完成头肩底并突破颈线；"
            f"突破月：{setup['breakout_month']}，收盘价 {setup['breakout_close']:.3f} "
            f"突破阻力位 {setup['resistance']:.3f}；"
            f"回踩窗口：{setup['pullback_start_month']} 至 {setup['pullback_low_month']}，"
            f"最低价 {setup['pullback_low']:.3f}，回踩均量/突破月量 {volume_ratio:.2f}；"
            f"头肩底：左肩 {setup['left_shoulder_date']}({setup['left_shoulder_low']:.3f})，"
            f"头部 {setup['head_date']}({setup['head_low']:.3f})，"
            f"右肩 {setup['right_shoulder_date']}({setup['right_shoulder_low']:.3f})；"
            f"颈线 {setup['neckline']:.3f}，{setup['signal_date']} 收盘价 "
            f"{setup['signal_close']:.3f} 向上突破颈线 {neckline_ratio:.2f}%，"
            f"距本次交易日 {setup['bars_since_signal']} 根日K。"
        )
