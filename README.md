# offload

[![Tests](https://github.com/hanpeter/offload/actions/workflows/test.yml/badge.svg)](https://github.com/hanpeter/offload/actions/workflows/test.yml)

CLI tool to organize photos and videos by extracting EXIF metadata. Automatically creates structured directories and supports archiving to zip files.

## Table of Contents

- [Purpose](#purpose)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Installing offload](#installing-offload)
- [Usage](#usage)
  - [Basic Syntax](#basic-syntax)
  - [Options](#options)
  - [Examples](#examples)
- [Contributing](#contributing)

## Purpose

`offload` is a command-line tool designed to help you organize and back up photos and videos from your devices. It automatically extracts metadata (such as date taken, location, camera make/model) from your media files and organizes them into a structured directory hierarchy. The tool can either copy files directly to your destination or archive them into zip files for easier storage and transfer.

Key features:
- Automatically organizes photos and videos by date, location, camera information, and software
- Supports multiple photo formats including JPEG, PNG, HEIC, and HEIF
- Supports video formats including MOV and MP4
- Extracts and preserves EXIF metadata
- Option to archive files into zip files instead of copying
- Flexible filtering by media type (photos, videos, or both)

## Installation

### Prerequisites

Before installing `offload`, you need to ensure the following dependencies are installed:

1. **pillow-heif**: Required for HEIC/HEIF image format support. See the [pillow-heif installation documentation](https://pillow-heif.readthedocs.io/en/latest/installation.html) for platform-specific installation instructions.

2. **pyexiftool**: Required for extracting metadata from media files. This library requires Phil Harvey's `exiftool` command-line application. See the [pyexiftool dependencies documentation](https://github.com/sylikc/pyexiftool?tab=readme-ov-file#pyexiftool-dependencies) for installation instructions.

### Installing offload

Once prerequisites are installed, you can install `offload` using Poetry:

```bash
poetry install
```

Or if you prefer pip:

```bash
pip install .
```

## Usage

The `offload` command-line tool provides several options to customize how your media files are processed:

### Basic Syntax

```bash
offload -s <source_directory> -d <destination_directory> [OPTIONS]
```

### Options

- **`-s, --source`** (required): Path to the source directory containing photos and/or videos to offload. The directory must exist.

- **`-d, --destination`** (required): Path to the destination directory where photos/videos will be copied or archived. The directory will be created if it doesn't exist.

- **`-a, --archive`**: When this flag is set, photos and videos will be archived into zip files instead of being copied directly. By default, files are copied.

- **`--media-type`**: Specifies which type of media to process. Options:
  - `photos`: Process only photos
  - `videos`: Process only videos
  - `both`: Process both photos and videos (default)

- **`--log-level`**: Sets the logging verbosity level. Options:
  - `DEBUG`: Detailed debugging information
  - `INFO`: General informational messages (default)
  - `WARNING`: Warning messages only
  - `ERROR`: Error messages only
  - `CRITICAL`: Critical errors only

### Examples

Copy all photos and videos from a source directory to a destination:

```bash
offload -s /path/to/photos -d /path/to/backup
```

Archive only photos into zip files:

```bash
offload -s /path/to/photos -d /path/to/backup --archive --media-type photos
```

Process videos with debug logging:

```bash
offload -s /path/to/videos -d /path/to/backup --media-type videos --log-level DEBUG
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
