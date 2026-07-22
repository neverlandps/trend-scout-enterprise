"""Widen key/token hash columns for bcrypt and index embed token prefix.

Bcrypt hashes are longer than the legacy 64-char SHA-256 hex digests, so
api_keys.key_hash and embed_tokens.token_hash are widened to 255 chars.
An index on embed_tokens.token_prefix supports prefix-based candidate lookup.

All operations are guarded by inspector checks: 001_initial predates some
tables (e.g. embed_tokens), so on databases created from a stale 001 the
missing tables/indexes are skipped instead of raising NoSuchTableError.
"""

import sqlalchemy as sa
from alembic import op

revision = '002_bcrypt_hash_columns'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()

    if 'api_keys' in tables:
        with op.batch_alter_table('api_keys') as batch_op:
            batch_op.alter_column(
                'key_hash',
                existing_type=sa.String(128),
                type_=sa.String(255),
                existing_nullable=False,
            )

    if 'embed_tokens' in tables:
        with op.batch_alter_table('embed_tokens') as batch_op:
            batch_op.alter_column(
                'token_hash',
                existing_type=sa.String(128),
                type_=sa.String(255),
                existing_nullable=False,
            )

        index_names = {idx['name'] for idx in inspector.get_indexes('embed_tokens')}
        if 'ix_embed_tokens_token_prefix' not in index_names:
            op.create_index(
                'ix_embed_tokens_token_prefix',
                'embed_tokens',
                ['token_prefix'],
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()

    if 'embed_tokens' in tables:
        index_names = {idx['name'] for idx in inspector.get_indexes('embed_tokens')}
        if 'ix_embed_tokens_token_prefix' in index_names:
            op.drop_index('ix_embed_tokens_token_prefix', table_name='embed_tokens')

        with op.batch_alter_table('embed_tokens') as batch_op:
            batch_op.alter_column(
                'token_hash',
                existing_type=sa.String(255),
                type_=sa.String(128),
                existing_nullable=False,
            )

    if 'api_keys' in tables:
        with op.batch_alter_table('api_keys') as batch_op:
            batch_op.alter_column(
                'key_hash',
                existing_type=sa.String(255),
                type_=sa.String(128),
                existing_nullable=False,
            )
