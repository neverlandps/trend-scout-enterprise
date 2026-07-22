"""Cascade-delete signal reviews when their raw item is deleted.

The review API records SignalReview rows that reference raw_items. Bulk
deletes (e.g. ``db.query(RawItem).filter(...).delete()`` in the smoke script)
bypass ORM cascades, so the database FK itself must cascade on PostgreSQL,
where FK enforcement is strict (SQLite leaves it off by default).

Defensive: recreates the FK only when the signal_reviews table exists.
"""

import sqlalchemy as sa
from alembic import op

revision = '005_signal_review_fk_cascade'
down_revision = '004_signal_review_feedback_type'
branch_labels = None
depends_on = None

_TABLE = 'signal_reviews'
_COLUMN = 'raw_item_id'
_FK_NAME = 'fk_signal_reviews_raw_item_id_cascade'


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _fk_names(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {fk['name'] for fk in insp.get_foreign_keys(table) if fk.get('name')}


def _has_cascade_fk(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return False
    for fk in insp.get_foreign_keys(table):
        if column in fk.get('constrained_columns', []):
            options = fk.get('options') or {}
            if str(options.get('ondelete', '')).upper() == 'CASCADE':
                return True
    return False


def upgrade():
    if not _table_exists(_TABLE):
        return
    # Idempotent: a database created from the current model metadata (001
    # snapshot or Base.metadata.create_all) already has the CASCADE FK.
    if _has_cascade_fk(_TABLE, _COLUMN):
        return

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for fk_name in _fk_names(_TABLE):
            op.drop_constraint(fk_name, _TABLE, type_='foreignkey')
        op.create_foreign_key(
            _FK_NAME, _TABLE, 'raw_items', [_COLUMN], ['id'], ondelete='CASCADE'
        )
    else:
        # SQLite: batch mode rebuilds the table with the new FK definition.
        with op.batch_alter_table(_TABLE) as batch_op:
            for fk_name in _fk_names(_TABLE):
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            batch_op.create_foreign_key(
                _FK_NAME, 'raw_items', [_COLUMN], ['id'], ondelete='CASCADE'
            )


def downgrade():
    if not _table_exists(_TABLE):
        return

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        if _FK_NAME in _fk_names(_TABLE):
            op.drop_constraint(_FK_NAME, _TABLE, type_='foreignkey')
        op.create_foreign_key(
            'signal_reviews_raw_item_id_fkey', _TABLE, 'raw_items', [_COLUMN], ['id']
        )
    else:
        with op.batch_alter_table(_TABLE) as batch_op:
            if _FK_NAME in _fk_names(_TABLE):
                batch_op.drop_constraint(_FK_NAME, type_='foreignkey')
            batch_op.create_foreign_key(
                'fk_signal_reviews_raw_item_id', 'raw_items', [_COLUMN], ['id']
            )
