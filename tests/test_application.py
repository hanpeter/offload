# -*- coding: utf-8 -*-
import logging
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from offload.application import Application, GroupBy, PhotoMetadata


class TestApplication:
    """Test suite for the Application class."""

    @pytest.fixture
    def logger(self):
        """Create a logger for testing."""
        logger = logging.getLogger('test_offload')
        logger.setLevel(logging.DEBUG)
        return logger

    @pytest.fixture
    def app(self, logger):
        """Create an Application instance for testing."""
        return Application(logger)

    def create_test_image(self, path: Path, exif_data: dict = None) -> Path:
        """Create a test image file with optional EXIF data."""
        img = Image.new('RGB', (100, 100), color='red')
        if exif_data:
            img.save(path, exif=exif_data)
        else:
            img.save(path)
        return path

    def test_init(self, logger):
        """Test Application initialization."""
        app = Application(logger)
        assert app.logger == logger

    def test_dms_to_decimal_north_east(self, app):
        """Test DMS to decimal conversion for North/East coordinates."""
        # Test coordinates: 37° 46' 26.2992" N, 122° 25' 52.0176" W
        lat_dms = (37, 46, 26.2992)
        lon_dms = (122, 25, 52.0176)

        lat = Application._dms_to_decimal(lat_dms, 'N')
        lon = Application._dms_to_decimal(lon_dms, 'E')

        assert lat > 0
        assert lon > 0
        assert abs(lat - 37.773972) < 0.001
        assert abs(lon - 122.431116) < 0.001

    def test_dms_to_decimal_south_west(self, app):
        """Test DMS to decimal conversion for South/West coordinates."""
        lat_dms = (37, 46, 26.2992)
        lon_dms = (122, 25, 52.0176)

        lat = Application._dms_to_decimal(lat_dms, 'S')
        lon = Application._dms_to_decimal(lon_dms, 'W')

        assert lat < 0
        assert lon < 0

    def test_parse_exif_date_datetime_original(self, app):
        """Test parsing date from DateTimeOriginal field."""
        exif_data = {'DateTimeOriginal': '2023:05:15 14:30:00'}
        date = app._parse_exif_date(exif_data)
        assert date is not None
        assert date.year == 2023
        assert date.month == 5
        assert date.day == 15

    def test_parse_exif_date_datetime_digitized(self, app):
        """Test parsing date from DateTimeDigitized field."""
        exif_data = {'DateTimeDigitized': '2023:05:15 14:30:00'}
        date = app._parse_exif_date(exif_data)
        assert date is not None
        assert date.year == 2023

    def test_parse_exif_date_datetime(self, app):
        """Test parsing date from DateTime field."""
        exif_data = {'DateTime': '2023:05:15 14:30:00'}
        date = app._parse_exif_date(exif_data)
        assert date is not None
        assert date.year == 2023

    def test_parse_exif_date_preference_order(self, app):
        """Test that DateTimeOriginal is preferred over other fields."""
        exif_data = {
            'DateTime': '2020:01:01 00:00:00',
            'DateTimeDigitized': '2021:01:01 00:00:00',
            'DateTimeOriginal': '2022:01:01 00:00:00'
        }
        date = app._parse_exif_date(exif_data)
        assert date is not None
        assert date.year == 2022

    def test_parse_exif_date_invalid_format(self, app):
        """Test parsing date with invalid format."""
        exif_data = {'DateTimeOriginal': 'invalid-date'}
        date = app._parse_exif_date(exif_data)
        assert date is None

    def test_parse_exif_date_no_date_fields(self, app):
        """Test parsing date when no date fields exist."""
        exif_data = {'Make': 'Canon'}
        date = app._parse_exif_date(exif_data)
        assert date is None

    def test_parse_exif_camera_info(self, app):
        """Test parsing camera information from EXIF."""
        exif_data = {
            'Make': 'Canon',
            'Model': 'EOS 5D',
            'Software': 'Camera Firmware 1.0'
        }
        make, model, software = app._parse_exif_camera_info(exif_data)
        assert make == 'Canon'
        assert model == 'EOS 5D'
        assert software == 'Camera Firmware 1.0'

    def test_parse_exif_camera_info_missing_fields(self, app):
        """Test parsing camera info with missing fields."""
        exif_data = {'Make': 'Canon'}
        make, model, software = app._parse_exif_camera_info(exif_data)
        assert make == 'Canon'
        assert model is None
        assert software is None

    def test_parse_exif_camera_info_none(self, app):
        """Test parsing camera info when all fields are None."""
        exif_data = {}
        make, model, software = app._parse_exif_camera_info(exif_data)
        assert make is None
        assert model is None
        assert software is None

    def test_read_photos_directory_not_exists(self, app):
        """Test read_photos with non-existent directory."""
        with pytest.raises(ValueError, match="Directory does not exist"):
            app.read_photos("/nonexistent/directory")

    def test_read_photos_path_not_directory(self, app):
        """Test read_photos with file path instead of directory."""
        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            tmpfile.write(b"test")
            tmp_path = Path(tmpfile.name)
            try:
                with pytest.raises(ValueError, match="Path is not a directory"):
                    app.read_photos(tmp_path)
            finally:
                tmp_path.unlink()

    def test_read_photos_empty_directory(self, app):
        """Test read_photos with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            photos = app.read_photos(tmpdir)
            assert photos == []

    def test_read_photos_with_photo_files(self, app):
        """Test read_photos with actual photo files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Create test images
            self.create_test_image(tmp_path / "photo1.jpg")
            self.create_test_image(tmp_path / "photo2.png")
            # Create non-photo file
            (tmp_path / "document.txt").write_text("not a photo")

            photos = app.read_photos(tmpdir)
            assert len(photos) == 2
            assert all(isinstance(p, PhotoMetadata) for p in photos)
            assert all(p.path.suffix.lower() in ['.jpg', '.png'] for p in photos)

    def test_read_photos_filters_by_extension(self, app):
        """Test that read_photos only includes supported photo extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            self.create_test_image(tmp_path / "photo.jpg")
            self.create_test_image(tmp_path / "photo.png")
            (tmp_path / "photo.gif").write_bytes(b"fake image")
            (tmp_path / "photo.bmp").write_bytes(b"fake image")

            photos = app.read_photos(tmpdir)
            extensions = {p.path.suffix.lower() for p in photos}
            assert '.jpg' in extensions
            assert '.png' in extensions
            assert '.gif' not in extensions
            assert '.bmp' not in extensions

    def test_get_bucket_key_software(self, app):
        """Test _get_bucket_key with SOFTWARE group_by."""
        photo = PhotoMetadata(path=Path("test.jpg"), software="iOS")
        key = app._get_bucket_key(photo, GroupBy.SOFTWARE)
        assert key == "iOS"

    def test_get_bucket_key_software_unknown(self, app):
        """Test _get_bucket_key with SOFTWARE group_by when software is None."""
        photo = PhotoMetadata(path=Path("test.jpg"), software=None)
        key = app._get_bucket_key(photo, GroupBy.SOFTWARE)
        assert key == "Unknown"

    def test_get_bucket_key_camera_make(self, app):
        """Test _get_bucket_key with CAMERA_MAKE group_by."""
        photo = PhotoMetadata(path=Path("test.jpg"), camera_make="Canon")
        key = app._get_bucket_key(photo, GroupBy.CAMERA_MAKE)
        assert key == "Canon"

    def test_get_bucket_key_camera_model(self, app):
        """Test _get_bucket_key with CAMERA_MODEL group_by."""
        photo = PhotoMetadata(path=Path("test.jpg"), camera_model="EOS 5D")
        key = app._get_bucket_key(photo, GroupBy.CAMERA_MODEL)
        assert key == "EOS 5D"

    def test_get_bucket_key_year(self, app):
        """Test _get_bucket_key with YEAR group_by."""
        photo = PhotoMetadata(path=Path("test.jpg"), date_taken=datetime(2023, 5, 15))
        key = app._get_bucket_key(photo, GroupBy.YEAR)
        assert key == "2023"

    def test_get_bucket_key_year_unknown(self, app):
        """Test _get_bucket_key with YEAR group_by when date_taken is None."""
        photo = PhotoMetadata(path=Path("test.jpg"), date_taken=None)
        key = app._get_bucket_key(photo, GroupBy.YEAR)
        assert key == "Unknown"

    def test_get_bucket_key_year_month(self, app):
        """Test _get_bucket_key with YEAR_MONTH group_by."""
        photo = PhotoMetadata(path=Path("test.jpg"), date_taken=datetime(2023, 5, 15))
        key = app._get_bucket_key(photo, GroupBy.YEAR_MONTH)
        assert key == "2023-05"

    def test_get_bucket_key_year_month_day(self, app):
        """Test _get_bucket_key with YEAR_MONTH_DAY group_by."""
        photo = PhotoMetadata(path=Path("test.jpg"), date_taken=datetime(2023, 5, 15))
        key = app._get_bucket_key(photo, GroupBy.YEAR_MONTH_DAY)
        assert key == "2023-05-15"

    def test_get_bucket_key_invalid_group_by(self, app):
        """Test _get_bucket_key with invalid group_by raises error."""
        photo = PhotoMetadata(path=Path("test.jpg"))
        with pytest.raises(ValueError, match="Unsupported group_by"):
            app._get_bucket_key(photo, "invalid")

    def test_bucket_photos_by_software(self, app):
        """Test bucket_photos grouping by software."""
        photos = [
            PhotoMetadata(path=Path("1.jpg"), software="iOS"),
            PhotoMetadata(path=Path("2.jpg"), software="Android"),
            PhotoMetadata(path=Path("3.jpg"), software="iOS"),
            PhotoMetadata(path=Path("4.jpg"), software=None),
        ]
        buckets = app.bucket_photos(photos, GroupBy.SOFTWARE)
        assert len(buckets) == 3
        assert len(buckets["iOS"]) == 2
        assert len(buckets["Android"]) == 1
        assert len(buckets["Unknown"]) == 1

    def test_bucket_photos_by_year_month(self, app):
        """Test bucket_photos grouping by year-month."""
        photos = [
            PhotoMetadata(path=Path("1.jpg"), date_taken=datetime(2023, 5, 15)),
            PhotoMetadata(path=Path("2.jpg"), date_taken=datetime(2023, 5, 20)),
            PhotoMetadata(path=Path("3.jpg"), date_taken=datetime(2023, 6, 10)),
            PhotoMetadata(path=Path("4.jpg"), date_taken=None),
        ]
        buckets = app.bucket_photos(photos, GroupBy.YEAR_MONTH)
        assert len(buckets) == 3
        assert len(buckets["2023-05"]) == 2
        assert len(buckets["2023-06"]) == 1
        assert len(buckets["Unknown"]) == 1

    def test_bucket_photos_empty_list(self, app):
        """Test bucket_photos with empty photo list."""
        buckets = app.bucket_photos([], GroupBy.YEAR)
        assert buckets == {}

    def test_get_sort_key_software(self, app):
        """Test _get_sort_key with SOFTWARE group_by."""
        photo1 = PhotoMetadata(path=Path("1.jpg"), software="iOS")
        photo2 = PhotoMetadata(path=Path("2.jpg"), software=None)

        key1 = app._get_sort_key(photo1, GroupBy.SOFTWARE)
        key2 = app._get_sort_key(photo2, GroupBy.SOFTWARE)

        assert key1[0] == 0  # Known values sort first
        assert key2[0] == 1  # Unknown values sort last
        assert key1 < key2

    def test_get_sort_key_year(self, app):
        """Test _get_sort_key with YEAR group_by."""
        photo1 = PhotoMetadata(path=Path("1.jpg"), date_taken=datetime(2023, 1, 1))
        photo2 = PhotoMetadata(path=Path("2.jpg"), date_taken=None)

        key1 = app._get_sort_key(photo1, GroupBy.YEAR)
        key2 = app._get_sort_key(photo2, GroupBy.YEAR)

        assert key1[0] == 0
        assert key2[0] == 1
        assert key1 < key2

    def test_sort_photos_by_year(self, app):
        """Test sort_photos sorting by year."""
        photos = [
            PhotoMetadata(path=Path("3.jpg"), date_taken=datetime(2023, 1, 1)),
            PhotoMetadata(path=Path("1.jpg"), date_taken=datetime(2021, 1, 1)),
            PhotoMetadata(path=Path("2.jpg"), date_taken=datetime(2022, 1, 1)),
        ]
        sorted_photos = app.sort_photos(photos, GroupBy.YEAR)
        assert sorted_photos[0].date_taken.year == 2021
        assert sorted_photos[1].date_taken.year == 2022
        assert sorted_photos[2].date_taken.year == 2023

    def test_sort_photos_unknown_last(self, app):
        """Test that photos with unknown values sort last."""
        photos = [
            PhotoMetadata(path=Path("1.jpg"), date_taken=None),
            PhotoMetadata(path=Path("2.jpg"), date_taken=datetime(2023, 1, 1)),
            PhotoMetadata(path=Path("3.jpg"), date_taken=None),
        ]
        sorted_photos = app.sort_photos(photos, GroupBy.YEAR)
        assert sorted_photos[0].date_taken is not None
        assert sorted_photos[-1].date_taken is None
        assert sorted_photos[-2].date_taken is None

    def test_copy_photos(self, app):
        """Test copy_photos copies files to destination."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Create source photos
            photo1_path = self.create_test_image(source_dir / "photo1.jpg")
            photo2_path = self.create_test_image(source_dir / "photo2.png")

            photos = [
                PhotoMetadata(path=photo1_path),
                PhotoMetadata(path=photo2_path),
            ]

            app.copy_photos(photos, dest_dir)

            assert (dest_dir / "photo1.jpg").exists()
            assert (dest_dir / "photo2.png").exists()
            assert (dest_dir / "photo1.jpg").stat().st_size == photo1_path.stat().st_size

    def test_copy_photos_creates_destination(self, app):
        """Test copy_photos creates destination directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest" / "subdir"
            source_dir.mkdir()

            photo_path = self.create_test_image(source_dir / "photo.jpg")
            photos = [PhotoMetadata(path=photo_path)]

            app.copy_photos(photos, dest_dir)

            assert dest_dir.exists()
            assert (dest_dir / "photo.jpg").exists()

    def test_copy_photos_nonexistent_source(self, app):
        """Test copy_photos raises error when source file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_dir = Path(tmpdir) / "dest"
            nonexistent_photo = PhotoMetadata(path=Path("/nonexistent/photo.jpg"))

            with pytest.raises(RuntimeError, match="Failed to copy"):
                app.copy_photos([nonexistent_photo], dest_dir)

    def test_archive_photos(self, app):
        """Test archive_photos creates zip file and removes originals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Create source photos
            photo1_path = self.create_test_image(source_dir / "photo1.jpg")
            photo2_path = self.create_test_image(source_dir / "photo2.png")

            photos = [
                PhotoMetadata(path=photo1_path),
                PhotoMetadata(path=photo2_path),
            ]

            app.archive_photos(photos, dest_dir)

            # Check zip file exists
            zip_path = dest_dir / "photos.zip"
            assert zip_path.exists()

            # Check original photos are removed
            assert not (dest_dir / "photo1.jpg").exists()
            assert not (dest_dir / "photo2.png").exists()

            # Verify zip contents
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                names = zipf.namelist()
                assert "photo1.jpg" in names
                assert "photo2.png" in names

    def test_save_photos_copy(self, app):
        """Test _save_photos with to_archive=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            photo_path = self.create_test_image(source_dir / "photo.jpg")
            photos = [PhotoMetadata(path=photo_path)]

            app._save_photos(photos, dest_dir, to_archive=False)

            assert (dest_dir / "photo.jpg").exists()
            assert not (dest_dir / "photos.zip").exists()

    def test_save_photos_archive(self, app):
        """Test _save_photos with to_archive=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            photo_path = self.create_test_image(source_dir / "photo.jpg")
            photos = [PhotoMetadata(path=photo_path)]

            app._save_photos(photos, dest_dir, to_archive=True)

            assert (dest_dir / "photos.zip").exists()
            assert not (dest_dir / "photo.jpg").exists()

    def test_offload_photos_copy_mode(self, app):
        """Test offload_photos in copy mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Create photos with dates
            photo1 = self.create_test_image(source_dir / "photo1.jpg")
            photo2 = self.create_test_image(source_dir / "photo2.jpg")

            # Mock _extract_metadata to return photos with dates
            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.side_effect = [
                    PhotoMetadata(path=photo1, date_taken=datetime(2023, 5, 15)),
                    PhotoMetadata(path=photo2, date_taken=datetime(2023, 5, 20)),
                ]

                app.offload_photos(source_dir, dest_dir, to_archive=False)

                # Check directory structure
                assert (dest_dir / "year=2023" / "month=05").exists()
                assert (dest_dir / "year=2023" / "month=05" / "photo1.jpg").exists()
                assert (dest_dir / "year=2023" / "month=05" / "photo2.jpg").exists()

    def test_offload_photos_archive_mode(self, app):
        """Test offload_photos in archive mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            photo = self.create_test_image(source_dir / "photo.jpg")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.return_value = PhotoMetadata(
                    path=photo, date_taken=datetime(2023, 5, 15)
                )

                app.offload_photos(source_dir, dest_dir, to_archive=True)

                # Check zip file exists
                assert (dest_dir / "year=2023" / "month=05" / "photos.zip").exists()

    def test_offload_photos_unknown_date(self, app):
        """Test offload_photos handles photos without dates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            photo = self.create_test_image(source_dir / "photo.jpg")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.return_value = PhotoMetadata(path=photo, date_taken=None)

                app.offload_photos(source_dir, dest_dir, to_archive=False)

                # Check unknown directory
                assert (dest_dir / "unknown").exists()
                assert (dest_dir / "unknown" / "photo.jpg").exists()

    def test_offload_photos_multiple_months(self, app):
        """Test offload_photos handles photos from multiple months."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            photo1 = self.create_test_image(source_dir / "photo1.jpg")
            photo2 = self.create_test_image(source_dir / "photo2.jpg")

            with patch.object(app, '_extract_metadata') as mock_extract:
                mock_extract.side_effect = [
                    PhotoMetadata(path=photo1, date_taken=datetime(2023, 5, 15)),
                    PhotoMetadata(path=photo2, date_taken=datetime(2023, 6, 10)),
                ]

                app.offload_photos(source_dir, dest_dir, to_archive=False)

                assert (dest_dir / "year=2023" / "month=05").exists()
                assert (dest_dir / "year=2023" / "month=06").exists()
                assert (dest_dir / "year=2023" / "month=05" / "photo1.jpg").exists()
                assert (dest_dir / "year=2023" / "month=06" / "photo2.jpg").exists()
