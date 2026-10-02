#!/usr/bin/env bash
set -euo pipefail

readonly APP_DIR="/srv/python/StockLensPro"
readonly PYTHON_BIN="/srv/python/AkshareStock/venv/bin/python3"
readonly LOCK_FILE="/tmp/stocklens_xueqiu_hot_stocks.lock"

cd "${APP_DIR}"

# 防止网络变慢时两个30分钟批次重叠执行。
exec /usr/bin/flock -n "${LOCK_FILE}" \
    "${PYTHON_BIN}" scripts/collect_xueqiu_hot_stocks.py --limit 100
