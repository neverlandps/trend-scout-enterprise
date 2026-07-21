"""Persist reviewer feedback type on signal reviews.

Adds the nullable feedback_type column to signal_reviews so feedback
submitted via POST /signals/{id}/feedback is stored on the review record.

Defensive: skips the column if it already exists (databases pre-created via
``Base.metadata.create_all`` may already have it).
"""

import sqlalchemy as sa
from alembic import op

revision = '004_signal_review_feedback_type'
down_revision = '003_signal_review'
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return False
    return column in {col['name'] for col in insp.get_columns(table)}


def upgrade():
    if not _has_column('signal_reviews', 'feedback_type'):
        op.add_column(
            'signal_reviews',
            sa.Column('feedback_type', sa.String(50), nullable=True),
        )


def downgrade():
    if _has_column('signal_reviews', 'feedback_type'):
        op.drop_column('signal_reviews', 'feedback_type')
