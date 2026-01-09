# -*- coding: utf-8 -*-
import logging
import click
from offload.application import Application

# To allow click to display help on '-h' as well
CONTEXT_SETTINGS = {
    'help_option_names': ['-h', '--help']
}

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--source', type=click.Path(exists=True, file_okay=False, dir_okay=True), required=True, help='Source directory containing photos')
@click.option('-d', '--destination', type=click.Path(exists=False, file_okay=False, dir_okay=True), required=True, help='Destination directory to copy photos to')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), default='INFO', help='Set the logging level')
def main(source, destination, log_level):
    # Create a basic logger
    logger = logging.getLogger('offload')

    # Create console handler if no handlers exist
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s: %(name)s/%(levelname)-9s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(log_level.upper())

    application = Application(logger)
    application.offload_photos(source, destination)

if __name__ == '__main__':
    main()
