import click

from trend_scout_enterprise.cli.backfill_embeddings import (
    backfill_embeddings as backfill_embeddings_cmd,
)
from trend_scout_enterprise.cli.migrate_sqlite_to_postgres import migrate


@click.group()
def main():
    """Trend Scout Enterprise CLI."""
    pass


main.add_command(migrate)
main.add_command(backfill_embeddings_cmd)
