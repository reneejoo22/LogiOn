from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    yield


app = FastAPI(title="LogiOn Backend", lifespan=lifespan)
app.include_router(router)
