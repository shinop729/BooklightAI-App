"""
add_fts_table

Revision ID: c5e8d9f12345
Revises: b5e8d9e12345
Create Date: 2025-04-02 09:33:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e8d9f12345'
down_revision: Union[str, None] = 'b5e8d9e12345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQLの全文検索用のカラムとインデックスを追加
    op.add_column('highlights', sa.Column('search_vector', sa.Text(), nullable=True))

    # 現在のDB dialectを取得
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # tsvector型に変換するための関数を作成 (PostgreSQLのみ)
        op.execute("""
        CREATE OR REPLACE FUNCTION highlights_trigger() RETURNS trigger AS $$
        begin
          new.search_vector := to_tsvector('english', coalesce(new.content, ''));
          return new;
        end
        $$ LANGUAGE plpgsql;
        """)

        # トリガーを作成 (PostgreSQLのみ)
        op.execute("""
        CREATE TRIGGER highlights_update_trigger
        BEFORE INSERT OR UPDATE ON highlights
        FOR EACH ROW EXECUTE FUNCTION highlights_trigger();
        """)

        # 既存のデータを更新 (PostgreSQLのみ)
        op.execute("""
        UPDATE highlights SET search_vector = to_tsvector('english', content);
        """)

        # 検索用のインデックスを作成（tsvector型として明示的に指定） (PostgreSQLのみ)
        op.execute("""
        CREATE INDEX highlights_search_idx ON highlights USING GIN(to_tsvector('english', content));
        """)
    else:
        # SQLiteなど他のDBの場合は警告を出すか、何もしない
        print("Skipping PostgreSQL-specific FTS setup for non-PostgreSQL database.")


def downgrade() -> None:
    # 現在のDB dialectを取得
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        # インデックスの削除 (PostgreSQLのみ)
        op.execute("DROP INDEX IF EXISTS highlights_search_idx")

        # トリガーの削除 (PostgreSQLのみ)
        op.execute("DROP TRIGGER IF EXISTS highlights_update_trigger ON highlights")

        # 関数の削除 (PostgreSQLのみ)
        op.execute("DROP FUNCTION IF EXISTS highlights_trigger()")

    # カラムの削除 (全DB共通)
    op.drop_column('highlights', 'search_vector')
