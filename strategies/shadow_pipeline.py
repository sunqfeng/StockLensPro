"""只读评估推荐，首次快照原子落盘；与原推荐表和交易隔离。"""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text

from recommendation_shadow import VERSION, evaluate_candidate

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs" / "recommendation_shadow"


def run_shadow(engine, trade_date, batch_no, output_dir=OUTPUT_DIR):
    day = date.fromisoformat(str(trade_date))
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if day > now.date():
        raise ValueError("不能评估未来推荐日期")
    target_dir = Path(output_dir)
    key = hashlib.sha256(str(batch_no).encode()).hexdigest()[:16]
    target = target_dir / f"{day}_{key}_{VERSION}.json"
    if target.exists():
        return target  # 不用后来修订的价格/模型覆盖首次证据。
    params = {"day": day, "batch": batch_no}
    market = pd.read_sql(text("""
        SELECT 100.0*SUM(CASE WHEN close_price>ma20 AND ma20>0 THEN 1 ELSE 0 END)
                   /NULLIF(SUM(CASE WHEN close_price>0 AND ma20>0 THEN 1 ELSE 0 END),0) breadth,
               SUM(CASE WHEN close_price>0 AND ma20>0 THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0) coverage
        FROM stock_daily WHERE trade_date=:day
    """), engine, params=params)
    rows = pd.read_sql(text("""
        WITH market_dates AS (
            SELECT DISTINCT trade_date FROM stock_daily
            WHERE trade_date<=:day AND trade_date>=DATE_SUB(:day,INTERVAL 400 DAY)
            ORDER BY trade_date DESC LIMIT 120
        ), highs AS (
            SELECT stock_code,MAX(high_price) high120,
                   COUNT(CASE WHEN high_price>0 THEN 1 END) high120_count,
                   CASE WHEN COUNT(is_adjusted)=COUNT(*) THEN COUNT(DISTINCT is_adjusted)
                        ELSE 0 END adjustment_kinds FROM stock_daily
            WHERE trade_date IN (SELECT trade_date FROM market_dates)
            AND stock_code IN (SELECT stock_code FROM stock_recommend_record
                               WHERE recommend_date=:day AND recommend_batch_no=:batch)
            GROUP BY stock_code
        )
        SELECT r.id,r.recommend_date,r.recommend_batch_no,r.strategy_name,r.stock_code,
               r.stock_name,r.industry,r.recommend_price,r.recommend_score,
               d.trade_date daily_date,d.close_price,d.ma20,d.data_quality,d.is_adjusted,
               s.trade_date tech_date,s.technical_score,s.score_model,s.score_version technical_version,
               h.high120,h.high120_count,h.adjustment_kinds
        FROM stock_recommend_record r
        LEFT JOIN stock_daily d ON d.stock_code=r.stock_code AND d.trade_date=r.recommend_date
        LEFT JOIN stock_recommend_tech_score s ON s.recommend_id=r.id
        LEFT JOIN highs h ON h.stock_code=r.stock_code
        WHERE r.recommend_date=:day AND r.recommend_batch_no=:batch
        ORDER BY r.id
    """), engine, params=params)
    if rows.empty:
        raise ValueError("该日期和批次没有推荐记录，不保存空快照")
    breadth = market.iloc[0]["breadth"]
    coverage = market.iloc[0]["coverage"]
    # pandas处理NaN、Decimal、日期序列化；strict JSON不保存NaN/Infinity。
    records = json.loads(rows.to_json(orient="records", date_format="iso", force_ascii=False))
    for row in records:
        decision, reason = evaluate_candidate(row, breadth, coverage)
        row.update(decision=decision, filter_reason=reason)
    code_hash = hashlib.sha256(Path(__file__).with_name("recommendation_shadow.py").read_bytes()
                               + Path(__file__).read_bytes()).hexdigest()
    payload = {"version": VERSION, "code_hash": code_hash,
               "mode": "前向影子" if day==now.date() and now.hour>=15 else "历史/盘中重放",
               "generated_at": now.isoformat(), "data_cutoff": str(day), "batch_no": batch_no,
               "market": json.loads(market.to_json(orient="records"))[0], "records": records}
    target_dir.mkdir(parents=True, exist_ok=True)
    # link只允许首次发布；并发运行不能覆盖已存在快照。
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target_dir, delete=False) as staged:
        staged_path = Path(staged.name)
        try:
            json.dump(payload, staged, ensure_ascii=False, indent=2, allow_nan=False)
            staged.flush()
            os.fsync(staged.fileno())
        except Exception:
            staged_path.unlink(missing_ok=True)
            raise
    try:
        os.link(staged_path, target)
    except FileExistsError:
        pass
    finally:
        staged_path.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description="影子候选筛选；不写推荐表，不执行交易")
    parser.add_argument("--date", required=True)
    parser.add_argument("--batch")
    args = parser.parse_args()
    from config import MYSQL_CONFIG, STRATEGY_CONFIG
    from mysql_data_engine import MySqlDataEngine
    engine = MySqlDataEngine(MYSQL_CONFIG, STRATEGY_CONFIG)
    print(run_shadow(engine.engine,args.date,args.batch or args.date.replace("-","")+"_001"))


if __name__ == "__main__":
    main()
