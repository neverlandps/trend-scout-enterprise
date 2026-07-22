import click
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import sessionmaker

# Importing the models package registers every model on Base.metadata so
# create_all below builds the full target schema (all 22 tables).
import trend_scout_enterprise.models  # noqa: F401
from trend_scout_enterprise.core.config import settings
from trend_scout_enterprise.core.database import Base


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

    session_source = sessionmaker(bind=sqlite_engine)
    session_target = sessionmaker(bind=target_engine)
    source_session = session_source()
    target_session = session_target()

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
                # Rows are copied verbatim; bcrypt password/API-key hashes are
                # portable across databases and need no transformation.
                target_session.execute(target_table.insert(), [dict(row) for row in rows])
        if not dry_run:
            target_session.commit()
            click.echo("Migration committed")
    except Exception as e:
        target_session.rollback()
        raise click.ClickException(str(e)) from e
    finally:
        source_session.close()
        target_session.close()


if __name__ == '__main__':
    migrate()
