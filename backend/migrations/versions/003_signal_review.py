"""Add human-in-the-loop signal review workflow.

Adds review_status/human_score/assigned_reviewer_id columns to raw_items and
creates the signal_reviews and review_assignments tables.

Defensive: databases created via ``Base.metadata.create_all`` (the development
lifespan path) may already contain some or all of these columns/tables without
an alembic version record. Every step checks the live schema first so this
migration is safe to run on both fresh and pre-created databases.
"""

import sqlalchemy as sa
from alembic import op

revision = '003_signal_review'
down_revision = '002_bcrypt_hash_columns'
branch_labels = None
depends_on = None

_NEW_COLUMNS = ('review_status', 'human_score', 'assigned_reviewer_id')


def _inspector():
    return sa.inspect(op.get_bind())


def _existing_columns(table: str) -> set[str]:
    insp = _inspector()
    if table not in insp.get_table_names():
        return set()
    return {col['name'] for col in insp.get_columns(table)}


def _existing_indexes(table: str) -> set[str]:
    insp = _inspector()
    if table not in insp.get_table_names():
        return set()
    return {idx['name'] for idx in insp.get_indexes(table)}


def upgrade():
    tables = set(_inspector().get_table_names())

    if 'raw_items' in tables:
        columns = _existing_columns('raw_items')
        indexes = _existing_indexes('raw_items')

        if 'review_status' not in columns:
            with op.batch_alter_table('raw_items') as batch_op:
                batch_op.add_column(
                    sa.Column('review_status', sa.String(20), server_default='auto')
                )
        if 'ix_raw_items_review_status' not in indexes:
            with op.batch_alter_table('raw_items') as batch_op:
                batch_op.create_index('ix_raw_items_review_status', ['review_status'])

        if 'human_score' not in columns:
            with op.batch_alter_table('raw_items') as batch_op:
                batch_op.add_column(sa.Column('human_score', sa.Float, nullable=True))

        if 'assigned_reviewer_id' not in columns:
            with op.batch_alter_table('raw_items') as batch_op:
                batch_op.add_column(
                    sa.Column(
                        'assigned_reviewer_id',
                        sa.String(36),
                        sa.ForeignKey(
                            'api_keys.id', name='fk_raw_items_assigned_reviewer_id'
                        ),
                        nullable=True,
                    )
                )

    if 'signal_reviews' not in tables:
        op.create_table(
            'signal_reviews',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column(
                'raw_item_id', sa.String(36), sa.ForeignKey('raw_items.id'), nullable=False
            ),
            sa.Column(
                'workspace_id', sa.String(36), sa.ForeignKey('workspaces.id'), nullable=False
            ),
            sa.Column('reviewer_id', sa.String(36), sa.ForeignKey('api_keys.id'), nullable=True),
            sa.Column('status', sa.String(20), nullable=False),
            sa.Column('human_score', sa.Float, nullable=True),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        )
    sr_indexes = _existing_indexes('signal_reviews')
    if 'ix_signal_reviews_raw_item_id' not in sr_indexes:
        op.create_index('ix_signal_reviews_raw_item_id', 'signal_reviews', ['raw_item_id'])
    if 'ix_signal_reviews_workspace_id' not in sr_indexes:
        op.create_index('ix_signal_reviews_workspace_id', 'signal_reviews', ['workspace_id'])

    if 'review_assignments' not in tables:
        op.create_table(
            'review_assignments',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column(
                'workspace_id', sa.String(36), sa.ForeignKey('workspaces.id'), nullable=False
            ),
            sa.Column('category', sa.String(100), nullable=False),
            sa.Column(
                'reviewer_id', sa.String(36), sa.ForeignKey('api_keys.id'), nullable=False
            ),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
            sa.UniqueConstraint(
                'workspace_id', 'category', name='uq_review_assignments_ws_category'
            ),
        )
    ra_indexes = _existing_indexes('review_assignments')
    if 'ix_review_assignments_workspace_id' not in ra_indexes:
        op.create_index(
            'ix_review_assignments_workspace_id', 'review_assignments', ['workspace_id']
        )


def downgrade():
    tables = set(_inspector().get_table_names())

    if 'review_assignments' in tables:
        if 'ix_review_assignments_workspace_id' in _existing_indexes('review_assignments'):
            op.drop_index(
                'ix_review_assignments_workspace_id', table_name='review_assignments'
            )
        op.drop_table('review_assignments')

    if 'signal_reviews' in tables:
        sr_indexes = _existing_indexes('signal_reviews')
        if 'ix_signal_reviews_workspace_id' in sr_indexes:
            op.drop_index('ix_signal_reviews_workspace_id', table_name='signal_reviews')
        if 'ix_signal_reviews_raw_item_id' in sr_indexes:
            op.drop_index('ix_signal_reviews_raw_item_id', table_name='signal_reviews')
        op.drop_table('signal_reviews')

    if 'raw_items' in tables:
        columns = _existing_columns('raw_items')
        indexes = _existing_indexes('raw_items')
        with op.batch_alter_table('raw_items') as batch_op:
            if 'ix_raw_items_review_status' in indexes:
                batch_op.drop_index('ix_raw_items_review_status')
            for col in reversed(_NEW_COLUMNS):
                if col in columns:
                    batch_op.drop_column(col)
