# -*- coding: utf-8 -*-
import logging
import click
from offload.photo_offloader import PhotoOffloader
from offload.video_offloader import VideoOffloader

# To allow click to display help on '-h' as well
CONTEXT_SETTINGS = {
    'help_option_names': ['-h', '--help']
}

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-s', '--source', type=click.Path(exists=True, file_okay=False, dir_okay=True), required=True, help='Source directory containing photos and/or videos')
@click.option('-d', '--destination', type=click.Path(exists=False, file_okay=False, dir_okay=True), required=True, help='Destination directory to copy photos/videos to')
@click.option('-a', '--archive', is_flag=True, default=False, help='Archive photos/videos into zip files instead of copying them')
@click.option('--media-type', type=click.Choice(['photos', 'videos', 'both']), default='both', help='Type of media to offload: photos, videos, or both (default: both)')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']), default='INFO', help='Set the logging level')
@click.option('--skip-unknown', is_flag=True, default=False, help='Skip files with unknown bucket key and/or invalid year-month separators instead of saving them to unknown directory')
def main(source, destination, archive, media_type, log_level, skip_unknown):
    # Create a basic logger
    logger = logging.getLogger('offload')

    # Create console handler if no handlers exist
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s: %(name)s/%(levelname)-9s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(log_level.upper())

    # Process photos if requested
    if media_type in ['photos', 'both']:
        photo_app = PhotoOffloader(logger)
        photo_app.offload_photos(source, destination, to_archive=archive, keep_unknown=not skip_unknown)

    # Process videos if requested
    if media_type in ['videos', 'both']:
        video_app = VideoOffloader(logger)
        video_app.offload_videos(source, destination, to_archive=archive, keep_unknown=not skip_unknown)

if __name__ == '__main__':  # pragma: no cover
    # Not testing the __main__ block as this is a built-in Python feature
    # that doesn't require us to double-check.
    main()
