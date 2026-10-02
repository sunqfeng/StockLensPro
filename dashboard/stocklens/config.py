"""数据库配置从环境变量或本地、未提交的 secrets.env 读取。"""
import os
from pathlib import Path

from stocklens.runtime_config import database_port, load_config, validate_database

PROJECT_DIR = Path(__file__).resolve().parents[1]
SECRETS_FILE = load_config(PROJECT_DIR)

DB_HOST = os.getenv('DB_HOST', '')
DB_PORT = database_port(os.getenv('DB_PORT'))
DB_USER = os.getenv('DB_USER', '')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', '')
DB_CHARSET = os.getenv('DB_CHARSET') or 'utf8mb4'


def require_database_config():
    validate_database(DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)


def configured_path(name, default):
    """部署路径从配置读取，默认值由项目位置推导。"""
    # 不 resolve 软链接：venv/bin/python 必须保留虚拟环境入口。
    return Path(os.getenv(name) or default).expanduser().absolute()
