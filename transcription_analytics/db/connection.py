from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from config.settings import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        _engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine
