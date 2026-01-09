# -*- coding: utf-8 -*-
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from offload.cli import main


class TestCLI:
    """Test suite for the CLI module."""

    def test_main_with_valid_arguments(self):
        """Test that main function works with valid arguments."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir)
                ])

                assert result.exit_code == 0
                mock_app_class.assert_called_once()
                mock_app.offload_photos.assert_called_once_with(
                    str(source_dir),
                    str(dest_dir),
                    to_archive=False
                )

    def test_main_with_archive_flag(self):
        """Test that archive flag is passed correctly."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir),
                    '--archive'
                ])

                assert result.exit_code == 0
                mock_app.offload_photos.assert_called_once_with(
                    str(source_dir),
                    str(dest_dir),
                    to_archive=True
                )

    def test_main_with_short_archive_flag(self):
        """Test that short archive flag (-a) works."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '-s', str(source_dir),
                    '-d', str(dest_dir),
                    '-a'
                ])

                assert result.exit_code == 0
                mock_app.offload_photos.assert_called_once_with(
                    str(source_dir),
                    str(dest_dir),
                    to_archive=True
                )

    def test_main_with_log_level_debug(self):
        """Test that log level DEBUG is set correctly."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir),
                    '--log-level', 'DEBUG'
                ])

                assert result.exit_code == 0
                logger = logging.getLogger('offload')
                assert logger.level == logging.DEBUG

    def test_main_with_log_level_info(self):
        """Test that log level INFO is set correctly (default)."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir)
                ])

                assert result.exit_code == 0
                logger = logging.getLogger('offload')
                assert logger.level == logging.INFO

    def test_main_with_log_level_warning(self):
        """Test that log level WARNING is set correctly."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir),
                    '--log-level', 'WARNING'
                ])

                assert result.exit_code == 0
                logger = logging.getLogger('offload')
                assert logger.level == logging.WARNING

    def test_main_with_log_level_error(self):
        """Test that log level ERROR is set correctly."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir),
                    '--log-level', 'ERROR'
                ])

                assert result.exit_code == 0
                logger = logging.getLogger('offload')
                assert logger.level == logging.ERROR

    def test_main_with_log_level_critical(self):
        """Test that log level CRITICAL is set correctly."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir),
                    '--log-level', 'CRITICAL'
                ])

                assert result.exit_code == 0
                logger = logging.getLogger('offload')
                assert logger.level == logging.CRITICAL

    def test_main_with_invalid_log_level(self):
        """Test that invalid log level raises an error."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            result = runner.invoke(main, [
                '--source', str(source_dir),
                '--destination', str(dest_dir),
                '--log-level', 'INVALID'
            ])

            assert result.exit_code != 0
            assert 'invalid' in result.output.lower() or 'choice' in result.output.lower()

    def test_main_with_missing_source(self):
        """Test that missing source directory raises an error."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            dest_dir = Path(tmpdir) / "dest"
            nonexistent_source = Path(tmpdir) / "nonexistent"

            result = runner.invoke(main, [
                '--source', str(nonexistent_source),
                '--destination', str(dest_dir)
            ])

            assert result.exit_code != 0
            assert "does not exist" in result.output.lower() or "path" in result.output.lower()

    def test_main_with_file_as_source(self):
        """Test that providing a file as source raises an error."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = Path(tmpdir) / "source.txt"
            dest_dir = Path(tmpdir) / "dest"
            source_file.write_text("test")

            result = runner.invoke(main, [
                '--source', str(source_file),
                '--destination', str(dest_dir)
            ])

            assert result.exit_code != 0

    def test_main_with_missing_required_options(self):
        """Test that missing required options raises an error."""
        runner = CliRunner()

        result = runner.invoke(main, [])

        assert result.exit_code != 0
        assert "missing" in result.output.lower() or "required" in result.output.lower()

    def test_main_help_text(self):
        """Test that help text is displayed correctly."""
        runner = CliRunner()

        result = runner.invoke(main, ['--help'])

        assert result.exit_code == 0
        assert 'Source directory' in result.output or 'source' in result.output.lower()
        assert 'Destination directory' in result.output or 'destination' in result.output.lower()
        assert 'Archive photos' in result.output or 'archive' in result.output.lower()
        assert 'log-level' in result.output.lower() or 'logging level' in result.output.lower()

    def test_main_help_with_h_flag(self):
        """Test that -h flag displays help."""
        runner = CliRunner()

        result = runner.invoke(main, ['-h'])

        assert result.exit_code == 0
        assert 'Source directory' in result.output or 'source' in result.output.lower()

    def test_logger_handler_setup(self):
        """Test that logger handler is set up correctly."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Clear any existing handlers
            logger = logging.getLogger('offload')
            logger.handlers.clear()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir)
                ])

                assert result.exit_code == 0
                assert len(logger.handlers) > 0
                assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_logger_formatter_setup(self):
        """Test that logger formatter is set up correctly."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Clear any existing handlers
            logger = logging.getLogger('offload')
            logger.handlers.clear()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir)
                ])

                assert result.exit_code == 0
                assert len(logger.handlers) > 0
                handler = logger.handlers[0]
                assert handler.formatter is not None
                assert isinstance(handler.formatter, logging.Formatter)
                expected_format = "%(asctime)s: %(name)s/%(levelname)-9s: %(message)s"
                assert handler.formatter._fmt == expected_format

    def test_logger_handler_not_duplicated(self):
        """Test that logger handler is not duplicated on multiple calls."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            # Clear any existing handlers
            logger = logging.getLogger('offload')
            logger.handlers.clear()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                # Call main twice
                runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir)
                ])

                handler_count_after_first = len(logger.handlers)

                runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir)
                ])

                # Handler count should not increase
                assert len(logger.handlers) == handler_count_after_first

    def test_application_receives_logger(self):
        """Test that Application is initialized with the logger."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            dest_dir = Path(tmpdir) / "dest"
            source_dir.mkdir()

            with patch('offload.cli.Application') as mock_app_class:
                mock_app = MagicMock()
                mock_app_class.return_value = mock_app

                result = runner.invoke(main, [
                    '--source', str(source_dir),
                    '--destination', str(dest_dir)
                ])

                assert result.exit_code == 0
                # Verify Application was called with a logger instance
                mock_app_class.assert_called_once()
                call_args = mock_app_class.call_args
                assert len(call_args[0]) == 1
                assert isinstance(call_args[0][0], logging.Logger)
                assert call_args[0][0].name == 'offload'
