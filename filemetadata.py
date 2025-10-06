"""
Modern metadata extraction from media files using Pillow for EXIF/IPTC.

This module provides a unified interface for extracting metadata from various
file types including images, videos, and audio files. It uses:
- Pillow for EXIF and IPTC metadata from images
- FFProbe for video and audio metadata
- python-magic for MIME type detection

Main functions:
- get_metadata(filepath, mimetype=None): Extract all available metadata
- get_mimetype(filepath): Get MIME type from file content
- hashfile(filepath): Calculate SHA1 hash of file
"""

import datetime
import hashlib
import json
import logging
import os
import re
import subprocess
from typing import Any, Dict, List, Optional

import magic
from dateutil import parser
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS
from PIL.IptcImagePlugin import getiptcinfo
from pillow_heif import register_heif_opener


register_heif_opener()

log = logging.getLogger(__name__)


# EXIF tag constants
EXIF_DATETIME_ORIGINAL = 36867
EXIF_DATETIME = 306
EXIF_GPS_INFO = 34853
EXIF_ORIENTATION = 274


class FFProbe:
    """
    Wrapper for the ffprobe command to extract metadata from video and audio files.
    """

    audio_mimemap = {
        "amr": "audio/amr",
        "3gp": "audio/3gpp",
        "3ga": "audio/3gpp",
        "m4a": "audio/mp4a-latm",
        "ogg": "audio/ogg",
        "mp3": "audio/mpeg",
    }

    video_mimemap = {
        "3gp": "video/3gpp",
    }

    ffprobe = "ffprobe"

    def __init__(self, path: str) -> None:
        self.path = path
        self.data: Optional[Dict[str, Any]] = None
        self.get_streams_dict()

    def get_streams_dict(self) -> bool:
        """
        Returns a Python dictionary containing information on the audio/video
        streams contained in the file.

        If no stream information is available, returns an empty dictionary.
        """
        command = self._ffprobe_command(self.path)
        log.debug(" ".join(command))
        try:
            output = subprocess.check_output(command, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as err:
            log.error(f"FFProbe subprocess error: {err}, Command: {' '.join(command)}")
            output = b"{}"
        except OSError as err:
            log.error(f"FFProbe OSError: {err}, Command: {' '.join(command)}")
            raise
        self.data = json.loads(output)
        return True

    def _ffprobe_command(self, url: str) -> List[str]:
        return [self.ffprobe, "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", url]

    def has_video_stream(self) -> bool:
        """Check if file has a valid video stream (duration > 1 second)."""
        if self.data is None or "streams" not in self.data:
            return False
        for stream_info in self.data["streams"]:
            if stream_info["codec_type"] == "video":
                duration = stream_info.get("duration", 0.0)
                if float(duration) > 1.0:
                    return True
        return False

    def has_audio_stream(self) -> bool:
        """Check if file has an audio stream."""
        if self.data is None or "streams" not in self.data:
            return False
        for stream_info in self.data["streams"]:
            if stream_info["codec_type"] == "audio":
                return True
        return False

    def is_video(self) -> bool:
        """Return True if file has a video stream."""
        return self.has_video_stream()

    def is_audio(self) -> bool:
        """Return True if file has an audio stream but not video stream."""
        return self.has_audio_stream() and not self.has_video_stream()

    def get_gps(self, info: Dict[str, Any]) -> None:
        """
        Extract GPS data (lat, lon, altitude) from video metadata.

        Supports formats:
        - Android: "location": "+60.2163+024.9808/"
        - iPhone: "com.apple.quicktime.location.ISO6709": "+60.1997+024.9473+016.943/"
        """
        loc = None
        gps = {}
        if self.data and "format" in self.data and "tags" in self.data["format"]:
            if "location" in self.data["format"]["tags"]:
                loc = self.data["format"]["tags"]["location"]
            elif "com.apple.quicktime.location.ISO6709" in self.data["format"]["tags"]:
                loc = self.data["format"]["tags"]["com.apple.quicktime.location.ISO6709"]

        if loc is not None:
            m = re.match(r"^(?P<lat>[\-+]\d+\.\d+)(?P<lon>[\-+]\d+\.\d+)(?P<alt>[\-+]\d+\.\d+)?", loc)
            if m:
                gps["lat"] = float(m.group("lat"))
                gps["lon"] = float(m.group("lon"))
                if m.group("alt"):
                    gps["altitude"] = float(m.group("alt"))
        info["gps"] = gps

    def get_creation_time(self, info: Dict[str, Any]) -> None:
        """Extract creation time from video metadata."""
        try:
            if self.data and "format" in self.data and "tags" in self.data["format"]:
                if "creation_time" in self.data["format"]["tags"]:
                    ts = self.data["format"]["tags"]["creation_time"]
                    info["creation_time"] = parser.parse(ts)
        except (KeyError, ValueError) as e:
            log.debug(f"Failed to parse creation_time: {e}")

    def get_duration(self, stream: Dict[str, Any], info: Dict[str, Any]) -> None:
        """Extract duration from stream."""
        if "duration" in stream:
            info["duration"] = float(stream.get("duration", 0.0))

    def get_videoinfo(self) -> Dict[str, Any]:
        """Extract video metadata including dimensions, duration, bitrate, GPS, and creation time."""
        info: Dict[str, Any] = {}
        if self.data is None or "streams" not in self.data:
            return info
        for stream in self.data["streams"]:
            if stream["codec_type"] == "video":
                self.get_duration(stream, info)
                info["width"] = int(stream.get("width", 0))
                info["height"] = int(stream.get("height", 0))
                break
        if self.data and "format" in self.data and "bit_rate" in self.data["format"]:
            info["bitrate"] = int(self.data["format"]["bit_rate"])
        # Sometimes duration is in format, not in video stream
        if "duration" not in info and self.data and "format" in self.data:
            self.get_duration(self.data["format"], info)
        self.get_gps(info)
        self.get_creation_time(info)
        return info

    def get_audioinfo(self) -> Dict[str, Any]:
        """Extract audio metadata including duration, bitrate, and MIME type."""
        info: Dict[str, Any] = {}
        if self.data is None or "streams" not in self.data:
            return info
        for stream in self.data["streams"]:
            if stream["codec_type"] == "audio":
                self.get_duration(stream, info)
                break
        if self.data and "format" in self.data and "bit_rate" in self.data["format"]:
            info["bitrate"] = int(self.data["format"]["bit_rate"])
        ext = os.path.splitext(self.path)[1].lstrip(".").lower()
        if ext in list(self.audio_mimemap.keys()):
            info["mimetype"] = self.audio_mimemap[ext]

        self.get_gps(info)
        self.get_creation_time(info)
        return info


def hashfile(filepath: str) -> str:
    """
    Calculate and return SHA1 hash of file in hex format.

    Args:
        filepath: Path to file

    Returns:
        SHA1 hash as hexadecimal string
    """
    block_size = 2**16  # 65536
    sha1 = hashlib.sha1()
    with open(filepath, "rb") as f:
        buf = f.read(block_size)
        while len(buf) > 0:
            sha1.update(buf)
            buf = f.read(block_size)
    return sha1.hexdigest()


def get_mimetype(filepath: str) -> str:
    """
    Get MIME type of file by reading its content with python-magic.

    Args:
        filepath: Path to file

    Returns:
        MIME type string (e.g., 'image/jpeg', 'video/mp4')
    """
    with open(filepath, "rb") as f:
        mimetype = magic.from_buffer(f.read(4096), mime=True)
    return mimetype


def _convert_gps_to_degrees(value: tuple) -> float:
    """
    Convert GPS coordinates to decimal degrees.

    Args:
        value: Tuple of (degrees, minutes, seconds) as floats or rationals

    Returns:
        Decimal degrees as float
    """
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)


def _parse_gps_info(gps_info: Dict[int, Any]) -> Dict[str, Any]:
    """
    Parse GPS information from EXIF GPSInfo dictionary.

    Args:
        gps_info: GPS data dictionary from EXIF (tag 34853)

    Returns:
        Dictionary with lat, lon, altitude, direction, gpstime if available
    """
    gps_data = {}

    # Convert numeric GPS tags to readable names
    gps_readable = {}
    for tag_id, value in gps_info.items():
        tag_name = GPSTAGS.get(tag_id, tag_id)
        gps_readable[tag_name] = value

    # Extract latitude
    if "GPSLatitude" in gps_readable and "GPSLatitudeRef" in gps_readable:
        lat = _convert_gps_to_degrees(gps_readable["GPSLatitude"])
        if gps_readable["GPSLatitudeRef"] != "N":
            lat = -lat
        gps_data["lat"] = lat

    # Extract longitude
    if "GPSLongitude" in gps_readable and "GPSLongitudeRef" in gps_readable:
        lon = _convert_gps_to_degrees(gps_readable["GPSLongitude"])
        if gps_readable["GPSLongitudeRef"] != "E":
            lon = -lon
        gps_data["lon"] = lon

    # Extract altitude
    if "GPSAltitude" in gps_readable:
        altitude = float(gps_readable["GPSAltitude"])
        if "GPSAltitudeRef" in gps_readable and gps_readable["GPSAltitudeRef"] == 1:
            altitude = -altitude
        gps_data["altitude"] = altitude

    # Extract direction
    if "GPSImgDirection" in gps_readable:
        gps_data["direction"] = float(gps_readable["GPSImgDirection"])
        if "GPSImgDirectionRef" in gps_readable:
            gps_data["direction_ref"] = gps_readable["GPSImgDirectionRef"]

    # Extract GPS timestamp
    if "GPSDateStamp" in gps_readable and "GPSTimeStamp" in gps_readable:
        try:
            date_str = gps_readable["GPSDateStamp"]
            time_tuple = gps_readable["GPSTimeStamp"]
            # Date format: "YYYY:MM:DD"
            year, month, day = [int(x) for x in date_str.split(":")]
            hour = int(time_tuple[0])
            minute = int(time_tuple[1])
            second = int(time_tuple[2])
            dt = datetime.datetime(year, month, day, hour, minute, second, tzinfo=datetime.timezone.utc)
            gps_data["gpstime"] = dt
        except (ValueError, IndexError, AttributeError) as e:
            log.debug(f"Failed to parse GPS timestamp: {e}")

    return gps_data


def _parse_exif_datetime(exif_data: Dict[int, Any]) -> Optional[datetime.datetime]:
    """
    Parse datetime from EXIF data.

    Tries DateTimeOriginal first, then DateTime.

    Args:
        exif_data: EXIF data dictionary

    Returns:
        Datetime object if found, None otherwise
    """
    # Try DateTimeOriginal first (tag 36867)
    dt_str = exif_data.get(EXIF_DATETIME_ORIGINAL)
    if not dt_str:
        # Fall back to DateTime (tag 306)
        dt_str = exif_data.get(EXIF_DATETIME)

    if dt_str:
        try:
            # Remove null bytes and strip whitespace
            dt_str = str(dt_str).strip("\0").strip()
            # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
            return datetime.datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        except ValueError as e:
            log.debug(f"Failed to parse EXIF datetime '{dt_str}': {e}")

    return None


def _parse_iptc_data(iptc_data: Dict[tuple, Any]) -> Dict[str, Any]:
    """
    Parse IPTC metadata from image.

    Args:
        iptc_data: IPTC data dictionary from PIL.IptcImagePlugin

    Returns:
        Dictionary with title, caption, headline, copyright, keywords/tags
    """
    info = {}

    def decode_iptc_value(value):
        """Decode IPTC value from bytes to string."""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return value

    # Caption/Abstract (IPTC tag 2:120)
    if (2, 120) in iptc_data:
        caption = decode_iptc_value(iptc_data[(2, 120)])
        if caption:
            info["caption"] = caption

    # Object Name (IPTC tag 2:5)
    if (2, 5) in iptc_data:
        title = decode_iptc_value(iptc_data[(2, 5)])
        if title:
            info["title"] = title

    # Headline (IPTC tag 2:105)
    if (2, 105) in iptc_data:
        headline = decode_iptc_value(iptc_data[(2, 105)])
        if headline:
            info["headline"] = headline

    # Copyright Notice (IPTC tag 2:116)
    if (2, 116) in iptc_data:
        copyright_notice = decode_iptc_value(iptc_data[(2, 116)])
        if copyright_notice:
            info["copyright"] = copyright_notice

    # Keywords (IPTC tag 2:25)
    if (2, 25) in iptc_data:
        keywords = iptc_data[(2, 25)]
        if isinstance(keywords, bytes):
            keywords = [decode_iptc_value(keywords)]
        elif isinstance(keywords, list):
            keywords = [decode_iptc_value(kw) for kw in keywords]
        if keywords and any(kw for kw in keywords):
            info["keywords"] = ",".join(keywords)
            info["tags"] = keywords

    return info


def get_pdf_metadata(filepath: str) -> Dict[str, Any]:
    """
    Extract basic metadata from PDF file.

    Currently returns minimal metadata. PDF files have different metadata
    structure than images (XMP, document properties), which could be
    extracted with PyPDF2 or similar libraries if needed in the future.

    Args:
        filepath: Path to PDF file

    Returns:
        Dictionary containing basic metadata (mostly empty for now)
    """
    info: Dict[str, Any] = {}
    info["gps"] = {}

    # PDF files don't have GPS or image-like metadata
    # Could be extended with PyPDF2 to read document properties,
    # creation date, author, etc. if needed

    return info


def get_image_metadata(filepath: str) -> Dict[str, Any]:
    """
    Extract metadata from image file using Pillow.

    Extracts:
    - EXIF data (GPS, datetime, orientation)
    - IPTC data (title, caption, keywords, copyright)
    - Image dimensions

    Args:
        filepath: Path to image file

    Returns:
        Dictionary containing all available metadata
    """
    info: Dict[str, Any] = {}
    info["gps"] = {}

    try:
        with Image.open(filepath) as im:
            # Get dimensions
            info["width"], info["height"] = im.size

            # Extract EXIF data
            try:
                exif_data = im.getexif()
                if exif_data:
                    # Parse GPS info
                    gps_ifd = exif_data.get_ifd(EXIF_GPS_INFO)
                    if gps_ifd:
                        info["gps"] = _parse_gps_info(gps_ifd)

                    # Parse datetime
                    dt = _parse_exif_datetime(exif_data)
                    if dt:
                        info["creation_time"] = dt

                    # Parse orientation
                    orientation = exif_data.get(EXIF_ORIENTATION)
                    if orientation:
                        info["orientation"] = orientation

                    # Store full EXIF for backwards compatibility if needed
                    # Convert to dictionary with tag names
                    exif_dict = {}
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        exif_dict[tag_name] = value
                    info["exif"] = exif_dict
            except Exception as e:
                log.debug(f"Error extracting EXIF from {filepath}: {e}")

            # Extract IPTC data
            try:
                iptc_data = getiptcinfo(im)
                if iptc_data:
                    iptc_info = _parse_iptc_data(iptc_data)
                    info.update(iptc_info)
            except Exception as e:
                log.debug(f"Error extracting IPTC from {filepath}: {e}")

    except Exception as e:
        log.error(f"Error opening image file {filepath}: {e}")
        return info

    # Backwards compatibility: add lat/lon at top level if GPS data exists
    if "lat" in info["gps"] and "lon" in info["gps"]:
        info["lat"] = info["gps"]["lat"]
        info["lon"] = info["gps"]["lon"]

    # Add gpstime to creation_time if no EXIF datetime but GPS time exists
    if "creation_time" not in info and "gpstime" in info["gps"]:
        info["creation_time"] = info["gps"]["gpstime"]

    return info


def get_metadata(filepath: str, mimetype: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract all available metadata from a file.

    This is the main entry point for metadata extraction. It automatically
    detects the file type and extracts appropriate metadata.

    Args:
        filepath: Path to file
        mimetype: Optional MIME type. If None, will be auto-detected.

    Returns:
        Dictionary containing metadata:
        - For images: width, height, gps (lat, lon, altitude), creation_time,
          IPTC data (title, caption, keywords, copyright), exif
        - For videos: width, height, duration, bitrate, gps, creation_time
        - For audio: duration, bitrate, gps, creation_time
        - For PDFs: basic metadata (can be extended with PyPDF2 if needed)
        - For all: mimetype, filemtime, filesize
    """
    info: Dict[str, Any] = {}

    # Detect MIME type if not provided
    if mimetype is None:
        mimetype = get_mimetype(filepath)

    # Extract metadata based on file type
    if mimetype.startswith("video/") or mimetype.startswith("audio/"):
        try:
            ffp = FFProbe(filepath)
            if ffp.is_video():
                info = ffp.get_videoinfo()
            elif ffp.is_audio():
                info = ffp.get_audioinfo()
                # Fix mimetype if it starts with video (e.g. video/3gpp for audio)
                if "mimetype" not in info and mimetype.startswith("video"):
                    info["mimetype"] = mimetype.replace("video", "audio")
        except Exception as e:
            log.error(f"Error running FFProbe on {filepath}: {e}")

    elif mimetype == "application/pdf":
        try:
            info = get_pdf_metadata(filepath)
        except Exception as e:
            log.error(f"Error extracting PDF metadata from {filepath}: {e}")

    elif mimetype.startswith("image/"):
        try:
            info = get_image_metadata(filepath)
        except Exception as e:
            log.error(f"Error extracting image metadata from {filepath}: {e}")

    # Add file system metadata
    try:
        info["filemtime"] = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
        info["filesize"] = os.path.getsize(filepath)
    except OSError as e:
        log.error(f"Error getting file stats for {filepath}: {e}")

    # Set mimetype if not already set
    if "mimetype" not in info:
        info["mimetype"] = mimetype

    return info


def main():
    """
    Command-line interface for testing metadata extraction.

    Usage:
        python filemetadata.py <filepath> [<filepath> ...]
    """
    import sys
    from pprint import pprint

    if len(sys.argv) < 2:
        print("Usage: python filemetadata.py <filepath> [<filepath> ...]")
        sys.exit(1)

    for filepath in sys.argv[1:]:
        print(f"\n{'=' * 80}")
        print(f"File: {filepath}")
        print(f"{'=' * 80}")

        if not os.path.exists(filepath):
            print(f"ERROR: File not found: {filepath}")
            continue

        try:
            metadata = get_metadata(filepath)
            pprint(metadata, width=120)

            # Also show hash and mimetype
            print(f"\nSHA1: {hashfile(filepath)}")
            print(f"MIME: {get_mimetype(filepath)}")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
