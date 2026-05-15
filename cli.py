"""CLI entry point for registry server"""

import click
from src.api import server as run_server


@click.group()
def cli():
    """Registry server CLI"""
    pass


@cli.command()
def launch():
    """Launch the registry server"""
    run_server()


if __name__ == "__main__":
    cli()
