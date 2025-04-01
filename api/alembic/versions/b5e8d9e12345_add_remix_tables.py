"""add_remix_tables

Revision ID: b5e8d9e12345
Revises: a5e7c9d12345
Create Date: 2025-03-31 21:22:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e8d9e12345'
down_revision: Union[str, None] = 'a5e7c9d12345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remixテーブル
    op.create_table(
        'remix',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('theme', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Remix-ハイライト関連テーブル
    op.create_table(
        'remix_highlights',
        sa.Column('remix_id', sa.Integer(), nullable=False),
        sa.Column('highlight_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['highlight_id'], ['highlights.id'], ),
        sa.ForeignKeyConstraint(['remix_id'], ['remix.id'], ),
        sa.PrimaryKeyConstraint('remix_id', 'highlight_id')
    )


def downgrade() -> None:
    op.drop_table('remix_highlights')
    op.drop_table('remix')
