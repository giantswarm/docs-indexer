import logging
import signal
import sys
from types import FrameType

import click

import hugo as hugomodule
import blog as blogmodule


@click.group()
def cli() -> None:
    pass


@cli.command()
def hugo() -> None:
    """
    Index hugo site content
    """
    hugomodule.run()


@cli.command()
def blog() -> None:
    """
    Index Hubspot blog content
    """
    blogmodule.run()


def sigterm_handler(_signo: int, _stack_frame: FrameType | None) -> None:
    logging.info("Terminating due to SIGTERM")
    sys.exit(0)


if __name__ == "__main__":
    # logging setup
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    root.addHandler(ch)

    signal.signal(signal.SIGTERM, sigterm_handler)

    cli()
