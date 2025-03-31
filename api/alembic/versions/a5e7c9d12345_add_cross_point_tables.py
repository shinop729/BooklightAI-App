"""add_cross_point_tables

Revision ID: a5e7c9d12345
Revises: 654f3789c890
Create Date: 2025-03-31 20:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5e7c9d12345'
down_revision: Union[str, None] = '654f3789c890'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Cross Point履歴テーブル
    op.create_table(
        'cross_point',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('highlight1_id', sa.Integer(), nullable=False),
        sa.Column('highlight2_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('liked', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['highlight1_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['highlight2_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cross_point_id'), 'cross_point', ['id'], unique=False)
    
    # ハイライト埋め込みキャッシュテーブル
    op.create_table(
        'highlight_embeddings',
        sa.Column('highlight_id', sa.Integer(), nullable=False),
        sa.Column('embedding', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['highlight_id'], ['highlights.id'], ),
        sa.PrimaryKeyConstraint('highlight_id')
    )
    
    # 既に表示した組み合わせを記録するテーブル
    op.create_table(
        'connection_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('highlight1_id', sa.Integer(), nullable=False),
        sa.Column('highlight2_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['highlight1_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['highlight2_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_connection_history_id'), 'connection_history', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_connection_history_id'), table_name='connection_history')
    op.drop_table('connection_history')
    op.drop_table('highlight_embeddings')
    op.drop_index(op.f('ix_cross_point_id'), table_name='cross_point')
    op.drop_table('cross_point')
