# -*- coding: utf-8 -*-
"""
Media file tools.

ffmpeg, ffprobe binaries must be installed.
PIL must be installed.
python-magic must be installed.

get mimetype

if image/*:
    try: PIL
    except: do fail
if video/*:
    is_audio
        try: ffmpeg
        except: do fail
    is_video:
        try: ffmpeg
        except: do fail
    else: do fail
if audio/*:
    is_audio
        try: ffmpeg
        except: do fail
    else: do fail
else:
    store
"""
import datetime

import sys
if __name__=='__main__':
    sys.path.append("..")
import os
import re
import time
import subprocess
import tempfile
from django.utils import timezone

import Image as ImagePIL
import magic
from ExifTags import TAGS, GPSTAGS
import EXIF
from iptcinfo import IPTCInfo
import pipeffmpeg

import logging
logger = logging.getLogger('django')

FFMPEG = '/opt/local/bin/ffmpeg'
FFMPEG = 'ffmpeg'

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

def get_mimetype(filepath):
    """
    Return mimetype of given file.
    Use python-magic if it is found, otherwise try
    `file` command found in most unix/linux systems.
    File for windows:
    http://gnuwin32.sourceforge.net/packages/file.htm
    """
    return magic.from_file(filepath, mime=True)
#    raise
#    file_cmd = ['file', '--mime-type', '--brief', '%s' % filepath]
#    # FIXME: this doesn't check if executable "file" exist at all
#    # TODO: think what to do if this fails
#    mime = subprocess.Popen(file_cmd,
#                            stdout=subprocess.PIPE).communicate()[0].strip()
#    return mime

def is_audio(info):
    """
    Return True if data from pipeffmpeg.get_info(fname) contains
    exactly 1 stream and it's codec_type is audio.
    """
    if len(info['streams']) == 1\
       and 'codec_type' in info['streams'][0]\
       and info['streams'][0].get('codec_type') == 'audio':
        return True
    return False

def is_video(info):
    """
    Return True if data from pipeffmpeg.get_info(fname) contains
    at least 1 stream and one of the has codec_type video.
    NOTE: JPEG images are detected as MJPEG (Motion JPEG) videos, so
    it'd better to handle JPEGs before calling this.
    """
    if len(info['streams']) > 0:
        for stream in info['streams']:
            if stream.get('codec_type') == 'video':
                return True
    return False

def get_ffmpeg_videoinfo(filepath):
    return pipeffmpeg.get_info(filepath)


def get_float(key, _dict):
    try:
        return float(_dict.get(key))
    except TypeError, err:
        print err, key, _dict
        return None
    except:
        raise

def get_videoinfo(info):
    data = {}
    data['duration'] = get_float('duration', info)
    #data['size'] = int(get_float('size', info))
    for stream in info['streams']:
        if stream.get('codec_type') == 'video':
            for key in stream.keys():
                if key in ['width', 'height']:
                    data[key] = int(stream[key]) if stream[key] else None
                if key in ['avg_frame_rate']:
                    # e.g. '1000000000/33333' -> 1000000000, 33333
                    a, b = [int(x) for x in stream[key].split('/')]
                    data['framerate'] = a / 1000.0 / b # 30.00030000300003
    return data

def get_audioinfo(info):
    data = {}
    data['duration'] = get_float('duration', info)
    #data['size'] = int(get_float('size', info))
    for stream in info['streams']:
        if stream.get('codec_type') == 'audio':
            for key in stream.keys():
                print key, stream[key]
                #if key in ['avg_frame_rate']:
                #    # e.g. '1000000000/33333' -> 1000000000, 33333
                #    a, b = [int(x) for x in stream[key].split('/')]
                #    data['framerate'] = a / 1000.0 / b # 30.00030000300003
    return data


def get_videoinfo_old(filepath):
    """
    Return duration, bitrate and size of given video file in a dictionary.
    All values are parsed from ffmpeg's output, which looks like
    something like this::

    Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'test.mp4':
      Duration: 00:00:07.27, start: 0.000000, bitrate: 2662 kb/s
        Stream #0.0(und): Video: mpeg4, yuv420p, 640x480 [PAR 1:1 DAR 4:3], 100 tbr, 3k tbn, 100 tbc
        Stream #0.1(und): Audio: aac, 48000 Hz, mono, s16

    Ffmpeg for windows:
    http://sourceforge.net/projects/mplayer-win32/files/
    """
    info = {"duration" : None,
            "bitrate" : None,
            "width" : None,
            "height" : None,
            }
    # FIXME: this doesn't check if executable "ffmpeg" exist at all
    #ffmpeg_cmd = 'ffmpeg -i "%s" 2>&1' % filepath
    #out = os.popen(ffmpeg_cmd).read().strip()
    ffmpeg_cmd = [FFMPEG, '-i', '%s' % filepath]
    p = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.stdout.read()
    dt = re.compile("Duration: (\d\d):(\d\d):(\d\d\.\d\d)").findall(out)
    if len(dt) > 0:
        #print dt
        info["duration"] = int(dt[0][0])*60*60 + int(dt[0][1])*60 + float(dt[0][2])
    bt = re.compile("bitrate: (\d+ .*)").findall(out)
    if len(bt) > 0:
        info["bitrate"] = bt[0]
    st = re.compile("Video.* (\d+)x(\d+)").findall(out)
    if len(st) > 0:
        info["width"] = int(st[0][0])
        info["height"] = int(st[0][1])
    return info

# https://gist.github.com/983821

def get_exif_data(image):
    """
    Return a dictionary from the exif data of an PIL Image item.
    Also converts the GPS Tags.
    """
    exif_data = {}
    try:
        info = image._getexif()
        if info:
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                if decoded == "GPSInfo":
                    gps_data = {}
                    for t in value:
                        sub_decoded = GPSTAGS.get(t, t)
                        gps_data[sub_decoded] = value[t]
                    exif_data[decoded] = gps_data
                else:
                    exif_data[decoded] = value
    except AttributeError: # This was missing from original code
        pass
    except IOError, err: # Broken files may throw IOError: not enough data ? 
        logger.exception(err)
        pass
    return exif_data

def _convert_to_degrees(value):
    """
    Helper function to convert the GPS coordinates
    stored in the EXIF to degrees in float format.
    """
    d0 = value[0][0]
    d1 = value[0][1]
    d = float(d0) / float(d1)

    m0 = value[1][0]
    m1 = value[1][1]
    m = float(m0) / float(m1)

    s0 = value[2][0]
    s1 = value[2][1]
    s = float(s0) / float(s1)

    return d + (m / 60.0) + (s / 3600.0)

def get_lat_lon(exif_data):
    """
    Returns the latitude and longitude, if available,
    from the provided exif_data (obtained through get_exif_data above).
    """
    lat = None
    lon = None

    if 'GPSInfo' in exif_data:
        gps_info = exif_data['GPSInfo']
        gps_latitude = gps_info.get('GPSLatitude')
        gps_latitude_ref = gps_info.get('GPSLatitudeRef')
        gps_longitude = gps_info.get('GPSLongitude')
        gps_longitude_ref = gps_info.get('GPSLongitudeRef')
        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            lat = _convert_to_degrees(gps_latitude)
            if gps_latitude_ref != "N":
                lat = -lat
            lon = _convert_to_degrees(gps_longitude)
            if gps_longitude_ref != "E":
                lon = -lon
    return lat, lon


def get_imageinfo(filepath):
    """
    Return EXIF and IPTC information found from image file in a dictionary.
    Uses EXIF.py, PIL.111 and iptcinfo.
    NOTE: PIL can read EXIF tags including GPS tags also.
    """
    info = {}
    file = open(filepath, "rb")
    exif = EXIF.process_file(file, stop_tag="UNDEF", details=True, strict=False, debug=False)
    file.close()
    if exif:
        info['exif'] = exif
    im = ImagePIL.open(filepath)
    exif_data = get_exif_data(im)
    info['lat'], info['lon'] = get_lat_lon(exif_data)
    if 'DateTimeOriginal' in exif_data:
        try:
            datestring = exif_data.get('DateTimeOriginal', '').strip('\0') # remove possible null bytes
            info['datetime'] = datetime.datetime.strptime(datestring,
                                                          '%Y:%m:%d %H:%M:%S')#.replace(tzinfo=timezone.utc)
            info['timestamp'] = time.strptime(datestring, '%Y:%m:%d %H:%M:%S')
        except ValueError, err: # E.g. value is '0000:00:00 00:00:00\x00'
            print "filetoos.py/get_imageinfo(): ", err
        except TypeError, err: # E.g. value is '4:24:26\x002004:06:25 0'
            print "filetoos.py/get_imageinfo(): ", err
        except Exception, err:
            #print exiftime
            print "filetoos.py/get_imageinfo(): ", err
            print "WRONG DATE: '"+ datestring + "'"
            print exif_data
            raise
            pass

    iptc = IPTCInfo(filepath, force=True)
    # TODO: extract more tags from iptc (copyright, author etc)
    #iptc2info_map = {
    #    'caption/abstract': 'caption',
    #    'object name': 'title',
    #    'keywords': 'keywords',
    #}
    if iptc:
        info['iptc'] = iptc
        if iptc.data['caption/abstract']:
            cap = iptc.data['caption/abstract']
            info['caption'] = cap.decode(guess_encoding(cap))
            #print info['caption'], type(info['caption'])
        if iptc.data['object name']:
            info['title'] = iptc.data['object name']
        if iptc.data['keywords']:
            kw_str = ', '.join(iptc.data['keywords'])
            info['keywords'] = kw_str.decode(guess_encoding(kw_str))
            #print info['keywords'], type(info['keywords'])
        # Convert all str values to unicode
        for key in info:
            #print key, type(key)
            if isinstance(info[key], str):
                info[key] = unicode(info[key], guess_encoding(info[key]))
                #print info[key], type(info[key])
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
            FFMPEG, '-y', '-ss', '1', '-i', src,
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


#import subprocess

def create_videoinstance(filepath, params = [], outfile = None, ext = 'webm'):
    #ffmpeg -y -i anni.mp4 -acodec libvorbis -ac 2 -ab 96k -ar 22050 -b 345k -s 320x240 output.webm
    ffmpeg_cmd = [FFMPEG, '-i', '%s' % filepath]
    if outfile is None:
        outfile = tempfile.NamedTemporaryFile(delete=False).name + '.' + ext
    if not params:
        params = ['-acodec', 'libvorbis', '-ac', '2', '-ab', '96k', '-ar', '22050', '-b', '345k', '-s', '320x240']
    full_cmd = ffmpeg_cmd + params + [outfile]
    print ' '.join(full_cmd)
    p = subprocess.Popen(full_cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.stdout.read()
    print out
    return outfile


def create_audioinstance(filepath, params = [], outfile = None, ext = 'mp3'):
    #ffmpeg -y -i anni.mp4 -acodec libvorbis -ac 2 -ab 96k -ar 22050 -b 345k -s 320x240 output.webm
    ffmpeg_cmd = [FFMPEG, '-i', '%s' % filepath]
    if outfile is None:
        outfile = tempfile.NamedTemporaryFile(delete=False).name + '.' + ext
    if not params:
        params = ['-acodec', 'libmp3lame', '-ab', '64k']
    full_cmd = ffmpeg_cmd + params + [outfile]
    p = subprocess.Popen(full_cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.stdout.read()
    # print out
    return outfile


# Not implemented
def convert_video(src, target):
    """
    TODO: finish this
    ffmpeg -i test.mp4 -r 24 -s 320x240 -y -f flv -ar 11025 -ab 64 -ac 1 test.flv
    """
    pass

# Not in use
def image_magick_resize(src, target, width, height):
    subprocess.check_call(['convert', src,
                           '-quality', '80',
                           '-geometry','%dx%d' % (width, height), target])
    # ffmpeg -i 000000037-32b9.mp4 -s 160x120  -vframes 1 -f mjpeg preview.jpg
    pass

def create_thumbnail(filepath, t):
    try:
        im = ImagePIL.open(filepath)
    except IOError: # ImagePIL file is corrupted
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


# Test functions

def _test_image(filepath):
    info = get_imageinfo(filepath)
    if 'exif' in info and 'JPEGThumbnail' in info['exif']:
        del info['exif']['JPEGThumbnail']
    #print info['exif']
    print info['exif'].keys()
    print ('%(lat).6f,%(lon).6f' % (info)) if 'lat' in info else "No lat,lon"
    sys.exit(0)
    # w, h, format, quality, rotate
    THUMBNAIL_PARAMETERS = (200, 200, 'JPEG', 80, 0)
    thumb = create_thumbnail(sys.argv[1], THUMBNAIL_PARAMETERS)
    thumb.close()
    print thumb.name

def _test_video(filepath):
    params = []
    new_video = create_videoinstance(filepath, params)
    info = get_ffmpeg_videoinfo(new_video)
    print info, new_video

def _test_audio(filepath):
    params = []
    new_audio = create_audioinstance(filepath, params)
    info = get_ffmpeg_videoinfo(new_audio)
    print info

if __name__=='__main__':
    filepath = sys.argv[1]
    mime = get_mimetype(filepath)
    type = mime.split('/')[0]
    print "testing", type, filepath
    if type == 'image':
        _test_image(filepath)
    elif type == 'video':
        #get_ffmpeg_videoinfo
        info = get_ffmpeg_videoinfo(filepath)
        if is_video(info):
            _test_video(filepath)
        elif is_audio(info):
            _test_audio(filepath)
    elif type == 'audio':
        _test_audio(filepath)
