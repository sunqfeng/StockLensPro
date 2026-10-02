#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stocklens.db import get_engine


MIGRATIONS = {
    "up": PROJECT_ROOT / "migrations" / "001_create_hot_stock_tables.sql",
    "down": PROJECT_ROOT / "migrations" / "001_drop_hot_stock_tables.sql",
}


def main():
    parser = argparse.ArgumentParser(description="执行热点股票数据库迁移")
    parser.add_argument("direction", choices=MIGRATIONS, nargs="?", default="up")
    args = parser.parse_args()

    sql_text = MIGRATIONS[args.direction].read_text(encoding="utf-8")
    statements = [statement.strip() for statement in sql_text.split(";") if statement.strip()]

    engine = get_engine()
    with engine.connect() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
        connection.commit()

    print(f"热点股票数据库迁移完成：{args.direction}，共{len(statements)}条语句")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
