"""
File utility functions for media processing.

This module provides utility functions for:
- Creating thumbnails from images, videos, and PDFs
- Running FFmpeg commands for media conversion
- Creating video and audio instances in different formats

For metadata extraction, use the filemetadata module instead.
"""

import io
import logging
import os
import subprocess
import tempfile
from typing import Tuple

from pdf2image import convert_from_path
from PIL import Image
from pillow_heif import register_heif_opener


register_heif_opener()

log = logging.getLogger(__name__)


def run_ffmpeg(filepath: str, params: list, outfile: str = None, ext: str = None) -> Tuple[str, str, bytes]:
    """
    Run ffmpeg command for `filepath`, using `params`.

    Args:
        filepath: Input file path
        params: FFmpeg parameters list
        outfile: Output file path (optional, will create temp file if None)
        ext: Output file extension

    Returns:
        Tuple of (output_file, command_string, stdout_output)
    """
    if outfile is None:
        outfile = "{}.{}".format(tempfile.NamedTemporaryFile(delete=False).name, ext)
    ffmpeg_cmd = ["ffmpeg", "-i", filepath]
    full_cmd = ffmpeg_cmd + params + [outfile]
    cmd_str = " ".join(full_cmd)
    log.debug(cmd_str)
    p = subprocess.Popen(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    output = p.stdout.read()
    return outfile, cmd_str, output


def create_videoinstance(filepath: str, params: list = (), outfile=None, ext="webm") -> Tuple[str, str, bytes]:
    """
    Create a video instance from input file with specified parameters.

    Args:
        filepath: Input video file path
        params: FFmpeg parameters (uses defaults if empty)
        outfile: Output file path (optional)
        ext: Output file extension (default: webm)

    Returns:
        Tuple of (output_file, command_string, stdout_output)
    """
    if not params:
        params = ["-acodec", "libvorbis", "-ac", "2", "-ab", "96k", "-ar", "22050", "-b", "345k", "-s", "320x240"]
    return run_ffmpeg(filepath, params, outfile, ext)


def create_audioinstance(filepath: str, params=(), outfile=None, ext="mp3") -> Tuple[str, str, bytes]:
    """
    Create an audio instance from input file with specified parameters.

    Args:
        filepath: Input audio file path
        params: FFmpeg parameters (uses defaults if empty)
        outfile: Output file path (optional)
        ext: Output file extension (default: mp3)

    Returns:
        Tuple of (output_file, command_string, stdout_output)
    """
    if not params:
        params = ["-acodec", "libmp3lame", "-ab", "64k"]
    return run_ffmpeg(filepath, params, outfile, ext)


def do_video_thumbnail(src: str, target: str, sec=1.0) -> bool:
    """
    Create a thumbnail from video file 'src' and save it to 'target'.

    Extracts a single frame from the video at the specified second.

    Args:
        src: Source video file path
        target: Target thumbnail file path
        sec: Second at which to extract frame (default: 1.0)

    Returns:
        True if successful, False otherwise

    Example:
        ffmpeg -ss 1 -i test.mp4 -vframes 1 -f mjpeg test-thumb.jpg
    """
    try:
        # NOTE: keep -ss before -i for better performance
        ffmpeg_cmd = ["ffmpeg", "-y", "-ss", str(sec), "-i", src, "-vframes", "1", "-f", "mjpeg", target]
        log.debug(f"Creating video thumbnail: {' '.join(ffmpeg_cmd)}")
        subprocess.check_call(ffmpeg_cmd, stderr=subprocess.DEVNULL)
        if os.path.isfile(target) and os.path.getsize(target) > 0:
            return True
        else:
            return False
    except subprocess.CalledProcessError as e:
        log.error(f"Failed to create video thumbnail for {src}: {e}")
        return False


def do_pdf_thumbnail(src: str, target: str) -> bool:
    """
    Create a thumbnail from a PDF file 'src' and save it to 'target'.

    Uses pdf2image library for better quality and reliability than ImageMagick.
    Extracts the first page of the PDF as a PNG image.

    Args:
        src: Source PDF file path
        target: Target thumbnail file path

    Returns:
        True if successful, False otherwise
    """
    try:
        images = convert_from_path(
            src,
            size=(1000, 1000),  # Max size, maintains aspect ratio
            first_page=1,  # First page (1-indexed)
            last_page=1,  # Only first page
            fmt="png",  # Output format
            strict=True,  # Strict mode for better error handling
        )
        if images:
            images[0].save(target, "PNG")
            log.debug(f"Successfully created PDF thumbnail: {src} -> {target}")
            return os.path.isfile(target) and os.path.getsize(target) > 0
        else:
            log.error(f"No images generated from PDF: {src}")
            return False
    except Exception as err:
        log.error(f"Error creating PDF thumbnail for {src}: {err}")
        return False


def create_thumbnail(filepath: str, t: list) -> io.BytesIO:
    """
    Create a thumbnail from an image file.

    Args:
        filepath: Path to image file
        t: List of [width, height, unused, jpeg_quality, rotate_degrees]

    Returns:
        BytesIO object containing the thumbnail JPEG data, or False on error

    Note:
        Rotation values: 0, 90, 180, 270 degrees (clockwise)
    """
    try:
        im = Image.open(filepath)
    except IOError:
        log.warning(f"ERROR in image file: {filepath}")
        return False

    if im.mode not in ("L", "RGB"):
        im = im.convert("RGB")

    size = (t[0], t[1])
    rotatemap = {
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }

    if t[4] != 0:
        im = im.transpose(rotatemap[t[4]])

    im.thumbnail(size, Image.Resampling.LANCZOS)

    # Save resized image to a temporary buffer
    tmp = io.BytesIO()
    im.save(tmp, "jpeg", quality=t[3])
    tmp.seek(0)
    return tmp


if __name__ == "__main__":
    print("filetools.py utility functions:")
    print("  - do_video_thumbnail(src, target, sec=1.0)")
    print("  - do_pdf_thumbnail(src, target)")
    print("  - create_thumbnail(filepath, [width, height, None, quality, rotate])")
    print("  - run_ffmpeg(filepath, params, outfile, ext)")
    print("\nFor metadata extraction, use filemetadata.py instead:")
    print("  python filemetadata.py <filepath>")
