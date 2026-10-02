# -*- coding: utf-8 -*-
"""
strategies/base.py

作用：
    定义策略基类和推荐结果对象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class RecommendResult:
    """
    推荐结果对象。

    这个对象的字段基本一一对应你的 stock_recommend_record 表。
    """

    recommend_batch_no: str
    recommend_date: str
    stock_code: str
    stock_name: Optional[str]
    industry: Optional[str]
    recommend_price: Optional[float]
    recommend_score: float
    strategy_name: str
    reason: str


class BaseStrategy(ABC):
    """
    策略基类。

    每个具体策略都继承它，并实现 run() 方法。
    """

    # 策略编码，命令行筛选策略时使用。
    strategy_code: str = "BASE"

    # 策略名称，登记到 stock_recommend_record.strategy_name。
    strategy_name: str = "基础策略"

    def __init__(self, engine, strategy_config, trade_date: str, batch_no: str) -> None:
        self.engine = engine
        self.strategy_config = strategy_config
        self.trade_date = trade_date
        self.batch_no = batch_no

    @abstractmethod
    def run(self) -> list[RecommendResult]:
        """
        执行策略。
        """
        raise NotImplementedError

    def build_result(
        self,
        stock_code: str,
        reason: str,
        recommend_score: Optional[float] = None,
    ) -> RecommendResult:
        """
        构造推荐结果。

        这里统一补充股票名称、行业、推荐价格。
        这样每个策略只需要关心“为什么选中”。
        """

        stock_code = str(stock_code).zfill(6)
        info = self.engine.get_stock_info(stock_code)
        price = self.engine.get_latest_close_price(stock_code, self.trade_date)

        if recommend_score is None:
            recommend_score = float(getattr(self.strategy_config, "default_recommend_score", 80.0))

        return RecommendResult(
            recommend_batch_no=self.batch_no,
            recommend_date=self.trade_date,
            stock_code=stock_code,
            stock_name=info.get("stock_name"),
            industry=info.get("industry"),
            recommend_price=price,
            recommend_score=float(recommend_score),
            strategy_name=self.strategy_name,
            reason=reason,
        )
