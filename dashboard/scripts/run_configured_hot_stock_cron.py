"""读取同一 secrets.env 后，使用配置的解释器执行原热榜采集入口。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stocklens.config import PROJECT_DIR, configured_path

app_dir = configured_path('STOCKLENS_APP_DIR', PROJECT_DIR)
python = os.getenv('STOCKLENS_PYWORKSPACE_PYTHON') or sys.executable
os.chdir(app_dir)
os.execv(python, [python, 'scripts/collect_xueqiu_hot_stocks.py', '--limit', '100'])
