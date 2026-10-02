#!/usr/bin/env python3
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stocklens.db import get_engine
from stocklens.hot_stocks.collector import fetch_hot_stock_html, parse_hot_stock_html
from stocklens.hot_stocks.repository import save_snapshot_batch


def bounded_int(minimum, maximum):
    def parse(value):
        parsed = int(value)
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"参数必须在{minimum}到{maximum}之间"
            )
        return parsed

    return parse


def main():
    parser = argparse.ArgumentParser(description="采集雪球1小时热门股票榜")
    parser.add_argument("--limit", type=bounded_int(1, 100), default=100)
    parser.add_argument("--timeout", type=bounded_int(1, 30), default=10)
    parser.add_argument("--dry-run", action="store_true", help="只采集校验，不写数据库")
    args = parser.parse_args()

    started = time.monotonic()
    html = fetch_hot_stock_html(timeout=args.timeout)
    records = parse_hot_stock_html(html, limit=args.limit)
    duration_ms = round((time.monotonic() - started) * 1000)

    if args.dry_run:
        print(f"采集校验成功：{len(records)}只，耗时{duration_ms}毫秒")
        return 0

    captured_at = datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    batch_id = save_snapshot_batch(
        get_engine(),
        records,
        captured_at=captured_at,
        requested_limit=args.limit,
        duration_ms=duration_ms,
    )
    print(f"热点股票入库成功：批次{batch_id}，共{len(records)}只")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
