"""Offline contract tests for frozen signal research and executable returns."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import threading
import unittest

from stocklens.paper_research import build_groups, freeze_json, net_outcome


class FreezeJsonTests(unittest.TestCase):
    def test_concurrent_first_writers_publish_one_complete_payload(self):
        payloads = [{"writer": i, "rows": [str(i) * 2000] * 4} for i in range(6)]
        barrier = threading.Barrier(len(payloads))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frozen.json"

            def write(payload):
                barrier.wait(timeout=10)
                return freeze_json(path, payload)

            with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
                results = list(executor.map(write, payloads))
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn(stored, payloads)
            for result in results:
                self.assertIsInstance(result, dict)
                self.assertEqual(result, stored)

    def test_existing_freeze_returns_original_without_changing_bytes(self):
        original = {"day": "2026-10-19", "codes": ["000001", "600001"]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frozen.json"
            self.assertEqual(freeze_json(path, original), original)
            original_bytes = path.read_bytes()
            self.assertEqual(freeze_json(path, {"codes": []}), original)
            self.assertEqual(path.read_bytes(), original_bytes)

    def test_nonfinite_nested_numbers_are_rejected_without_publishing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, number in enumerate((float("nan"), float("inf"), -float("inf"))):
                with self.subTest(number=number):
                    path = Path(directory) / f"invalid-{index}.json"
                    with self.assertRaises((ValueError, TypeError)):
                        freeze_json(path, {"rows": [{"score": number}]})
                    self.assertFalse(path.exists())


class BuildGroupsTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"stock_code": code, "eligible": True, "candidate": candidate,
             "score": score, "stratum": stratum}
            for code, candidate, score, stratum in (
                ("000005", True, 4, "small"),
                ("000003", True, 9, "small"),
                ("000002", True, 9, "large"),
                ("000001", True, 1, "large"),
                ("000004", True, 6, "small"),
                ("000006", False, 100, "small"),
                ("000007", False, 100, "large"),
            )
        ]
        self.rows.append({"stock_code": "999999", "eligible": False,
                          "candidate": True, "score": 999, "stratum": "large"})

    def test_candidates_require_eligibility_and_rank_ties_break_by_code(self):
        groups = build_groups(self.rows, "2026-10-19")["groups"]
        self.assertEqual(groups["rps_all"], ["000001", "000002", "000003", "000004", "000005"])
        self.assertEqual(groups["legacy_top3"], ["000002", "000003", "000004"])

    def test_random_groups_are_fixed_size_unique_and_input_order_independent(self):
        baseline = build_groups(self.rows, "2026-10-19")
        shuffled = deepcopy(self.rows)
        random.Random(123).shuffle(shuffled)
        repeated = build_groups(shuffled, "2026-10-19")
        self.assertEqual(baseline, repeated)
        for seed in (17, 43, 97):
            with self.subTest(seed=seed):
                picked = baseline["groups"][f"rps_random3_seed{seed}"]
                self.assertEqual(len(picked), 3)
                self.assertEqual(len(set(picked)), 3)
                self.assertTrue(set(picked) <= set(baseline["groups"]["rps_all"]))
        for cohort in ([], self.rows[:2]):
            with self.subTest(small_cohort=len(cohort)):
                groups = build_groups(cohort, "2026-10-19")["groups"]
                for seed in (17, 43, 97):
                    self.assertEqual(set(groups[f"rps_random3_seed{seed}"]),
                                     set(groups["rps_all"]))

    def test_matched_groups_preserve_strata_and_can_overlap_rps(self):
        strata = {row["stock_code"]: row["stratum"] for row in self.rows}
        groups = build_groups(self.rows, "2026-10-19")["groups"]
        for seed in (17, 43, 97):
            picked = groups[f"universe_matched_seed{seed}"]
            self.assertEqual(len(picked), 5)
            self.assertEqual(len(set(picked)), 5)
            self.assertNotIn("999999", picked)
            self.assertEqual(sum(strata[code] == "large" for code in picked), 2)
            self.assertEqual(sum(strata[code] == "small" for code in picked), 3)
        # In each stratum, the only eligible universe is the RPS cohort itself.
        # Matching must retain it instead of excluding RPS or borrowing strata.
        rows = [row for row in self.rows if row["candidate"]]
        result = build_groups(rows, "2026-10-19")
        self.assertIsInstance(result["matching"], dict)
        expected = set(result["groups"]["rps_all"])
        for seed in (17, 43, 97):
            with self.subTest(seed=seed):
                picked = result["groups"][f"universe_matched_seed{seed}"]
                self.assertEqual(len(picked), len(expected))
                self.assertEqual(set(picked), expected)


class NetOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.entry = {"stock_code": "000001", "entry_price": 10.0,
                      "trade_date": "2026-10-19"}
        self.dates = ["2026-10-19", "2026-10-20", "2026-10-21"]
        self.bars = [
            {"trade_date": day, "close_price": close, "prev_close": previous,
             "volume": 10000, "is_adjusted": False, "sell_locked": False}
            for day, close, previous in zip(self.dates, (10.0, 10.5, 11.0), (9.9, 10.0, 10.5))
        ]
        self.config = {"nominal_budget": 100000, "commission_rate": .0003,
                       "min_commission": 5, "sell_tax_rate": .0005, "slippage_bps": 5}

    def assert_unsettled(self, bars=None, entry=None):
        result = net_outcome(entry or self.entry, self.bars if bars is None else bars,
                             self.dates, self.config)
        self.assertNotEqual(result["status"], "complete")
        self.assertIsNone(result["net_return_pct"])
        return result

    def test_net_return_charges_both_slippages_commissions_and_sell_tax(self):
        result = net_outcome(self.entry, self.bars, self.dates, self.config)
        # 9,900 shares; each commission/tax is rounded to cents HALF_UP.
        # Debit=99,049.50+29.71; credit=108,845.55-32.65-54.42.
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["quantity"], 9900)
        self.assertAlmostEqual(result["invested_cost"], 99079.21, places=2)
        self.assertAlmostEqual(result["net_pnl"], 9679.27, places=2)
        self.assertLessEqual(result["invested_cost"], self.config["nominal_budget"])
        self.assertAlmostEqual(result["net_return_pct"], 9679.27 / 99079.21 * 100, places=6)
        self.assertAlmostEqual(result["budget_return_pct"], 9.67927, places=6)

    def test_minimum_commissions_and_idle_cash_affect_the_two_return_bases(self):
        self.entry["entry_price"] = 1.0
        self.config["nominal_budget"] = 1000
        for bar in self.bars:
            bar["close_price"] = bar["prev_close"] = 1.0
        result = net_outcome(self.entry, self.bars, self.dates, self.config)
        # 900 shares: debit=900.45+5; credit=899.55-5-.45.
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["quantity"], 900)
        self.assertAlmostEqual(result["invested_cost"], 905.45, places=2)
        self.assertLessEqual(result["invested_cost"], self.config["nominal_budget"])
        self.assertAlmostEqual(result["net_return_pct"], -11.35 / 905.45 * 100, places=6)
        self.assertAlmostEqual(result["budget_return_pct"], -1.135, places=6)

    def test_price_too_high_for_one_board_lot_is_not_executable(self):
        self.entry["entry_price"] = 1000.0
        for bar in self.bars:
            bar["close_price"] = bar["prev_close"] = 1000.0
        self.assert_unsettled()

    def test_any_missing_market_date_prevents_settlement_instead_of_zero_fill(self):
        for missing_index in range(len(self.bars)):
            with self.subTest(missing_day=self.dates[missing_index]):
                self.assert_unsettled([bar for i, bar in enumerate(self.bars) if i != missing_index])

    def test_suspension_on_any_expected_day_prevents_settlement(self):
        for index in range(len(self.bars)):
            with self.subTest(suspended_day=self.dates[index]):
                bars = deepcopy(self.bars)
                bars[index]["volume"] = 0
                self.assert_unsettled(bars)

    def test_sell_locked_target_day_has_no_realized_net_return(self):
        self.bars[-1]["sell_locked"] = True
        self.assert_unsettled()

    def test_adjusted_and_raw_prices_cannot_be_mixed(self):
        for index in range(len(self.bars)):
            with self.subTest(adjusted_day=self.dates[index]):
                bars = deepcopy(self.bars)
                bars[index]["is_adjusted"] = True
                self.assert_unsettled(bars)
        bars = deepcopy(self.bars)
        for bar in bars:
            bar["is_adjusted"] = True
        self.assert_unsettled(bars)

    def test_previous_close_discontinuity_is_rejected_but_tolerance_is_allowed(self):
        for delta in (.02, -.02):
            with self.subTest(delta=delta):
                bars = deepcopy(self.bars)
                bars[1]["prev_close"] += delta
                self.assert_unsettled(bars)
        bars = deepcopy(self.bars)
        bars[1]["prev_close"] += .01
        self.assertEqual(net_outcome(self.entry, bars, self.dates, self.config)["status"], "complete")
        self.entry["entry_price"] = 200.0
        for bar in self.bars:
            bar["close_price"] = bar["prev_close"] = 200.0
        for delta, acceptable in ((.019, True), (.021, False)):
            with self.subTest(relative_tolerance=delta):
                bars = deepcopy(self.bars)
                bars[1]["prev_close"] += delta
                if acceptable:
                    result = net_outcome(self.entry, bars, self.dates, self.config)
                    self.assertEqual(result["status"], "complete")
                else:
                    self.assert_unsettled(bars)

    def test_nonfinite_entry_or_price_fields_never_produce_a_realized_return(self):
        for number in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(field="entry_price", number=number):
                entry = dict(self.entry, entry_price=number)
                self.assert_unsettled(entry=entry)
            for field in ("close_price", "prev_close", "volume"):
                with self.subTest(field=field, number=number):
                    bars = deepcopy(self.bars)
                    bars[1][field] = number
                    self.assert_unsettled(bars)


if __name__ == "__main__":
    unittest.main()
