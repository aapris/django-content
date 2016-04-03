# -*- coding: utf-8 -*-
import hashlib
import os
import re
import subprocess
import json
import datetime
import tempfile
import logging
import warnings
import functools
from dateutil import parser
import magic
import exifparser
from PIL import Image as ImagePIL
from iptcinfo import IPTCInfo

logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger('content')

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
    """
    Wrapper for the ffprobe command
    """

    data = None
    ffprobe = 'ffprobe'  # TODO: try to find full path of ffprobe

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
        try:
            output = subprocess.check_output(command)
        except subprocess.CalledProcessError as err:  # Probably file not found
            msg = 'Subprocess error: "{}". Command: "{}".'.format(
                err, ' '.join(command))
            # print('File exists: {}'.format(os.path.isfile(command[-1])))
            logger.warning(msg)
            raise
        except OSError as err:  # Probably executable was not found
            msg = 'OSError error: "{}". ' \
                  'Probably ffprobe executable not found. ' \
                  'Command: "{}".'.format(
                err, ' '.join(command))
            logger.warn(msg)
            raise

        self.data = json.loads(output)
        return True

    def _ffprobe_command(self, url):
        return [self.ffprobe,
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
            if streamInfo['codec_type'] == 'video':
                # Images and other binaries are sometimes parsed as videos,
                # so also check that there's at least 1 second of video
                duration = streamInfo.get('duration')
                if duration is None:
                    if 'format' in self.data:
                        duration = self.data['format'].get('duration', 0.0)
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
            if streamInfo['codec_type'] == 'audio':
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
        if (self.has_audio_stream() is True and
                self.has_video_stream() is False):
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
        except KeyError:
            pass

    def get_creation_time(self, info):
        try:
            if 'creation_time' in self.data['format']['tags']:
                ts = self.data['format']['tags']['creation_time']
                info['creation_time'] = parser.parse(ts)
        except KeyError:
            pass

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
                # file --mime --brief thinks .ts files (MPEG transport stream)
                # are application/octet-stream, but ffprobe knows it better
                # https://en.wikipedia.org/wiki/MPEG_transport_stream
                if 'format' in self.data:
                    if self.data['format'].get('format_name') == 'mpegts':
                        info['mimetype'] = 'video/mp2t'
                    elif self.data['format'].get('format_name') == 'flv':
                        info['mimetype'] = 'video/flv'
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


def hashfile(filepath):
    """
    Return md5 and sha1 hashes of file in hex format
    """
    blocksize = 65536
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    with open(filepath, 'rb') as f:
        buf = f.read(blocksize)
        while len(buf) > 0:
            md5.update(buf)
            sha1.update(buf)
            buf = f.read(blocksize)
    return md5.hexdigest(), sha1.hexdigest()


def guess_encoding(str_):
    """
    Try to guess is the str utf8, mac-roman or latin-1 encoded.
    http://en.wikipedia.org/wiki/Mac_OS_Roman
    http://en.wikipedia.org/wiki/Latin1
    Code values 00–1F, 7F–9F are not assigned to characters by ISO/IEC 8859-1.
    http://stackoverflow.com/questions/4198804/how-to-reliably-guess-the-encoding-between-macroman-cp1252-latin1-utf-8-and-a
    """
    try:
        unicode(str_, 'utf8')
        return "utf8"
    except UnicodeDecodeError:
        if re.compile(r'[\x00–\x1f\x7f-\x9f]').findall(str_):
            return "mac-roman"
        else:
            return "latin-1"


def get_mimetype(filepath):
    """
    Return mimetype of given file.
    Use python-magic if it is found, otherwise try
    `file` command found in most unix/linux systems.
    File for windows:
    http://gnuwin32.sourceforge.net/packages/file.htm

    TODO:
    if ext in VIDEO_EXTENSIONS:
        try to find video and audio stream with ffprobe
    elif ext in AUDIO_EXTENSIONS:
        try to find audio stream with ffprobe
        if found: return arm -> audio/arm
    """
    if isinstance(filepath, str):
        filepath = filepath.decode('utf-8')
    return magic.from_file(filepath, mime=True)


def get_imageinfo(filepath):
    """
    Return EXIF and IPTC information found from image file in a dictionary.
    """
    info = {}
    info['exif'] = exif = exifparser.read_exif(filepath)
    info.update(exifparser.parse_datetime(exif, 'EXIF DateTimeOriginal'))
    info['gps'] = gps = exifparser.parse_gps(exif)
    if 'lat' in gps:  # Backwards compatibility
        info['lat'], info['lon'] = gps['lat'], gps['lon']
    info['iptc'] = iptc = IPTCInfo(filepath, force=True)
    if iptc:  # TODO: this to own function
        if iptc.data['caption/abstract']:
            info['caption'] = iptc.data['caption/abstract']
        if iptc.data['object name']:
            info['title'] = iptc.data['object name']
        if iptc.data['keywords']:
            kw_str = ','.join(iptc.data['keywords'])
            info['keywords'] = kw_str
            info['tags'] = iptc.data['keywords']
        for key in info:  # Convert all str values to unicode
            if isinstance(info[key], str):
                info[key] = unicode(info[key], guess_encoding(info[key]))
    with open(str(filepath), 'rb') as f:
        im = ImagePIL.open(f)
        info['width'], info['height'] = im.size
        del im
    return info


def fileinfo(filepath):
    """
    Retrieves file metadata.
    filemtime, filesize and mimetypa are always present.
    Image, Video and audio files may have also width, height, duration,
    creation_time, lat, lon (gps coordinates) etc. info.
    Images may have also some exif and IPTC field parsed.

    Args:
        filepath (str):

    Returns:
        A dict containing some information from file found in `filepath`.
        Example:
        {
            'mimetype': 'image/jpeg',
            'width': 4032,
            'height': 3024,
            'lat': 65.01416666666667,
            'lon': 25.471327777777777,
            'iptc': <iptcinfo.IPTCInfo object at 0x10fb41910>,
            'filesize': 2229010,
            'filemtime': datetime.datetime(2015, 12, 15, 14, 33, 46),
            'creation_time': datetime.datetime(2015, 12, 15, 14, 33, 46),
            'gps': {
                'gpstime': datetime.datetime(2015, 12, 15, 12, 33, 45,
                                             tzinfo=<UTC>),
                'direction': 289.50522648083626,
                'lat': 65.01416666666667,
                'direction_ref': u'T',
                'altitude': 20.712585034013607,
                'lon': 25.471327777777777
            }
        }

    """
    info = {}
    # Get quickly mimetype first, because we don't want to run FFProbe
    # for e.g. xml files
    with open(filepath, 'rb') as f:
        mimetype = magic.from_buffer(f.read(4096), mime=True)
    # Do not ffprobe, if mimetype is some of these:
    # no_ffprobe = ['application/pdf', 'application/xml']
    if mimetype.startswith(('video', 'audio')) or \
                    mimetype == 'application/octet-stream':
        ffp = FFProbe(filepath)
        if ffp.is_video():
            info = ffp.get_videoinfo()
        elif ffp.is_audio():
            info = ffp.get_audioinfo()
            # Fix mimetype if it starts with video (e.g. video/3gpp)
            if 'mimetype' not in info and mimetype.startswith('video'):
                info['mimetype'] = mimetype.replace('video', 'audio')
    else:
        try:
            info = get_imageinfo(filepath)
            if 'exif' in info:
                del info['exif']
        except IOError:  # is not image
            pass
    info['filemtime'] = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
    info['filesize'] = os.path.getsize(filepath)
    if 'mimetype' not in info:  # FFProbe() did not detect file
        info['mimetype'] = mimetype
    return info


def create_videoinstance(filepath, params=[], outfile=None, ext='webm'):
    ffmpeg_cmd = ['ffmpeg', '-i', '%s' % filepath]
    if outfile is None:
        outfile = tempfile.NamedTemporaryFile(delete=False).name + '.' + ext
    if not params:
        params = ['-c:a', 'libvorbis', '-c:v', 'libvpx', '-ac', '2', '-b:v', '512k', '-vf', 'scale=320:-1']
    full_cmd = ffmpeg_cmd + params + [outfile]
    cmd_str = ' '.join(full_cmd)
    p = subprocess.Popen(full_cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.stdout.read()
    # print "OUT", out
    return outfile, cmd_str


def create_audioinstance(filepath, params=[], outfile=None, ext='mp3'):
    # ffmpeg -y -i anni.mp4 -acodec libvorbis -ac 2 -ab 96k -ar 22050 -b 345k -s 320x240 output.webm
    ffmpeg_cmd = ['ffmpeg', '-i', '%s' % filepath]
    if outfile is None:
        outfile = tempfile.NamedTemporaryFile(delete=False).name + '.' + ext
    if not params:
        params = ['-acodec', 'libmp3lame', '-ab', '64k']
    full_cmd = ffmpeg_cmd + params + [outfile]
    cmd_str = ' '.join(full_cmd)
    p = subprocess.Popen(full_cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    # out = p.stdout.read()
    # print out
    return outfile, cmd_str


def do_video_thumbnail(src, target, sec=1.0):
    """
    Create a thumbnail from video file 'src' and save it to 'target'.
    Return True if subprocess was called with error code 0.
    TODO: make -ss configurable, now it is hardcoded 1 seconds.

    subprocess.check_call(
      ['ffmpeg', '-ss', '1', '-i', 'test_content/05012009044.mp4',
       '-vframes', '1', '-f', 'mjpeg', '-s', '320x240', 'test-1.jpg'])

    ffmpeg -ss 1 -i test.mp4 -vframes 1 -f mjpeg -s 320x240 test-1.jpg
    ffmpeg -ss 2 -i test.mp4 -vframes 1 -f mjpeg -s 320x240 test-2.jpg
    ffmpeg -ss 3 -i test.mp4 -vframes 1 -f mjpeg -s 320x240 test-3.jpg
    """
    try:
        # FIXME: this fails to create thumbnail if the seconds
        # value after -ss exeeds clip length
        command = [
            'ffmpeg', '-y', '-ss', str(sec), '-i', src,
            '-vframes', '1', '-f', 'mjpeg', target
        ]
        subprocess.check_call(command)
        if os.path.isfile(target):  # TODO: check that size > 0 ?
            return True
        else:
            return False
    except subprocess.CalledProcessError as err:
        msg = 'Subprocess error in do_video_thumbnail: "{}". ' \
              'Command: "{}".'.format(err, ' '.join(command))
        logger.warning(msg)
        return False


def do_pdf_thumbnail(src, target):
    """
    Create a thumbnail from a PDF file 'src' and save it to 'target'.
    Return True if subprocess returns with error code 0 and target exits.
    """
    CONVERT = 'convert'
    # convert -flatten  -geometry 1000x1000 foo.pdf[0] thumb.png
    try:
        command = [CONVERT, '-flatten', '-geometry', '1000x1000',
                   src+'[0]', target]
        subprocess.check_call(command)
        # TODO: check also that target is really non-broken file
        if os.path.isfile(target):
            return True
        else:
            return False
    except subprocess.CalledProcessError as err:
        msg = 'Subprocess error in do_pdf_thumbnail: "{}". ' \
              'Command: "{}".'.format(err, ' '.join(command))
        logger.warning(msg)
        return False


def create_thumbnail(filepath, t):
    try:
        im = ImagePIL.open(filepath)
    except IOError:  # ImagePIL file is corrupted
        print "ERROR in image file:", filepath
        return False
    if im.mode not in ('L', 'RGB'):
        im = im.convert('RGB')
    size = (t[0], t[1])
    rotatemap = {
        90: ImagePIL.ROTATE_270,
       180: ImagePIL.ROTATE_180,
       270: ImagePIL.ROTATE_90,
    }
    if t[4] != 0:
        im = im.transpose(rotatemap[t[4]])
    im.thumbnail(size, ImagePIL.ANTIALIAS)
    # TODO: use imagemagick and convert
    # Save resized image to a temporary file
    # NOTE: the size will be increased if original is smaller than size
    tmp = tempfile.NamedTemporaryFile() # FIXME: use StringIO
    im.save(tmp, "jpeg", quality=t[3])
    tmp.seek(0)
    return tmp


if __name__ == '__main__':
    import sys
    for path in sys.argv[1:]:
        print path, fileinfo(path)
    # ffp = FFProbe(path)
    # print path, ffp.is_video(), ffp.is_audio()
    # if ffp.is_video(): print ffp.get_videoinfo()
    # if ffp.is_audio(): print ffp.get_audioinfo()
