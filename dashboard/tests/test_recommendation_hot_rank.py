import unittest
from datetime import datetime

import pandas as pd

from stocklens.data.hot_stock_loaders import attach_latest_hot_rank


class RecommendationHotRankTests(unittest.TestCase):
    def test_attaches_rank_without_changing_scores_or_row_order(self):
        recommendations = pd.DataFrame(
            [
                {"股票代码": "000001", "股票名称": "平安银行", "推荐分数": 85},
                {"股票代码": "600519", "股票名称": "贵州茅台", "推荐分数": 92},
            ]
        )
        hot_ranks = pd.DataFrame(
            [
                {"normalized_code": "SZ000001", "rank_no": 12},
            ]
        )
        captured_at = datetime(2026, 8, 14, 20, 0)

        result = attach_latest_hot_rank(
            recommendations,
            hot_ranks,
            captured_at=captured_at,
            observation_cutoff=100,
        )

        self.assertEqual(result["股票代码"].tolist(), ["000001", "600519"])
        self.assertEqual(result["推荐分数"].tolist(), [85, 92])
        self.assertEqual(
            result["雪球讨论热度排名"].tolist(),
            ["第12名", "100名外"],
        )
        self.assertEqual(
            result["雪球热度采集时间"].tolist(),
            [captured_at, captured_at],
        )

    def test_reports_unavailable_when_no_successful_snapshot_exists(self):
        recommendations = pd.DataFrame(
            [{"股票代码": "300750", "股票名称": "宁德时代", "推荐分数": 88}]
        )

        result = attach_latest_hot_rank(
            recommendations,
            pd.DataFrame(),
            captured_at=None,
            observation_cutoff=100,
        )

        self.assertEqual(result.loc[0, "雪球讨论热度排名"], "暂无数据")
        self.assertTrue(pd.isna(result.loc[0, "雪球热度采集时间"]))
        self.assertEqual(result.loc[0, "推荐分数"], 88)


if __name__ == "__main__":
    unittest.main()
