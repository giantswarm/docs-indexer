import logging
import signal
import sys

import click

import docs as docsmodule
import blog as blogmodule

@click.group()
def cli():
    pass

@cli.command()
def docs():
    """
    Index documentation content
    """
    docsmodule.run()

@cli.command()
def blog():
    """
    Index blog content
    """
    blogmodule.run()


def sigterm_handler(_signo, _stack_frame):
    logging.info("Terminating due to SIGTERM")
    sys.exit(0)

if __name__ == '__main__':    
    # logging setup
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

    signal.signal(signal.SIGTERM, sigterm_handler)

    cli()
