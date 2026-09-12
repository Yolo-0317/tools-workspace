"""Local personal app API; immutable casts precede every external AI call."""
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from fastapi import BackgroundTasks, FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .config import PROJECT, Settings
from .core import cast_coins, describe_cast
from .rules import select_passages
from .corpus import get_hexagram, list_hexagrams, load_materials
from .interpretation import generate_interpretation, InterpretationError, PROMPT_VERSION
from .models import Base
from .repository import Conflict, NotFound, Repository
from .presentation import simplify, present_hexagram, present_reading
from .calendar import normalize_cast_time
from .najia import build_najia

TOPICS = [
    {'id':'work','label':'工作事业','templates':['对于目前这项工作，我接下来应注意什么？','推进新项目之前，我需要看清哪些条件？']},
    {'id':'cooperation','label':'合作关系','templates':['推进这次合作前，我需要看清哪些条件？','面对目前的合作分歧，我可以怎样调整？']},
    {'id':'relationship','label':'感情相处','templates':['面对目前的相处困境，我可以怎样调整？','与对方沟通时，我需要留意什么？']},
    {'id':'learning','label':'学习成长','templates':['推进这项学习计划，我应把精力放在哪里？','面对学习中遇到的困难，我可以怎样调整？']},
    {'id':'life','label':'生活选择','templates':['关于搬家这件事，目前有哪些值得考虑的因素？','面对眼前的选择，我还需要看清什么？']},
]


class ReadingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=1000)
    topic: str = Field(default='', max_length=50)
    background: str = Field(default='', max_length=3000)
    horizon: str = Field(default='', max_length=100)
    mode: Literal['classic', 'najia'] = 'classic'
    cast_time: str | None = None
    location: str = Field(default='', max_length=100)

    @field_validator('question', 'request_id', mode='before')
    @classmethod
    def trim_required(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode='after')
    def validate_cast_time(self):
        if self.mode == 'najia' and self.cast_time:
            try:
                parsed = datetime.fromisoformat(self.cast_time.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('起卦时间格式无效') from None
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError('六爻纳甲的起卦时间必须包含时区')
        return self


class AttemptInput(BaseModel):
    request_id: str = Field(min_length=1, max_length=80, pattern=r'\S')


class ReflectionInput(BaseModel):
    text: str = Field(min_length=1, max_length=5000)

    @field_validator('text', mode='before')
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class NajiaUseInput(BaseModel):
    choice: Literal['世爻', '应爻', '父母', '兄弟', '子孙', '妻财', '官鬼']


def build_engine(settings):
    return create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=1800,
                         connect_args={'connect_timeout':5,'read_timeout':15,'write_timeout':15},
                         hide_parameters=True)


def create_app(settings=None, *, engine=None, interpretation_generator=generate_interpretation):
    settings = settings or Settings.load()
    own_engine = engine is None
    engine = engine or build_engine(settings)
    repository = Repository(engine)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if own_engine:
            engine.dispose()

    app = FastAPI(title='观易 · 起卦与读经', lifespan=lifespan)
    app.state.repository = repository
    app.state.settings = settings

    @app.middleware('http')
    async def protect_local_writes(request: Request, call_next):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            origin = request.headers.get('origin')
            if origin:
                parsed = urlsplit(origin)
                local_dev = parsed.hostname in ('localhost','127.0.0.1') and parsed.port == 5173
                if parsed.netloc != request.headers.get('host') and not local_dev:
                    return JSONResponse(status_code=403, content={'detail':'请从本应用页面提交操作'})
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        if request.url.path.startswith('/api/readings'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(NotFound)
    async def missing(request, error):
        return JSONResponse(status_code=404, content={'detail':str(error)})

    @app.exception_handler(Conflict)
    async def conflict(request, error):
        return JSONResponse(status_code=409, content={'detail':str(error)})

    @app.exception_handler(SQLAlchemyError)
    async def database_failure(request, error):
        return JSONResponse(status_code=503, content={'detail':'数据库暂时不可用，请稍后重试；不要重复更改问题'})

    @app.get('/api/health')
    def health():
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        return {'status':'ok','database':'connected','model':settings.model,
                'ai_configured':bool(settings.api_key),'hexagrams':len(list_hexagrams())}

    @app.get('/api/topics')
    def topics():
        return TOPICS

    @app.get('/api/classics')
    def classics():
        return [dict(h,name=simplify(h['name'])) for h in list_hexagrams()]

    @app.get('/api/classics/{identifier}')
    def classic(identifier: int = PathParam(ge=1, le=64)):
        return present_hexagram(get_hexagram(identifier))

    @app.post('/api/readings', status_code=201)
    def create_reading(body: ReadingInput):
        coins = cast_coins()
        cast = describe_cast(coins)
        cast['coins'] = coins
        selection = select_passages(cast)
        materials = load_materials(selection)
        if body.mode == 'najia':
            calendar = normalize_cast_time(body.cast_time)
            najia = build_najia(cast, calendar, body.topic)
            question = body.model_dump(exclude={'request_id', 'mode'})
        else:
            calendar = najia = None
            question = body.model_dump(exclude={'request_id', 'mode', 'cast_time', 'location'})
        return present_reading(repository.create_reading(
            body.request_id, question, cast, selection, materials,
            mode=body.mode, calendar=calendar, najia=najia,
        ))

    @app.get('/api/readings')
    def readings(offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100)):
        return repository.list_readings(offset, limit)

    @app.get('/api/readings/{identifier}')
    def reading(identifier: str):
        return present_reading(repository.get_reading(identifier))

    @app.post('/api/readings/{identifier}/reflections', status_code=201)
    def reflection(identifier: str, body: ReflectionInput):
        return repository.add_reflection(identifier, body.text)

    @app.post('/api/readings/{identifier}/najia-use')
    def najia_use(identifier: str, body: NajiaUseInput):
        return present_reading(repository.set_najia_use(identifier, body.choice))

    def interpret_in_background(reading_id, attempt_id):
        try:
            snapshot = present_reading(repository.get_reading(reading_id))
            packet = dict(snapshot['question'], selection=snapshot['selection'],
                          mode=snapshot.get('mode', 'classic'),
                          calendar=snapshot.get('calendar'), najia=snapshot.get('najia'))
            materials=[{k:v for k,v in m.items() if k not in ('source_text','source_checksum')}
                       for m in snapshot['materials']]
            output = interpretation_generator(packet, materials, settings)
        except InterpretationError as error:
            message = str(error)
        except Exception:
            message = '解读未完成，卦象已保存，可以稍后重试'
        else:
            message = None
        try:
            repository.finish_attempt(attempt_id, result=output if message is None else None, error=message)
        except SQLAlchemyError:
            # Persisted lease remains recoverable; never log connection or prompt data.
            pass

    @app.post('/api/readings/{identifier}/interpretations', status_code=202)
    def interpret(identifier: str, body: AttemptInput, background: BackgroundTasks):
        attempt, claimed = repository.begin_attempt(identifier, body.request_id, settings.model,
                                                     PROMPT_VERSION, settings.lease_seconds)
        if claimed:
            background.add_task(interpret_in_background, identifier, attempt['id'])
        return attempt

    dist = PROJECT / 'frontend' / 'dist'
    if (dist / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=dist/'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path == 'api' or path.startswith('api/'):
            raise HTTPException(404, '接口不存在')
        if not (dist / 'index.html').is_file():
            return JSONResponse(status_code=503, content={'detail':'前端尚未构建'})
        target = (dist / path).resolve()
        if target.is_relative_to(dist.resolve()) and target.is_file():
            return FileResponse(target)
        return FileResponse(dist / 'index.html')

    return app
