#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly APP_DIR="${STOCKLENS_APP_DIR:-${SCRIPT_APP_DIR}}"
DEFAULT_PYTHON="${SCRIPT_APP_DIR}/../AkshareStock/venv/bin/python3"
if [[ ! -x "${DEFAULT_PYTHON}" ]]; then DEFAULT_PYTHON="python3"; fi
readonly PYTHON_BIN="${STOCKLENS_PYWORKSPACE_PYTHON:-${DEFAULT_PYTHON}}"
readonly LOCK_FILE="/tmp/stocklens_xueqiu_hot_stocks.lock"

cd "${APP_DIR}"

# 防止网络变慢时两个30分钟批次重叠执行。
exec /usr/bin/flock -n "${LOCK_FILE}" \
    "${PYTHON_BIN}" scripts/run_configured_hot_stock_cron.py
