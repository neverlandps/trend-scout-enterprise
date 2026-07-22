"""Add signal_embeddings table for dialect-agnostic vector search.

Stores embedding vectors as JSON float lists so both SQLite and PostgreSQL
work without pgvector. Similarity is computed in Python; pgvector is the
documented evolution path once the corpus outgrows in-memory scans.

Defensive: databases created via ``Base.metadata.create_all`` (the development
lifespan path) may already contain the table without an alembic version
record. Every step checks the live schema first.
"""

import sqlalchemy as sa
from alembic import op

revision = '006_signal_embeddings'
down_revision = '005_signal_review_fk_cascade'
branch_labels = None
depends_on = None

_TABLE = 'signal_embeddings'


def _inspector():
    return sa.inspect(op.get_bind())


def _existing_indexes(table: str) -> set[str]:
    insp = _inspector()
    if table not in insp.get_table_names():
        return set()
    return {idx['name'] for idx in insp.get_indexes(table)}


def upgrade():
    tables = set(_inspector().get_table_names())

    if _TABLE not in tables:
        op.create_table(
            _TABLE,
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column(
                'raw_item_id',
                sa.String(36),
                sa.ForeignKey('raw_items.id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column(
                'workspace_id', sa.String(36), sa.ForeignKey('workspaces.id'), nullable=False
            ),
            sa.Column('embedding', sa.JSON, nullable=False),
            sa.Column('model', sa.String(100), nullable=False),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        )

    indexes = _existing_indexes(_TABLE)
    if 'ix_signal_embeddings_raw_item_id' not in indexes:
        op.create_index(
            'ix_signal_embeddings_raw_item_id', _TABLE, ['raw_item_id'], unique=True
        )
    if 'ix_signal_embeddings_workspace_id' not in indexes:
        op.create_index('ix_signal_embeddings_workspace_id', _TABLE, ['workspace_id'])


def downgrade():
    if _TABLE not in set(_inspector().get_table_names()):
        return
    indexes = _existing_indexes(_TABLE)
    if 'ix_signal_embeddings_workspace_id' in indexes:
        op.drop_index('ix_signal_embeddings_workspace_id', table_name=_TABLE)
    if 'ix_signal_embeddings_raw_item_id' in indexes:
        op.drop_index('ix_signal_embeddings_raw_item_id', table_name=_TABLE)
    op.drop_table(_TABLE)
