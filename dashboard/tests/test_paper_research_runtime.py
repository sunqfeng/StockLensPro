import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from stocklens.paper_research import freeze_json, read_snapshot, build_groups, net_outcome
from stocklens.paper_research_runtime import collect, make_rows, settle


class ResearchRuntimeTests(unittest.TestCase):
    def inputs(self):
        dates = pd.bdate_range(end='2026-10-22', periods=22)
        history = pd.DataFrame([{'stock_code': '000001', 'trade_date': d,
            'close_price': 10, 'prev_close': 10, 'volume': 10000, 'turnover': 200_000_000,
            'is_adjusted': 0, 'data_quality': 'HIGH'} for d in dates])
        info = pd.DataFrame([{'stock_code': '000001', 'stock_name': '测试股份', 'sub_industry': '行业'}])
        signals = [{'stock_code': '000001', 'id': 1, 'score': 95,
                    'reason': '过去120日涨幅80%；RPS 98.72，当前收盘价接近120日高点12.000。'}]
        quotes = {'000001': {'stock_code': '000001', 'stock_name': '测试股份',
                  'close_price': 10, 'prev_close': 10, 'volume': 10000,
                  'quote_time': '2026-10-23 14:45:00'}}
        return history, info, signals, quotes

    def test_live_revalidation_keeps_original_candidate_for_comparison(self):
        rows = make_rows('2026-10-23', '2026-10-22', *self.inputs())
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['eligible'])
        self.assertTrue(rows[0]['candidate'])
        self.assertEqual(rows[0]['raw_rps'], 98.72)
        self.assertEqual(rows[0]['rps_high120'], 12)
        self.assertFalse(rows[0]['live_proximity_pass'])

    def test_stale_and_missing_quotes_remain_visible(self):
        history, info, signals, quotes = self.inputs()
        quotes['000001']['quote_time'] = '2026-10-23 14:30:00'
        rows = make_rows('2026-10-23', '2026-10-22', history, info, signals, quotes)
        self.assertFalse(rows[0]['eligible'])
        self.assertIn('quote_outside_capture_window', rows[0]['exclusions'])
        rows = make_rows('2026-10-23', '2026-10-22', history, info, signals, {})
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['entry_price'])
        self.assertTrue(rows[0]['candidate'])

    def test_st_filter_uses_actual_quote_name(self):
        history, info, signals, quotes = self.inputs()
        quotes['000001']['stock_name'] = '*ST测试'
        rows = make_rows('2026-10-23', '2026-10-22', history, info, signals, quotes)
        self.assertFalse(rows[0]['eligible'])
        self.assertIn('ST', rows[0]['exclusions'])

    def test_missing_score_stays_missing_and_cannot_fabricate_a_ranking(self):
        history, info, signals, quotes = self.inputs()
        signals[0].update(score=float('nan'), status='SKIPPED', status_reason='position limit', config_version=2)
        rows = make_rows('2026-10-23', '2026-10-22', history, info, signals, quotes)
        self.assertIsNone(rows[0]['score'])
        self.assertEqual(rows[0]['source_signal']['status_reason'], 'position limit')
        self.assertEqual(rows[0]['signal_config_version'], 2)
        self.assertEqual(rows[0]['source_order'], 0)
        groups = build_groups(rows, '2026-10-23')
        self.assertEqual(groups['groups']['rps_all'], ['000001'])
        self.assertEqual(groups['groups']['legacy_top3'], [])
        self.assertEqual(groups['ranking']['status'], 'unavailable')

    def test_entry_day_invalid_reference_price_is_not_a_complete_outcome(self):
        bars = [{'trade_date': '2026-10-22', 'close_price': 10, 'prev_close': float('nan'),
                 'volume': 100, 'is_adjusted': 0, 'sell_locked': False},
                {'trade_date': '2026-10-23', 'close_price': 11, 'prev_close': 10,
                 'volume': 100, 'is_adjusted': 0, 'sell_locked': False}]
        config = dict(nominal_budget=100000, commission_rate=.0003, min_commission=5,
                      sell_tax_rate=.0005, slippage_bps=5)
        outcome = net_outcome({'trade_date': '2026-10-22', 'entry_price': 10}, bars,
                              ['2026-10-22', '2026-10-23'], config)
        self.assertNotEqual(outcome['status'], 'complete')
        self.assertIsNone(outcome['net_return_pct'])

    def test_gzip_snapshot_is_immutable_and_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'cohort.json.gz'
            freeze_json(target, {'x': [1, 2, 3]})
            first = target.read_bytes()
            self.assertEqual(read_snapshot(target), {'x': [1, 2, 3]})
            self.assertEqual(freeze_json(target, {'x': 9}), {'x': [1, 2, 3]})
            self.assertEqual(target.read_bytes(), first)

    def test_weekend_does_not_read_production_or_create_a_cohort(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch('stocklens.paper_research_runtime.datetime') as clock, \
                patch('stocklens.paper_research_runtime.read_inputs') as query:
            clock.now.return_value = datetime(2026, 10, 24, 14, 45)
            result = collect(output=folder)
            self.assertEqual(result['event'], 'capture_skipped')
            query.assert_not_called()
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_settlement_uses_next_market_day_and_freezes_only_mature_horizon(self):
        costs = dict(nominal_budget=100000, commission_rate=.0003, min_commission=5,
                     sell_tax_rate=.0005, slippage_bps=5)
        rows = [{'stock_code': '000001', 'entry_price': 10, 'eligible': True,
                 'candidate': True, 'score': 95, 'stratum': 'Main:0:0'}]
        groups = build_groups(rows, '2026-10-19')['groups']
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            freeze_json(root/'cohorts/2026-10-19.json.gz', {'trade_date': '2026-10-19',
                'mode': 'prospective_1445', 'rows': rows, 'groups': groups, 'costs': costs,
                'benchmarks': {'sh000300': {'entry_price': 100}}})
            for day, close, reference in [('2026-10-19', 10, 10), ('2026-10-20', 11, 10)]:
                freeze_json(root/'market_closes'/f'{day}.json.gz', {'stocks': {'000001': {
                    'trade_date': day, 'close_price': close, 'prev_close': reference,
                    'volume': 1000, 'is_adjusted': 0, 'sell_locked': False}}, 'indices': {'sh000300': 110}})
            with patch('stocklens.paper_research_runtime.datetime') as clock, \
                    patch('stocklens.paper_research_runtime._trade_dates', return_value={'2026-10-19', '2026-10-20'}), \
                    patch('stocklens.paper_research_runtime.capture_close'):
                clock.now.return_value = datetime(2026, 10, 20, 16, 10)
                result = settle(root)
                self.assertEqual(result['new_horizons'], 1)
                self.assertEqual(result['pending_horizons'], 3)
                target = root/'outcomes/2026-10-19/01d.json'
                first = target.read_bytes()
                outcome = read_snapshot(target)
                self.assertEqual(outcome['target_date'], '2026-10-20')
                self.assertEqual(outcome['groups']['rps_all']['complete_n'], 1)
                self.assertAlmostEqual(outcome['benchmark_price_returns_pct']['sh000300'], 10)
                self.assertEqual(settle(root)['new_horizons'], 0)
                self.assertEqual(target.read_bytes(), first)


if __name__ == '__main__':
    unittest.main()
