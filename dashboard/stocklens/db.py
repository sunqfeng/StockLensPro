from urllib.parse import quote_plus

from sqlalchemy import create_engine

from stocklens.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


def get_engine():
    """创建 MySQL 数据库连接。"""
    password = quote_plus(DB_PASSWORD)
    db_url = (
        f"mysql+pymysql://{DB_USER}:{password}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )

    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
