import os
import re
import subprocess
import json
from dateutil import parser

"""

for i in ~/s2plus/sdcard/DCIM/Camera/20130630_161432_Perhepuistontie.jpg ~/s2plus/sdcard/Sounds/Puhe\ 001_Jousimiehentie_07072013.m4a ~/s2plus/sdcard/DCIM/Camera/20130721_191930_Sorsavuorenkatu.mp4 /Users/arista/s2plus/sdcard/Sounds/Audio\ 001.amr; do echo $i; python ~/Documents/workspace/Djangos/MestaDB/mestadb/content/filetools2.py "$i";done


"""

class FFProbe:
    """Wrapper for the ffprobe command"""

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
        #print ' '.join(command)
        #print os.path.isfile(url)
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        output, err = process.communicate()
        #print "RAW JSON", output, err
        self.data = json.loads(output)

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
            #print codecType, streamInfo
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
        #"+60.1878+025.0339/"
        try:
            if 'location' in self.data['format']['tags']:
                loc = self.data['format']['tags']['location']
                m = re.match(r'^(?P<lat>[\-\+][\d]+\.[\d]+)(?P<lon>[\-\+][\d]+\.[\d]+)', loc)
                if m:
                    info['lat'] = float(m.group('lat'))
                    info['lon'] = float(m.group('lon'))
        except KeyError, e:
            pass
            #print "Does not exist", e

    def get_creation_time(self, info):
        try:
            if 'creation_time' in self.data['format']['tags']:
                ts = self.data['format']['tags']['creation_time']
                info['creation_time'] = parser.parse(ts)
        except KeyError, e:
            pass
            #print "Does not exist", e

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
        self.get_latlon(info)
        self.get_creation_time(info)
        return info


if __name__ == '__main__':
    import sys
    url = sys.argv[1]
    ffp = FFProbe(url)
    print url, ffp.is_video(), ffp.is_audio()
    if ffp.is_video(): print ffp.get_videoinfo()
    if ffp.is_audio(): print ffp.get_audioinfo()
