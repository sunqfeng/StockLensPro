import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


class CronConfigurationTests(unittest.TestCase):
    def test_cron_uses_configured_interpreter_without_running_collection(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/run_configured_hot_stock_cron.py'
        env = dict(STOCKLENS_APP_DIR=str(script.parent.parent),
                   STOCKLENS_PYWORKSPACE_PYTHON='/demo/venv/bin/python')
        with patch.dict(os.environ, env), patch('os.chdir') as chdir, patch('os.execv') as execute:
            runpy.run_path(str(script))
        chdir.assert_called_once_with(script.parent.parent)
        execute.assert_called_once_with('/demo/venv/bin/python',
                                       ['/demo/venv/bin/python', 'scripts/collect_xueqiu_hot_stocks.py', '--limit', '100'])
