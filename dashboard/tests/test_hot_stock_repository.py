import json
import unittest
from datetime import datetime
from decimal import Decimal

from stocklens.hot_stocks.collector import HotStockRecord
from stocklens.hot_stocks.repository import (
    build_snapshot_rows,
    normalize_capture_slot,
    snapshot_content_hash,
    validate_record_count,
)


def sample_record(rank_no=1, symbol="SH603259", heat="2915"):
    return HotStockRecord(
        rank_no=rank_no,
        external_symbol=symbol,
        normalized_code="603259",
        stock_name="药明康德",
        market="CN_SH",
        heat_score=Decimal(heat),
        quote_change_pct=Decimal("8.49"),
        topic="#创新药持续活跃#",
        raw_payload={"symbol": symbol, "name": "药明康德", "value": int(heat)},
    )


class RepositoryHelperTests(unittest.TestCase):
    def test_capture_slot_is_normalized_to_minute(self):
        moment = datetime(2026, 8, 10, 10, 30, 42, 123456)

        self.assertEqual(
            normalize_capture_slot(moment),
            datetime(2026, 8, 10, 10, 30),
        )

    def test_snapshot_rows_are_json_serializable_and_keep_decimal_values(self):
        rows = build_snapshot_rows(77, [sample_record()])

        self.assertEqual(rows[0]["batch_id"], 77)
        self.assertEqual(rows[0]["heat_score"], Decimal("2915"))
        self.assertEqual(rows[0]["quote_change_pct"], Decimal("8.49"))
        self.assertEqual(
            json.loads(rows[0]["raw_payload"])["symbol"],
            "SH603259",
        )

    def test_content_hash_is_stable_for_same_records(self):
        records = [sample_record(), sample_record(2, "SZ301308", "2551")]

        self.assertEqual(
            snapshot_content_hash(records),
            snapshot_content_hash(list(records)),
        )

    def test_incomplete_response_is_rejected_before_database_write(self):
        with self.assertRaisesRegex(ValueError, "数量不足"):
            validate_record_count([sample_record()], requested_limit=100)

    def test_nearly_complete_response_is_rejected_before_database_write(self):
        records = [
            sample_record(
                rank_no=index + 1,
                symbol=f"SH{600000 + index:06d}",
                heat=str(1000 - index),
            )
            for index in range(99)
        ]

        with self.assertRaisesRegex(ValueError, "数量不足"):
            validate_record_count(records, requested_limit=100)


if __name__ == "__main__":
    unittest.main()
