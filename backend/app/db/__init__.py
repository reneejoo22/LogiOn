import os
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def db_path() -> Path:
    """DB 파일 위치. 환경변수 LOGION_DB로 바꿀 수 있다 (테스트에서 사용)."""
    return Path(os.environ.get("LOGION_DB", BACKEND_DIR / "data" / "logion.db"))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # 의존성(get_db)과 엔드포인트가 서로 다른 스레드에서 돌 수 있어 check_same_thread를 끈다
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def get_db():
    """요청 하나당 연결 하나. 정상 종료면 커밋, 예외면 롤백."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
