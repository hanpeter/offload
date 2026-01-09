# -*- coding: utf-8 -*-
import click
from offload.application import Application

# To allow click to display help on '-h' as well
CONTEXT_SETTINGS = {
    'help_option_names': ['-h', '--help']
}

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--source', type=click.Path(exists=True, file_okay=False, dir_okay=True), required=True, help='Source directory containing photos')
@click.option('-d', '--destination', type=click.Path(exists=False, file_okay=False, dir_okay=True), required=True, help='Destination directory to copy photos to')
def main(source, destination):
    application = Application()
    application.offload_photos(source, destination)

if __name__ == '__main__':
    main()
