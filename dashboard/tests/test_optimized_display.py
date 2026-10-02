import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from stocklens.data.optimized_recommendations import read_optimized_ids
from stocklens.data.loaders import load_detail_data, load_strategy_stats
from stocklens.data import optimized_recommendations as recommendations


class OptimizedDisplayTests(unittest.TestCase):
    def test_history_is_preserved_and_new_rules_only_apply_from_effective_date(self):
        with patch.object(recommendations, 'get_engine', return_value=object(), create=True), \
             patch.object(recommendations, 'pd', create=True) as pandas, \
             patch.object(recommendations, 'read_optimized_ids', return_value=((9,), dict(
                 issues=[], replayed=False, evaluated_batches=[('2026-10-08', 'new')])) ) as snapshots:
            pandas.read_sql.return_value = pd.DataFrame({'id': [1, 2, 3, 4]})
            ids, info = recommendations.load_display_ids.__wrapped__(
                '2026-09-01', '2026-10-08', '全部')
            self.assertEqual(ids, (1, 2, 3, 4, 9))
            self.assertEqual(info['historical_records'], 4)
            self.assertEqual(info['optimized_records'], 1)
            snapshots.assert_called_once_with('2026-10-02', '2026-10-08', '全部')
            params = pandas.read_sql.call_args.kwargs['params']
            self.assertEqual(params['end_date'], '2026-10-01')

    def test_history_does_not_require_an_optimization_snapshot(self):
        with patch.object(recommendations, 'get_engine', return_value=object(), create=True), \
             patch.object(recommendations, 'pd', create=True) as pandas, \
             patch.object(recommendations, 'read_optimized_ids') as snapshots:
            pandas.read_sql.return_value = pd.DataFrame({'id': [1, 2]})
            ids, info = recommendations.load_display_ids.__wrapped__(
                '2026-09-01', '2026-09-30', 'old')
            self.assertEqual(ids, (1, 2))
            snapshots.assert_not_called()
            self.assertEqual(pandas.read_sql.call_args.kwargs['params']['selected_batch'], 'old')

    def test_future_without_new_candidates_does_not_fall_back_to_old_algorithm(self):
        with patch.object(recommendations, 'get_engine', create=True) as engine, \
             patch.object(recommendations, 'read_optimized_ids', return_value=((), dict(
                 issues=[], replayed=False, evaluated_batches=[]))):
            ids, info = recommendations.load_display_ids.__wrapped__(
                '2026-10-02', '2026-10-08', '全部')
            self.assertEqual(ids, ())
            self.assertEqual(info['historical_records'], 0)
            engine.assert_not_called()

    def snapshot(self,folder,version='candidate-v1.2'):
        records=[{'id':i,'recommend_date':'2026-09-30','recommend_batch_no':'b',
                  'decision':decision} for i,decision in [(1,'候选保留'),(2,'规则过滤'),(3,'数据待核查'),(4,'未纳入优化')]]
        (Path(folder)/f'snapshot_{version}.json').write_text(json.dumps(dict(
            version=version,data_cutoff='2026-09-30',batch_no='b',mode='历史/盘中重放',records=records)),encoding='utf-8')

    def test_only_current_version_candidates_are_displayed(self):
        with tempfile.TemporaryDirectory() as folder:
            self.snapshot(folder)
            self.snapshot(folder,'candidate-v1.1')
            ids,info=read_optimized_ids('2026-09-01','2026-10-02','全部',Path(folder))
            self.assertEqual(ids,(1,))
            self.assertEqual(info['evaluated_records'],4)
            self.assertTrue(info['replayed'])

    def test_empty_missing_corrupt_and_wrong_batch_never_fall_back_to_original(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(read_optimized_ids('2026-09-01','2026-10-02','全部',Path(folder))[0],())
            self.snapshot(folder)
            self.assertEqual(read_optimized_ids('2026-09-01','2026-10-02','other',Path(folder))[0],())
            self.assertEqual(read_optimized_ids('2026-08-01','2026-08-31','全部',Path(folder))[0],())
            (Path(folder)/'bad_candidate-v1.2.json').write_text('{',encoding='utf-8')
            ids,info=read_optimized_ids('2026-09-01','2026-10-02','全部',Path(folder))
            self.assertEqual(ids,(1,))
            self.assertTrue(info['issues'])

    def test_stats_and_detail_use_the_identical_parameterized_scope(self):
        for ids in [(1,),()]:
            with self.subTest(ids=ids),patch('stocklens.data.loaders.get_engine',return_value=object()), \
                 patch('stocklens.data.loaders.pd.read_sql',return_value=pd.DataFrame()) as sql, \
                 patch('stocklens.data.loaders.load_latest_hot_rank_lookup',return_value=({},pd.DataFrame())), \
                 patch('stocklens.data.loaders.attach_latest_hot_rank',return_value=pd.DataFrame()):
                load_strategy_stats.clear()
                load_detail_data.clear()
                load_strategy_stats('2026-09-01','2026-10-02','按策略','全部','全部',recommendation_ids=ids)
                load_detail_data('2026-09-01','2026-10-02','全部','全部',recommendation_ids=ids)
                self.assertEqual(sql.call_count,2)
                for call in sql.call_args_list:
                    self.assertIn('r.id IN',str(call.args[0]))
                    self.assertEqual(call.kwargs['params']['recommendation_ids'],ids)

    def test_inconsistent_snapshot_is_excluded_entirely(self):
        with tempfile.TemporaryDirectory() as folder:
            self.snapshot(folder)
            path=Path(folder)/'snapshot_candidate-v1.2.json'
            payload=json.loads(path.read_text(encoding='utf-8'))
            payload['records'][1]['recommend_batch_no']='wrong'
            path.write_text(json.dumps(payload),encoding='utf-8')
            ids,info=read_optimized_ids('2026-09-01','2026-10-02','全部',Path(folder))
            self.assertEqual(ids,())
            self.assertTrue(info['issues'])


if __name__=='__main__':
    unittest.main()
