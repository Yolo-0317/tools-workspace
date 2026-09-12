"""Explicit schema initialization and corpus sync for the dedicated database."""
import argparse
from sqlalchemy import inspect, text
from .api import build_engine
from .config import Settings
from .corpus import list_hexagrams, get_hexagram
from .models import Base
from .repository import Repository


def main():
    parser = argparse.ArgumentParser(description='初始化周易数据库表与典籍')
    parser.add_argument('command', choices=['init'])
    parser.parse_args()
    settings = Settings.load()
    engine = build_engine(settings)
    try:
        Base.metadata.create_all(engine)
        reading_columns = {c['name'] for c in inspect(engine).get_columns('readings')}
        with engine.begin() as connection:
            if 'mode' not in reading_columns:
                connection.execute(text("ALTER TABLE readings ADD COLUMN mode VARCHAR(20) NOT NULL DEFAULT 'classic'"))
            if 'calendar' not in reading_columns:
                connection.execute(text('ALTER TABLE readings ADD COLUMN calendar JSON NULL'))
            if 'najia' not in reading_columns:
                connection.execute(text('ALTER TABLE readings ADD COLUMN najia JSON NULL'))
        if 'sequence' not in {c['name'] for c in inspect(engine).get_columns('interpretations')}:
            with engine.begin() as connection:
                connection.execute(text('ALTER TABLE interpretations ADD COLUMN sequence INT NOT NULL DEFAULT 1'))
                rows=connection.execute(text('SELECT id, reading_id FROM interpretations ORDER BY reading_id, started_at, id')).all()
                counts={}
                for identifier,reading_id in rows:
                    counts[reading_id]=counts.get(reading_id,0)+1
                    connection.execute(text('UPDATE interpretations SET sequence=:seq WHERE id=:id'),
                                       {'seq':counts[reading_id],'id':identifier})
                connection.execute(text('CREATE UNIQUE INDEX uq_reading_sequence ON interpretations(reading_id, sequence)'))
        entries = []
        for info in list_hexagrams():
            h = get_hexagram(info['id'])
            entries.extend([h['judgment'], *h['lines'], h['tuan'], h['xiang'],
                            *h['xiaoxiang'], *h['commentaries']])
            if h['use']:
                entries.append(h['use'])
        Repository(engine).sync_classics(entries)
        print(f'独立库表已就绪，典籍条目 {len(entries)} 条。')
    except Exception:
        print('初始化失败，请检查独立库和应用账号权限。连接配置不会输出。')
        raise SystemExit(1) from None
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
