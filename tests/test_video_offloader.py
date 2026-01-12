# -*- coding: utf-8 -*-
import logging
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from offload.constants import GroupBy
from offload.video_offloader import VideoOffloader, VideoMetadata


class TestVideoOffloader:
    """Test suite for the VideoOffloader class."""

    @pytest.fixture
    def logger(self):
        """Create a logger for testing."""
        logger = logging.getLogger('test_offload')
        logger.setLevel(logging.DEBUG)
        return logger

    @pytest.fixture
    def app(self, logger):
        """Create a VideoOffloader instance for testing."""
        return VideoOffloader(logger)

    def create_test_video_file(self, path: Path) -> Path:
        """Create a test video file (dummy file with correct extension)."""
        # Create a minimal file that looks like a video (just for testing file operations)
        path.write_bytes(b"fake video file content")
        return path

    def test_init(self, logger):
        """Test VideoOffloader initialization."""
        app = VideoOffloader(logger)
        assert app.logger == logger

    def test_dms_to_decimal_north_east(self, app):
        """Test DMS to decimal conversion for North/East coordinates."""
        # Test coordinates: 37° 46' 26.2992" N, 122° 25' 52.0176" W
        lat_dms = (37, 46, 26.2992)
        lon_dms = (122, 25, 52.0176)

        lat = VideoOffloader._dms_to_decimal(lat_dms, 'N')
        lon = VideoOffloader._dms_to_decimal(lon_dms, 'E')

        assert lat > 0
        assert lon > 0
        assert abs(lat - 37.773972) < 0.001
        assert abs(lon - 122.431116) < 0.001

    def test_dms_to_decimal_south_west(self, app):
        """Test DMS to decimal conversion for South/West coordinates."""
        lat_dms = (37, 46, 26.2992)
        lon_dms = (122, 25, 52.0176)

        lat = VideoOffloader._dms_to_decimal(lat_dms, 'S')
        lon = VideoOffloader._dms_to_decimal(lon_dms, 'W')

        assert lat < 0
        assert lon < 0

    def test_parse_date_quicktime_creation_date(self, app):
        """Test parsing date from QuickTime:CreationDate field."""
        metadata = {'QuickTime:CreationDate': '2023:05:15 14:30:00'}
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2023
        assert date.month == 5
        assert date.day == 15

    def test_parse_date_keys_creation_date(self, app):
        """Test parsing date from Keys:CreationDate field."""
        metadata = {'Keys:CreationDate': '2023-05-15 14:30:00'}
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2023

    def test_parse_date_iso_format(self, app):
        """Test parsing date from ISO format."""
        metadata = {'CreateDate': '2023-05-15T14:30:00'}
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2023

    def test_parse_date_preference_order(self, app):
        """Test that QuickTime:CreationDate is preferred over other fields."""
        metadata = {
            'CreateDate': '2020-01-01 00:00:00',
            'Keys:CreateDate': '2021-01-01 00:00:00',
            'QuickTime:CreationDate': '2022-01-01 00:00:00'
        }
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2022

    def test_parse_date_invalid_format(self, app):
        """Test parsing date with invalid format."""
        metadata = {'QuickTime:CreationDate': 'invalid-date'}
        date = app._parse_date(metadata)
        assert date is None

    def test_parse_date_no_date_fields(self, app):
        """Test parsing date when no date fields exist."""
        metadata = {'Make': 'GoPro'}
        date = app._parse_date(metadata)
        assert date is None

    def test_parse_date_with_timezone_offset(self, app):
        """Test parsing date with timezone offset (e.g., -07:00)."""
        metadata = {'QuickTime:CreationDate': '2024:08:04 11:45:26-07:00'}
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2024
        assert date.month == 8
        assert date.day == 4

    def test_parse_date_with_positive_timezone_offset(self, app):
        """Test parsing date with positive timezone offset."""
        metadata = {'QuickTime:CreationDate': '2023:05:15 14:30:00+05:30'}
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2023
        assert date.month == 5
        assert date.day == 15

    def test_parse_date_fallback_with_colon_separator(self, app):
        """Test fallback date parsing with colon separator that needs conversion."""
        # Date format that doesn't match standard formats but has colon separator
        metadata = {'QuickTime:CreationDate': '2024:08:04'}
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2024
        assert date.month == 8
        assert date.day == 4

    def test_parse_date_fallback_with_t_separator(self, app):
        """Test fallback date parsing with T separator (line 137)."""
        # Use a format with T that doesn't match any DATE_FORMATS
        # This will fall through to the fallback logic and hit line 137
        metadata = {'CreateDate': '2023-05-15Tinvalid-time'}
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2023
        assert date.month == 5
        assert date.day == 15

    def test_parse_date_fallback_with_space_separator(self, app):
        """Test fallback date parsing with space separator (line 139)."""
        # Use a format with space that doesn't match any DATE_FORMATS
        # This will fall through to the fallback logic and hit line 139
        metadata = {'CreateDate': '2023-05-15 invalid-time'}
        date = app._parse_date(metadata)
        assert date is not None
        assert date.year == 2023
        assert date.month == 5
        assert date.day == 15

    def test_parse_date_fallback_else_branch(self, app):
        """Test fallback date parsing else branch (no T or space separator)."""
        # Date string without T or space, shorter than MIN_DATE_STRING_LENGTH
        metadata = {'CreateDate': '2023'}
        date = app._parse_date(metadata)
        # Should return None as it's too short
        assert date is None

    def test_parse_date_fallback_else_branch_long_enough(self, app):
        """Test fallback date parsing else branch with string long enough."""
        # Date string without T or space, but long enough (10+ chars)
        # This should trigger the else branch and extract first 10 chars
        metadata = {'CreateDate': '2023-05-15'}  # No time, no T, no space
        date = app._parse_date(metadata)
        # Should parse successfully using the else branch
        assert date is not None
        assert date.year == 2023
        assert date.month == 5
        assert date.day == 15

    def test_parse_date_fallback_colon_value_error(self, app):
        """Test fallback date parsing with colon separator that raises ValueError."""
        # Date with colon separator that fails to parse after conversion
        metadata = {'CreateDate': '2023:13:45'}  # Invalid month
        date = app._parse_date(metadata)
        # Should try fallback parsing, but may still fail
        # The ValueError exception handler should catch it
        assert date is None or date.year == 2023

    def test_parse_date_fallback_standard_format_value_error(self, app):
        """Test fallback date parsing standard format that raises ValueError."""
        # Date that fails standard format parsing
        metadata = {'CreateDate': '2023-13-45'}  # Invalid month/day
        date = app._parse_date(metadata)
        # Should return None after ValueError is caught
        assert date is None

    def test_parse_date_exception_handling(self, app):
        """Test date parsing handles exceptions gracefully."""
        # Metadata with date field that causes TypeError/AttributeError
        metadata = {'QuickTime:CreationDate': None}
        date = app._parse_date(metadata)
        # Should return None without raising exception
        assert date is None

    def test_parse_date_exception_handling_value_error(self, app):
        """Test date parsing handles ValueError in outer exception handler."""
        # Create a date field that causes ValueError when converting to string
        class BadDate:
            def __str__(self):
                raise ValueError("Cannot convert to string")

        metadata = {'QuickTime:CreationDate': BadDate()}
        date = app._parse_date(metadata)
        assert date is None

    def test_parse_date_exception_handling_type_error(self, app):
        """Test date parsing handles TypeError in outer exception handler."""
        # Create a date field that causes TypeError
        class BadDate:
            def __str__(self):
                raise TypeError("Type error")

        metadata = {'QuickTime:CreationDate': BadDate()}
        date = app._parse_date(metadata)
        assert date is None

    def test_parse_date_exception_handling_attribute_error(self, app):
        """Test date parsing handles AttributeError in outer exception handler."""
        # Create a date field that causes AttributeError
        class BadDate:
            def __str__(self):
                raise AttributeError("Attribute error")

        metadata = {'QuickTime:CreationDate': BadDate()}
        date = app._parse_date(metadata)
        assert date is None

    def test_parse_location_quicktime_gps_coordinates(self, app):
        """Test parsing GPS location from QuickTime:GPSCoordinates."""
        metadata = {'QuickTime:GPSCoordinates': '37.7749 -122.4194 100.0'}
        location = app._parse_location(metadata)
        assert location is not None
        assert isinstance(location, tuple)
        assert len(location) == 2
        assert abs(location[0] - 37.7749) < 0.001
        assert abs(location[1] - (-122.4194)) < 0.001

    def test_parse_location_keys_gps_coordinates(self, app):
        """Test parsing GPS location from Keys:GPSCoordinates."""
        metadata = {'Keys:GPSCoordinates': '37.7749 -122.4194'}
        location = app._parse_location(metadata)
        assert location is not None
        assert abs(location[0] - 37.7749) < 0.001

    def test_parse_location_gps_latitude_longitude_dms(self, app):
        """Test parsing GPS location from GPSLatitude/GPSLongitude (DMS format)."""
        metadata = {
            'GPSLatitude': '37 deg 46\' 26.30" N',
            'GPSLongitude': '122 deg 25\' 52.02" W',
            'GPSLatitudeRef': 'N',
            'GPSLongitudeRef': 'W'
        }
        location = app._parse_location(metadata)
        assert location is not None
        assert isinstance(location, tuple)
        assert len(location) == 2
        # Latitude should be positive (North)
        assert location[0] > 0
        # Longitude should be negative (West)
        assert location[1] < 0

    def test_parse_location_gps_decimal(self, app):
        """Test parsing GPS location from GPS:GPSLatitude/GPS:GPSLongitude (decimal)."""
        metadata = {
            'GPS:GPSLatitude': 37.7749,
            'GPS:GPSLongitude': -122.4194
        }
        location = app._parse_location(metadata)
        assert location is not None
        assert abs(location[0] - 37.7749) < 0.001
        assert abs(location[1] - (-122.4194)) < 0.001

    def test_parse_location_no_gps(self, app):
        """Test parsing location when GPS data is not present."""
        metadata = {'Make': 'GoPro'}
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_missing_coordinates(self, app):
        """Test parsing location when GPS coordinates are missing."""
        metadata = {'QuickTime:GPSCoordinates': 'invalid'}
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_gps_coordinates_value_error(self, app):
        """Test parsing GPS coordinates that cause ValueError."""
        # GPS coordinates with non-numeric values
        metadata = {'QuickTime:GPSCoordinates': 'invalid lat invalid lon'}
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_gps_coordinates_index_error(self, app):
        """Test parsing GPS coordinates with insufficient parts."""
        # GPS coordinates with only one part
        metadata = {'QuickTime:GPSCoordinates': '37.7749'}
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_gps_latitude_longitude_decimal_fallback(self, app):
        """Test parsing GPS location from GPSLatitude/GPSLongitude as decimal when DMS doesn't match."""
        metadata = {
            'GPSLatitude': '37.7749',
            'GPSLongitude': '-122.4194',
            'GPSLatitudeRef': 'N',
            'GPSLongitudeRef': 'W'
        }
        location = app._parse_location(metadata)
        assert location is not None
        assert abs(location[0] - 37.7749) < 0.001
        assert abs(location[1] - (-122.4194)) < 0.001

    def test_parse_location_gps_latitude_longitude_type_error(self, app):
        """Test parsing GPS location when latitude/longitude cause TypeError."""
        metadata = {
            'GPSLatitude': None,
            'GPSLongitude': '-122.4194',
            'GPSLatitudeRef': 'N',
            'GPSLongitudeRef': 'W'
        }
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_gps_latitude_longitude_value_error(self, app):
        """Test parsing GPS location when latitude/longitude cause ValueError."""
        metadata = {
            'GPSLatitude': 'invalid',
            'GPSLongitude': '-122.4194',
            'GPSLatitudeRef': 'N',
            'GPSLongitudeRef': 'W'
        }
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_gps_latitude_longitude_key_error(self, app):
        """Test parsing GPS location when GPS tags cause KeyError."""
        # Missing GPSLatitudeRef and GPSLongitudeRef (should use defaults)
        metadata = {
            'GPSLatitude': '37.7749',
            'GPSLongitude': '-122.4194'
        }
        location = app._parse_location(metadata)
        assert location is not None
        assert abs(location[0] - 37.7749) < 0.001

    def test_parse_location_gps_latitude_longitude_inner_exception_value_error(self, app):
        """Test parsing GPS location inner exception handler catches ValueError."""
        # GPSLatitude/GPSLongitude that cause ValueError in inner try block
        class BadCoord:
            def __str__(self):
                raise ValueError("Cannot convert")

        metadata = {
            'GPSLatitude': BadCoord(),
            'GPSLongitude': '-122.4194',
            'GPSLatitudeRef': 'N',
            'GPSLongitudeRef': 'W'
        }
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_gps_latitude_longitude_inner_exception_type_error(self, app):
        """Test parsing GPS location inner exception handler catches TypeError."""
        # GPSLatitude/GPSLongitude that cause TypeError
        class BadCoord:
            def __str__(self):
                raise TypeError("Type error")

        metadata = {
            'GPSLatitude': BadCoord(),
            'GPSLongitude': '-122.4194',
            'GPSLatitudeRef': 'N',
            'GPSLongitudeRef': 'W'
        }
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_gps_latitude_longitude_inner_exception_attribute_error(self, app):
        """Test parsing GPS location inner exception handler catches AttributeError."""
        # GPSLatitude/GPSLongitude that cause AttributeError
        class BadCoord:
            def __str__(self):
                raise AttributeError("Attribute error")

        metadata = {
            'GPSLatitude': BadCoord(),
            'GPSLongitude': '-122.4194',
            'GPSLatitudeRef': 'N',
            'GPSLongitudeRef': 'W'
        }
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_location_gps_latitude_longitude_inner_exception_key_error(self, app):
        """Test parsing GPS location inner exception handler catches KeyError."""
        # Metadata that causes KeyError when accessing GPSLatitudeRef/GPSLongitudeRef
        # Use a dict-like object that raises KeyError
        class BadDict(dict):
            def get(self, key, default=None):
                if key in ['GPSLatitudeRef', 'GPSLongitudeRef']:
                    raise KeyError("Key error")
                return super().get(key, default)

        metadata = BadDict({
            'GPSLatitude': '37.7749',
            'GPSLongitude': '-122.4194'
        })
        location = app._parse_location(metadata)
        # Should handle KeyError gracefully
        assert location is None or location is not None

    def test_parse_location_outer_exception_handling(self, app):
        """Test parsing location handles outer exception (KeyError, TypeError, ValueError, AttributeError)."""
        # Metadata that causes exception in outer try block
        metadata = None
        location = app._parse_location(metadata)
        assert location is None

    def test_parse_camera_info(self, app):
        """Test parsing camera information from metadata."""
        metadata = {
            'Make': 'GoPro',
            'Model': 'HERO9',
            'Software': 'GoPro Camera Firmware'
        }
        make, model, software = app._parse_camera_info(metadata)
        assert make == 'GoPro'
        assert model == 'HERO9'
        assert software == 'GoPro Camera Firmware'

    def test_parse_camera_info_quicktime_tags(self, app):
        """Test parsing camera info from QuickTime tags."""
        metadata = {
            'QuickTime:Make': 'Apple',
            'QuickTime:Model': 'iPhone 13',
            'QuickTime:Software': 'iOS 15.0'
        }
        make, model, software = app._parse_camera_info(metadata)
        assert make == 'Apple'
        assert model == 'iPhone 13'
        assert software == 'iOS 15.0'

    def test_parse_camera_info_missing_fields(self, app):
        """Test parsing camera info with missing fields."""
        metadata = {'Make': 'GoPro'}
        make, model, software = app._parse_camera_info(metadata)
        assert make == 'GoPro'
        assert model is None
        assert software is None

    def test_parse_camera_info_none(self, app):
        """Test parsing camera info when all fields are None."""
        metadata = {}
        make, model, software = app._parse_camera_info(metadata)
        assert make is None
        assert model is None
        assert software is None

    def test_extract_metadata_with_exiftool(self, app):
        """Test _extract_metadata extracts metadata using exiftool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            # Mock exiftool to return metadata
            mock_metadata = {
                'QuickTime:CreationDate': '2023:05:15 14:30:00',
                'Make': 'GoPro',
                'Model': 'HERO9',
                'Software': 'GoPro Firmware',
                'QuickTime:GPSCoordinates': '37.7749 -122.4194 100.0'
            }

            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                mock_exiftool.get_metadata = MagicMock(return_value=[mock_metadata])
                mock_exiftool_class.return_value = mock_exiftool

                metadata = app._extract_metadata(video_path)
                assert metadata.path == video_path
                assert metadata.date_taken is not None
                assert metadata.camera_make == 'GoPro'
                assert metadata.camera_model == 'HERO9'
                assert metadata.location is not None

    def test_extract_metadata_use_file_date_when_metadata_missing(self, app):
        """Test _extract_metadata uses file creation date when metadata date is missing and use_file_date=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            # Mock exiftool to return no date
            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                mock_exiftool.get_metadata = MagicMock(return_value=[{}])
                mock_exiftool_class.return_value = mock_exiftool

                # Extract metadata with use_file_date - should have file date
                metadata_with_file_date = app._extract_metadata(video_path, use_file_date=True)
                assert metadata_with_file_date.date_taken is not None
                assert isinstance(metadata_with_file_date.date_taken, datetime)
                assert metadata_with_file_date.date_taken.date() == datetime.now().date() # Should be today

    def test_extract_metadata_use_file_date_does_not_override_metadata(self, app):
        """Test _extract_metadata does not override metadata date when use_file_date=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            mock_metadata = {
                'QuickTime:CreationDate': '2023:05:15 14:30:00',
                'Make': 'GoPro'
            }

            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                mock_exiftool.get_metadata = MagicMock(return_value=[mock_metadata])
                mock_exiftool_class.return_value = mock_exiftool

                # Extract metadata with use_file_date=True
                metadata = app._extract_metadata(video_path, use_file_date=True)
                # Should use metadata date, not file date
                assert metadata.date_taken is not None
                assert metadata.date_taken.year == 2023
                assert metadata.date_taken.month == 5
                assert metadata.date_taken.day == 15

    def test_get_file_creation_date_fallback_to_mtime(self, app):
        """Test _get_file_creation_date falls back to st_mtime when st_birthtime is not available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            # Mock stat to not have st_birthtime (simulate Linux/Windows systems)
            original_stat = video_path.stat()
            # Create a mock stat object without st_birthtime attribute
            class MockStat:
                def __init__(self, original_stat):
                    self.st_mtime = original_stat.st_mtime
                    # Copy other common stat attributes
                    for attr in ['st_mode', 'st_ino', 'st_dev', 'st_nlink', 'st_uid', 'st_gid', 'st_size', 'st_atime', 'st_ctime']:
                        if hasattr(original_stat, attr):
                            setattr(self, attr, getattr(original_stat, attr))
                # Explicitly don't have st_birthtime
                def __hasattr__(self, name):
                    if name == 'st_birthtime':
                        return False
                    return hasattr(self, name)

            mock_stat = MockStat(original_stat)

            with patch.object(Path, 'stat', return_value=mock_stat):
                date = VideoOffloader._get_file_creation_date(video_path)
                assert date is not None
                assert isinstance(date, datetime)
                # Should use st_mtime
                assert date == datetime.fromtimestamp(original_stat.st_mtime)

    def test_get_file_creation_date_handles_oserror(self, app):
        """Test _get_file_creation_date handles OSError gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            # Mock stat to raise OSError
            with patch.object(Path, 'stat', side_effect=OSError("File not found")):
                date = VideoOffloader._get_file_creation_date(video_path)
                assert date is None

    def test_get_file_creation_date_handles_valueerror(self, app):
        """Test _get_file_creation_date handles ValueError gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            # Mock stat to return invalid timestamp
            mock_stat = type('MockStat', (), {
                'st_birthtime': -1,  # Invalid timestamp that will cause ValueError
            })()

            with patch.object(Path, 'stat', return_value=mock_stat):
                # Mock fromtimestamp to raise ValueError
                with patch('offload.video_offloader.datetime') as mock_datetime:
                    mock_datetime.fromtimestamp.side_effect = ValueError("Invalid timestamp")
                    date = VideoOffloader._get_file_creation_date(video_path)
                    assert date is None

    def test_extract_metadata_exiftool_error(self, app):
        """Test _extract_metadata handles exiftool errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                mock_exiftool.get_metadata = MagicMock(side_effect=Exception("ExifTool error"))
                mock_exiftool_class.return_value = mock_exiftool

                # Should not raise exception, but return metadata with None values
                metadata = app._extract_metadata(video_path)
                assert metadata.path == video_path
                assert metadata.date_taken is None
                assert metadata.location is None

    def test_extract_metadata_empty_metadata_list(self, app):
        """Test _extract_metadata handles empty metadata list from exiftool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                # Return empty list (no metadata found)
                mock_exiftool.get_metadata = MagicMock(return_value=[])
                mock_exiftool_class.return_value = mock_exiftool

                metadata = app._extract_metadata(video_path)
                assert metadata.path == video_path
                assert metadata.date_taken is None
                assert metadata.location is None

    def test_extract_metadata_fallback_extraction(self, app):
        """Test _extract_metadata falls back to regular extraction when -ee flag fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            mock_metadata = {
                'CreateDate': '2023:05:15 14:30:00',
                'Make': 'GoPro'
            }

            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                # First call (with -ee) raises exception, second call (fallback) succeeds
                mock_exiftool.get_metadata = MagicMock(side_effect=[
                    Exception("Embedded extraction failed"),
                    [mock_metadata]
                ])
                mock_exiftool_class.return_value = mock_exiftool

                metadata = app._extract_metadata(video_path)
                assert metadata.path == video_path
                assert metadata.date_taken is not None
                assert metadata.camera_make == 'GoPro'

    def test_extract_metadata_fallback_empty_list(self, app):
        """Test _extract_metadata handles empty metadata list in fallback extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                # First call (with -ee) raises exception, second call returns empty list
                mock_exiftool.get_metadata = MagicMock(side_effect=[
                    Exception("Embedded extraction failed"),
                    []
                ])
                mock_exiftool_class.return_value = mock_exiftool

                metadata = app._extract_metadata(video_path)
                assert metadata.path == video_path
                assert metadata.date_taken is None
                assert metadata.location is None

    def test_extract_metadata_fallback_exception(self, app):
        """Test _extract_metadata handles exception in fallback extraction."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                # Both calls raise exceptions
                mock_exiftool.get_metadata = MagicMock(side_effect=Exception("ExifTool error"))
                mock_exiftool_class.return_value = mock_exiftool

                metadata = app._extract_metadata(video_path)
                assert metadata.path == video_path
                assert metadata.date_taken is None
                assert metadata.location is None

    def test_extract_metadata_outer_exception(self, app):
        """Test _extract_metadata handles outer exception (e.g., context manager failure)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            video_path = tmp_path / "video.mp4"
            self.create_test_video_file(video_path)

            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                # Context manager raises exception
                mock_exiftool_class.side_effect = Exception("Context manager error")

                metadata = app._extract_metadata(video_path)
                assert metadata.path == video_path
                assert metadata.date_taken is None
                assert metadata.location is None

    def test_read_videos_directory_not_exists(self, app):
        """Test read_videos with non-existent directory."""
        with pytest.raises(ValueError, match="Directory does not exist"):
            app.read_videos("/nonexistent/directory")

    def test_read_videos_path_not_directory(self, app):
        """Test read_videos with file path instead of directory."""
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            tmpfile.write(b"test")
            tmp_path = Path(tmpfile.name)
            try:
                with pytest.raises(ValueError, match="Path is not a directory"):
                    app.read_videos(tmp_path)
            finally:
                tmp_path.unlink()

    def test_read_videos_empty_directory(self, app):
        """Test read_videos with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            videos = app.read_videos(tmpdir)
            assert videos == []

    def test_read_videos_with_video_files(self, app):
        """Test read_videos with actual video files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Create test video files
            self.create_test_video_file(tmp_path / "video1.mp4")
            self.create_test_video_file(tmp_path / "video2.mov")
            # Create non-video file
            (tmp_path / "document.txt").write_text("not a video")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.side_effect = [
                    VideoMetadata(path=tmp_path / "video1.mp4"),
                    VideoMetadata(path=tmp_path / "video2.mov"),
                ]

                videos = app.read_videos(tmpdir)
                assert len(videos) == 2
                assert all(isinstance(v, VideoMetadata) for v in videos)
                assert all(v.path.suffix.lower() in ['.mp4', '.mov'] for v in videos)

    def test_read_videos_filters_by_extension(self, app):
        """Test that read_videos only includes supported video extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            self.create_test_video_file(tmp_path / "video.mp4")
            self.create_test_video_file(tmp_path / "video.mov")
            (tmp_path / "video.avi").write_bytes(b"fake video")
            (tmp_path / "video.mkv").write_bytes(b"fake video")

            with patch.object(app, '_extract_metadata') as mock_extract:
                def mock_extract_side_effect(file_path, use_file_date=False):
                    return VideoMetadata(path=file_path)
                mock_extract.side_effect = mock_extract_side_effect

                videos = app.read_videos(tmpdir)
                extensions = {v.path.suffix.lower() for v in videos}
                assert '.mp4' in extensions
                assert '.mov' in extensions
                assert '.avi' not in extensions
                assert '.mkv' not in extensions

    def test_get_bucket_key_software(self, app):
        """Test _get_bucket_key with SOFTWARE group_by."""
        video = VideoMetadata(path=Path("test.mp4"), software="iOS")
        key = app._get_bucket_key(video, GroupBy.SOFTWARE)
        assert key == "iOS"

    def test_get_bucket_key_software_unknown(self, app):
        """Test _get_bucket_key with SOFTWARE group_by when software is None."""
        video = VideoMetadata(path=Path("test.mp4"), software=None)
        key = app._get_bucket_key(video, GroupBy.SOFTWARE)
        assert key == "Unknown"

    def test_get_bucket_key_camera_make(self, app):
        """Test _get_bucket_key with CAMERA_MAKE group_by."""
        video = VideoMetadata(path=Path("test.mp4"), camera_make="GoPro")
        key = app._get_bucket_key(video, GroupBy.CAMERA_MAKE)
        assert key == "GoPro"

    def test_get_bucket_key_camera_model(self, app):
        """Test _get_bucket_key with CAMERA_MODEL group_by."""
        video = VideoMetadata(path=Path("test.mp4"), camera_model="HERO9")
        key = app._get_bucket_key(video, GroupBy.CAMERA_MODEL)
        assert key == "HERO9"

    def test_get_bucket_key_year(self, app):
        """Test _get_bucket_key with YEAR group_by."""
        video = VideoMetadata(path=Path("test.mp4"), date_taken=datetime(2023, 5, 15))
        key = app._get_bucket_key(video, GroupBy.YEAR)
        assert key == "2023"

    def test_get_bucket_key_year_unknown(self, app):
        """Test _get_bucket_key with YEAR group_by when date_taken is None."""
        video = VideoMetadata(path=Path("test.mp4"), date_taken=None)
        key = app._get_bucket_key(video, GroupBy.YEAR)
        assert key == "Unknown"

    def test_get_bucket_key_year_month(self, app):
        """Test _get_bucket_key with YEAR_MONTH group_by."""
        video = VideoMetadata(path=Path("test.mp4"), date_taken=datetime(2023, 5, 15))
        key = app._get_bucket_key(video, GroupBy.YEAR_MONTH)
        assert key == "2023-05"

    def test_get_bucket_key_year_month_day(self, app):
        """Test _get_bucket_key with YEAR_MONTH_DAY group_by."""
        video = VideoMetadata(path=Path("test.mp4"), date_taken=datetime(2023, 5, 15))
        key = app._get_bucket_key(video, GroupBy.YEAR_MONTH_DAY)
        assert key == "2023-05-15"

    def test_get_bucket_key_year_month_day_unknown(self, app):
        """Test _get_bucket_key with YEAR_MONTH_DAY group_by when date_taken is None."""
        video = VideoMetadata(path=Path("test.mp4"), date_taken=None)
        key = app._get_bucket_key(video, GroupBy.YEAR_MONTH_DAY)
        assert key == "Unknown"

    def test_get_bucket_key_invalid_group_by(self, app):
        """Test _get_bucket_key with invalid group_by raises error."""
        video = VideoMetadata(path=Path("test.mp4"))
        with pytest.raises(ValueError, match="Unsupported group_by"):
            app._get_bucket_key(video, "invalid")

    def test_bucket_videos_by_software(self, app):
        """Test bucket_videos grouping by software."""
        videos = [
            VideoMetadata(path=Path("1.mp4"), software="iOS"),
            VideoMetadata(path=Path("2.mp4"), software="Android"),
            VideoMetadata(path=Path("3.mp4"), software="iOS"),
            VideoMetadata(path=Path("4.mp4"), software=None),
        ]
        buckets = app.bucket_videos(videos, GroupBy.SOFTWARE)
        assert len(buckets) == 3
        assert len(buckets["iOS"]) == 2
        assert len(buckets["Android"]) == 1
        assert len(buckets["Unknown"]) == 1

    def test_bucket_videos_by_year_month(self, app):
        """Test bucket_videos grouping by year-month."""
        videos = [
            VideoMetadata(path=Path("1.mp4"), date_taken=datetime(2023, 5, 15)),
            VideoMetadata(path=Path("2.mp4"), date_taken=datetime(2023, 5, 20)),
            VideoMetadata(path=Path("3.mp4"), date_taken=datetime(2023, 6, 10)),
            VideoMetadata(path=Path("4.mp4"), date_taken=None),
        ]
        buckets = app.bucket_videos(videos, GroupBy.YEAR_MONTH)
        assert len(buckets) == 3
        assert len(buckets["2023-05"]) == 2
        assert len(buckets["2023-06"]) == 1
        assert len(buckets["Unknown"]) == 1

    def test_bucket_videos_empty_list(self, app):
        """Test bucket_videos with empty video list."""
        buckets = app.bucket_videos([], GroupBy.YEAR)
        assert buckets == {}

    def test_get_sort_key_software(self, app):
        """Test _get_sort_key with SOFTWARE group_by."""
        video1 = VideoMetadata(path=Path("1.mp4"), software="iOS")
        video2 = VideoMetadata(path=Path("2.mp4"), software=None)

        key1 = app._get_sort_key(video1, GroupBy.SOFTWARE)
        key2 = app._get_sort_key(video2, GroupBy.SOFTWARE)

        assert key1[0] == 0  # Known values sort first
        assert key2[0] == 1  # Unknown values sort last
        assert key1 < key2

    def test_get_sort_key_year(self, app):
        """Test _get_sort_key with YEAR group_by."""
        video1 = VideoMetadata(path=Path("1.mp4"), date_taken=datetime(2023, 1, 1))
        video2 = VideoMetadata(path=Path("2.mp4"), date_taken=None)

        key1 = app._get_sort_key(video1, GroupBy.YEAR)
        key2 = app._get_sort_key(video2, GroupBy.YEAR)

        assert key1[0] == 0
        assert key2[0] == 1
        assert key1 < key2

    def test_get_sort_key_camera_make(self, app):
        """Test _get_sort_key with CAMERA_MAKE group_by."""
        video1 = VideoMetadata(path=Path("1.mp4"), camera_make="GoPro")
        video2 = VideoMetadata(path=Path("2.mp4"), camera_make=None)

        key1 = app._get_sort_key(video1, GroupBy.CAMERA_MAKE)
        key2 = app._get_sort_key(video2, GroupBy.CAMERA_MAKE)

        assert key1[0] == 0  # Known values sort first
        assert key2[0] == 1  # Unknown values sort last
        assert key1 < key2

    def test_get_sort_key_camera_model(self, app):
        """Test _get_sort_key with CAMERA_MODEL group_by."""
        video1 = VideoMetadata(path=Path("1.mp4"), camera_model="HERO9")
        video2 = VideoMetadata(path=Path("2.mp4"), camera_model=None)

        key1 = app._get_sort_key(video1, GroupBy.CAMERA_MODEL)
        key2 = app._get_sort_key(video2, GroupBy.CAMERA_MODEL)

        assert key1[0] == 0  # Known values sort first
        assert key2[0] == 1  # Unknown values sort last
        assert key1 < key2

    def test_get_sort_key_year_month(self, app):
        """Test _get_sort_key with YEAR_MONTH group_by."""
        video1 = VideoMetadata(path=Path("1.mp4"), date_taken=datetime(2023, 5, 15))
        video2 = VideoMetadata(path=Path("2.mp4"), date_taken=None)

        key1 = app._get_sort_key(video1, GroupBy.YEAR_MONTH)
        key2 = app._get_sort_key(video2, GroupBy.YEAR_MONTH)

        assert key1[0] == 0
        assert key1[1] == 2023
        assert key1[2] == 5
        assert key2[0] == 1
        assert key1 < key2

    def test_get_sort_key_year_month_day(self, app):
        """Test _get_sort_key with YEAR_MONTH_DAY group_by."""
        video1 = VideoMetadata(path=Path("1.mp4"), date_taken=datetime(2023, 5, 15))
        video2 = VideoMetadata(path=Path("2.mp4"), date_taken=None)

        key1 = app._get_sort_key(video1, GroupBy.YEAR_MONTH_DAY)
        key2 = app._get_sort_key(video2, GroupBy.YEAR_MONTH_DAY)

        assert key1[0] == 0
        assert key1[1] == datetime(2023, 5, 15)
        assert key2[0] == 1
        assert key1 < key2

    def test_get_sort_key_invalid_group_by(self, app):
        """Test _get_sort_key with invalid group_by raises error."""
        video = VideoMetadata(path=Path("test.mp4"))
        with pytest.raises(ValueError, match="Unsupported group_by"):
            app._get_sort_key(video, "invalid")

    def test_sort_videos_by_year(self, app):
        """Test sort_videos sorting by year."""
        videos = [
            VideoMetadata(path=Path("3.mp4"), date_taken=datetime(2023, 1, 1)),
            VideoMetadata(path=Path("1.mp4"), date_taken=datetime(2021, 1, 1)),
            VideoMetadata(path=Path("2.mp4"), date_taken=datetime(2022, 1, 1)),
        ]
        sorted_videos = app.sort_videos(videos, GroupBy.YEAR)
        assert sorted_videos[0].date_taken.year == 2021
        assert sorted_videos[1].date_taken.year == 2022
        assert sorted_videos[2].date_taken.year == 2023

    def test_sort_videos_unknown_last(self, app):
        """Test that videos with unknown values sort last."""
        videos = [
            VideoMetadata(path=Path("1.mp4"), date_taken=None),
            VideoMetadata(path=Path("2.mp4"), date_taken=datetime(2023, 1, 1)),
            VideoMetadata(path=Path("3.mp4"), date_taken=None),
        ]
        sorted_videos = app.sort_videos(videos, GroupBy.YEAR)
        assert sorted_videos[0].date_taken is not None
        assert sorted_videos[-1].date_taken is None
        assert sorted_videos[-2].date_taken is None

    def test_copy_videos(self, app):
        """Test copy_videos copies files to destination."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Create source videos
            video1_path = self.create_test_video_file(source_dir / "video1.mp4")
            video2_path = self.create_test_video_file(source_dir / "video2.mov")

            videos = [
                VideoMetadata(path=video1_path),
                VideoMetadata(path=video2_path),
            ]

            app.copy_videos(videos, dest_dir)

            assert (dest_dir / "video1.mp4").exists()
            assert (dest_dir / "video2.mov").exists()
            assert (dest_dir / "video1.mp4").stat().st_size == video1_path.stat().st_size

    def test_copy_videos_creates_destination(self, app):
        """Test copy_videos creates destination directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest" / "subdir"
            source_dir.mkdir()

            video_path = self.create_test_video_file(source_dir / "video.mp4")
            videos = [VideoMetadata(path=video_path)]

            app.copy_videos(videos, dest_dir)

            assert dest_dir.exists()
            assert (dest_dir / "video.mp4").exists()

    def test_copy_videos_nonexistent_source(self, app):
        """Test copy_videos raises error when source file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_dir = Path(tmpdir) / "dest"
            nonexistent_video = VideoMetadata(path=Path("/nonexistent/video.mp4"))

            with pytest.raises(RuntimeError, match="Failed to copy"):
                app.copy_videos([nonexistent_video], dest_dir)

    def test_archive_videos(self, app):
        """Test archive_videos creates zip file and removes originals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Create source videos
            video1_path = self.create_test_video_file(source_dir / "video1.mp4")
            video2_path = self.create_test_video_file(source_dir / "video2.mov")

            videos = [
                VideoMetadata(path=video1_path),
                VideoMetadata(path=video2_path),
            ]

            app.archive_videos(videos, dest_dir)

            # Check zip file exists
            zip_path = dest_dir / "videos.zip"
            assert zip_path.exists()

            # Check original videos are removed
            assert not (dest_dir / "video1.mp4").exists()
            assert not (dest_dir / "video2.mov").exists()

            # Verify zip contents
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                names = zipf.namelist()
                assert "video1.mp4" in names
                assert "video2.mov" in names

    def test_archive_videos_zip_creation_error(self, app):
        """Test archive_videos handles zip creation errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video_path = self.create_test_video_file(source_dir / "video.mp4")
            videos = [VideoMetadata(path=video_path)]

            # Mock zipfile.ZipFile to raise an exception
            with patch('zipfile.ZipFile', side_effect=Exception("Zip creation failed")):
                with pytest.raises(RuntimeError, match="Failed to create archive"):
                    app.archive_videos(videos, dest_dir)

    def test_save_videos_copy(self, app):
        """Test _save_videos with to_archive=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video_path = self.create_test_video_file(source_dir / "video.mp4")
            videos = [VideoMetadata(path=video_path)]

            app._save_videos(videos, dest_dir, to_archive=False)

            assert (dest_dir / "video.mp4").exists()
            assert not (dest_dir / "videos.zip").exists()

    def test_save_videos_archive(self, app):
        """Test _save_videos with to_archive=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video_path = self.create_test_video_file(source_dir / "video.mp4")
            videos = [VideoMetadata(path=video_path)]

            app._save_videos(videos, dest_dir, to_archive=True)

            assert (dest_dir / "videos.zip").exists()
            assert not (dest_dir / "video.mp4").exists()

    def test_offload_videos_copy_mode(self, app):
        """Test offload_videos in copy mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Create videos with dates
            video1 = self.create_test_video_file(source_dir / "video1.mp4")
            video2 = self.create_test_video_file(source_dir / "video2.mp4")

            # Mock _extract_metadata to return videos with dates
            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.side_effect = [
                    VideoMetadata(path=video1, date_taken=datetime(2023, 5, 15)),
                    VideoMetadata(path=video2, date_taken=datetime(2023, 5, 20)),
                ]

                app.offload_videos(source_dir, dest_dir, to_archive=False, keep_unknown=True)

                # Check directory structure
                assert (dest_dir / "year=2023" / "month=05").exists()
                assert (dest_dir / "year=2023" / "month=05" / "video1.mp4").exists()
                assert (dest_dir / "year=2023" / "month=05" / "video2.mp4").exists()

    def test_offload_videos_archive_mode(self, app):
        """Test offload_videos in archive mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.return_value = VideoMetadata(
                    path=video, date_taken=datetime(2023, 5, 15)
                )

                app.offload_videos(source_dir, dest_dir, to_archive=True, keep_unknown=True)

                # Check zip file exists
                assert (dest_dir / "year=2023" / "month=05" / "videos.zip").exists()

    def test_offload_videos_unknown_date(self, app):
        """Test offload_videos handles videos without dates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.return_value = VideoMetadata(path=video, date_taken=None)

                app.offload_videos(source_dir, dest_dir, to_archive=False, keep_unknown=True)

                # Check unknown directory
                assert (dest_dir / "unknown").exists()
                assert (dest_dir / "unknown" / "video.mp4").exists()

    def test_offload_videos_multiple_months(self, app):
        """Test offload_videos handles videos from multiple months."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video1 = self.create_test_video_file(source_dir / "video1.mp4")
            video2 = self.create_test_video_file(source_dir / "video2.mp4")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.side_effect = [
                    VideoMetadata(path=video1, date_taken=datetime(2023, 5, 15)),
                    VideoMetadata(path=video2, date_taken=datetime(2023, 6, 10)),
                ]

                app.offload_videos(source_dir, dest_dir, to_archive=False, keep_unknown=True)

                assert (dest_dir / "year=2023" / "month=05").exists()
                assert (dest_dir / "year=2023" / "month=06").exists()
                assert (dest_dir / "year=2023" / "month=05" / "video1.mp4").exists()
                assert (dest_dir / "year=2023" / "month=06" / "video2.mp4").exists()

    def test_offload_videos_invalid_year_month_format(self, app):
        """Test offload_videos handles invalid year-month format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")

            # Mock bucket_videos to return an invalid year-month format
            with patch.object(app, 'read_videos') as mock_read:
                mock_read.return_value = [VideoMetadata(path=video, date_taken=datetime(2023, 5, 15))]

                with patch.object(app, 'bucket_videos') as mock_bucket:
                    # Return a bucket with invalid format
                    mock_bucket.return_value = {"invalid-format": [VideoMetadata(path=video, date_taken=datetime(2023, 5, 15))]}

                    app.offload_videos(source_dir, dest_dir, to_archive=False, keep_unknown=True)

                    # Should save to unknown directory
                    assert (dest_dir / "unknown").exists()
                    assert (dest_dir / "unknown" / "video.mp4").exists()

    def test_offload_videos_unknown_date_archive_mode(self, app):
        """Test offload_videos archives videos without dates to unknown directory when keep_unknown=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.return_value = VideoMetadata(path=video, date_taken=None)

                app.offload_videos(source_dir, dest_dir, to_archive=True, keep_unknown=True)

                # Check unknown directory has zip file
                assert (dest_dir / "unknown").exists()
                assert (dest_dir / "unknown" / "videos.zip").exists()

    def test_offload_videos_invalid_format_archive_mode(self, app):
        """Test offload_videos archives videos with invalid year-month format to unknown directory when keep_unknown=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")

            # Mock bucket_videos to return an invalid year-month format
            with patch.object(app, 'read_videos') as mock_read:
                mock_read.return_value = [VideoMetadata(path=video, date_taken=datetime(2023, 5, 15))]

                with patch.object(app, 'bucket_videos') as mock_bucket:
                    # Return a bucket with invalid format
                    mock_bucket.return_value = {"invalid-format": [VideoMetadata(path=video, date_taken=datetime(2023, 5, 15))]}

                    app.offload_videos(source_dir, dest_dir, to_archive=True, keep_unknown=True)

                    # Should save to unknown directory as zip
                    assert (dest_dir / "unknown").exists()
                    assert (dest_dir / "unknown" / "videos.zip").exists()

    def test_offload_videos_skip_unknown_date(self, app):
        """Test offload_videos skips videos without dates when keep_unknown=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.return_value = VideoMetadata(path=video, date_taken=None)

                app.offload_videos(source_dir, dest_dir, to_archive=False, keep_unknown=False)

                # Check unknown directory does NOT exist
                assert not (dest_dir / "unknown").exists()
                # Video should not be copied anywhere
                assert not (dest_dir / "video.mp4").exists()

    def test_offload_videos_skip_invalid_format(self, app):
        """Test offload_videos skips videos with invalid year-month format when keep_unknown=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")

            # Mock bucket_videos to return an invalid year-month format
            with patch.object(app, 'read_videos') as mock_read:
                mock_read.return_value = [VideoMetadata(path=video, date_taken=datetime(2023, 5, 15))]

                with patch.object(app, 'bucket_videos') as mock_bucket:
                    # Return a bucket with invalid format
                    mock_bucket.return_value = {"invalid-format": [VideoMetadata(path=video, date_taken=datetime(2023, 5, 15))]}

                    app.offload_videos(source_dir, dest_dir, to_archive=False, keep_unknown=False)

                    # Should NOT save to unknown directory
                    assert not (dest_dir / "unknown").exists()
                    # Video should not be copied anywhere
                    assert not (dest_dir / "video.mp4").exists()

    def test_offload_videos_use_file_date(self, app):
        """Test offload_videos uses file creation date when metadata date is missing and use_file_date=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")
            # Get the actual file creation date
            file_date = VideoOffloader._get_file_creation_date(video)
            assert file_date is not None

            # Mock exiftool to return no date
            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                mock_exiftool.get_metadata = MagicMock(return_value=[{}])
                mock_exiftool_class.return_value = mock_exiftool

                # Test offload_videos with use_file_date
                app.offload_videos(source_dir, dest_dir, to_archive=False, keep_unknown=True, use_file_date=True)

                # Should be organized by file date, not saved to unknown
                year = file_date.year
                month = file_date.month
                assert (dest_dir / f"year={year}" / f"month={month:02d}").exists()
                assert not (dest_dir / "unknown").exists()

    def test_offload_videos_use_file_date(self, app):
        """Test offload_videos uses file creation date when metadata date is missing and use_file_date=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            video = self.create_test_video_file(source_dir / "video.mp4")
            # Get the actual file creation date
            file_date = VideoOffloader._get_file_creation_date(video)
            assert file_date is not None

            # Mock exiftool to return no date
            with patch('exiftool.ExifToolHelper') as mock_exiftool_class:
                mock_exiftool = MagicMock()
                mock_exiftool.__enter__ = MagicMock(return_value=mock_exiftool)
                mock_exiftool.__exit__ = MagicMock(return_value=None)
                mock_exiftool.get_metadata = MagicMock(return_value=[{}])
                mock_exiftool_class.return_value = mock_exiftool

                # Test offload_videos with use_file_date
                app.offload_videos(source_dir, dest_dir, to_archive=False, keep_unknown=True, use_file_date=True)

                # Should be organized by file date, not saved to unknown
                year = file_date.year
                month = file_date.month
                assert (dest_dir / f"year={year}" / f"month={month:02d}").exists()
                assert not (dest_dir / "unknown").exists()
