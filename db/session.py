"""DB接続セッション管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "keiba.db"

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
