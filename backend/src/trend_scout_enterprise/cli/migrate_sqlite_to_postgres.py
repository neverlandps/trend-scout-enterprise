import click
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import sessionmaker
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import Base, engine as pg_engine


@click.command()
@click.option('--sqlite-path', default='trend_scout.db', help='Path to existing SQLite database')
@click.option('--postgres-url', default=None, help='PostgreSQL URL (defaults to DATABASE_URL env)')
@click.option('--dry-run', is_flag=True, help='Print what would be migrated without writing')
def migrate(sqlite_path, postgres_url, dry_run):
    """Migrate data from SQLite to PostgreSQL."""
    sqlite_url = f"sqlite:///{sqlite_path}"
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    target_url = postgres_url or settings.database_url
    target_engine = create_engine(target_url)

    if not dry_run:
        # Create target schema
        Base.metadata.create_all(bind=target_engine)
        click.echo(f"Created tables in {target_url}")

    # Reflect source and target tables
    source_meta = MetaData()
    source_meta.reflect(bind=sqlite_engine)
    target_meta = MetaData()
    target_meta.reflect(bind=target_engine)

    SessionSource = sessionmaker(bind=sqlite_engine)
    SessionTarget = sessionmaker(bind=target_engine)
    source_session = SessionSource()
    target_session = SessionTarget()

    try:
        for table_name in source_meta.tables:
            source_table = source_meta.tables[table_name]
            if table_name not in target_meta.tables:
                click.echo(f"Skipping {table_name}: not in target schema")
                continue
            rows = source_session.execute(source_table.select()).mappings().all()
            click.echo(f"Table {table_name}: {len(rows)} rows")
            if not dry_run and rows:
                target_table = target_meta.tables[table_name]
                target_session.execute(target_table.insert(), [dict(row) for row in rows])
        if not dry_run:
            target_session.commit()
            click.echo("Migration committed")
    except Exception as e:
        target_session.rollback()
        raise click.ClickException(str(e))
    finally:
        source_session.close()
        target_session.close()


if __name__ == '__main__':
    migrate()
