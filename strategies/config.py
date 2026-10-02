# -*- coding: utf-8 -*-
"""
config.py

作用：
    统一存放 MySQL 连接配置、策略参数配置。

数据库连接信息通过环境变量或本地 config/secrets.env 提供，不写入源码。
"""

from dataclasses import dataclass, field
import os
from pathlib import Path

from runtime_config import database_port, load_config, validate_database

PROJECT_DIR = Path(__file__).resolve().parent
SECRETS_FILE = load_config(PROJECT_DIR)


@dataclass(repr=False)
class MySqlConfig:
    """
    MySQL 数据库配置。

    说明：
        host     : MySQL 服务器 IP
        port     : MySQL 端口
        user     : 用户名
        password : 密码
        database : 数据库名
        charset  : 字符集，建议 utf8mb4，防止中文乱码
    """

    host: str = os.getenv('DB_HOST', '')
    port: int = database_port(os.getenv('DB_PORT'))
    user: str = os.getenv('DB_USER', '')
    password: str = field(default=os.getenv('DB_PASSWORD', ''), repr=False)
    database: str = os.getenv('DB_NAME', '')
    charset: str = os.getenv('DB_CHARSET') or 'utf8mb4'

    def validate(self):
        validate_database(self.host, self.port, self.user, self.password, self.database)


def configured_path(name, default):
    # 保留虚拟环境解释器软链接，不转成系统 Python。
    return Path(os.getenv(name) or default).expanduser().absolute()


@dataclass
class StrategyConfig:
    """
    策略参数配置。

    说明：
        这些参数先集中放这里，后面你想调优，不需要到每个策略文件里到处找。
    """

    # 每只股票最多读取最近多少根日 K。
    # 260 大约是一年的交易日数量，足够大多数策略使用。
    kline_limit: int = 260

    # 海龟突破策略：成交额门槛，默认 1 亿。
    turtle_turnover_min: float = 100_000_000

    # RPS 策略：计算周期，默认 120 个交易日。
    rps_period: int = 120

    # RPS 策略：强度排名门槛，默认前 10%，即 RPS >= 90。
    rps_threshold: float = 90.0

    # 定增公告策略：回看最近多少天。
    private_placement_lookback_days: int = 7

    # 默认推荐分数。
    # 后续你可以根据策略强弱、行业分数、涨幅位置等动态计算。
    default_recommend_score: float = 80.0


# =====================================================================
# 数据库连接信息从本地配置读取；这里只创建配置对象。
# =====================================================================
MYSQL_CONFIG = MySqlConfig()


# 策略配置，一般先不用改。
STRATEGY_CONFIG = StrategyConfig()
