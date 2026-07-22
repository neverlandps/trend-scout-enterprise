"""Initial schema: create all tables from the current model metadata.

Historically this migration hand-wrote 7 tables and the application relied on
``Base.metadata.create_all`` in the lifespan to fill in the rest, which left
pure-alembic deployments broken (later migrations reference tables that were
never created). It now delegates to the model metadata itself so the chain
001 -> 005 produces the full current schema on an empty database.

Later migrations (002-005) are defensive and no-op against tables/columns that
already match the current models, so this snapshot stays compatible with the
rest of the chain.
"""

import sqlalchemy as sa
from alembic import op

# Importing the models package registers every table on Base.metadata.
import trend_scout_enterprise.models  # noqa: F401
from trend_scout_enterprise.core.database import Base

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    tables = [
        table
        for name, table in Base.metadata.tables.items()
        if name not in existing and name != 'alembic_version'
    ]
    if tables:
        Base.metadata.create_all(bind=bind, tables=tables)


def downgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    tables = [
        table
        for table in reversed(Base.metadata.sorted_tables)
        if table.name in existing and table.name != 'alembic_version'
    ]
    if tables:
        Base.metadata.drop_all(bind=bind, tables=tables)
