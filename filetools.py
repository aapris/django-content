"""
Read as much metadata from a file as possible. Mainly usable with
media files (image, video, audio files), but can do also video and pdf
thumbnail.
"""
import datetime
import hashlib
import io
import json
import logging
import os
import re
import subprocess
import tempfile
from typing import Tuple

import magic
from PIL import Image
from dateutil import parser
from iptcinfo3 import IPTCInfo

from content.exifparser import read_exif, parse_datetime, parse_gps


# from .exifparser import read_exif, parse_datetime, parse_gps


class FFProbe:
    """
    Wrapper for the ffprobe command
    """

    audio_mimemap = {
        "amr": "audio/amr",
        "3gp": "audio/3gpp",
        "3ga": "audio/3gpp",
        "m4a": "audio/mp4a-latm",  # 'audio/mp4',
        "ogg": "audio/ogg",
        "mp3": "audio/mpeg",
    }

    video_mimemap = {
        "3gp": "video/3gpp",
    }

    ffprobe = "ffprobe"  # TODO: try to find full path of ffprobe

    def __init__(self, path):
        self.path = path
        self.data = None
        self.get_streams_dict()

    def get_streams_dict(self):
        """
        Returns a Python dictionary containing
        information on the audio/video streams contained
        in the file located at 'url'

        If no stream information is available (e.g.
        because the file is not parsable by ffprobe/ffmpeg), returns
        an empty dictionary
        """
        command = self._ffprobe_command(self.path)
        logging.debug(" ".join(command))
        try:
            output = subprocess.check_output(command, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as err:  # Probably file not found
            # TODO: log file and error here.
            logging.error("Subprocess error: {}".format(err, " ".join(command)))
            output = "{}"  # empty json object
            # raise
        except OSError as err:  # Probably executable was not found
            # TODO: log file and error here.
            logging.error("OSError: {}".format(err, " ".join(command)))
            raise
        self.data = json.loads(output)
        # print(json.dumps(self.data, indent=1))
        return True

    def _ffprobe_command(self, url: str) -> list:
        return [self.ffprobe, "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", url]

    def has_video_stream(self):
        """
        Use ffprobe wrapper to check whether the file
        at path is a valid video file.
        """
        # If there are no streams available, then the file is not a video
        if "streams" not in self.data:
            return False
        # Check each stream, looking for a video
        for streamInfo in self.data["streams"]:
            # Check if the codec is a video
            codec_type = streamInfo["codec_type"]
            if codec_type == "video":
                # Images and other binaries are sometimes parsed as videos,
                # so also check that there's at least 1 second of video
                duration = streamInfo.get("duration", 0.0)
                if float(duration) > 1.0:
                    return True
        # If we can't find any video streams, the file is not a video
        return False

    def has_audio_stream(self):
        """
        Use ffprobe wrapper to check whether the file
        at path is a valid audio file.
        """
        # If there are no streams available, then the file is not a video
        if "streams" not in self.data:
            return False
        # Check each stream, looking for a video
        for streamInfo in self.data["streams"]:
            # Check if the codec is a video
            codec_type = streamInfo["codec_type"]
            if codec_type == "audio":
                return True
        # If we can't find any audio streams, the file is not a audio
        return False

    def is_video(self):
        """
        Return True if file has a video stream.
        """
        return self.has_video_stream()

    def is_audio(self):
        """
        Return True if file has an audio stream, but not video stream.
        """
        if self.has_audio_stream() is True and self.has_video_stream() is False:
            return True
        else:
            return False

    def get_gps(self, info: dict):
        """
        Add gps data (lat, lon and optionally altitude) to info.

        Android OnePlus 9:
        "location": "+60.2163+024.9808/"
        iPhone 12 Pro Max:
        "com.apple.quicktime.location.ISO6709": "+60.1997+024.9473+016.943/",
        """
        loc = None
        gps = {}
        if "location" in self.data["format"]["tags"]:
            loc = self.data["format"]["tags"]["location"]
        elif "com.apple.quicktime.location.ISO6709" in self.data["format"]["tags"]:
            loc = self.data["format"]["tags"]["com.apple.quicktime.location.ISO6709"]
        # loc = "+60.1997+024.9473/"
        if loc is not None:
            m = re.match(r"^(?P<lat>[\-+]\d+\.\d+)(?P<lon>[\-+]\d+\.\d+)(?P<alt>[\-+]\d+\.\d+)?", loc)
            if m:
                print(m)
                gps["lat"] = float(m.group("lat"))
                gps["lon"] = float(m.group("lon"))
                if m.group("alt"):
                    gps["altitude"] = float(m.group("alt"))
        info["gps"] = gps

    def get_creation_time(self, info: dict):
        try:
            if "creation_time" in self.data["format"]["tags"]:
                ts = self.data["format"]["tags"]["creation_time"]
                info["creation_time"] = parser.parse(ts)
        except KeyError:
            pass

    def get_duration(self, stream, info):
        if "duration" in stream:
            info["duration"] = float(stream.get("duration", 0.0))

    def get_videoinfo(self):
        info = {}
        if "streams" not in self.data:
            return info
        for stream in self.data["streams"]:
            # Check if the codec is a video
            if stream["codec_type"] == "video":
                self.get_duration(stream, info)
                info["width"] = int(stream.get("width", 0))
                info["height"] = int(stream.get("height", 0))
                break
        if "bit_rate" in self.data["format"]:
            info["bitrate"] = int(self.data["format"]["bit_rate"])
        # Sometimes duration is not in video stream but in format
        if "duration" not in info and "format" in self.data:
            self.get_duration(self.data["format"], info)
        self.get_gps(info)
        self.get_creation_time(info)
        return info

    def get_audioinfo(self):
        info = {}
        if "streams" not in self.data:
            return info
        for stream in self.data["streams"]:
            # Check if the codec is a video
            if stream["codec_type"] == "audio":
                self.get_duration(stream, info)
                break
        if "bit_rate" in self.data["format"]:
            info["bitrate"] = int(self.data["format"]["bit_rate"])
        ext = os.path.splitext(self.path)[1].lstrip(".").lower()
        if ext in list(self.audio_mimemap.keys()):
            info["mimetype"] = self.audio_mimemap[ext]

        self.get_gps(info)
        self.get_creation_time(info)
        return info


def hashfile(filepath: str) -> Tuple[str, str]:
    """
    Return md5 and sha1 hashes of file in hex format
    """
    block_size = 65536
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    with open(filepath, "rb") as f:
        buf = f.read(block_size)
        while len(buf) > 0:
            md5.update(buf)
            sha1.update(buf)
            buf = f.read(block_size)
    return md5.hexdigest(), sha1.hexdigest()


def guess_encoding(b: bytes) -> str:
    """
    NOTE: this is from Python 2.x times and outdated. Kept here for now, though.
    Try to guess is the text utf8, mac-roman or latin-1 encoded.
    http://en.wikipedia.org/wiki/Mac_OS_Roman
    http://en.wikipedia.org/wiki/Latin1
    Code values 00–1F, 7F–9F are not assigned to characters by ISO/IEC 8859-1.
    http://stackoverflow.com/questions/4198804
    """
    try:
        b.decode("utf8")
        return "utf8"
    except UnicodeDecodeError:
        if re.compile(r"[\x00–\x1f\x7f-\x9f]").findall(b):
            return "mac-roman"
        else:
            return "latin-1"


def get_mimetype(filepath: str) -> str:
    """
    Return mimetype of given file by reading first bytes of it
    and using python-magic.
    """
    with open(filepath, "rb") as f:
        mimetype = magic.from_buffer(f.read(4096), mime=True)
    return mimetype


def get_imageinfo(filepath: str) -> dict:
    """
    Return EXIF and IPTC information found from image file in a dictionary.
    """
    info = {}
    info["exif"] = exif = read_exif(filepath)
    info["gps"] = gps = parse_gps(exif)
    info.update(parse_datetime(exif, tag_name="EXIF DateTimeOriginal", gps=gps))
    if "lat" in gps:  # Backwards compatibility
        info["lat"], info["lon"] = gps["lat"], gps["lon"]
    info["iptc"] = iptc = IPTCInfo(filepath, force=True)
    try:
        if iptc.data["caption/abstract"]:
            info["caption"] = iptc.data["caption/abstract"]
        if iptc.data["object name"]:
            info["title"] = iptc.data["object name"]
        if iptc.data["keywords"]:
            kw_str = ",".join(iptc.data["keywords"])
            info["keywords"] = kw_str
            info["tags"] = iptc.data["keywords"]
        for key in info:  # Convert all str values to unicode
            if isinstance(info[key], str):
                info[key] = str(info[key], guess_encoding(info[key]))
    except AttributeError:
        pass
    with open(str(filepath), "rb") as f:
        im = Image.open(f)
        info["width"], info["height"] = im.size
        del im
    return info


def fileinfo(filepath: str) -> dict:
    """
    Return some information from file found in 'filepath'.
    filemtime, filesize and mimetype are always present.
    Image, Video and audio files may have also width, height, duration,
    creation_time, lat, lon (gps coordinates) etc. info.
    Images may have also some exif and IPTC field parsed.
    """
    info = {}
    # Get quickly mimetype first, because we don't want to run FFProbe
    # for e.g. xml files
    mimetype = get_mimetype(filepath)
    if mimetype.startswith(("video/", "audio/")):
        ffp = FFProbe(filepath)
        if ffp.is_video():
            info = ffp.get_videoinfo()
        elif ffp.is_audio():
            info = ffp.get_audioinfo()
            # Fix mimetype if it starts with video (e.g. video/3gpp)
            if "mimetype" not in info and mimetype.startswith("video"):
                info["mimetype"] = mimetype.replace("video", "audio")
    elif mimetype.startswith(("image/",)) or mimetype in ("application/pdf",):
        try:
            info = get_imageinfo(filepath)
            if "exif" in info:
                del info["exif"]
        except IOError:  # is not image
            pass
    else:
        pass
    info["filemtime"] = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
    info["filesize"] = os.path.getsize(filepath)
    if "mimetype" not in info:  # FFProbe() did not detect file
        info["mimetype"] = mimetype
    return info


def run_ffmpeg(filepath: str, params: list, outfile: str = None, ext: str = None) -> Tuple[str, str, bytes]:
    """
    Run ffmpeg command for `filepath`, using `params`.
    Return output file name, the actual command which was run and command's stdout output.
    Commands stderr is piped to devnull.
    """
    if outfile is None:
        outfile = "{}.{}".format(tempfile.NamedTemporaryFile(delete=False).name, ext)
    ffmpeg_cmd = ["ffmpeg", "-i", filepath]
    full_cmd = ffmpeg_cmd + params + [outfile]
    cmd_str = " ".join(full_cmd)
    logging.debug(cmd_str)
    p = subprocess.Popen(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    output = p.stdout.read()
    return outfile, cmd_str, output


def create_videoinstance(filepath: str, params: list = (), outfile=None, ext="webm") -> Tuple[str, str, bytes]:
    if not params:
        params = ["-acodec", "libvorbis", "-ac", "2", "-ab", "96k", "-ar", "22050", "-b", "345k", "-s", "320x240"]
    return run_ffmpeg(filepath, params, outfile, ext)


def create_audioinstance(filepath: str, params=(), outfile=None, ext="mp3") -> Tuple[str, str, bytes]:
    if not params:
        params = ["-acodec", "libmp3lame", "-ab", "64k"]
    return run_ffmpeg(filepath, params, outfile, ext)


def do_video_thumbnail(src: str, target: str, sec=1.0):
    """
    Create a thumbnail from video file 'src' and save it to 'target'.
    Return True if subprocess was called with error code 0.
    TODO: make -ss configurable, now it is hardcoded 1 seconds.

    subprocess.check_call([
        'ffmpeg', '-ss', '1', '-i', 'test_content/05012009044.mp4', '-vframes',
        '1', '-f', 'mjpeg', '-s', '320x240', 'test-1.jpg'])
        ffmpeg -ss 1 -i test.mp4 -vframes 1 -f mjpeg -s 320x240 test-1.jpg
        ffmpeg -ss 2 -i test.mp4 -vframes 1 -f mjpeg -s 320x240 test-2.jpg
        ffmpeg -ss 3 -i test.mp4 -vframes 1 -f mjpeg -s 320x240 test-3.jpg
    """
    try:
        # FIXME: this fails to create thumbnail if the seconds value after -ss exeeds clip length
        # NOTE: keep -ss before -i
        ffmpeg_cmd = ["ffmpeg", "-y", "-ss", str(sec), "-i", src, "-vframes", "1", "-f", "mjpeg", target]
        logging.debug(ffmpeg_cmd)
        subprocess.check_call(ffmpeg_cmd, stderr=subprocess.DEVNULL)
        if os.path.isfile(target):  # TODO: check that size > 0 ?
            return True
        else:
            return False
    except subprocess.CalledProcessError:
        # TODO: log file and error here.
        return False


def do_pdf_thumbnail(src: str, target: str) -> bool:
    """
    Create a thumbnail from a PDF file 'src' and save it to 'target'.
    Return True if subprocess returns with error code 0 and target exits.
    """
    convert = "convert"
    # convert -flatten  -geometry 1000x1000 foo.pdf[0] thumb.png
    try:
        cmd = [convert, "-flatten", "-geometry", "1000x1000", src + "[0]", target]
        logging.debug(cmd)
        subprocess.check_call(cmd, stderr=subprocess.DEVNULL)
        # TODO: check also that target is really non-broken file
        if os.path.isfile(target):  # TODO: check that size > 0 ?
            return True
        else:
            return False
    except subprocess.CalledProcessError:
        # TODO: log file and error here.
        return False


def create_thumbnail(filepath: str, t: list) -> io.BytesIO:
    """
    t = [width, height, ?, jpeg quality, rotate degrees]
    """
    try:
        im = Image.open(filepath)
    except IOError:  # Image file is corrupted
        logging.warning(f"ERROR in image file: {filepath}")
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
    # NOTE: the size will be increased if original is smaller than size
    tmp = io.BytesIO()
    im.save(tmp, "jpeg", quality=t[3])
    tmp.seek(0)
    return tmp


if __name__ == "__main__":
    import sys
    from pprint import pprint

    for path in sys.argv[1:]:
        print(path)
        pprint(fileinfo(path))
        create_thumbnail(path, (400, 400, None, 80, 0))
