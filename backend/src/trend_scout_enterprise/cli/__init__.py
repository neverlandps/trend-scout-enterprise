import click

from trend_scout_enterprise.cli.migrate_sqlite_to_postgres import migrate


@click.group()
def main():
    """Trend Scout Enterprise CLI."""
    pass


main.add_command(migrate)
