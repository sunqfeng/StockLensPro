#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stocklens.paper_research_runtime import collect, settle


def main():
    parser = argparse.ArgumentParser(description='Independent prospective RPS controls; never writes paper trading tables')
    parser.add_argument('action', choices=['capture', 'settle', 'preview'])
    parser.add_argument('--date', help='Required only for historical close preview; never creates a forward cohort')
    args = parser.parse_args()
    if args.action != 'preview' and args.date:
        parser.error('--date is only valid for preview')
    if args.action == 'preview' and not args.date:
        parser.error('preview requires --date')
    try:
        result = settle() if args.action == 'settle' else collect(args.date, preview=args.action == 'preview')
    except Exception as exc:
        print(json.dumps({'event': 'paper_research_failed', 'action': args.action,
                          'error_type': type(exc).__name__}, ensure_ascii=False), flush=True)
        return 1
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
