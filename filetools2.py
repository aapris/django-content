# -*- coding: utf-8 -*-
import hashlib
import os
import re
import subprocess
import json
import datetime
import warnings
import functools
from dateutil import parser
import magic
import EXIF
from get_lat_lon_exif_pil import get_exif_data, get_lat_lon
from PIL import Image as ImagePIL
from iptcinfo import IPTCInfo


def deprecated(func):
    """
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    """

    @functools.wraps(func)
    def new_func(*args, **kwargs):
        warnings.warn_explicit(
            "Call to deprecated function {}.".format(func.__name__),
            category=DeprecationWarning,
            filename=func.func_code.co_filename,
            lineno=func.func_code.co_firstlineno + 1
        )
        return func(*args, **kwargs)
    return new_func


class FFProbe:
    """Wrapper for the ffprobe command"""

    audio_mimemap = {
        'amr': 'audio/amr',
        '3gp': 'audio/3gpp',
        '3ga': 'audio/3gpp',
        'm4a': 'audio/mp4a-latm',  # 'audio/mp4',
        'ogg': 'audio/ogg',
        'mp3': 'audio/mpeg',
    }

    video_mimemap = {
        '3gp': 'video/3gpp',
    }

    def __init__(self, path):
        self.path = path
        self.get_streams_dict()
        self.data = None

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
        # print ' '.join(command)
        # print os.path.isfile(url)
        try:
            # print ' '.join(command)
            output = subprocess.check_output(command)
        except subprocess.CalledProcessError, err:  # Probably file not found
            # TODO: log file and error here.
            print "Subprocess error:", err
            print ' '.join(command)
            raise
        except OSError, err:  # Probably executable was not found
            # TODO: log file and error here.
            print "OSError:", err
            print ' '.join(command)
            raise

        self.data = json.loads(output)
        return True

    def _ffprobe_command(self, url):
        return ['ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-show_format',
                '%s' % url]

    def has_video_stream(self):
        """
        Use ffprobe wrapper to check whether the file
        at path is a valid video file.
        """
        # If there are no streams available, then the file is not a video
        if 'streams' not in self.data:
            return False
        # Check each stream, looking for a video
        for streamInfo in self.data['streams']:
            # Check if the codec is a video
            codecType = streamInfo['codec_type']
            if codecType == 'video':
                # Images and other binaries are sometimes parsed as videos,
                # so also check that there's at least 1 second of video
                duration = streamInfo.get('duration', 0.0)
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
        if 'streams' not in self.data:
            return False
        # Check each stream, looking for a video
        for streamInfo in self.data['streams']:
            # Check if the codec is a video
            codecType = streamInfo['codec_type']
            # print codecType, streamInfo
            if codecType == 'audio':
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
        if (self.has_audio_stream() is True
            and self.has_video_stream() is False):
            return True
        else:
            return False

    def get_latlon(self, info):
        # "+60.1878+025.0339/"
        try:
            if 'location' in self.data['format']['tags']:
                loc = self.data['format']['tags']['location']
                m = re.match(r'^(?P<lat>[\-\+][\d]+\.[\d]+)(?P<lon>[\-\+][\d]+\.[\d]+)', loc)
                if m:
                    info['lat'] = float(m.group('lat'))
                    info['lon'] = float(m.group('lon'))
        except KeyError, e:
            pass
            # print "Does not exist", e

    def get_creation_time(self, info):
        try:
            if 'creation_time' in self.data['format']['tags']:
                ts = self.data['format']['tags']['creation_time']
                info['creation_time'] = parser.parse(ts)
        except KeyError, e:
            pass
            # print "Does not exist", e

    def get_duration(self, stream, info):
        if 'duration' in stream:
            info['duration'] = float(stream.get('duration', 0.0))

    def get_videoinfo(self):
        info = {}
        if 'streams' not in self.data:
            return info
        for stream in self.data['streams']:
            # Check if the codec is a video
            if stream['codec_type'] == 'video':
                self.get_duration(stream, info)
                info['width'] = int(stream.get('width', 0))
                info['height'] = int(stream.get('height', 0))
                break
        if 'bit_rate' in self.data['format']:
            info['bitrate'] = int(self.data['format']['bit_rate'])
        # Sometimes duration is not in video stream but in format
        if 'duration' not in info and 'format' in self.data:
            self.get_duration(self.data['format'], info)
        self.get_latlon(info)
        self.get_creation_time(info)
        return info

    def get_audioinfo(self):
        info = {}
        if 'streams' not in self.data:
            return info
        for stream in self.data['streams']:
            # Check if the codec is a video
            if stream['codec_type'] == 'audio':
                self.get_duration(stream, info)
                break
        if 'bit_rate' in self.data['format']:
            info['bitrate'] = int(self.data['format']['bit_rate'])
        ext = os.path.splitext(self.path)[1].lstrip('.').lower()
        if ext in self.audio_mimemap.keys():
            info['mimetype'] = self.audio_mimemap[ext]

        # print ext, info
        self.get_latlon(info)
        self.get_creation_time(info)
        return info


def hashfile(path):
    BLOCKSIZE = 65536
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    with open(path, 'rb') as f:
        buf = f.read(BLOCKSIZE)
        while len(buf) > 0:
            md5.update(buf)
            sha1.update(buf)
            buf = f.read(BLOCKSIZE)
    return (md5.hexdigest(), sha1.hexdigest())


def guess_encoding(str):
    """
    Try to guess is the str utf8, mac-roman or latin-1 encoded.
    http://en.wikipedia.org/wiki/Mac_OS_Roman
    http://en.wikipedia.org/wiki/Latin1
    Code values 00–1F, 7F–9F are not assigned to characters by ISO/IEC 8859-1.
    http://stackoverflow.com/questions/4198804/how-to-reliably-guess-the-encoding-between-macroman-cp1252-latin1-utf-8-and-a
    """
    try:
        unicode(str, 'utf8')
        return "utf8"
    except UnicodeDecodeError:
        if re.compile(r'[\x00–\x1f\x7f-\x9f]').findall(str):
            return "mac-roman"
        else:
            return "latin-1"


def get_imageinfo(filepath):
    """
    Return EXIF and IPTC information found from image file in a dictionary.
    Uses EXIF.py, PIL and iptcinfo.
    NOTE: PIL can read EXIF tags including GPS tags also.
    """
    info = {}
    with open(filepath, "rb") as f:
        try:
            exif = EXIF.process_file(f, stop_tag="UNDEF", details=True, strict=False, debug=False)
        except IndexError, err:
            # File "content/EXIF.py", line 1680, in process_file
            # f.seek(offset+thumb_off.values[0])
            exif = None
        if exif:
            info['exif'] = exif
        im = ImagePIL.open(filepath)
        info['width'], info['height'] = im.size
        try:
            exif_data = get_exif_data(im)
            # print exif_data['GPSInfo']
            if 'GPSInfo' in exif_data:
                latlon = get_lat_lon(exif_data)
                if latlon[0] is not None:
                    info['lat'], info['lon'] = latlon
            if 'DateTimeOriginal' in exif_data:
                try:
                    datestring = exif_data.get('DateTimeOriginal', '').strip('\0')  # remove possible null bytes
                    datestring = datestring.replace(':', '-', 2)
                    info['creation_time'] = parser.parse(datestring)  #  .replace(tzinfo=timezone.utc)
                    # print "XXXXXXxxxxx", datestring, info['creation_time']
                    print exif_data.keys()
                except ValueError, err:  # E.g. value is '0000:00:00 00:00:00\x00'
                    pass  # TODO: logger.warning(str(err))
                except TypeError, err:  # E.g. value is '4:24:26\x002004:06:25 0'
                    pass  # TODO: logger.warning(str(err))
                except Exception, err:
                    pass  # TODO: logger.warning(str(err))
                    # print "WRONG DATE: '"+ datestring + "'"
        except AttributeError, err:  # _getexif does not exist
            pass

    iptc = IPTCInfo(filepath, force=True)
    # TODO: extract more tags from iptc (copyright, author etc)
    # iptc2info_map = {
    #    'caption/abstract': 'caption',
    #    'object name': 'title',
    #    'keywords': 'keywords',
    # }
    if iptc:
        info['iptc'] = iptc
        if iptc.data['caption/abstract']:
            # cap = iptc.data['caption/abstract']
            # info['caption'] = cap.decode(guess_encoding(cap))
            info['caption'] = iptc.data['caption/abstract']
            # print info['caption'], type(info['caption'])
        if iptc.data['object name']:
            info['title'] = iptc.data['object name']
        if iptc.data['keywords']:
            kw_str = ','.join(iptc.data['keywords'])
            # info['keywords'] = kw_str.decode(guess_encoding(kw_str))
            info['keywords'] = kw_str
            info['tags'] = iptc.data['keywords']
            # print info['keywords'], type(info['keywords'])
        for key in info:  # Convert all str values to unicode
            if isinstance(info[key], str):
                info[key] = unicode(info[key], guess_encoding(info[key]))
    return info


def fileinfo(path):
    """
    Return some information from file found in 'path'.
    filemtime, filesize and mimetypa are always present.
    Image, Video and audio files may have also width, height, duration,
    creation_time, lat, lon (gps coordinates) etc. info.
    Images may have also some exif and IPTC field parsed.
    """
    info = {}
    # Get quickly mimetype first, because we don't want to run FFProbe
    # for e.g. xml files
    with open(path, 'rb') as f:
        mimetype = magic.from_buffer(f.read(4096), mime=True)
    # mimetype = magic.from_file(path, mime=True)
    if mimetype not in ['application/xml'] and not mimetype.startswith('image'):
        ffp = FFProbe(path)
        if ffp.is_video():
            info = ffp.get_videoinfo()
        elif ffp.is_audio():
            info = ffp.get_audioinfo()
            # Fix mimetype if it starts with video (e.g. video/3gpp)
            if 'mimetype' not in info and mimetype.startswith('video'):
                info['mimetype'] = mimetype.replace('video', 'audio')
    else:
        try:
            info = get_imageinfo(path)
            if 'exif' in info:
                del info['exif']
        except IOError:  # is not image
            pass
    info['filemtime'] = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    info['filesize'] = os.path.getsize(path)
    if 'mimetype' not in info:  # FFProbe() did not detect file
        info['mimetype'] = mimetype
    return info


def do_video_thumbnail(src, target):
    """
    Create a thumbnail from video file 'src' and save it to 'target'.
    Return True if subprocess was called with error code 0.
    TODO: make -ss configurable, now it is hardcoded 1 seconds.

    subprocess.check_call(
    ['ffmpeg', '-ss', '1', '-i', 'test_content/05012009044.mp4', '-vframes', '1', '-f', 'mjpeg', '-s', '320x240', 'test-1.jpg'])
    ffmpeg -ss 1 -i test_content/05012009044.mp4 -vframes 1 -f mjpeg -s 320x240 test-1.jpg
    ffmpeg -ss 2 -i test_content/05012009044.mp4 -vframes 1 -f mjpeg -s 320x240 test-2.jpg
    ffmpeg -ss 3 -i test_content/05012009044.mp4 -vframes 1 -f mjpeg -s 320x240 test-3.jpg
    """
    try:
        # FIXME: this fails to create thumbnail if the seconds value after -ss exeeds clip length
        subprocess.check_call([
            'ffmpeg', '-y', '-ss', '1', '-i', src,
            '-vframes', '1', '-f', 'mjpeg', target
            ])
        if os.path.isfile(target):
            return True
        else:
            return False
    except subprocess.CalledProcessError:
        # TODO: log file and error here.
        return False

def do_pdf_thumbnail(src, target):
    """
    Create a thumbnail from a PDF file 'src' and save it to 'target'.
    Return True if subprocess returns with error code 0 and target exits.
    """
    CONVERT = 'convert'
    # convert -flatten  -geometry 1000x1000 foo.pdf[0] thumb.png
    try:
        cmd = [CONVERT, '-flatten', '-geometry', '1000x1000', src+'[0]', target]
        print ' '.join(cmd)
        subprocess.check_call(cmd)
        # TODO: check also that target is really non-broken file
        if os.path.isfile(target):
            return True
        else:
            return False
    except subprocess.CalledProcessError:
        # TODO: log file and error here.
        return False




if __name__ == '__main__':
    import sys
    for path in sys.argv[1:]:
        print path, fileinfo(path)
    # ffp = FFProbe(path)
    # print path, ffp.is_video(), ffp.is_audio()
    # if ffp.is_video(): print ffp.get_videoinfo()
    # if ffp.is_audio(): print ffp.get_audioinfo()
