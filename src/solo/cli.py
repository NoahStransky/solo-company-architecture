"""Command line entry point for solo."""

import click

from . import __version__
from .commands.complete_cmd import complete
from .commands.dispatch_cmd import dispatch
from .commands.init_cmd import init
from .commands.setup_cmd import setup
from .commands.start_cmd import start
from .commands.status_cmd import status
from .commands.validate_cmd import validate


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-v", "--version")
def main():
    """Project-level Solo Company CLI."""


main.add_command(init)
main.add_command(dispatch)
main.add_command(complete)
main.add_command(status)
main.add_command(start)
main.add_command(setup)
main.add_command(validate)
