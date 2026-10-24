from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import assistant
from app.api.routes import router
from app.db import connect, init_db
from app.db.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버를 켤 때 테이블을 만들고, 비어 있으면 시연용 데이터를 넣는다
    init_db()
    conn = connect()
    try:
        seed(conn)
        conn.commit()
    finally:
        conn.close()

    # 음성 비서 모델은 여기서 한 번만 올린다. 못 올려도 (demo/ 폴더가 없어도) 서버는 뜬다
    try:
        from app.services.assistant import load_assistant

        app.state.assistant, app.state.assistant_error = load_assistant()
    except ImportError as e:
        app.state.assistant, app.state.assistant_error = None, str(e)
    yield


app = FastAPI(title="LogiOn Backend", lifespan=lifespan)
app.include_router(router)
app.include_router(assistant.router)
