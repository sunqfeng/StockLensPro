# -*- coding: utf-8 -*-
"""
run_select_and_record.py

作用：
    执行选股策略，并把结果登记到 stock_recommend_record 表。

常用命令：
    1. 执行全部策略：
        python run_select_and_record.py

    2. 指定交易日：
        python run_select_and_record.py --trade-date 2026-05-15

    3. 只执行某一个策略：
        python run_select_and_record.py --strategy TURTLE_TRADE

    4. 指定批次号：
        python run_select_and_record.py --batch-no 20260515_001
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Type

from config import MYSQL_CONFIG, STRATEGY_CONFIG
from mysql_data_engine import MySqlDataEngine
from recommend_record_repository import RecommendRecordRepository
from strategies.base import BaseStrategy, RecommendResult
from strategies.high_tight_flag import HighTightFlagStrategy
from strategies.limit_up_shakeout import LimitUpShakeoutStrategy
from strategies.ma_volume import MaVolumeStrategy
from strategies.monthly_breakout_pullback_hs import MonthlyBreakoutPullbackHsStrategy
from strategies.private_placement import PrivatePlacementStrategy
from strategies.rps_breakout import RpsBreakoutStrategy
from strategies.trend_pullback_v2 import TrendPullbackV2Strategy
from strategies.turtle_trade import TurtleTradeStrategy
from strategies.uptrend_limit_down import UptrendLimitDownStrategy


# 统一注册策略。
# 后续新增策略，只需要：
#   1. 新增策略文件
#   2. import 进来
#   3. 加到这个列表
STRATEGY_CLASSES: List[Type[BaseStrategy]] = [
    TrendPullbackV2Strategy,
    MonthlyBreakoutPullbackHsStrategy,
    TurtleTradeStrategy,
    MaVolumeStrategy,
    HighTightFlagStrategy,
    LimitUpShakeoutStrategy,
    UptrendLimitDownStrategy,
    RpsBreakoutStrategy,
    # 定增策略依赖 akshare 和网络，默认也注册。
    # 如果你不想跑它，可以命令行指定其他策略，或者把这一行注释掉。
    PrivatePlacementStrategy,
]


TECH_SCORE_PROJECT_DIR = Path(os.getenv('STOCKLENS_TECH_SCORE_DIR') or '/srv/python/stock_tech_score_project')
TECH_SCORE_MAIN = TECH_SCORE_PROJECT_DIR / "main.py"


def run_tech_score(recommend_date: str, batch_no: str) -> None:
    """调用推荐股票技术评分任务，处理本次选股批次。"""

    if not TECH_SCORE_MAIN.exists():
        raise FileNotFoundError(f"技术评分入口不存在：{TECH_SCORE_MAIN}")

    tech_score_python = TECH_SCORE_PROJECT_DIR / "venv" / "bin" / "python"
    python_executable = str(tech_score_python) if tech_score_python.exists() else sys.executable
    cmd = [
        python_executable,
        str(TECH_SCORE_MAIN),
        "--date",
        recommend_date,
        "--batch",
        batch_no,
    ]

    print()
    print("=" * 80)
    print(f"开始执行技术评分任务：{TECH_SCORE_MAIN}")
    print(f"Python 解释器：{python_executable}")
    print(f"评分范围：recommend_date={recommend_date}, batch_no={batch_no}")
    print("=" * 80)

    env = os.environ.copy()
    env.update({
        "DB_HOST": str(MYSQL_CONFIG.host),
        "DB_PORT": str(MYSQL_CONFIG.port),
        "DB_USER": str(MYSQL_CONFIG.user),
        "DB_PASSWORD": str(MYSQL_CONFIG.password),
        "DB_NAME": str(MYSQL_CONFIG.database),
    })

    subprocess.run(cmd, cwd=str(TECH_SCORE_PROJECT_DIR), env=env, check=True)
    print("[INFO] 技术评分任务执行完成")


def parse_args():
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="执行 MySQL A股选股策略并登记推荐记录")

    parser.add_argument(
        "--trade-date",
        type=str,
        default=None,
        help="指定选股交易日，例如 2026-05-15。不传则使用 stock_daily 最新交易日。",
    )

    parser.add_argument(
        "--strategy",
        type=str,
        default=None,
        help="只执行某一个策略编码，例如 TURTLE_TRADE、MA_VOLUME、RPS_BREAKOUT。",
    )

    parser.add_argument(
        "--batch-no",
        type=str,
        default=None,
        help="推荐批次号，例如 20260515_001。不传则自动生成。",
    )

    return parser.parse_args()


def build_batch_no(trade_date: str) -> str:
    """
    自动生成推荐批次号。

    示例：
        trade_date = 2026-05-15
        batch_no = 20260515_001
    """

    return trade_date.replace("-", "") + "_001"


def main() -> None:
    args = parse_args()

    # 初始化数据引擎。
    engine = MySqlDataEngine(MYSQL_CONFIG, STRATEGY_CONFIG)

    # 如果命令行没有指定交易日，就取 stock_daily 最新交易日。
    trade_date = args.trade_date or engine.get_latest_trade_date()
    if not trade_date:
        print("[ERROR] 无法获取交易日，请检查 stock_daily 表是否有数据")
        return

    # 统一只保留 YYYY-MM-DD。
    trade_date = str(trade_date)[:10]

    batch_no = args.batch_no or build_batch_no(trade_date)

    print("=" * 80)
    print(f"本次选股交易日：{trade_date}")
    print(f"本次推荐批次号：{batch_no}")
    print("=" * 80)

    # 按命令行过滤策略。
    strategy_classes = STRATEGY_CLASSES
    if args.strategy:
        strategy_code = args.strategy.strip().upper()
        strategy_classes = [
            cls for cls in STRATEGY_CLASSES
            if cls.strategy_code.upper() == strategy_code
        ]
        if not strategy_classes:
            print(f"[ERROR] 未找到策略：{strategy_code}")
            print("可用策略如下：")
            for cls in STRATEGY_CLASSES:
                print(f"  - {cls.strategy_code}: {cls.strategy_name}")
            return

    all_results: list[RecommendResult] = []

    # 逐个执行策略。
    for strategy_cls in strategy_classes:
        print(f"\n========== 开始执行策略：{strategy_cls.strategy_name} [{strategy_cls.strategy_code}] ==========")
        strategy = strategy_cls(engine, STRATEGY_CONFIG, trade_date, batch_no)
        try:
            results = strategy.run()
            all_results.extend(results)
        except Exception as exc:
            # 单个策略失败，不影响其他策略继续执行。
            print(f"[ERROR] 策略 {strategy_cls.strategy_name} 执行失败：{exc}")

    print("\n" + "=" * 80)
    print(f"全部策略执行完成，共产生推荐记录 {len(all_results)} 条")
    print("=" * 80)

    if not all_results:
        print("[INFO] 没有选出股票，不登记数据库")
        return

    # 登记到 stock_recommend_record。
    repository = RecommendRecordRepository(engine)
    try:
        saved_count = repository.save_results(all_results)
        print(f"[INFO] 已登记/更新 stock_recommend_record：{saved_count} 条")
    except Exception as exc:
        print(f"[ERROR] 登记 stock_recommend_record 失败：{exc}")
        raise

    try:
        run_tech_score(trade_date, batch_no)
    except Exception as exc:
        print(f"[ERROR] 技术评分任务执行失败：{exc}")
        raise

    # 候选算法只记录影子结果，绝不替换all_results或修改原推荐/模拟交易。
    try:
        from shadow_pipeline import run_shadow
        snapshot = run_shadow(engine.engine, trade_date, batch_no)
        print(f"[INFO] 优化候选影子快照：{snapshot}")
    except Exception as exc:
        print(f"[WARN] 影子筛选失败，原推荐已保存且未改变：{type(exc).__name__}")


if __name__ == "__main__":
    main()
