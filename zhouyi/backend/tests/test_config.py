from pathlib import Path
import pytest

from zhouyi.config import Settings


def test_local_config_overrides_shared_without_importing_business_fields(tmp_path):
    shared = tmp_path / 'shared.env'
    shared.write_text('MYSQL_URL=mysql+pymysql://app:secret@oldhost:8886/stock_data\nDEEPSEEK_API_KEY=test-key\nLLM_BACKEND=cursor\n')
    local = tmp_path / '.env'
    local.write_text(f'ZHOUYI_SHARED_ENV={shared}\nZHOUYI_MYSQL_HOST=192.168.1.13\nZHOUYI_MYSQL_PORT=3306\nDEEPSEEK_MODEL=deepseek-flash\n')
    settings = Settings.load(local, environ={})
    assert settings.database_url.host == '192.168.1.13'
    assert settings.database_url.port == 3306
    assert settings.database_url.database == 'zhouyi'
    assert settings.api_key == 'test-key'
    assert settings.model == 'deepseek-flash'
    assert 'secret' not in repr(settings)
    assert 'test-key' not in repr(settings)


def test_environment_takes_precedence(tmp_path):
    local = tmp_path / '.env'
    local.write_text('DEEPSEEK_MODEL=old\nMYSQL_URL=mysql+pymysql://app:pw@host/stock_data\n')
    settings = Settings.load(local, environ={'DEEPSEEK_MODEL': 'chosen'})
    assert settings.model == 'chosen'
    assert settings.database_url.database == 'zhouyi'


def test_refuses_existing_stock_database(tmp_path):
    local = tmp_path / '.env'
    local.write_text('MYSQL_URL=mysql+pymysql://app:pw@host/stock_data\nZHOUYI_DATABASE=stock_data\n')
    with pytest.raises(ValueError):
        Settings.load(local, environ={})
