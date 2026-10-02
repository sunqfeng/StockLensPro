# -*- coding: utf-8 -*-
"""
mysql_data_engine.py

作用：
    1. 使用 SQLAlchemy 连接 MySQL，给 pandas.read_sql 使用，避免 pandas 的 UserWarning。
    2. 使用 pymysql 保留原生连接能力，给插入/更新推荐记录使用。
    3. 统一读取 stock_daily、stock_basic_info、stock_full_info。

你的核心行情表默认使用：
    stock_daily

需要字段：
    stock_code
    trade_date
    open_price
    high_price
    low_price
    close_price
    volume
    turnover
    change_percent
"""

from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import quote_plus

import pandas as pd
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class MySqlDataEngine:
    """
    MySQL 数据引擎。

    这个类只负责“取数”，不负责具体选股。
    每个策略都通过它获取股票列表、K线、股票名称、行业等信息。
    """

    def __init__(self, mysql_config, strategy_config=None) -> None:
        """
        初始化数据引擎。

        参数：
            mysql_config:
                config.py 中的 MYSQL_CONFIG。

            strategy_config:
                config.py 中的 STRATEGY_CONFIG。
                当前数据引擎只是保存起来，方便后续扩展。
        """

        self.config = mysql_config
        self.strategy_config = strategy_config
        self.charset = getattr(mysql_config, "charset", "utf8mb4")

        # 使用 SQLAlchemy Engine 给 pandas.read_sql 使用。
        # 注意 password 需要 URL 编码，防止密码里有 @、#、%、! 等特殊字符导致连接串解析失败。
        self.engine: Engine = create_engine(
            self._build_sqlalchemy_url(),
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True,
        )

    def _build_sqlalchemy_url(self) -> str:
        """
        构造 SQLAlchemy MySQL 连接字符串。

        返回示例：
            mysql+pymysql://<user>:<password>@<host>:<port>/<database>?charset=utf8mb4
        """

        user = quote_plus(str(self.config.user))
        password = quote_plus(str(self.config.password))
        host = str(self.config.host)
        port = int(self.config.port)
        database = str(self.config.database)

        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{host}:{port}/{database}?charset={self.charset}"
        )

    def get_connection(self):
        """
        获取 pymysql 原生连接。

        说明：
            推荐记录表的插入、更新使用这个连接，事务控制更直观。
        """

        return pymysql.connect(
            host=self.config.host,
            port=int(self.config.port),
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset=self.charset,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )

    def read_sql(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """
        统一 SQL 查询入口。

        注意：
            SQL 参数使用 SQLAlchemy 风格，例如：
                WHERE stock_code = :stock_code
        """

        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def get_latest_trade_date(self) -> Optional[str]:
        """
        获取 stock_daily 表中的最新交易日。
        """

        sql = """
            SELECT MAX(trade_date) AS latest_trade_date
            FROM stock_daily
        """
        df = self.read_sql(sql)

        if df.empty:
            return None

        value = df.loc[0, "latest_trade_date"]
        if pd.isna(value):
            return None

        # 如果数据库返回的是 date/datetime 类型，str 后可能是 2026-05-15。
        return str(value)[:10]

    def get_all_stock_codes(self, trade_date: Optional[str] = None) -> List[str]:
        """
        获取股票代码列表。

        参数：
            trade_date:
                如果传入，则只取该交易日有行情的股票，减少无效扫描。
                如果为空，则取 stock_daily 中所有出现过的股票。
        """

        if trade_date:
            sql = """
                SELECT DISTINCT stock_code
                FROM stock_daily
                WHERE stock_code IS NOT NULL
                  AND stock_code <> ''
                  AND trade_date = :trade_date
                ORDER BY stock_code
            """
            df = self.read_sql(sql, {"trade_date": trade_date})
        else:
            sql = """
                SELECT DISTINCT stock_code
                FROM stock_daily
                WHERE stock_code IS NOT NULL
                  AND stock_code <> ''
                ORDER BY stock_code
            """
            df = self.read_sql(sql)

        if df.empty:
            return []

        return df["stock_code"].astype(str).str.zfill(6).tolist()

    def get_local_symbols(self, trade_date: Optional[str] = None) -> List[str]:
        """
        兼容原 Sequoia-X 策略的方法名。

        有些策略调用：
            self.engine.get_local_symbols()

        有些策略调用：
            self.engine.get_local_symbols(trade_date)

        所以这里允许传 trade_date。
        """

        return self.get_all_stock_codes(trade_date)

    def get_ohlcv(
        self,
        stock_code: str,
        end_date: Optional[str] = None,
        limit: int = 260,
    ) -> pd.DataFrame:
        """
        读取某只股票最近 N 根日 K 数据。

        返回字段统一为：
            stock_code
            date
            open
            high
            low
            close
            volume
            turnover
            change_percent
        """

        if not end_date:
            end_date = self.get_latest_trade_date()

        if not end_date:
            return pd.DataFrame()

        sql = """
            SELECT *
            FROM (
                SELECT
                    stock_code,
                    trade_date AS date,
                    open_price AS open,
                    high_price AS high,
                    low_price AS low,
                    close_price AS close,
                    volume,
                    turnover,
                    change_percent
                FROM stock_daily
                WHERE stock_code = :stock_code
                  AND trade_date <= :end_date
                ORDER BY trade_date DESC
                LIMIT :limit
            ) t
            ORDER BY t.date ASC
        """

        df = self.read_sql(
            sql,
            {
                "stock_code": str(stock_code).zfill(6),
                "end_date": end_date,
                "limit": int(limit),
            },
        )

        return self._clean_ohlcv_df(df)

    def get_all_daily_for_rps(
        self,
        end_date: Optional[str] = None,
        limit_days: int = 260,
    ) -> pd.DataFrame:
        """
        获取全市场最近 N 个交易日数据，用于 RPS 横向排名。

        返回字段：
            symbol
            date
            close
            high
        """

        if not end_date:
            end_date = self.get_latest_trade_date()

        if not end_date:
            return pd.DataFrame()

        sql = """
            SELECT
                stock_code AS symbol,
                trade_date AS date,
                close_price AS close,
                high_price AS high
            FROM stock_daily
            WHERE trade_date IN (
                SELECT trade_date
                FROM (
                    SELECT DISTINCT trade_date
                    FROM stock_daily
                    WHERE trade_date <= :end_date
                    ORDER BY trade_date DESC
                    LIMIT :limit_days
                ) d
            )
            ORDER BY stock_code, trade_date
        """

        df = self.read_sql(
            sql,
            {
                "end_date": end_date,
                "limit_days": int(limit_days),
            },
        )

        if df.empty:
            return df

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["symbol"] = df["symbol"].astype(str).str.zfill(6)

        for col in ["close", "high"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["close", "high"])
        return df.sort_values(["symbol", "date"]).reset_index(drop=True)

    def get_stock_info(self, stock_code: str) -> Dict[str, Optional[str]]:
        """
        查询股票名称、行业。

        优先查 stock_basic_info：
            stock_name
            sub_industry

        如果失败，再查 stock_full_info。
        """

        stock_code = str(stock_code).zfill(6)

        # 优先查 stock_basic_info。
        sql_basic = """
            SELECT
                stock_code,
                stock_name,
                sub_industry AS industry
            FROM stock_basic_info
            WHERE stock_code = :stock_code
            LIMIT 1
        """

        try:
            df = self.read_sql(sql_basic, {"stock_code": stock_code})
            if not df.empty:
                row = df.iloc[0]
                return {
                    "stock_code": stock_code,
                    "stock_name": self._safe_str(row.get("stock_name")),
                    "industry": self._safe_str(row.get("industry")),
                }
        except Exception:
            # 表不存在、字段不一致时，不让程序中断，继续尝试 stock_full_info。
            pass

        # 再查 stock_full_info。
        sql_full = """
            SELECT
                stock_code,
                stock_name,
                sub_industry AS industry
            FROM stock_full_info
            WHERE stock_code = :stock_code
            LIMIT 1
        """

        try:
            df = self.read_sql(sql_full, {"stock_code": stock_code})
            if not df.empty:
                row = df.iloc[0]
                return {
                    "stock_code": stock_code,
                    "stock_name": self._safe_str(row.get("stock_name")),
                    "industry": self._safe_str(row.get("industry")),
                }
        except Exception:
            pass

        return {
            "stock_code": stock_code,
            "stock_name": None,
            "industry": None,
        }

    def get_latest_close_price(
        self,
        stock_code: str,
        trade_date: Optional[str] = None,
    ) -> Optional[float]:
        """
        查询某只股票在指定日期之前最近一个交易日的收盘价。
        """

        stock_code = str(stock_code).zfill(6)

        if not trade_date:
            trade_date = self.get_latest_trade_date()

        if not trade_date:
            return None

        sql = """
            SELECT close_price
            FROM stock_daily
            WHERE stock_code = :stock_code
              AND trade_date <= :trade_date
            ORDER BY trade_date DESC
            LIMIT 1
        """

        df = self.read_sql(
            sql,
            {
                "stock_code": stock_code,
                "trade_date": trade_date,
            },
        )

        if df.empty:
            return None

        value = df.loc[0, "close_price"]
        if pd.isna(value):
            return None

        return float(value)

    def _clean_ohlcv_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗 K 线数据。
        """

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

        if "stock_code" in df.columns:
            df["stock_code"] = df["stock_code"].astype(str).str.zfill(6)

        numeric_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover",
            "change_percent",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        required_cols = ["date", "open", "high", "low", "close", "volume", "turnover"]
        df = df.dropna(subset=[col for col in required_cols if col in df.columns])
        df = df.sort_values("date").reset_index(drop=True)
        return df

    @staticmethod
    def _safe_str(value) -> Optional[str]:
        """
        安全转字符串。
        """

        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass

        value = str(value).strip()
        return value if value else None
