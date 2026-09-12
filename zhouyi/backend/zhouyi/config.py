"""Application configuration; never load another project's business settings."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import re

from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url

PROJECT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: URL = field(repr=False)
    api_key: str = field(default='', repr=False)
    model: str = 'deepseek-flash'
    api_url: str = 'https://api.deepseek.com/v1/chat/completions'
    host: str = '127.0.0.1'
    port: int = 8796
    lease_seconds: int = 600

    @classmethod
    def load(cls, env_file: Path | None = None, environ=None):
        env_file = env_file or PROJECT / '.env'
        local = {k: v for k, v in dotenv_values(env_file).items() if v is not None}
        env = dict(os.environ if environ is None else environ)
        shared_path = env.get('ZHOUYI_SHARED_ENV', local.get('ZHOUYI_SHARED_ENV', ''))
        shared = {}
        if shared_path:
            path = Path(shared_path).expanduser()
            if not path.is_absolute():
                path = env_file.parent / path
            shared = {k: v for k, v in dotenv_values(path).items()
                      if k in ('MYSQL_URL', 'DEEPSEEK_API_KEY', 'DEEPSEEK_MODEL') and v is not None}
        values = shared | local | env
        database = values.get('ZHOUYI_DATABASE', 'zhouyi')
        if not re.fullmatch(r'zhouyi(?:_[a-z0-9_]+)?', database):
            raise ValueError('业务库名必须为 zhouyi 或以 zhouyi_ 开头')
        try:
            url = make_url(values.get('MYSQL_URL', 'mysql+pymysql://localhost/zhouyi'))
            if not url.drivername.startswith('mysql'):
                raise ValueError('需要 MySQL 连接')
            url = url.set(drivername='mysql+pymysql', database=database,
                          host=values.get('ZHOUYI_MYSQL_HOST') or url.host,
                          port=int(values.get('ZHOUYI_MYSQL_PORT') or url.port or 3306))
        except Exception:
            raise ValueError('MySQL 配置无效，请检查本机配置文件') from None
        return cls(database_url=url, api_key=values.get('DEEPSEEK_API_KEY', ''),
                   model=values.get('DEEPSEEK_MODEL') or 'deepseek-flash',
                   host=values.get('ZHOUYI_HOST', '127.0.0.1'),
                   port=int(values.get('ZHOUYI_PORT', 8796)))
