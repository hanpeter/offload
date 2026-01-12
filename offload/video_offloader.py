# -*- coding: utf-8 -*-
import logging
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import exiftool

from offload.constants import (
    DEFAULT_LATITUDE_REF,
    DEFAULT_LONGITUDE_REF,
    GroupBy,
    MONTH_PREFIX,
    NEGATIVE_DIRECTIONS,
    UNKNOWN_BUCKET_KEY,
    UNKNOWN_DIRECTORY,
    YEAR_MONTH_SEPARATOR,
    YEAR_PREFIX,
)


@dataclass
class VideoMetadata:
    """Metadata extracted from a video file."""
    path: Path
    date_taken: Optional[datetime] = None
    location: Optional[tuple[float, float]] = None  # (latitude, longitude)
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None  # Application/software used to record the video


class VideoOffloader:
    # Supported video file extensions
    # TODO: Allow this to be configured via environment variable
    VIDEO_EXTENSIONS = {'.mov', '.mp4'}

    # Regex pattern for timezone offset (e.g., "-07:00", "+05:30")
    TZ_OFFSET_PATTERN = re.compile(r'[+-]\d{2}:\d{2}$')

    # Regex pattern for DMS (degrees, minutes, seconds) format
    # Matches: "37 deg 46' 26.30\"" or "37 deg 46 26.30" (with or without quotes)
    DMS_PATTERN = re.compile(r"(\d+)\s+deg\s+(\d+)\s*'?\s*([\d.]+)\s*\"?")

    # Date field names in order of preference for extraction
    DATE_FIELDS = [
        'QuickTime:CreationDate',
        'QuickTime:CreateDate',
        'QuickTime:MediaCreateDate',
        'Keys:CreationDate',
        'Keys:CreateDate',
        'CreateDate',
        'CreationDate',
        'DateTimeOriginal',
        'MediaCreateDate',
    ]

    # Date format strings for parsing
    DATE_FORMATS = [
        '%Y:%m:%d %H:%M:%S',  # EXIF format (without timezone)
        '%Y-%m-%d %H:%M:%S',  # ISO format
        '%Y-%m-%dT%H:%M:%S',  # ISO with T separator
        '%Y-%m-%dT%H:%M:%S.%f',  # ISO with microseconds
    ]

    # GPS coordinate tag names
    GPS_COORDINATES_TAGS = ['QuickTime:GPSCoordinates', 'Keys:GPSCoordinates']
    GPS_LATITUDE_TAGS = ['GPSLatitude', 'GPS:GPSLatitude']
    GPS_LONGITUDE_TAGS = ['GPSLongitude', 'GPS:GPSLongitude']
    GPS_LATITUDE_REF_TAG = 'GPSLatitudeRef'
    GPS_LONGITUDE_REF_TAG = 'GPSLongitudeRef'

    # Camera info tag names
    CAMERA_MAKE_TAGS = ['Make', 'QuickTime:Make', 'Keys:Make']
    CAMERA_MODEL_TAGS = ['Model', 'QuickTime:Model', 'Keys:Model']
    CAMERA_SOFTWARE_TAGS = ['Software', 'QuickTime:Software', 'Keys:Software', 'CreatorTool']

    # Date parsing constants
    MIN_DATE_STRING_LENGTH = 10
    COLON_REPLACEMENT_COUNT = 2  # Number of colons to replace in date string

    # GPS coordinate parsing constants
    MIN_GPS_PARTS = 2  # Minimum parts needed for lat/lon coordinates

    # ExifTool parameters
    EXIFTOOL_EMBEDDED_PARAMS = ['-ee']  # Flag to extract embedded GPMF data

    # Archive filename
    ARCHIVE_FILENAME = "videos.zip"

    def __init__(self, logger: logging.Logger):
        """
        Initialize the VideoOffloader.

        Args:
            logger: Logger instance for logging operations
        """
        self.logger = logger

    @staticmethod
    def _dms_to_decimal(dms: tuple, ref: str) -> float:
        """Convert degrees, minutes, seconds to decimal degrees."""
        degrees = float(dms[0])
        minutes = float(dms[1]) / 60.0
        seconds = float(dms[2]) / 3600.0
        decimal = degrees + minutes + seconds
        return -decimal if ref in NEGATIVE_DIRECTIONS else decimal

    def _parse_date(self, metadata: dict) -> Optional[datetime]:
        """Parse date taken from video metadata."""
        # Try different date fields in order of preference
        for field in VideoOffloader.DATE_FIELDS:
            if field in metadata:
                try:
                    date_str = str(metadata[field])
                    # Strip timezone offset if present (e.g., "-07:00" or "+05:30")
                    # We'll parse the date/time part and ignore timezone for now
                    if VideoOffloader.TZ_OFFSET_PATTERN.search(date_str):
                        # Remove timezone offset for parsing
                        date_str_no_tz = VideoOffloader.TZ_OFFSET_PATTERN.sub('', date_str)
                    else:
                        date_str_no_tz = date_str

                    # Try multiple date formats
                    for fmt in VideoOffloader.DATE_FORMATS:
                        try:
                            return datetime.strptime(date_str_no_tz, fmt)
                        except ValueError:
                            continue
                    # If no format matches, try parsing just the date part
                    # Handle both colon and dash separators
                    if 'T' in date_str_no_tz:
                        date_part = date_str_no_tz.split('T')[0]
                    elif ' ' in date_str_no_tz:
                        date_part = date_str_no_tz.split(' ')[0]
                    else:
                        date_part = date_str_no_tz[:VideoOffloader.MIN_DATE_STRING_LENGTH] if len(date_str_no_tz) >= VideoOffloader.MIN_DATE_STRING_LENGTH else date_str_no_tz

                    # Try parsing date part with colon separator (EXIF format)
                    if ':' in date_part and len(date_part) >= VideoOffloader.MIN_DATE_STRING_LENGTH:
                        try:
                            # Replace colons with dashes for date part: "2024:08:04" -> "2024-08-04"
                            date_part_dash = date_part.replace(':', '-', VideoOffloader.COLON_REPLACEMENT_COUNT)
                            return datetime.strptime(date_part_dash[:VideoOffloader.MIN_DATE_STRING_LENGTH], '%Y-%m-%d')
                        except ValueError:
                            pass
                    # Try standard date format
                    if len(date_part) >= VideoOffloader.MIN_DATE_STRING_LENGTH:
                        try:
                            return datetime.strptime(date_part[:VideoOffloader.MIN_DATE_STRING_LENGTH], '%Y-%m-%d')
                        except ValueError:
                            pass
                except (ValueError, TypeError, AttributeError):
                    continue
        return None

    def _parse_location(self, metadata: dict) -> Optional[tuple[float, float]]:
        """
        Parse GPS location from video metadata.

        Args:
            metadata: Dictionary of metadata tags from exiftool
        """
        try:
            # Try QuickTime GPSCoordinates format (space-separated "lat lon alt")
            for gps_tag in VideoOffloader.GPS_COORDINATES_TAGS:
                if gps_tag in metadata:
                    coords_str = str(metadata[gps_tag])
                    parts = coords_str.split()
                    if len(parts) >= VideoOffloader.MIN_GPS_PARTS:
                        try:
                            lat = float(parts[0])
                            lon = float(parts[1])
                            return (lat, lon)
                        except (ValueError, IndexError):
                            pass

            # Try standard GPSLatitude/GPSLongitude (DMS format)
            if any(tag in metadata for tag in VideoOffloader.GPS_LATITUDE_TAGS) and any(tag in metadata for tag in VideoOffloader.GPS_LONGITUDE_TAGS):
                try:
                    # Find the first available latitude tag
                    lat_tag = next(tag for tag in VideoOffloader.GPS_LATITUDE_TAGS if tag in metadata)
                    lon_tag = next(tag for tag in VideoOffloader.GPS_LONGITUDE_TAGS if tag in metadata)
                    lat_str = str(metadata[lat_tag])
                    lon_str = str(metadata[lon_tag])
                    lat_ref = metadata.get(VideoOffloader.GPS_LATITUDE_REF_TAG, DEFAULT_LATITUDE_REF)
                    lon_ref = metadata.get(VideoOffloader.GPS_LONGITUDE_REF_TAG, DEFAULT_LONGITUDE_REF)

                    # Parse DMS format: "37 deg 46' 26.30\" N"
                    # Extract degrees, minutes, seconds
                    lat_match = VideoOffloader.DMS_PATTERN.match(lat_str)
                    lon_match = VideoOffloader.DMS_PATTERN.match(lon_str)

                    if lat_match and lon_match:
                        lat_dms = (int(lat_match.group(1)), int(lat_match.group(2)), float(lat_match.group(3)))
                        lon_dms = (int(lon_match.group(1)), int(lon_match.group(2)), float(lon_match.group(3)))
                        latitude = VideoOffloader._dms_to_decimal(lat_dms, lat_ref)
                        longitude = VideoOffloader._dms_to_decimal(lon_dms, lon_ref)
                        return (latitude, longitude)
                    else:
                        # If DMS format doesn't match, try parsing as decimal format
                        try:
                            lat = float(lat_str)
                            lon = float(lon_str)
                            return (lat, lon)
                        except (ValueError, TypeError):
                            pass
                except (ValueError, TypeError, AttributeError, KeyError):
                    pass

        except (KeyError, TypeError, ValueError, AttributeError):
            pass

        return None

    def _parse_camera_info(self, metadata: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse camera information from video metadata.

        Returns:
            Tuple of (camera_make, camera_model, software)
        """
        camera_make = None
        camera_model = None
        software = None

        for tag in VideoOffloader.CAMERA_MAKE_TAGS:
            if tag in metadata:
                camera_make = str(metadata[tag])
                break

        for tag in VideoOffloader.CAMERA_MODEL_TAGS:
            if tag in metadata:
                camera_model = str(metadata[tag])
                break

        for tag in VideoOffloader.CAMERA_SOFTWARE_TAGS:
            if tag in metadata:
                software = str(metadata[tag])
                break

        return (camera_make, camera_model, software)

    def _extract_metadata(self, file_path: Path) -> VideoMetadata:
        """Extract metadata from a video file."""
        date_taken = None
        location = None
        camera_make = None
        camera_model = None
        software = None

        try:
            # Use exiftool to extract metadata
            # For GoPro videos, use -ee flag to extract embedded GPMF data
            with exiftool.ExifToolHelper() as et:
                # Try with -ee flag first (for GoPro GPMF data)
                try:
                    metadata_list = et.get_metadata([str(file_path)], params=VideoOffloader.EXIFTOOL_EMBEDDED_PARAMS)
                    if metadata_list:
                        metadata = metadata_list[0]
                    else:
                        metadata = {}
                except Exception:
                    # Fallback to regular extraction if -ee fails
                    try:
                        metadata_list = et.get_metadata([str(file_path)])
                        if metadata_list:
                            metadata = metadata_list[0]
                        else:
                            metadata = {}
                    except Exception as e:
                        self.logger.warning("Failed to extract metadata from %s: %s", file_path, e)
                        metadata = {}

                if metadata:
                    date_taken = self._parse_date(metadata)
                    location = self._parse_location(metadata)
                    camera_make, camera_model, software = self._parse_camera_info(metadata)

        except Exception as e:
            # If we can't read the video or extract metadata, continue with None values
            self.logger.warning("Failed to extract metadata from %s: %s", file_path, e)

        return VideoMetadata(
            path=file_path,
            date_taken=date_taken,
            location=location,
            camera_make=camera_make,
            camera_model=camera_model,
            software=software
        )

    def read_videos(self, source_dir: str | Path) -> list[VideoMetadata]:
        """
        Read all video files from the source directory and extract their metadata.

        Args:
            source_dir: Path to the directory where videos are stored

        Returns:
            List of VideoMetadata objects containing path, date_taken, location,
            camera_make, camera_model, and software
        """
        videos_dir = Path(source_dir)
        if not videos_dir.exists():
            raise ValueError(f"Directory does not exist: {source_dir}")
        if not videos_dir.is_dir():
            raise ValueError(f"Path is not a directory: {source_dir}")

        self.logger.debug("Reading videos from %s", source_dir)
        videos = []
        for file_path in videos_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in VideoOffloader.VIDEO_EXTENSIONS:
                video_metadata = self._extract_metadata(file_path)
                videos.append(video_metadata)

        self.logger.info("Read videos from %s, found %d video(s)", source_dir, len(videos))
        return videos

    def _get_bucket_key(self, video: VideoMetadata, group_by: GroupBy) -> str:
        """Get the bucket key for a video based on the group_by parameter."""
        if group_by == GroupBy.SOFTWARE:
            return video.software if video.software is not None else UNKNOWN_BUCKET_KEY
        elif group_by == GroupBy.CAMERA_MAKE:
            return video.camera_make if video.camera_make is not None else UNKNOWN_BUCKET_KEY
        elif group_by == GroupBy.CAMERA_MODEL:
            return video.camera_model if video.camera_model is not None else UNKNOWN_BUCKET_KEY
        elif group_by == GroupBy.YEAR:
            return str(video.date_taken.year) if video.date_taken is not None else UNKNOWN_BUCKET_KEY
        elif group_by == GroupBy.YEAR_MONTH:
            if video.date_taken is not None:
                return f"{video.date_taken.year}{YEAR_MONTH_SEPARATOR}{video.date_taken.month:02d}"
            return UNKNOWN_BUCKET_KEY
        elif group_by == GroupBy.YEAR_MONTH_DAY:
            if video.date_taken is not None:
                return f"{video.date_taken.year}{YEAR_MONTH_SEPARATOR}{video.date_taken.month:02d}{YEAR_MONTH_SEPARATOR}{video.date_taken.day:02d}"
            return UNKNOWN_BUCKET_KEY
        else:
            raise ValueError(f"Unsupported group_by parameter: {group_by}")

    def bucket_videos(self, videos: list[VideoMetadata], group_by: GroupBy) -> dict[str, list[VideoMetadata]]:
        """
        Group videos by a specified parameter.

        Args:
            videos: List of VideoMetadata objects to bucket
            group_by: Enum specifying which parameter to bucket by

        Returns:
            Dictionary where keys are the bucket values and values are lists of VideoMetadata
        """
        self.logger.debug("Bucketing %d video(s) by %s", len(videos), group_by.value)
        buckets: dict[str, list[VideoMetadata]] = {}

        for video in videos:
            key = self._get_bucket_key(video, group_by)
            buckets.setdefault(key, []).append(video)

        self.logger.info("Bucketed %d video(s), created %d bucket(s)", len(videos), len(buckets))
        return buckets

    def _get_sort_key(self, video: VideoMetadata, group_by: GroupBy) -> tuple:
        """
        Get a sort key for a video based on the group_by parameter.
        Returns a tuple that can be used for sorting, with Unknown values sorting last.
        """
        if group_by == GroupBy.SOFTWARE:
            return (0, video.software) if video.software is not None else (1, UNKNOWN_BUCKET_KEY)
        elif group_by == GroupBy.CAMERA_MAKE:
            return (0, video.camera_make) if video.camera_make is not None else (1, UNKNOWN_BUCKET_KEY)
        elif group_by == GroupBy.CAMERA_MODEL:
            return (0, video.camera_model) if video.camera_model is not None else (1, UNKNOWN_BUCKET_KEY)
        elif group_by == GroupBy.YEAR:
            if video.date_taken is not None:
                return (0, video.date_taken.year)
            return (1, datetime.max)
        elif group_by == GroupBy.YEAR_MONTH:
            if video.date_taken is not None:
                return (0, video.date_taken.year, video.date_taken.month)
            return (1, datetime.max)
        elif group_by == GroupBy.YEAR_MONTH_DAY:
            if video.date_taken is not None:
                return (0, video.date_taken)
            return (1, datetime.max)
        else:
            raise ValueError(f"Unsupported group_by parameter: {group_by}")

    def sort_videos(self, videos: list[VideoMetadata], group_by: GroupBy) -> list[VideoMetadata]:
        """
        Sort videos by a specified parameter.

        Args:
            videos: List of VideoMetadata objects to sort
            group_by: Enum specifying which parameter to sort by

        Returns:
            Sorted list of VideoMetadata objects
        """
        self.logger.debug("Sorting %d video(s) by %s", len(videos), group_by.value)
        sorted_videos = sorted(videos, key=lambda video: self._get_sort_key(video, group_by))
        self.logger.info("Sorted %d video(s)", len(videos))
        return sorted_videos

    def copy_videos(self, videos: list[VideoMetadata], destination: str | Path) -> None:
        """
        Copy videos to a destination directory.

        Args:
            videos: List of VideoMetadata objects to copy
            destination: Path to the destination directory
        """
        self.logger.debug("Copying %d video(s) to %s", len(videos), destination)
        dest_path = Path(destination)

        # Create destination directory if it doesn't exist
        dest_path.mkdir(parents=True, exist_ok=True)

        for video in videos:
            try:
                # Copy the file to the destination, preserving the filename
                shutil.copy2(video.path, dest_path / video.path.name)
                self.logger.debug("Copied %s to %s", video.path.name, destination)
            except Exception as e:
                # Log or handle the error, but continue with other videos
                # In a production system, you might want to collect errors and return them
                self.logger.error("Failed to copy %s to %s: %s", video.path, destination, e)
                raise RuntimeError(f"Failed to copy {video.path} to {destination}: {e}") from e

        self.logger.info("Copied %d video(s) to %s", len(videos), destination)

    def archive_videos(self, videos: list[VideoMetadata], destination: str | Path) -> None:
        """
        Archive videos to a destination directory by copying them and then compressing
        them into a zip file. The original videos are removed after archiving.

        Args:
            videos: List of VideoMetadata objects to archive
            destination: Path to the destination directory (leaf directory where zip will be created)
        """
        self.logger.debug("Archiving %d video(s) to %s", len(videos), destination)
        dest_path = Path(destination)

        # First, copy videos to the destination directory
        self.copy_videos(videos, destination)

        # Create zip file in the destination directory
        zip_path = dest_path / VideoOffloader.ARCHIVE_FILENAME
        self.logger.debug("Creating zip archive at %s", zip_path)

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all video files in the destination directory to the zip
                for video_file in dest_path.iterdir():
                    if video_file.is_file() and video_file.suffix.lower() in VideoOffloader.VIDEO_EXTENSIONS:
                        zipf.write(video_file, video_file.name)
                        self.logger.debug("Added %s to archive", video_file.name)

            # Remove the original video files after archiving
            removed_count = 0
            for video_file in dest_path.iterdir():
                if video_file.is_file() and video_file.suffix.lower() in VideoOffloader.VIDEO_EXTENSIONS:
                    video_file.unlink()
                    removed_count += 1

            self.logger.info("Archived %d video(s) to %s", len(videos), zip_path)
        except Exception as e:
            self.logger.error("Failed to create archive at %s: %s", zip_path, e)
            raise RuntimeError(f"Failed to create archive at {zip_path}: {e}") from e

    def _save_videos(self, videos: list[VideoMetadata], destination: Path, to_archive: bool) -> None:
        """
        Save videos to a destination directory, either by copying or archiving.

        Args:
            videos: List of VideoMetadata objects to save
            destination: Path to the destination directory
            to_archive: If True, archive videos into zip files instead of copying them
        """
        destination.mkdir(parents=True, exist_ok=True)
        if to_archive:
            self.archive_videos(videos, destination)
        else:
            self.copy_videos(videos, destination)

    def offload_videos(self, source_dir: str | Path, destination_dir: str | Path, to_archive: bool = False, keep_unknown: bool = True) -> None:
        """
        Read videos from source directory, bucket by year-month, and copy or archive to destination
        organized in year=X/month=Y directory structure.

        Args:
            source_dir: Path to the source directory containing videos
            destination_dir: Path to the destination directory
            to_archive: If True, archive videos into zip files instead of copying them
            keep_unknown: If True, save files with unknown bucket key and/or invalid year-month separators
                         to the unknown directory. If False, skip them with a log message.
        """
        self.logger.debug("Offloading videos from %s to %s", source_dir, destination_dir)
        videos = self.read_videos(source_dir)

        # Bucket videos by year-month
        buckets = self.bucket_videos(videos, GroupBy.YEAR_MONTH)

        dest_path = Path(destination_dir)
        dest_path.mkdir(parents=True, exist_ok=True)

        # Process each bucket
        unknown_count = 0
        invalid_format_count = 0
        for year_month, bucket_videos in buckets.items():
            if year_month == UNKNOWN_BUCKET_KEY:
                unknown_count += len(bucket_videos)
                if keep_unknown:
                    # Save videos without date information to unknown directory
                    unknown_dir = dest_path / UNKNOWN_DIRECTORY
                    self.logger.info("Processing %d video(s) without date information", len(bucket_videos))
                    self._save_videos(bucket_videos, unknown_dir, to_archive)
                else:
                    # Skip videos without date information
                    for video in bucket_videos:
                        self.logger.info("Skipping video %s: missing date information", video.path)
                continue

            # Parse year-month string (format: "YYYY-MM")
            try:
                year, month = year_month.split(YEAR_MONTH_SEPARATOR)
                year = int(year)
                month = int(month)
            except ValueError:
                invalid_format_count += len(bucket_videos)
                if keep_unknown:
                    # Save videos with invalid year-month format to unknown directory
                    unknown_dir = dest_path / UNKNOWN_DIRECTORY
                    self.logger.info("Processing %d video(s) with invalid year-month format (%s) to unknown directory", len(bucket_videos), year_month)
                    self._save_videos(bucket_videos, unknown_dir, to_archive)
                else:
                    # Skip videos with invalid year-month format
                    for video in bucket_videos:
                        self.logger.info("Skipping video %s: invalid year-month format (%s)", video.path, year_month)
                continue

            # Create directory structure: year=X/month=YY (HDFS format with padded month)
            month_dir = dest_path / f"{YEAR_PREFIX}{year}" / f"{MONTH_PREFIX}{month:02d}"
            self.logger.info("Processing %d video(s) for %s", len(bucket_videos), year_month)
            self._save_videos(bucket_videos, month_dir, to_archive)

        # Log photos that were saved to unknown directory or skipped
        if unknown_count > 0:
            if keep_unknown:
                self.logger.info("%d video(s) were saved to unknown directory due to missing date information", unknown_count)
            else:
                self.logger.info("%d video(s) were skipped due to missing date information", unknown_count)
        if invalid_format_count > 0:
            if keep_unknown:
                self.logger.info("%d video(s) were saved to unknown directory due to invalid year-month format", invalid_format_count)
            else:
                self.logger.info("%d video(s) were skipped due to invalid year-month format", invalid_format_count)
        self.logger.info("Offloaded videos from %s to %s", source_dir, destination_dir)
