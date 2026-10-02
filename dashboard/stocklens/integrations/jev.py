from __future__ import annotations

import os
from time import perf_counter
from typing import Any

from stocklens.config import PROJECT_DIR, SECRETS_FILE
from stocklens.runtime_config import load_config


QUESTION_VERSION = "stock-signal-v1"

QUESTIONS = {
    "signal_quality": {
        "type": "noul",
        "instructions": (
            "Based only on the supplied evidence, is this stock signal sufficiently "
            "supported for a paper-trading candidate?"
        ),
    },
    "risk_conflict": {
        "type": "noul",
        "instructions": (
            "Does the supplied evidence contain material risk that conflicts with "
            "opening a new paper-trading position?"
        ),
    },
    "setup_quality": {
        "type": "score",
        "instructions": "How strong and internally consistent is the current trading setup?",
        "criteria": [
            "Poor: evidence is weak or contradictory",
            "Fair: some support exists but important uncertainty remains",
            "Good: multiple supplied signals support the setup",
            "Excellent: supplied evidence is strong and consistent with limited visible risk",
        ],
    },
}


def build_signal_state(
    *,
    stock_code: str,
    stock_name: str | None,
    industry: str | None,
    strategy_code: str,
    strategy_name: str,
    recommend_score: float,
    reason: str | None,
    quote: dict,
    account: dict,
    config: dict,
    open_positions: int,
) -> dict:
    current = float(quote.get("close_price") or 0)
    previous = float(quote.get("prev_close") or 0)
    change_pct = round((current / previous - 1) * 100, 4) if current > 0 and previous > 0 else None
    return {
        "stock": {
            "code": str(stock_code).zfill(6),
            "name": stock_name or "",
            "industry": industry or "",
        },
        "strategy": {
            "code": strategy_code,
            "name": strategy_name,
            "recommend_score": float(recommend_score),
            "reason": (reason or "")[:2000],
        },
        "market": {
            "latest_price": current,
            "previous_close": previous or None,
            "daily_change_pct": change_pct,
            "quote_time": str(quote.get("quote_time") or ""),
        },
        "account": {
            "available_cash": float(account.get("cash") or 0),
            "open_positions": int(open_positions),
            "max_positions": int(config["max_positions"]),
            "max_daily_buys": int(config["max_daily_buys"]),
            "position_pct": float(config["position_pct"]),
        },
        "scope": "Forward paper trading only. Judge only the supplied state; do not assume live market facts.",
    }


def _empty_result(status: str, latency_ms: int, error_message: str | None = None) -> dict:
    return {
        "status": status,
        "mode": "SHADOW",
        "question_version": QUESTION_VERSION,
        "model_requested": os.getenv("TYPESAFE_DEFAULT_MODEL", "jev-latest"),
        "model_resolved": None,
        "quality_probability": None,
        "risk_probability": None,
        "setup_score": None,
        "setup_confidence": None,
        "response_json": None,
        "latency_ms": latency_ms,
        "error_message": error_message,
    }


def _evaluate_with_client(state: dict, client: Any, started: float) -> dict:
    response = client.system_one(state, QUESTIONS)
    raw_response = response.raw_http_response.json()
    return {
        "status": "SUCCESS",
        "mode": "SHADOW",
        "question_version": QUESTION_VERSION,
        "model_requested": os.getenv("TYPESAFE_DEFAULT_MODEL", "jev-latest"),
        "model_resolved": response.model,
        "quality_probability": float(response.nouls["signal_quality"].noul),
        "risk_probability": float(response.nouls["risk_conflict"].noul),
        "setup_score": float(response.scores["setup_quality"].score),
        "setup_confidence": float(response.scores["setup_quality"].confidence),
        "response_json": raw_response,
        "latency_ms": round((perf_counter() - started) * 1000),
        "error_message": None,
    }


def evaluate_signal(state: dict, client: Any | None = None) -> dict:
    """Evaluate one candidate without allowing Jev failure to affect paper trading."""
    started = perf_counter()
    try:
        if client is not None:
            return _evaluate_with_client(state, client, started)

        load_config(PROJECT_DIR)
        if not os.getenv("TYPESAFE_API_KEY"):
            return _empty_result("DISABLED", 0, "TYPESAFE_API_KEY is not configured")

        from typesafe_sdk import RetryPolicy, TypeSafeClient

        retry = RetryPolicy(max_retries=1, backoff_max=0.2, timeout=3.0)
        with TypeSafeClient(retry=retry) as owned_client:
            return _evaluate_with_client(state, owned_client, started)
    except Exception as exc:
        latency_ms = round((perf_counter() - started) * 1000)
        return _empty_result("ERROR", latency_ms, str(exc)[:2000])
