import hashlib
import json
from datetime import datetime

from sqlalchemy import text


def normalize_capture_slot(moment):
    """将实际采集时间归一到分钟，作为幂等键的一部分。"""
    return moment.replace(second=0, microsecond=0)


def validate_record_count(records, *, requested_limit):
    """拒绝残缺的响应，避免错误触发股票离榜。"""
    if not 1 <= requested_limit <= 100:
        raise ValueError("requested_limit必须在1到100之间")
    if len(records) < requested_limit:
        raise ValueError(
            f"热点股票数量不足：期望{requested_limit}只，实际{len(records)}只"
        )
    if len(records) > requested_limit:
        raise ValueError(
            f"热点股票数量超出：期望{requested_limit}只，实际{len(records)}只"
        )


def build_snapshot_rows(batch_id, records):
    return [
        {
            "batch_id": batch_id,
            "rank_no": record.rank_no,
            "external_symbol": record.external_symbol,
            "normalized_code": record.normalized_code,
            "stock_name": record.stock_name,
            "market": record.market,
            "heat_score": record.heat_score,
            "quote_change_pct": record.quote_change_pct,
            "topic": record.topic,
            "raw_payload": json.dumps(
                record.raw_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
        for record in records
    ]


def snapshot_content_hash(records):
    payload = [
        {
            "rank": record.rank_no,
            "symbol": record.external_symbol,
            "heat": format(record.heat_score, "f"),
            "percent": (
                None
                if record.quote_change_pct is None
                else format(record.quote_change_pct, "f")
            ),
            "topic": record.topic,
        }
        for record in records
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def save_snapshot_batch(
    engine,
    records,
    *,
    captured_at,
    requested_limit=100,
    duration_ms=None,
    source="XUEQIU",
    ranking_type="HOT_STOCK",
    source_scope="GLOBAL",
    window_minutes=60,
    primary_cutoff=50,
):
    """在一个事务中幂等保存采集批次和股票快照。"""
    validate_record_count(records, requested_limit=requested_limit)
    capture_slot = normalize_capture_slot(captured_at)
    content_hash = snapshot_content_hash(records)

    batch_params = {
        "source": source,
        "ranking_type": ranking_type,
        "source_scope": source_scope,
        "window_minutes": window_minutes,
        "capture_slot": capture_slot,
        "captured_at": captured_at,
        "primary_cutoff": primary_cutoff,
        "observation_cutoff": requested_limit,
        "duration_ms": duration_ms,
    }

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO stock_hot_batch (
                    source, ranking_type, source_scope, window_minutes,
                    capture_slot, captured_at, primary_cutoff,
                    observation_cutoff, status, duration_ms
                ) VALUES (
                    :source, :ranking_type, :source_scope, :window_minutes,
                    :capture_slot, :captured_at, :primary_cutoff,
                    :observation_cutoff, 'RUNNING', :duration_ms
                )
                ON DUPLICATE KEY UPDATE
                    captured_at = VALUES(captured_at),
                    primary_cutoff = VALUES(primary_cutoff),
                    observation_cutoff = VALUES(observation_cutoff),
                    status = 'RUNNING',
                    duration_ms = VALUES(duration_ms),
                    item_count = 0,
                    content_hash = NULL,
                    error_code = NULL,
                    error_message = NULL
                """
            ),
            batch_params,
        )
        batch_id = connection.execute(
            text(
                """
                SELECT id
                FROM stock_hot_batch
                WHERE source = :source
                  AND ranking_type = :ranking_type
                  AND source_scope = :source_scope
                  AND window_minutes = :window_minutes
                  AND capture_slot = :capture_slot
                """
            ),
            batch_params,
        ).scalar_one()

        connection.execute(
            text("DELETE FROM stock_hot_snapshot WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        )
        connection.execute(
            text(
                """
                INSERT INTO stock_hot_snapshot (
                    batch_id, rank_no, external_symbol, normalized_code,
                    stock_name, market, heat_score, quote_change_pct,
                    topic, raw_payload
                ) VALUES (
                    :batch_id, :rank_no, :external_symbol, :normalized_code,
                    :stock_name, :market, :heat_score, :quote_change_pct,
                    :topic, :raw_payload
                )
                """
            ),
            build_snapshot_rows(batch_id, records),
        )
        connection.execute(
            text(
                """
                UPDATE stock_hot_batch
                SET status = 'SUCCESS',
                    item_count = :item_count,
                    content_hash = :content_hash,
                    error_code = NULL,
                    error_message = NULL
                WHERE id = :batch_id
                """
            ),
            {
                "batch_id": batch_id,
                "item_count": len(records),
                "content_hash": content_hash,
            },
        )
    return batch_id
