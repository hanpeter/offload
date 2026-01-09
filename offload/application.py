# -*- coding: utf-8 -*-
import logging
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from PIL import Image
from PIL.ExifTags import GPS, TAGS
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # pillow-heif not available, HEIC files may not work


@dataclass
class PhotoMetadata:
    """Metadata extracted from a photo file."""
    path: Path
    date_taken: Optional[datetime] = None
    location: Optional[tuple[float, float]] = None  # (latitude, longitude)
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None  # Application/software used to take the photo


class GroupBy(Enum):
    """Enum for photo grouping and sorting parameters."""
    SOFTWARE = "software"
    CAMERA_MAKE = "camera_make"
    CAMERA_MODEL = "camera_model"
    YEAR = "year"
    YEAR_MONTH = "year_month"
    YEAR_MONTH_DAY = "year_month_day"


class Application:
    # Supported photo file extensions
    # TODO: Allow this to be configured via environment variable
    PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.heif'}

    # EXIF tag ID for GPSInfo (GPS IFD)
    GPS_INFO_TAG_ID = 34853

    def __init__(self, logger: logging.Logger):
        """
        Initialize the Application.

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
        return -decimal if ref in ['S', 'W'] else decimal

    def _parse_exif_date(self, exif_data: dict) -> Optional[datetime]:
        """Parse date taken from EXIF data."""
        # Try different date fields in order of preference
        date_fields = ['DateTimeOriginal', 'DateTimeDigitized', 'DateTime']
        for field in date_fields:
            if field in exif_data:
                try:
                    date_str = exif_data[field]
                    # EXIF date format: "YYYY:MM:DD HH:MM:SS"
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                except (ValueError, TypeError):
                    continue
        return None

    def _parse_exif_location(self, exif_data, exif_dict: dict) -> Optional[tuple[float, float]]:
        """
        Parse GPS location from EXIF data.

        Args:
            exif_data: Raw PIL Exif object (for accessing GPS IFD)
            exif_dict: Dictionary of EXIF tags converted to string names
        """
        # Check if GPSInfo exists in the raw EXIF data
        if Application.GPS_INFO_TAG_ID not in exif_data:
            return None

        try:
            # GPSInfo may be stored as an integer IFD offset, use get_ifd() to get the actual GPS IFD
            gps_info = exif_data.get_ifd(Application.GPS_INFO_TAG_ID)

            # GPS coordinates are stored as tuples of (degrees, minutes, seconds)
            # GPS tag IDs: 1=LatitudeRef, 2=Latitude, 3=LongitudeRef, 4=Longitude
            lat_ref = gps_info.get(1, 'N')
            lat_data = gps_info.get(2)
            lon_ref = gps_info.get(3, 'E')
            lon_data = gps_info.get(4)

            if lat_data is None or lon_data is None:
                return None

            latitude = Application._dms_to_decimal(lat_data, lat_ref)
            longitude = Application._dms_to_decimal(lon_data, lon_ref)

            return (latitude, longitude)
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            return None

    def _parse_exif_camera_info(self, exif_data: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse camera information from EXIF data.

        Returns:
            Tuple of (camera_make, camera_model, software)
        """
        camera_make = exif_data.get('Make')
        camera_model = exif_data.get('Model')
        software = exif_data.get('Software')

        # Convert to string if not None
        camera_make = str(camera_make) if camera_make is not None else None
        camera_model = str(camera_model) if camera_model is not None else None
        software = str(software) if software is not None else None

        return (camera_make, camera_model, software)

    def _extract_metadata(self, file_path: Path) -> PhotoMetadata:
        """Extract metadata from a photo file."""
        date_taken = None
        location = None
        camera_make = None
        camera_model = None
        software = None

        try:
            with Image.open(file_path) as img:
                exif_data = img.getexif()
                if exif_data:
                    # Convert EXIF to a more usable format
                    exif_dict = {}
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        exif_dict[tag] = value

                    date_taken = self._parse_exif_date(exif_dict)
                    location = self._parse_exif_location(exif_data, exif_dict)
                    camera_make, camera_model, software = self._parse_exif_camera_info(exif_dict)
        except Exception as e:
            # If we can't read the image or extract metadata, continue with None values
            self.logger.warning("Failed to extract metadata from %s: %s", file_path, e)

        return PhotoMetadata(
            path=file_path,
            date_taken=date_taken,
            location=location,
            camera_make=camera_make,
            camera_model=camera_model,
            software=software
        )

    def read_photos(self, source_dir: str | Path) -> list[PhotoMetadata]:
        """
        Read all photo files from the source directory and extract their metadata.

        Args:
            source_dir: Path to the directory where photos are stored

        Returns:
            List of PhotoMetadata objects containing path, date_taken, location,
            camera_make, camera_model, and software
        """
        photos_dir = Path(source_dir)
        if not photos_dir.exists():
            raise ValueError(f"Directory does not exist: {source_dir}")
        if not photos_dir.is_dir():
            raise ValueError(f"Path is not a directory: {source_dir}")

        self.logger.debug("Reading photos from %s", source_dir)
        photos = []
        for file_path in photos_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in Application.PHOTO_EXTENSIONS:
                photo_metadata = self._extract_metadata(file_path)
                photos.append(photo_metadata)

        self.logger.info("Read photos from %s, found %d photo(s)", source_dir, len(photos))
        return photos

    def _get_bucket_key(self, photo: PhotoMetadata, group_by: GroupBy) -> str:
        """Get the bucket key for a photo based on the group_by parameter."""
        if group_by == GroupBy.SOFTWARE:
            return photo.software if photo.software is not None else "Unknown"
        elif group_by == GroupBy.CAMERA_MAKE:
            return photo.camera_make if photo.camera_make is not None else "Unknown"
        elif group_by == GroupBy.CAMERA_MODEL:
            return photo.camera_model if photo.camera_model is not None else "Unknown"
        elif group_by == GroupBy.YEAR:
            return str(photo.date_taken.year) if photo.date_taken is not None else "Unknown"
        elif group_by == GroupBy.YEAR_MONTH:
            if photo.date_taken is not None:
                return f"{photo.date_taken.year}-{photo.date_taken.month:02d}"
            return "Unknown"
        elif group_by == GroupBy.YEAR_MONTH_DAY:
            if photo.date_taken is not None:
                return f"{photo.date_taken.year}-{photo.date_taken.month:02d}-{photo.date_taken.day:02d}"
            return "Unknown"
        else:
            raise ValueError(f"Unsupported group_by parameter: {group_by}")

    def bucket_photos(self, photos: list[PhotoMetadata], group_by: GroupBy) -> dict[str, list[PhotoMetadata]]:
        """
        Group photos by a specified parameter.

        Args:
            photos: List of PhotoMetadata objects to bucket
            group_by: Enum specifying which parameter to bucket by

        Returns:
            Dictionary where keys are the bucket values and values are lists of PhotoMetadata
        """
        self.logger.debug("Bucketing %d photo(s) by %s", len(photos), group_by.value)
        buckets: dict[str, list[PhotoMetadata]] = {}

        for photo in photos:
            key = self._get_bucket_key(photo, group_by)
            buckets.setdefault(key, []).append(photo)

        self.logger.info("Bucketed %d photo(s), created %d bucket(s)", len(photos), len(buckets))
        return buckets

    def _get_sort_key(self, photo: PhotoMetadata, group_by: GroupBy) -> tuple:
        """
        Get a sort key for a photo based on the group_by parameter.
        Returns a tuple that can be used for sorting, with Unknown values sorting last.
        """
        if group_by == GroupBy.SOFTWARE:
            return (0, photo.software) if photo.software is not None else (1, "Unknown")
        elif group_by == GroupBy.CAMERA_MAKE:
            return (0, photo.camera_make) if photo.camera_make is not None else (1, "Unknown")
        elif group_by == GroupBy.CAMERA_MODEL:
            return (0, photo.camera_model) if photo.camera_model is not None else (1, "Unknown")
        elif group_by == GroupBy.YEAR:
            if photo.date_taken is not None:
                return (0, photo.date_taken.year)
            return (1, datetime.max)
        elif group_by == GroupBy.YEAR_MONTH:
            if photo.date_taken is not None:
                return (0, photo.date_taken.year, photo.date_taken.month)
            return (1, datetime.max)
        elif group_by == GroupBy.YEAR_MONTH_DAY:
            if photo.date_taken is not None:
                return (0, photo.date_taken)
            return (1, datetime.max)
        else:
            raise ValueError(f"Unsupported group_by parameter: {group_by}")

    def sort_photos(self, photos: list[PhotoMetadata], group_by: GroupBy) -> list[PhotoMetadata]:
        """
        Sort photos by a specified parameter.

        Args:
            photos: List of PhotoMetadata objects to sort
            group_by: Enum specifying which parameter to sort by

        Returns:
            Sorted list of PhotoMetadata objects
        """
        self.logger.debug("Sorting %d photo(s) by %s", len(photos), group_by.value)
        sorted_photos = sorted(photos, key=lambda photo: self._get_sort_key(photo, group_by))
        self.logger.info("Sorted %d photo(s)", len(photos))
        return sorted_photos

    def copy_photos(self, photos: list[PhotoMetadata], destination: str | Path) -> None:
        """
        Copy photos to a destination directory.

        Args:
            photos: List of PhotoMetadata objects to copy
            destination: Path to the destination directory
        """
        self.logger.debug("Copying %d photo(s) to %s", len(photos), destination)
        dest_path = Path(destination)

        # Create destination directory if it doesn't exist
        dest_path.mkdir(parents=True, exist_ok=True)

        for photo in photos:
            try:
                # Copy the file to the destination, preserving the filename
                shutil.copy2(photo.path, dest_path / photo.path.name)
                self.logger.debug("Copied %s to %s", photo.path.name, destination)
            except Exception as e:
                # Log or handle the error, but continue with other photos
                # In a production system, you might want to collect errors and return them
                self.logger.error("Failed to copy %s to %s: %s", photo.path, destination, e)
                raise RuntimeError(f"Failed to copy {photo.path} to {destination}: {e}") from e

        self.logger.info("Copied %d photo(s) to %s", len(photos), destination)

    def archive_photos(self, photos: list[PhotoMetadata], destination: str | Path) -> None:
        """
        Archive photos to a destination directory by copying them and then compressing
        them into a zip file. The original photos are removed after archiving.

        Args:
            photos: List of PhotoMetadata objects to archive
            destination: Path to the destination directory (leaf directory where zip will be created)
        """
        self.logger.debug("Archiving %d photo(s) to %s", len(photos), destination)
        dest_path = Path(destination)

        # First, copy photos to the destination directory
        self.copy_photos(photos, destination)

        # Create zip file in the destination directory
        zip_path = dest_path / "photos.zip"
        self.logger.debug("Creating zip archive at %s", zip_path)

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all photo files in the destination directory to the zip
                for photo_file in dest_path.iterdir():
                    if photo_file.is_file() and photo_file.suffix.lower() in Application.PHOTO_EXTENSIONS:
                        zipf.write(photo_file, photo_file.name)
                        self.logger.debug("Added %s to archive", photo_file.name)

            # Remove the original photo files after archiving
            removed_count = 0
            for photo_file in dest_path.iterdir():
                if photo_file.is_file() and photo_file.suffix.lower() in Application.PHOTO_EXTENSIONS:
                    photo_file.unlink()
                    removed_count += 1

            self.logger.info("Archived %d photo(s) to %s", len(photos), zip_path)
        except Exception as e:
            self.logger.error("Failed to create archive at %s: %s", zip_path, e)
            raise RuntimeError(f"Failed to create archive at {zip_path}: {e}") from e

    def _save_photos(self, photos: list[PhotoMetadata], destination: Path, to_archive: bool) -> None:
        """
        Save photos to a destination directory, either by copying or archiving.

        Args:
            photos: List of PhotoMetadata objects to save
            destination: Path to the destination directory
            to_archive: If True, archive photos into zip files instead of copying them
        """
        destination.mkdir(parents=True, exist_ok=True)
        if to_archive:
            self.archive_photos(photos, destination)
        else:
            self.copy_photos(photos, destination)

    def offload_photos(self, source_dir: str | Path, destination_dir: str | Path, to_archive: bool = False) -> None:
        """
        Read photos from source directory, bucket by year-month, and copy or archive to destination
        organized in year=X/month=Y directory structure.

        Args:
            source_dir: Path to the source directory containing photos
            destination_dir: Path to the destination directory
            to_archive: If True, archive photos into zip files instead of copying them
        """
        self.logger.debug("Offloading photos from %s to %s", source_dir, destination_dir)
        photos = self.read_photos(source_dir)

        # Bucket photos by year-month
        buckets = self.bucket_photos(photos, GroupBy.YEAR_MONTH)

        dest_path = Path(destination_dir)
        dest_path.mkdir(parents=True, exist_ok=True)

        # Process each bucket
        unknown_count = 0
        invalid_format_count = 0
        for year_month, bucket_photos in buckets.items():
            if year_month == "Unknown":
                # Save photos without date information to unknown directory
                unknown_dir = dest_path / "unknown"
                unknown_count += len(bucket_photos)
                self.logger.info("Processing %d photo(s) without date information", len(bucket_photos))
                self._save_photos(bucket_photos, unknown_dir, to_archive)
                continue

            # Parse year-month string (format: "YYYY-MM")
            try:
                year, month = year_month.split("-")
                year = int(year)
                month = int(month)
            except ValueError:
                # Save photos with invalid year-month format to unknown directory
                unknown_dir = dest_path / "unknown"
                invalid_format_count += len(bucket_photos)
                self.logger.warning("Processing %d photo(s) with invalid year-month format (%s) to unknown directory", len(bucket_photos), year_month)
                self._save_photos(bucket_photos, unknown_dir, to_archive)
                continue

            # Create directory structure: year=X/month=YY (HDFS format with padded month)
            month_dir = dest_path / f"year={year}" / f"month={month:02d}"
            self.logger.info("Processing %d photo(s) for %s", len(bucket_photos), year_month)
            self._save_photos(bucket_photos, month_dir, to_archive)

        # Log warnings for photos that were saved to unknown directory
        if unknown_count > 0:
            self.logger.warning("%d photo(s) were saved to unknown directory due to missing date information", unknown_count)
        if invalid_format_count > 0:
            self.logger.warning("%d photo(s) were saved to unknown directory due to invalid year-month format", invalid_format_count)
        self.logger.info("Offloaded photos from %s to %s", source_dir, destination_dir)
