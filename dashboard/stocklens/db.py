from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from stocklens.config import DB_CHARSET, DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER, require_database_config


def get_engine():
    """创建 MySQL 数据库连接。"""
    require_database_config()
    db_url = URL.create('mysql+pymysql', username=DB_USER, password=DB_PASSWORD,
                        host=DB_HOST, port=DB_PORT, database=DB_NAME,
                        query={'charset': DB_CHARSET})

    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
