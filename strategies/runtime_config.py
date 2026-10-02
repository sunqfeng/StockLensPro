"""本地配置文件加载与数据库配置校验，不包含任何部署凭证。"""
import os
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """只报告配置项名称，不回显密码、地址或文件路径。"""


def load_config(project_dir):
    """环境变量优先；显式指定文件时不再回退到默认文件。"""
    explicit = os.environ.get('STOCKLENS_CONFIG_FILE')
    path = (Path(explicit).expanduser() if explicit else Path(project_dir) / 'config' / 'secrets.env').resolve()
    if explicit and not path.is_file():
        raise ConfigurationError('STOCKLENS_CONFIG_FILE 指定的配置文件不存在或不可读取。')
    try:
        # 密码中的 ${...} 是字面值，不能被 dotenv 的变量展开改变。
        load_dotenv(path, override=False, interpolate=False)
    except OSError:
        raise ConfigurationError('本地配置文件不可读取，请检查 STOCKLENS_CONFIG_FILE 和文件权限。') from None
    return path


def database_port(value=None):
    try:
        port = int('3306' if value is None else value)
        if not 1 <= port <= 65535:
            raise ValueError
        return port
    except (ValueError, TypeError):
        raise ConfigurationError('DB_PORT 必须是 1 到 65535 的整数。') from None


def validate_database(host, port, user, password, database):
    values = dict(DB_HOST=host, DB_USER=user, DB_PASSWORD=password, DB_NAME=database)
    missing = [key for key, value in values.items() if not str(value or '').strip()]
    if missing:
        raise ConfigurationError('缺少数据库配置：' + ', '.join(missing) + '；请填写本地 secrets.env 或环境变量。')
    database_port(port)
