import sqlalchemy as sa
from alembic import op

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key_hash', sa.String(128), nullable=False, unique=True),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('role', sa.String(50)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime),
    )

    op.create_table(
        'scoring_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_default', sa.Boolean, default=False),
        sa.Column('dimensions', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'llm_providers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('base_url', sa.Text, nullable=False),
        sa.Column('api_key_encrypted', sa.Text),
        sa.Column('model', sa.String(255), nullable=False),
        sa.Column('temperature', sa.Float),
        sa.Column('max_tokens', sa.Integer),
        sa.Column('is_default', sa.Boolean, default=False),
    )

    op.create_table(
        'sources',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('config_encrypted', sa.Text, nullable=False),
        sa.Column('category', sa.String(100)),
        sa.Column('tags', sa.JSON),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('refresh_interval_minutes', sa.Integer),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('api_keys.id'), nullable=False),
        sa.Column('health_status', sa.String(20)),
        sa.Column('last_scan_at', sa.DateTime),
        sa.Column('last_failure_reason', sa.Text),
        sa.Column('suggested_fix', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        'scan_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source_id', sa.String(36), sa.ForeignKey('sources.id'), nullable=False),
        sa.Column('status', sa.String(20)),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('items_collected', sa.Integer, default=0),
        sa.Column('items_new', sa.Integer, default=0),
        sa.Column('items_analyzed', sa.Integer, default=0),
        sa.Column('items_failed', sa.Integer, default=0),
        sa.Column('error_log', sa.JSON),
        sa.Column('suggested_fix', sa.Text),
    )

    op.create_table(
        'raw_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source_id', sa.String(36), sa.ForeignKey('sources.id'), nullable=False),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('title', sa.Text),
        sa.Column('summary', sa.Text),
        sa.Column('published_at', sa.DateTime),
        sa.Column('collected_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('metadata_json', sa.JSON),
        sa.Column('tags', sa.JSON),
        sa.Column('relevance_score', sa.Float),
        sa.Column('signal_strength', sa.Float),
        sa.Column('cross_domain_impact', sa.Float),
        sa.Column('investment_velocity', sa.Float),
        sa.Column('technical_feasibility', sa.Float),
        sa.Column('strategic_fit', sa.Float),
        sa.Column('overall_score', sa.Float),
    )

    op.create_table(
        'reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner_id', sa.String(36), sa.ForeignKey('api_keys.id'), nullable=False),
        sa.Column('title', sa.String(500)),
        sa.Column('report_type', sa.String(50)),
        sa.Column('status', sa.String(20)),
        sa.Column('file_path', sa.Text),
        sa.Column('summary_text', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('metadata_json', sa.JSON),
    )


def downgrade():
    op.drop_table('reports')
    op.drop_table('raw_items')
    op.drop_table('scan_runs')
    op.drop_table('sources')
    op.drop_table('llm_providers')
    op.drop_table('scoring_profiles')
    op.drop_table('api_keys')
