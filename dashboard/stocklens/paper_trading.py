from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date, datetime, time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text

from stocklens.db import get_engine
from stocklens.integrations.jev import build_signal_state, evaluate_signal


TZ = ZoneInfo("Asia/Shanghai")
BASE_DIR = Path("/srv/python")
STRATEGY_DIR = BASE_DIR / "sequoia_mysql_strategy"
QUOTE_MODULE = BASE_DIR / "pyworkspace" / "auto_update_stock_daily.py"
TRADE_CALENDAR_CACHE = Path(__file__).resolve().parents[1] / "task_logs" / "a_share_trade_dates.json"

DEFAULT_CONFIG = {
    "strategies": ["TREND_PULLBACK_V2"],
    "position_pct": 10.0,
    "max_positions": 10,
    "max_daily_buys": 3,
    "min_score": 0.0,
    "take_profit_pct": 10.0,
    "stop_loss_pct": 5.0,
    "max_holding_days": 20,
    "commission_rate": 0.0003,
    "min_commission": 5.0,
    "sell_tax_rate": 0.0005,
    "slippage_bps": 5.0,
}

STRATEGY_NAMES = {
    "TREND_PULLBACK_V2": "趋势回踩 + 行业主线",
    "MONTHLY_BREAKOUT_PULLBACK_HS": "月线突破回踩 + 日线头肩底",
    "TURTLE_TRADE": "海龟20日突破",
    "MA_VOLUME": "均线金叉放量",
    "HIGH_TIGHT_FLAG": "高旗形整理",
    "LIMIT_UP_SHAKEOUT": "涨停洗盘",
    "UPTREND_LIMIT_DOWN": "上升趋势放量跌停",
    "RPS_BREAKOUT": "RPS强势突破",
    "PRIVATE_PLACEMENT": "定向增发公告",
}


def now_cn() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


@lru_cache(maxsize=1)
def _trade_dates(today: date) -> set[str]:
    cached_dates: set[str] = set()
    try:
        cached = json.loads(TRADE_CALENDAR_CACHE.read_text(encoding="utf-8"))
        if not isinstance(cached.get("dates"), list):
            raise ValueError("无效的交易日历缓存。")
        cached_dates = set(cached["dates"])
        if cached.get("updated_on") == today.isoformat():
            return cached_dates
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        import akshare as ak

        frame = ak.tool_trade_date_hist_sina()
        dates = sorted({str(value)[:10] for value in frame["trade_date"]})
        if not dates or dates[-1] < today.isoformat():
            raise RuntimeError("交易日历未覆盖当前日期。")
        payload = {"updated_on": today.isoformat(), "dates": dates}
        TRADE_CALENDAR_CACHE.parent.mkdir(parents=True, exist_ok=True)
        temporary = TRADE_CALENDAR_CACHE.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(TRADE_CALENDAR_CACHE)
        return set(dates)
    except Exception as exc:
        if cached_dates and max(cached_dates) >= today.isoformat():
            return cached_dates
        raise RuntimeError(f"无法确认A股是否开市，已停止模拟交易：{exc}") from exc


def is_a_share_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day.isoformat() in _trade_dates(day)


def load_config(raw: str | None) -> dict:
    config = dict(DEFAULT_CONFIG)
    if raw:
        config.update(json.loads(raw))
    return config


def validate_config(config: dict) -> dict:
    result = load_config(json.dumps(config, ensure_ascii=False))
    result["strategies"] = [code for code in result["strategies"] if code in STRATEGY_NAMES]
    if not result["strategies"]:
        raise ValueError("至少选择一个策略。")
    for key in ("position_pct", "take_profit_pct", "stop_loss_pct"):
        result[key] = float(result[key])
        if result[key] <= 0:
            raise ValueError(f"{key} 必须大于 0。")
    if result["position_pct"] > 100:
        raise ValueError("单只仓位不能超过 100%。")
    for key in ("max_positions", "max_daily_buys", "max_holding_days"):
        result[key] = int(result[key])
        if result[key] < 1:
            raise ValueError(f"{key} 必须至少为 1。")
    for key in ("min_score", "commission_rate", "min_commission", "sell_tax_rate", "slippage_bps"):
        result[key] = float(result[key])
        if result[key] < 0:
            raise ValueError(f"{key} 不能为负数。")
    return result


def buy_fee(amount: float, config: dict) -> float:
    return round(max(amount * config["commission_rate"], config["min_commission"]), 2)


def sell_cost(amount: float, config: dict) -> tuple[float, float]:
    return buy_fee(amount, config), round(amount * config["sell_tax_rate"], 2)


def calculate_buy_quantity(cash: float, equity: float, quote_price: float, config: dict) -> tuple[int, float, float]:
    fill_price = round(quote_price * (1 + config["slippage_bps"] / 10_000), 4)
    budget = min(cash, equity * config["position_pct"] / 100)
    quantity = int(budget / fill_price / 100) * 100
    while quantity > 0:
        amount = round(quantity * fill_price, 2)
        fee = buy_fee(amount, config)
        if amount + fee <= cash:
            return quantity, fill_price, fee
        quantity -= 100
    return 0, fill_price, 0.0


def exit_reason(price: float, take_profit: float, stop_loss: float, holding_days: int, max_days: int) -> str | None:
    if price >= take_profit:
        return "止盈"
    if price <= stop_loss:
        return "止损"
    if holding_days >= max_days:
        return "到期"
    return None


def _price_limit_pct(stock_code: str, stock_name: str | None) -> float:
    name = (stock_name or "").upper()
    if "ST" in name:
        return 5.0
    if stock_code.startswith(("300", "301", "688", "689")):
        return 20.0
    if stock_code.startswith(("4", "8", "92")):
        return 30.0
    return 10.0


def limit_locked(quote: dict, side: str) -> bool:
    previous = float(quote.get("prev_close") or 0)
    current = float(quote.get("close_price") or 0)
    if previous <= 0 or current <= 0:
        return True
    limit_pct = _price_limit_pct(str(quote["stock_code"]), quote.get("stock_name"))
    limit_price = round(previous * (1 + (limit_pct if side == "BUY" else -limit_pct) / 100), 2)
    # ponytail: conservative price-only lock check; replace with order-book depth if real execution is added.
    return current >= limit_price if side == "BUY" else current <= limit_price


def create_account(name: str, initial_cash: float, config: dict) -> int:
    if initial_cash <= 0:
        raise ValueError("初始金额必须大于 0。")
    config = validate_config(config)
    engine = get_engine()
    with engine.begin() as conn:
        active = conn.execute(text("SELECT id FROM paper_accounts WHERE status IN ('ACTIVE','PAUSED') LIMIT 1")).scalar()
        if active:
            raise ValueError("已有模拟账户，不能重复创建。")
        result = conn.execute(
            text("""
                INSERT INTO paper_accounts (name, initial_cash, cash, config_json)
                VALUES (:name, :initial_cash, :initial_cash, :config_json)
            """),
            {"name": name.strip() or "前向模拟账户", "initial_cash": initial_cash,
             "config_json": json.dumps(config, ensure_ascii=False)},
        )
        account_id = int(result.lastrowid)
        conn.execute(
            text("""
                INSERT INTO paper_cash_ledger
                    (account_id, event_time, event_type, amount, balance_after, description)
                VALUES (:account_id, :now, 'INITIAL', :amount, :amount, '初始资金')
            """),
            {"account_id": account_id, "now": now_cn(), "amount": initial_cash},
        )
        conn.execute(
            text("INSERT INTO paper_config_versions (account_id,version_no,config_json) VALUES (:id,1,:config)"),
            {"id": account_id, "config": json.dumps(config, ensure_ascii=False)},
        )
    return account_id


def update_account_config(account_id: int, config: dict) -> None:
    config = validate_config(config)
    with get_engine().begin() as conn:
        conn.execute(
            text("""
                UPDATE paper_accounts
                SET config_json=:config_json, config_version=config_version+1
                WHERE id=:account_id
            """),
            {"account_id": account_id, "config_json": json.dumps(config, ensure_ascii=False)},
        )
        version = conn.execute(
            text("SELECT config_version FROM paper_accounts WHERE id=:id"), {"id": account_id}
        ).scalar_one()
        conn.execute(
            text("INSERT INTO paper_config_versions (account_id,version_no,config_json) VALUES (:id,:version,:config)"),
            {"id": account_id, "version": version, "config": json.dumps(config, ensure_ascii=False)},
        )


def set_account_status(account_id: int, status: str) -> None:
    if status not in {"ACTIVE", "PAUSED"}:
        raise ValueError("无效账户状态。")
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE paper_accounts SET status=:status WHERE id=:id"), {"id": account_id, "status": status})


def get_account() -> dict | None:
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT * FROM paper_accounts ORDER BY id DESC LIMIT 1")).mappings().first()
    if not row:
        return None
    result = dict(row)
    result["config"] = load_config(result.pop("config_json"))
    return result


def load_positions(status: str | None = None) -> pd.DataFrame:
    where = "WHERE p.status=:status" if status else ""
    return pd.read_sql(
        text(f"""
            SELECT p.*, DATEDIFF(COALESCE(p.exit_time, NOW()), p.entry_time) AS calendar_days
            FROM paper_positions p {where}
            ORDER BY p.entry_time DESC
        """), get_engine(), params={"status": status} if status else None,
    )


def load_signals(limit: int = 200) -> pd.DataFrame:
    return pd.read_sql(
        text("""
            SELECT s.*,
                j.status AS jev_status,
                j.run_mode AS jev_mode,
                j.model_resolved AS jev_model,
                j.quality_probability AS jev_quality_probability,
                j.risk_probability AS jev_risk_probability,
                j.setup_score AS jev_setup_score,
                j.setup_confidence AS jev_setup_confidence,
                j.latency_ms AS jev_latency_ms,
                j.error_message AS jev_error_message
            FROM paper_signals s
            LEFT JOIN paper_jev_decisions j ON j.id = (
                SELECT MAX(j2.id) FROM paper_jev_decisions j2 WHERE j2.signal_id=s.id
            )
            ORDER BY s.signal_time DESC, s.score DESC
            LIMIT :limit
        """),
        get_engine(), params={"limit": int(limit)},
    )


def load_nav() -> pd.DataFrame:
    return pd.read_sql(text("SELECT * FROM paper_nav_daily ORDER BY trade_date"), get_engine())


def load_runs(limit: int = 100) -> pd.DataFrame:
    return pd.read_sql(
        text("SELECT * FROM paper_runs ORDER BY started_at DESC LIMIT :limit"),
        get_engine(), params={"limit": int(limit)},
    )


def _quote_function():
    spec = importlib.util.spec_from_file_location("stocklens_realtime_quotes", QUOTE_MODULE)
    if not spec or not spec.loader:
        raise RuntimeError(f"无法加载行情模块：{QUOTE_MODULE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.get_realtime_quotes


def fetch_quotes(stock_codes: list[str]) -> dict[str, dict]:
    if not stock_codes:
        return {}
    frame = _quote_function()(sorted(set(stock_codes)))
    if frame is None or frame.empty:
        return {}
    return {str(row["stock_code"]).zfill(6): row.to_dict() for _, row in frame.iterrows()}


def _valid_today_quote(quote: dict, today: date, max_age_minutes: int | None = None) -> bool:
    quote_time = pd.to_datetime(quote.get("quote_time"), errors="coerce")
    if pd.isna(quote_time) or quote_time.date() != today or float(quote.get("close_price") or 0) <= 0:
        return False
    if max_age_minutes is not None:
        age = abs((now_cn() - quote_time.to_pydatetime()).total_seconds())
        return age <= max_age_minutes * 60
    return True


def _code_version() -> str:
    try:
        version = subprocess.check_output(
            ["git", "-C", str(STRATEGY_DIR), "rev-parse", "--short", "HEAD"], text=True
        ).strip()
        dirty = subprocess.run(
            ["git", "-C", str(STRATEGY_DIR), "status", "--porcelain"],
            capture_output=True, text=True, check=False,
        ).stdout.strip()
        return version + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def _strategy_runtime():
    sys.path.insert(0, str(STRATEGY_DIR))
    try:
        from config import MYSQL_CONFIG, STRATEGY_CONFIG
        from mysql_data_engine import MySqlDataEngine
        from run_select_and_record import STRATEGY_CLASSES
        return MySqlDataEngine(MYSQL_CONFIG, STRATEGY_CONFIG), STRATEGY_CONFIG, STRATEGY_CLASSES
    finally:
        sys.path.pop(0)


def _latest_complete_data_date(engine, today: date) -> str:
    frame = engine.read_sql(
        "SELECT MAX(trade_date) AS data_date FROM stock_daily WHERE trade_date < :today",
        {"today": today.isoformat()},
    )
    value = frame.loc[0, "data_date"] if not frame.empty else None
    if pd.isna(value):
        raise RuntimeError("没有可用的完整历史日线。")
    return str(value)[:10]


def _start_run(account_id: int, run_type: str, today: date, data_date: str | None = None) -> int:
    with get_engine().begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO paper_runs (account_id, run_type, trade_date, data_date, code_version)
                VALUES (:account_id, :run_type, :trade_date, :data_date, :code_version)
            """),
            {"account_id": account_id, "run_type": run_type, "trade_date": today,
             "data_date": data_date, "code_version": _code_version()},
        )
        return int(result.lastrowid)


def _finish_run(run_id: int, status: str, message: str) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE paper_runs SET status=:status, message=:message, finished_at=:now WHERE id=:id"),
            {"id": run_id, "status": status, "message": message[:4000], "now": now_cn()},
        )


def _account_equity(conn, account: dict) -> float:
    market_value = conn.execute(
        text("SELECT COALESCE(SUM(quantity * current_price),0) FROM paper_positions WHERE account_id=:id AND status='OPEN'"),
        {"id": account["id"]},
    ).scalar()
    return float(account["cash"]) + float(market_value or 0)


def _save_jev_decisions(records: list[tuple[int, dict, dict]]) -> None:
    if not records:
        return
    statement = text("""
        INSERT INTO paper_jev_decisions
            (signal_id,run_mode,question_version,status,model_requested,model_resolved,
             quality_probability,risk_probability,setup_score,setup_confidence,
             request_state_json,response_json,latency_ms,error_message)
        VALUES
            (:signal_id,:run_mode,:question_version,:status,:model_requested,:model_resolved,
             :quality_probability,:risk_probability,:setup_score,:setup_confidence,
             :request_state_json,:response_json,:latency_ms,:error_message)
        ON DUPLICATE KEY UPDATE
            run_mode=VALUES(run_mode),status=VALUES(status),model_requested=VALUES(model_requested),
            model_resolved=VALUES(model_resolved),quality_probability=VALUES(quality_probability),
            risk_probability=VALUES(risk_probability),setup_score=VALUES(setup_score),
            setup_confidence=VALUES(setup_confidence),request_state_json=VALUES(request_state_json),
            response_json=VALUES(response_json),latency_ms=VALUES(latency_ms),
            error_message=VALUES(error_message)
    """)
    with get_engine().begin() as conn:
        for signal_id, state, decision in records:
            conn.execute(statement, {
                "signal_id": signal_id,
                "run_mode": decision["mode"],
                "question_version": decision["question_version"],
                "status": decision["status"],
                "model_requested": decision["model_requested"],
                "model_resolved": decision["model_resolved"],
                "quality_probability": decision["quality_probability"],
                "risk_probability": decision["risk_probability"],
                "setup_score": decision["setup_score"],
                "setup_confidence": decision["setup_confidence"],
                "request_state_json": json.dumps(state, ensure_ascii=False),
                "response_json": json.dumps(decision["response_json"], ensure_ascii=False)
                    if decision["response_json"] is not None else None,
                "latency_ms": decision["latency_ms"],
                "error_message": decision["error_message"],
            })


def _holding_days(conn, entry_time: datetime, today: date) -> int:
    if entry_time.date() >= today:
        return 0
    completed = conn.execute(
        text("SELECT COUNT(DISTINCT trade_date) FROM stock_daily WHERE trade_date>:entry AND trade_date<:today"),
        {"entry": entry_time.date(), "today": today},
    ).scalar()
    return int(completed or 0) + 1


def monitor_positions(account: dict | None = None) -> str:
    account = account or get_account()
    if not account or account["status"] not in {"ACTIVE", "PAUSED"}:
        return "没有运行中的模拟账户。"
    today = now_cn().date()
    positions = load_positions("OPEN")
    if positions.empty:
        return "当前没有持仓。"
    quotes = fetch_quotes(positions["stock_code"].astype(str).tolist())
    sold = 0
    with get_engine().begin() as conn:
        locked = dict(conn.execute(text("SELECT * FROM paper_accounts WHERE id=:id FOR UPDATE"), {"id": account["id"]}).mappings().one())
        cash = float(locked["cash"])
        for position in positions.to_dict("records"):
            code = str(position["stock_code"]).zfill(6)
            quote = quotes.get(code)
            if not quote or not _valid_today_quote(quote, today, max_age_minutes=15):
                continue
            price = float(quote["close_price"])
            quote_time = pd.to_datetime(quote["quote_time"]).to_pydatetime()
            conn.execute(
                text("UPDATE paper_positions SET current_price=:price,current_quote_time=:quote_time WHERE id=:id"),
                {"id": position["id"], "price": price, "quote_time": quote_time},
            )
            holding_days = _holding_days(conn, pd.to_datetime(position["entry_time"]).to_pydatetime(), today)
            reason = exit_reason(
                price, float(position["take_profit_price"]), float(position["stop_loss_price"]),
                holding_days, int(position["max_holding_days"]),
            )
            if not reason or holding_days < 1 or limit_locked(quote, "SELL"):
                continue
            position_config = {
                "commission_rate": float(position["commission_rate"]),
                "min_commission": float(position["min_commission"]),
                "sell_tax_rate": float(position["sell_tax_rate"]),
                "slippage_bps": float(position["slippage_bps"]),
            }
            fill_price = round(price * (1 - position_config["slippage_bps"] / 10_000), 4)
            gross = round(int(position["quantity"]) * fill_price, 2)
            fee, tax = sell_cost(gross, position_config)
            proceeds = round(gross - fee - tax, 2)
            cost = round(int(position["quantity"]) * float(position["entry_price"]) + float(position["entry_fee"]), 2)
            pnl = round(proceeds - cost, 2)
            cash = round(cash + proceeds, 2)
            conn.execute(
                text("""
                    UPDATE paper_positions SET status='CLOSED', current_price=:price,
                        exit_time=:now, exit_price=:fill, exit_fee=:fee, exit_tax=:tax,
                        realized_pnl=:pnl, exit_reason=:reason WHERE id=:id
                """),
                {"id": position["id"], "price": price, "now": now_cn(), "fill": fill_price,
                 "fee": fee, "tax": tax, "pnl": pnl, "reason": reason},
            )
            conn.execute(
                text("""
                    INSERT INTO paper_cash_ledger
                        (account_id,position_id,event_time,event_type,amount,balance_after,description)
                    VALUES (:account_id,:position_id,:now,'SELL',:amount,:balance,:description)
                """),
                {"account_id": account["id"], "position_id": position["id"], "now": now_cn(),
                 "amount": proceeds, "balance": cash, "description": f"{reason}卖出，费用{fee + tax:.2f}"},
            )
            sold += 1
        conn.execute(text("UPDATE paper_accounts SET cash=:cash WHERE id=:id"), {"cash": cash, "id": account["id"]})
    return f"检查 {len(positions)} 个持仓，卖出 {sold} 个。"


def run_signals(account: dict | None = None) -> str:
    account = account or get_account()
    if not account or account["status"] != "ACTIVE":
        return "没有运行中的模拟账户。"
    today = now_cn().date()
    if not is_a_share_trading_day(today):
        return f"{today} A股休市，不产生推荐信号。"
    with get_engine().connect() as conn:
        completed = conn.execute(
            text("""
                SELECT id FROM paper_runs
                WHERE account_id=:account_id AND run_type='SIGNAL'
                  AND trade_date=:today AND status='SUCCESS' LIMIT 1
            """),
            {"account_id": account["id"], "today": today},
        ).scalar()
    if completed:
        return f"{today} 的推荐任务已经成功执行，不重复买入。"
    engine, strategy_config, classes = _strategy_runtime()
    data_date = _latest_complete_data_date(engine, today)
    run_id = _start_run(account["id"], "SIGNAL", today, data_date)
    try:
        selected = set(account["config"]["strategies"])
        strategy_classes = [cls for cls in classes if cls.strategy_code in selected]
        results = []
        for strategy_cls in strategy_classes:
            results.extend(strategy_cls(engine, strategy_config, data_date, f"PAPER_{today:%Y%m%d}").run())
        codes = [result.stock_code for result in results]
        quotes = fetch_quotes(codes)
        signal_rows = []
        class_codes = {cls.strategy_name: cls.strategy_code for cls in strategy_classes}
        for result in results:
            quote = quotes.get(str(result.stock_code).zfill(6), {})
            valid = _valid_today_quote(quote, today, max_age_minutes=15)
            signal_rows.append({
                "result": result,
                "strategy_code": class_codes.get(result.strategy_name, result.strategy_name),
                "quote": quote,
                "quote_price": float(quote.get("close_price") or 0) if valid else None,
                "quote_time": pd.to_datetime(quote.get("quote_time")).to_pydatetime() if valid else None,
                "status": "CANDIDATE" if valid else "SKIPPED",
                "reason": None if valid else "没有当日有效实时行情",
            })
        signal_rows.sort(key=lambda row: float(row["result"].recommend_score), reverse=True)
        bought = 0
        used_stocks = set()
        jev_candidates = []
        with get_engine().begin() as conn:
            locked = dict(conn.execute(text("SELECT * FROM paper_accounts WHERE id=:id FOR UPDATE"), {"id": account["id"]}).mappings().one())
            config = load_config(locked["config_json"])
            cash = float(locked["cash"])
            open_rows = conn.execute(
                text("SELECT stock_code FROM paper_positions WHERE account_id=:id AND status='OPEN'"), {"id": account["id"]}
            ).all()
            open_stocks = {str(row[0]).zfill(6) for row in open_rows}
            open_count = len(open_rows)
            equity = _account_equity(conn, locked)
            for row in signal_rows:
                result, quote = row["result"], row["quote"]
                code = str(result.stock_code).zfill(6)
                if float(result.recommend_score) < config["min_score"]:
                    row["status"], row["reason"] = "SKIPPED", "低于最低评分"
                elif code in open_stocks or code in used_stocks:
                    row["status"], row["reason"] = "SKIPPED", "已有持仓或当日重复信号"
                elif bought >= config["max_daily_buys"]:
                    row["status"], row["reason"] = "SKIPPED", "达到每日买入上限"
                elif open_count + bought >= config["max_positions"]:
                    row["status"], row["reason"] = "SKIPPED", "达到最大持仓数"
                elif row["status"] == "CANDIDATE" and limit_locked(quote, "BUY"):
                    row["status"], row["reason"] = "SKIPPED", "涨停或报价不可成交"
                signal_id = conn.execute(
                    text("""
                        INSERT INTO paper_signals
                            (account_id,run_id,signal_date,signal_time,data_date,stock_code,stock_name,
                             industry,strategy_code,strategy_name,score,reason,quote_price,quote_time,
                             status,status_reason,config_version)
                        VALUES
                            (:account_id,:run_id,:signal_date,:signal_time,:data_date,:stock_code,:stock_name,
                             :industry,:strategy_code,:strategy_name,:score,:signal_reason,:quote_price,:quote_time,
                             :status,:status_reason,:config_version)
                        ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id), run_id=VALUES(run_id),
                            quote_price=VALUES(quote_price),quote_time=VALUES(quote_time),
                            status=VALUES(status),status_reason=VALUES(status_reason)
                    """),
                    {"account_id": account["id"], "run_id": run_id, "signal_date": today,
                     "signal_time": now_cn(), "data_date": data_date, "stock_code": code,
                     "stock_name": result.stock_name, "industry": result.industry,
                     "strategy_code": row["strategy_code"], "strategy_name": result.strategy_name,
                     "score": result.recommend_score, "signal_reason": result.reason,
                     "quote_price": row["quote_price"], "quote_time": row["quote_time"],
                     "status": row["status"], "status_reason": row["reason"],
                     "config_version": locked["config_version"]},
                ).lastrowid
                if row["status"] != "CANDIDATE":
                    continue
                jev_candidates.append((
                    int(signal_id),
                    build_signal_state(
                        stock_code=code,
                        stock_name=result.stock_name,
                        industry=result.industry,
                        strategy_code=row["strategy_code"],
                        strategy_name=result.strategy_name,
                        recommend_score=result.recommend_score,
                        reason=result.reason,
                        quote=quote,
                        account=locked,
                        config=config,
                        open_positions=open_count + bought,
                    ),
                ))
                quantity, fill_price, fee = calculate_buy_quantity(cash, equity, row["quote_price"], config)
                if quantity <= 0:
                    conn.execute(
                        text("UPDATE paper_signals SET status='SKIPPED',status_reason='可用资金不足一手' WHERE id=:id"),
                        {"id": signal_id},
                    )
                    continue
                amount = round(quantity * fill_price, 2)
                cash = round(cash - amount - fee, 2)
                position_id = conn.execute(
                    text("""
                        INSERT INTO paper_positions
                            (account_id,signal_id,stock_code,stock_name,strategy_code,strategy_name,
                             config_version,quantity,entry_time,entry_price,entry_fee,take_profit_price,
                             stop_loss_price,max_holding_days,commission_rate,min_commission,
                             sell_tax_rate,slippage_bps,current_price,current_quote_time)
                        VALUES
                            (:account_id,:signal_id,:stock_code,:stock_name,:strategy_code,:strategy_name,
                             :config_version,:quantity,:entry_time,:entry_price,:entry_fee,:take_profit,
                             :stop_loss,:max_days,:commission_rate,:min_commission,
                             :sell_tax_rate,:slippage_bps,:current_price,:quote_time)
                    """),
                    {"account_id": account["id"], "signal_id": signal_id, "stock_code": code,
                     "stock_name": result.stock_name, "strategy_code": row["strategy_code"],
                     "strategy_name": result.strategy_name, "config_version": locked["config_version"],
                     "quantity": quantity, "entry_time": now_cn(), "entry_price": fill_price,
                     "entry_fee": fee, "take_profit": round(fill_price * (1 + config["take_profit_pct"] / 100), 4),
                     "stop_loss": round(fill_price * (1 - config["stop_loss_pct"] / 100), 4),
                     "max_days": config["max_holding_days"], "commission_rate": config["commission_rate"],
                     "min_commission": config["min_commission"], "sell_tax_rate": config["sell_tax_rate"],
                     "slippage_bps": config["slippage_bps"], "current_price": row["quote_price"],
                     "quote_time": row["quote_time"]},
                ).lastrowid
                conn.execute(text("UPDATE paper_signals SET status='BOUGHT' WHERE id=:id"), {"id": signal_id})
                conn.execute(
                    text("""
                        INSERT INTO paper_cash_ledger
                            (account_id,position_id,event_time,event_type,amount,balance_after,description)
                        VALUES (:account_id,:position_id,:now,'BUY',:amount,:balance,:description)
                    """),
                    {"account_id": account["id"], "position_id": position_id, "now": now_cn(),
                     "amount": -(amount + fee), "balance": cash, "description": f"模拟买入，费用{fee:.2f}"},
                )
                used_stocks.add(code)
                bought += 1
            conn.execute(text("UPDATE paper_accounts SET cash=:cash WHERE id=:id"), {"cash": cash, "id": account["id"]})
        jev_summary = "Jev影子评估无可评估信号。"
        if jev_candidates:
            try:
                jev_records = [
                    (signal_id, state, evaluate_signal(state))
                    for signal_id, state in jev_candidates
                ]
                _save_jev_decisions(jev_records)
                successes = sum(decision["status"] == "SUCCESS" for _, _, decision in jev_records)
                jev_summary = f"Jev影子评估 {successes}/{len(jev_records)} 个成功。"
            except Exception as exc:
                jev_summary = f"Jev影子评估记录失败，交易结果不受影响：{str(exc)[:200]}"
        message = (
            f"{data_date} 数据产生 {len(signal_rows)} 个信号，模拟买入 {bought} 个。"
            f"{jev_summary}"
        )
        _finish_run(run_id, "SUCCESS", message)
        return message
    except Exception as exc:
        _finish_run(run_id, "FAILED", str(exc))
        raise


def settle_nav(account: dict | None = None) -> str:
    account = account or get_account()
    if not account:
        return "没有模拟账户。"
    today = now_cn().date()
    if not is_a_share_trading_day(today):
        return f"{today} A股休市，不生成日结记录。"
    positions = load_positions("OPEN")
    if not positions.empty:
        quotes = fetch_quotes(positions["stock_code"].astype(str).tolist())
        with get_engine().begin() as conn:
            for position in positions.to_dict("records"):
                quote = quotes.get(str(position["stock_code"]).zfill(6))
                if quote and _valid_today_quote(quote, today):
                    conn.execute(
                        text("UPDATE paper_positions SET current_price=:price,current_quote_time=:qt WHERE id=:id"),
                        {"id": position["id"], "price": quote["close_price"],
                         "qt": pd.to_datetime(quote["quote_time"]).to_pydatetime()},
                    )
    with get_engine().begin() as conn:
        account_row = dict(conn.execute(text("SELECT * FROM paper_accounts WHERE id=:id"), {"id": account["id"]}).mappings().one())
        aggregates = conn.execute(text("""
            SELECT
                COALESCE(SUM(CASE WHEN status='OPEN' THEN quantity*current_price ELSE 0 END),0) market_value,
                COALESCE(SUM(CASE WHEN status='OPEN' THEN quantity*(current_price-entry_price)-entry_fee ELSE 0 END),0) unrealized,
                COALESCE(SUM(CASE WHEN status='CLOSED' THEN realized_pnl ELSE 0 END),0) realized,
                COALESCE(SUM(entry_fee + COALESCE(exit_fee,0) + COALESCE(exit_tax,0)),0) fees,
                SUM(status='OPEN') position_count
            FROM paper_positions WHERE account_id=:id
        """), {"id": account["id"]}).mappings().one()
        cash = float(account_row["cash"])
        total_assets = round(cash + float(aggregates["market_value"]), 2)
        previous = conn.execute(
            text("SELECT total_assets FROM paper_nav_daily WHERE account_id=:id AND trade_date<:today ORDER BY trade_date DESC LIMIT 1"),
            {"id": account["id"], "today": today},
        ).scalar()
        base = float(previous) if previous is not None else float(account_row["initial_cash"])
        daily_pnl = round(total_assets - base, 2)
        daily_return = daily_pnl / base * 100 if base else 0
        cumulative = (total_assets / float(account_row["initial_cash"]) - 1) * 100
        peak = conn.execute(
            text("SELECT MAX(total_assets) FROM paper_nav_daily WHERE account_id=:id"), {"id": account["id"]}
        ).scalar()
        peak = max(float(peak or 0), total_assets, float(account_row["initial_cash"]))
        drawdown = (total_assets / peak - 1) * 100 if peak else 0
        conn.execute(text("""
            INSERT INTO paper_nav_daily
                (account_id,trade_date,cash,market_value,total_assets,realized_pnl,unrealized_pnl,
                 total_fees,daily_pnl,daily_return_pct,cumulative_return_pct,drawdown_pct,positions_count)
            VALUES
                (:account_id,:trade_date,:cash,:market_value,:total_assets,:realized,:unrealized,
                 :fees,:daily_pnl,:daily_return,:cumulative,:drawdown,:positions_count)
            ON DUPLICATE KEY UPDATE cash=VALUES(cash),market_value=VALUES(market_value),
                total_assets=VALUES(total_assets),realized_pnl=VALUES(realized_pnl),
                unrealized_pnl=VALUES(unrealized_pnl),total_fees=VALUES(total_fees),
                daily_pnl=VALUES(daily_pnl),daily_return_pct=VALUES(daily_return_pct),
                cumulative_return_pct=VALUES(cumulative_return_pct),drawdown_pct=VALUES(drawdown_pct),
                positions_count=VALUES(positions_count)
        """), {"account_id": account["id"], "trade_date": today, "cash": cash,
                 "market_value": aggregates["market_value"], "total_assets": total_assets,
                 "realized": aggregates["realized"], "unrealized": aggregates["unrealized"],
                 "fees": aggregates["fees"], "daily_pnl": daily_pnl, "daily_return": daily_return,
                 "cumulative": cumulative, "drawdown": drawdown,
                 "positions_count": int(aggregates["position_count"] or 0)})
    return f"已结算 {today}，总资产 {total_assets:,.2f}。"


def run_tick(force_signals: bool = False) -> str:
    now = now_cn()
    if not is_a_share_trading_day(now.date()):
        return f"{now.date()} A股休市，不运行。"
    in_market = time(9, 30) <= now.time() <= time(11, 30) or time(13, 0) <= now.time() <= time(15, 30)
    if not in_market and not force_signals:
        return "非交易时段。"
    messages = [monitor_positions()]
    if force_signals or (now.hour == 14 and now.minute == 10):
        messages.append(run_signals())
    return " ".join(messages)
