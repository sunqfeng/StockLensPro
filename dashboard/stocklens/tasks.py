import json
import os
import re
import shlex
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(os.getenv('STOCKLENS_WORKSPACE_DIR') or '/srv/python')
APP_DIR = BASE_DIR / "StockLensPro"
TASK_LOG_DIR = APP_DIR / "task_logs"
TASK_RUN_DIR = TASK_LOG_DIR / "runs"
TASK_CONFIG_DIR = APP_DIR / "task_config"
CUSTOM_TASK_PATH = TASK_CONFIG_DIR / "custom_tasks.json"
TASK_VISIBILITY_PATH = TASK_CONFIG_DIR / "task_visibility.json"

PYWORKSPACE_DIR = BASE_DIR / "pyworkspace"
SEQUOIA_DIR = BASE_DIR / "sequoia_mysql_strategy"
TECH_SCORE_DIR = BASE_DIR / "stock_tech_score_project"

PYWORKSPACE_PYTHON = BASE_DIR / "AkshareStock" / "venv" / "bin" / "python3"
SEQUOIA_PYTHON = SEQUOIA_DIR / "venv" / "bin" / "python"
TECH_SCORE_PYTHON = TECH_SCORE_DIR / "venv" / "bin" / "python"

STRATEGY_OPTIONS = [
    "全部",
    "TREND_PULLBACK_V2",
    "TURTLE_TRADE",
    "MA_VOLUME",
    "HIGH_TIGHT_FLAG",
    "LIMIT_UP_SHAKEOUT",
    "UPTREND_LIMIT_DOWN",
    "RPS_BREAKOUT",
    "PRIVATE_PLACEMENT",
]


@dataclass(frozen=True)
class TaskDefinition:
    task_id: str
    name: str
    category: str
    description: str
    cwd: Path
    base_command: tuple[str, ...]
    impact: str
    is_builtin: bool = True
    owner: str = "StockLens"


def _python_path(preferred_path: Path) -> str:
    if preferred_path.exists():
        return str(preferred_path)
    return sys.executable


TASK_DEFINITIONS = {
    "collect_xueqiu_hot_stocks": TaskDefinition(
        task_id="collect_xueqiu_hot_stocks",
        name="采集雪球股票热榜",
        category="市场热度",
        description="采集雪球股票热榜前100名，并保存分钟级历史快照。",
        cwd=APP_DIR,
        base_command=(
            _python_path(PYWORKSPACE_PYTHON),
            "scripts/collect_xueqiu_hot_stocks.py",
        ),
        impact="会写入热点榜单批次和快照；同一分钟重复执行会幂等覆盖，不会产生重复批次。",
    ),
    "sync_stock_basic_info": TaskDefinition(
        task_id="sync_stock_basic_info",
        name="同步 stock_basic_info",
        category="基础数据",
        description="执行 sync_stock_basic_info_job.py，同步股票基础财务信息。",
        cwd=PYWORKSPACE_DIR,
        base_command=(
            _python_path(PYWORKSPACE_PYTHON),
            "sync_stock_basic_info_job.py",
        ),
        impact="会更新 stock_basic_info，适合收盘后或发现基础字段过期时手动补跑。",
    ),
    "update_stock_daily": TaskDefinition(
        task_id="update_stock_daily",
        name="同步 stock_daily",
        category="日线数据",
        description="执行 auto_update_stock_daily.py，同步股票日线行情并计算均线。",
        cwd=PYWORKSPACE_DIR,
        base_command=(
            _python_path(PYWORKSPACE_PYTHON),
            "auto_update_stock_daily.py",
        ),
        impact="会更新 stock_daily，耗时可能较长，建议避开正在自动调度的时间。",
    ),
    "recommend_tracker": TaskDefinition(
        task_id="recommend_tracker",
        name="刷新推荐跟踪",
        category="推荐跟踪",
        description="执行 stock_recommend_tracker_V03.py，更新推荐后的跟踪表现。",
        cwd=PYWORKSPACE_DIR,
        base_command=(
            _python_path(PYWORKSPACE_PYTHON),
            "stock_recommend_tracker_V03.py",
        ),
        impact="会更新 stock_recommend_track，用于刷新推荐股票后续涨跌表现。",
    ),
    "run_strategy": TaskDefinition(
        task_id="run_strategy",
        name="运行选股策略",
        category="策略推荐",
        description="执行 run_select_and_record.py，生成 stock_recommend_record，并触发技术评分。",
        cwd=SEQUOIA_DIR,
        base_command=(
            _python_path(SEQUOIA_PYTHON),
            "run_select_and_record.py",
        ),
        impact="会新增推荐记录；可按交易日、策略、批次号控制范围。",
    ),
    "tech_score": TaskDefinition(
        task_id="tech_score",
        name="刷新技术评分",
        category="技术评分",
        description="执行 stock_tech_score_project/main.py，写入 stock_recommend_tech_score。",
        cwd=TECH_SCORE_DIR,
        base_command=(
            _python_path(TECH_SCORE_PYTHON),
            "main.py",
        ),
        impact="会更新 stock_recommend_tech_score，可按最近天数、日期或批次补算。",
    ),
}


def _task_to_dict(task):
    return {
        "task_id": task.task_id,
        "name": task.name,
        "category": task.category,
        "description": task.description,
        "cwd": str(task.cwd),
        "base_command": list(task.base_command),
        "impact": task.impact,
        "is_builtin": task.is_builtin,
        "owner": task.owner,
    }


def _task_from_dict(data):
    return TaskDefinition(
        task_id=data["task_id"],
        name=data["name"],
        category=data.get("category") or "自定义任务",
        description=data.get("description") or "",
        cwd=Path(data["cwd"]),
        base_command=tuple(data["base_command"]),
        impact=data.get("impact") or "自定义任务，请确认执行影响。",
        is_builtin=False,
        owner=data.get("owner") or "自定义",
    )


def _normalize_task_id(value):
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        normalized = uuid.uuid4().hex[:8]
    if not normalized.startswith("custom_"):
        normalized = f"custom_{normalized}"
    return normalized[:80]


def _ensure_safe_cwd(cwd):
    cwd_path = Path(cwd).expanduser()
    if not cwd_path.is_absolute():
        cwd_path = BASE_DIR / cwd_path

    resolved = cwd_path.resolve()
    allowed_roots = [Path("/srv").resolve()]
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise ValueError("工作目录必须在 /srv 下面。")
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"工作目录不存在：{resolved}")
    return resolved


def _load_custom_task_dicts():
    if not CUSTOM_TASK_PATH.exists():
        return []

    try:
        data = json.loads(CUSTOM_TASK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []
    return data


def _save_custom_task_dicts(task_dicts):
    TASK_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = CUSTOM_TASK_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(task_dicts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(CUSTOM_TASK_PATH)


def _load_task_visibility():
    if not TASK_VISIBILITY_PATH.exists():
        return {"hidden_builtin_task_ids": []}

    try:
        data = json.loads(TASK_VISIBILITY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"hidden_builtin_task_ids": []}

    if not isinstance(data, dict):
        return {"hidden_builtin_task_ids": []}

    hidden_ids = data.get("hidden_builtin_task_ids", [])
    if not isinstance(hidden_ids, list):
        hidden_ids = []
    return {"hidden_builtin_task_ids": sorted(set(str(item) for item in hidden_ids))}


def _save_task_visibility(data):
    TASK_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = TASK_VISIBILITY_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(TASK_VISIBILITY_PATH)


def list_hidden_builtin_task_ids():
    return _load_task_visibility()["hidden_builtin_task_ids"]


def load_custom_tasks():
    tasks = {}
    for item in _load_custom_task_dicts():
        try:
            task = _task_from_dict(item)
        except (KeyError, TypeError, ValueError):
            continue
        tasks[task.task_id] = task
    return tasks


def get_all_task_definitions():
    all_tasks = dict(TASK_DEFINITIONS)
    all_tasks.update(load_custom_tasks())
    return all_tasks


def list_tasks():
    hidden_ids = set(list_hidden_builtin_task_ids())
    return [
        task
        for task in get_all_task_definitions().values()
        if not (task.is_builtin and task.task_id in hidden_ids)
    ]


def list_custom_tasks():
    return list(load_custom_tasks().values())


def add_custom_task(*, name, category, description, cwd, command_text, impact, owner="自定义"):
    if not name.strip():
        raise ValueError("任务名称不能为空。")

    command = shlex.split(command_text.strip())
    if not command:
        raise ValueError("执行命令不能为空。")

    task_id = _normalize_task_id(name)
    all_tasks = get_all_task_definitions()
    if task_id in all_tasks:
        task_id = f"{task_id}_{uuid.uuid4().hex[:6]}"

    task = TaskDefinition(
        task_id=task_id,
        name=name.strip(),
        category=category.strip() or "自定义任务",
        description=description.strip(),
        cwd=_ensure_safe_cwd(cwd),
        base_command=tuple(command),
        impact=impact.strip() or "自定义任务，请确认执行影响。",
        is_builtin=False,
        owner=owner.strip() or "自定义",
    )

    task_dicts = _load_custom_task_dicts()
    task_dicts.append(_task_to_dict(task))
    _save_custom_task_dicts(task_dicts)
    return task


def delete_custom_task(task_id):
    custom_tasks = load_custom_tasks()
    if task_id not in custom_tasks:
        raise ValueError("只能删除自定义任务，内置任务不允许删除。")

    kept_tasks = [
        item for item in _load_custom_task_dicts() if item.get("task_id") != task_id
    ]
    _save_custom_task_dicts(kept_tasks)


def remove_task_from_schedule(task_id):
    custom_tasks = load_custom_tasks()
    if task_id in custom_tasks:
        delete_custom_task(task_id)
        return "custom"

    if task_id not in TASK_DEFINITIONS:
        raise ValueError("任务不存在。")

    visibility = _load_task_visibility()
    hidden_ids = set(visibility["hidden_builtin_task_ids"])
    hidden_ids.add(task_id)
    visibility["hidden_builtin_task_ids"] = sorted(hidden_ids)
    _save_task_visibility(visibility)
    return "builtin"


def restore_builtin_task(task_id):
    if task_id not in TASK_DEFINITIONS:
        raise ValueError("只能恢复内置任务。")

    visibility = _load_task_visibility()
    hidden_ids = set(visibility["hidden_builtin_task_ids"])
    hidden_ids.discard(task_id)
    visibility["hidden_builtin_task_ids"] = sorted(hidden_ids)
    _save_task_visibility(visibility)


def build_strategy_command(trade_date=None, strategy=None, batch_no=None):
    task = TASK_DEFINITIONS["run_strategy"]
    command = list(task.base_command)

    if trade_date:
        command.extend(["--trade-date", str(trade_date)])
    if strategy and strategy != "全部":
        command.extend(["--strategy", strategy])
    if batch_no:
        command.extend(["--batch-no", batch_no.strip()])

    return command


def build_tech_score_command(mode, days=None, score_date=None, batch_no=None):
    task = TASK_DEFINITIONS["tech_score"]
    command = list(task.base_command)

    if mode == "最近N天":
        command.extend(["--days", str(days or 1)])
    elif mode == "指定日期" and score_date:
        command.extend(["--date", str(score_date)])
    elif mode == "指定批次" and batch_no:
        command.extend(["--batch", batch_no.strip()])

    return command


def get_task_command(task_id, **params):
    task = get_all_task_definitions()[task_id]

    if task_id == "run_strategy":
        return build_strategy_command(
            trade_date=params.get("trade_date"),
            strategy=params.get("strategy"),
            batch_no=params.get("batch_no"),
        )

    if task_id == "tech_score":
        return build_tech_score_command(
            mode=params.get("mode", "最近N天"),
            days=params.get("days"),
            score_date=params.get("score_date"),
            batch_no=params.get("batch_no"),
        )

    return list(task.base_command)


def read_run_status(run_id):
    status_path = TASK_RUN_DIR / f"{run_id}.json"
    if not status_path.exists():
        return None

    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_recent_runs(limit=20):
    if not TASK_RUN_DIR.exists():
        return []

    runs = []
    for status_path in TASK_RUN_DIR.glob("*.json"):
        status = read_run_status(status_path.stem)
        if status:
            runs.append(status)

    runs.sort(key=lambda item: item.get("started_at", ""), reverse=True)
    return runs[:limit]


def start_task(task_id, command, params=None):
    task = get_all_task_definitions()[task_id]
    TASK_RUN_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{now}_{task_id}_{uuid.uuid4().hex[:8]}"
    status_path = TASK_RUN_DIR / f"{run_id}.json"
    stdout_path = TASK_RUN_DIR / f"{run_id}.out.log"
    stderr_path = TASK_RUN_DIR / f"{run_id}.err.log"

    initial_status = {
        "run_id": run_id,
        "task_id": task_id,
        "task_name": task.name,
        "status": "QUEUED",
        "command": command,
        "cwd": str(task.cwd),
        "params": params or {},
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "finished_at": None,
        "return_code": None,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    status_path.write_text(
        json.dumps(initial_status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    runner_command = [
        sys.executable,
        "-m",
        "stocklens.task_runner",
        "--status-path",
        str(status_path),
        "--stdout-path",
        str(stdout_path),
        "--stderr-path",
        str(stderr_path),
        "--cwd",
        str(task.cwd),
        "--",
        *command,
    ]

    subprocess.Popen(
        runner_command,
        cwd=str(APP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
        env=os.environ.copy(),
    )

    return run_id
