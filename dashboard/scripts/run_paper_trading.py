#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stocklens.paper_trading import run_signals, run_tick, settle_nav


def main():
    parser = argparse.ArgumentParser(description="StockLens 前向模拟交易")
    parser.add_argument("action", choices=["tick", "signals", "settle"])
    args = parser.parse_args()
    if args.action == "tick":
        print(run_tick())
    elif args.action == "signals":
        print(run_signals())
    else:
        print(settle_nav())


if __name__ == "__main__":
    main()
