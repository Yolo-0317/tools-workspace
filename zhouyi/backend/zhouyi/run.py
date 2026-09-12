import uvicorn
from .config import Settings
from .api import create_app


if __name__ == '__main__':
    settings = Settings.load()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, access_log=False)
