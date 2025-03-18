from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# プロジェクトのモデルをインポート
import sys
import os
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.base import Base
from database.models import User, Book, Highlight

# Alembicの設定ファイルからの設定を読み込む
config = context.config

# ロギング設定の読み込み（オプション）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# マイグレーションのターゲットとなるメタデータを設定
target_metadata = Base.metadata

def run_migrations_offline():
    """オフラインモードでマイグレーションを実行"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """オンラインモードでマイグレーションを実行"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
