# -*- coding: utf-8 -*-
from enum import Enum


class GroupBy(Enum):
    """Enum for grouping and sorting parameters."""
    SOFTWARE = "software"
    CAMERA_MAKE = "camera_make"
    CAMERA_MODEL = "camera_model"
    YEAR = "year"
    YEAR_MONTH = "year_month"
    YEAR_MONTH_DAY = "year_month_day"


# Bucket key constants
UNKNOWN_BUCKET_KEY = "Unknown"
UNKNOWN_DIRECTORY = "unknown"

# GPS reference constants
DEFAULT_LATITUDE_REF = 'N'
DEFAULT_LONGITUDE_REF = 'E'
NEGATIVE_DIRECTIONS = ['S', 'W']  # Directions that make coordinates negative

# Directory structure constants
YEAR_MONTH_SEPARATOR = "-"
YEAR_PREFIX = "year="
MONTH_PREFIX = "month="
