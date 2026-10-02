# -*- coding: utf-8 -*-
"""
recommend_record_repository.py

作用：
    把策略选出来的股票登记到你的 stock_recommend_record 表。

你的表结构：
    recommend_batch_no
    recommend_date
    stock_code
    stock_name
    industry
    recommend_price
    recommend_score
    strategy_name
    reason
    status
"""

from __future__ import annotations

from typing import Iterable

from strategies.base import RecommendResult


class RecommendRecordRepository:
    """
    推荐记录表操作类。

    去重逻辑：
        因为你当前表里没有唯一索引，所以这里先用代码判断是否存在。

        判断维度：
            recommend_date + stock_code + strategy_name

        如果存在：更新。
        如果不存在：插入。
    """

    def __init__(self, engine) -> None:
        self.engine = engine

    def save_results(self, results: Iterable[RecommendResult]) -> int:
        """
        保存多个推荐结果。

        返回：
            实际处理的记录数量。更新和新增都算处理。
        """

        count = 0
        with self.engine.get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    for result in results:
                        self._save_one(cursor, result)
                        count += 1
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return count

    def _save_one(self, cursor, result: RecommendResult) -> None:
        """
        保存单条推荐结果。
        """

        exists_sql = """
            SELECT id
            FROM stock_recommend_record
            WHERE recommend_date = %s
              AND stock_code = %s
              AND strategy_name = %s
            LIMIT 1
        """

        cursor.execute(
            exists_sql,
            (
                result.recommend_date,
                result.stock_code,
                result.strategy_name,
            ),
        )
        exists = cursor.fetchone()

        if exists:
            update_sql = """
                UPDATE stock_recommend_record
                SET
                    recommend_batch_no = %s,
                    stock_name = %s,
                    industry = %s,
                    recommend_price = %s,
                    recommend_score = %s,
                    reason = %s,
                    status = 'TRACKING',
                    update_time = NOW()
                WHERE id = %s
            """
            cursor.execute(
                update_sql,
                (
                    result.recommend_batch_no,
                    result.stock_name,
                    result.industry,
                    result.recommend_price,
                    result.recommend_score,
                    result.reason,
                    exists["id"],
                ),
            )
        else:
            insert_sql = """
                INSERT INTO stock_recommend_record (
                    recommend_batch_no,
                    recommend_date,
                    stock_code,
                    stock_name,
                    industry,
                    recommend_price,
                    recommend_score,
                    strategy_name,
                    reason,
                    status,
                    create_time,
                    update_time
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    'TRACKING',
                    NOW(), NOW()
                )
            """
            cursor.execute(
                insert_sql,
                (
                    result.recommend_batch_no,
                    result.recommend_date,
                    result.stock_code,
                    result.stock_name,
                    result.industry,
                    result.recommend_price,
                    result.recommend_score,
                    result.strategy_name,
                    result.reason,
                ),
            )
