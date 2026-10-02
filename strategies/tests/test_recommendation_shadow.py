import math
import unittest

from recommendation_shadow import evaluate_candidate


class CandidateTests(unittest.TestCase):
    def row(self, strategy="海龟20日突破", **changes):
        row = dict(strategy_name=strategy, recommend_date="2026-09-30",
                   daily_date="2026-09-30", recommend_price=10, close_price=10,
                   ma20=9.5, technical_score=90, tech_date="2026-09-30",
                   score_model="TURTLE_20_BREAKOUT_V1", data_quality="HIGH",
                   high120=10.1, high120_count=120,adjustment_kinds=1,technical_version="v1.0")
        row.update(changes)
        return row

    def decision(self, row, breadth=50, coverage=1):
        return evaluate_candidate(row, breadth, coverage)[0]

    def test_turtle_quality_and_overheat(self):
        self.assertEqual(self.decision(self.row()), "候选保留")
        self.assertEqual(self.decision(self.row(ma20=8)), "规则过滤")
        self.assertEqual(self.decision(self.row(technical_score=84)), "规则过滤")

    def test_ma_requires_market_breadth_not_technical_score(self):
        row=self.row("均线金叉放量", technical_score=None)
        self.assertEqual(self.decision(row,40), "规则过滤")
        self.assertEqual(self.decision(row,40.1), "候选保留")

    def test_rps_near_high_and_risk(self):
        row=self.row("RPS强势突破",score_model="RPS_STRONG_BREAKOUT_V1")
        self.assertEqual(self.decision(row), "候选保留")
        self.assertEqual(self.decision(dict(row,high120=11)), "规则过滤")
        self.assertEqual(self.decision(dict(row,technical_score=74)), "规则过滤")
        self.assertEqual(self.decision(dict(row,high120_count=119)), "数据待核查")
        self.assertEqual(self.decision(dict(row,adjustment_kinds=2)), "数据待核查")

    def test_missing_stale_or_nonfinite_inputs_never_pass(self):
        for changes in [dict(close_price=None),dict(ma20=0),dict(ma20=math.nan),
                        dict(technical_score=math.inf),dict(tech_date="2026-10-01"),
                        dict(daily_date="2026-09-29"),dict(score_model="GENERAL_STRONG_V1"),
                        dict(data_quality="LOW")]:
            with self.subTest(changes=changes):
                self.assertEqual(self.decision(self.row(**changes)), "数据待核查")
        self.assertEqual(self.decision(self.row("均线金叉放量"),None), "数据待核查")
        self.assertEqual(self.decision(self.row("均线金叉放量"),50,.79), "数据待核查")

    def test_price_revision_does_not_replace_original_baseline(self):
        row=self.row(close_price=10.2)
        original=dict(row)
        self.assertEqual(self.decision(row), "数据待核查")
        self.assertEqual(row,original)

    def test_other_strategies_are_explicitly_not_optimized(self):
        self.assertEqual(self.decision(self.row("高旗形整理")), "未纳入优化")


if __name__ == "__main__":
    unittest.main()
