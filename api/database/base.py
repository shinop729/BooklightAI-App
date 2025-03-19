from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# データベース接続URLを環境変数から取得
DATABASE_URL = os.getenv('DATABASE_URL')

# Heroku Postgresの場合、URLスキームを修正
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# SQLAlchemyエンジンの作成
engine = create_engine(DATABASE_URL or 'sqlite:///./booklight.db')

# セッションの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ベースクラスの作成
Base = declarative_base()

def get_db():
    """データベースセッションを取得するジェネレータ"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
