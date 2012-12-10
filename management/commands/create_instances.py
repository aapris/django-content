# -*- coding: utf-8 -*-
import email
import sys
import os
import re
import datetime
from dateutil import tz
import time
from optparse import make_option
from django.contrib.auth.models import User

from django.db import transaction
from django.db.models import Count, Q #, Avg, Max, Min
from django.core.management.base import BaseCommand #, CommandError
from django.conf import settings
settings.DEBUG = False

import logging
log = logging.getLogger('fetch_mail')

from content.models import Content, Mail

# FIXME: handle mailed files elsewhere, e.g. in comeup app

from content.filetools import get_ffmpeg_videoinfo, get_videoinfo, get_audioinfo
from content.filetools import create_videoinstance, create_audioinstance
from content.filetools import is_audio, is_video

from content.models import Videoinstance, Audioinstance

def create_instances(limit, pk, uid):
    qset = Q(mimetype__startswith='video') | Q(mimetype__startswith='audio')
    contents = Content.objects.filter(qset)
    if uid: contents = contents.filter(uid=uid)
    if pk: contents = contents.filter(pk=pk)
    contents.order_by('-created')
    if limit > 0:
        contents = contents[:limit]
    for c in contents:
        old_instances = list(c.audioinstances.all()) + list(c.videoinstances.all())
        for inst in old_instances:
            if os.path.isfile(inst.file.path):
                #print "DELETING", inst.file.path
                os.unlink(inst.file.path)
            inst.delete()
        maintype = c.mimetype.split('/')[0]
        if maintype in ['video', 'audio']:
            finfo = get_ffmpeg_videoinfo(c.file.path)
            print finfo
            if is_video(finfo):
                params = (
                    #('webm', 'video/webm', ['-acodec', 'libvorbis', '-ac', '2', '-ab', '96k', '-ar', '22050', '-b', '345k', '-s', '320x240']),
                    #('mp4', 'video/mp4', ['-deinterlace', '-vcodec', 'libx264', '-vsync', '2', '-acodec', 'libfaac', '-ab', '64k', '-async', '1', '-f', 'mp4', '-s', '320x240']),
                    #('mp4', 'video/mp4', ['-deinterlace', '-vcodec', 'libx264', '-vsync', '2', '-ab', '64k', '-async', '1', '-f', 'mp4', '-s', '320x240']),
                    ('mp4', 'video/mp4', ['-vcodec', 'libx264', '-preset', 'fast', '-vprofile', 'baseline', '-vsync', '2', '-ab', '64k', '-async', '1', '-f', 'mp4', '-s', '320x240']),
                    ('webm', 'video/webm', ['-acodec', 'libvorbis', '-ac', '2', '-ab', '96k', '-ar', '22050', '-s', '320x240']),
                    #('mov', 'video/quicktime', ['-s', '320x240']),
                )
                for x in params:
                    ext, mimetype, param = x
                    new_video = create_videoinstance(c.file.path, param, ext = ext)
                    vi = Videoinstance(content=c)
                    vi.save()
                    c.video.generate_thumb()
                    print new_video, ext
                    vi.set_file(new_video, ext)
                    info = get_videoinfo(get_ffmpeg_videoinfo(vi.file.path))
                    #os.unlink(new_video)
                    print info
                    vi.set_metadata(info)
                    vi.save()
                    print vi.mimetype, vi.duration, vi.width, vi.height
            if is_audio(finfo):
                params = (
                    ('ogg', 'audio/ogg', ['-acodec', 'libvorbis', '-ab', '64k']),
                    ('mp3', 'audio/mpeg', ['-acodec', 'libmp3lame', '-ab', '64k']),
                )
                for x in params:
                    ext, mimetype, param = x
                    new_video = create_audioinstance(c.file.path, param, ext = ext)
                    ai = Audioinstance(content=c)
                    ai.save()
                    ai.set_file(new_video, ext)
                    info = get_audioinfo(get_ffmpeg_videoinfo(ai.file.path))
                    print info
                    ai.set_metadata(info)
                    ai.save()
                    print ai.mimetype, ai.duration


class Command(BaseCommand):
    # Limit max number of contents to process
    option_list = BaseCommand.option_list + (
        make_option('--limit',
                    action='store',
                    dest='limit',
                    type='int',
                    default=0,
                    help='Limit the number of contents to handle'),
        )
    option_list = option_list + (
        make_option('--types',
                    action='store_true',
                    dest='simulate',
                    default=False,
                    help=u'Process content but do not flag it processed, also do not save actual files to the database'),
        )
    option_list = option_list + (
        make_option('--pk',
                    action='store',
                    dest='pk',
                    help=u'Process only Content with given PK (id)'),
        )
    option_list = option_list + (
        make_option('--uid',
                    action='store',
                    dest='uid',
                    help=u'Process only Content with given UID'),
        )
    args = ''
    help = 'Process new retrieved contents'

    def handle(self, *args, **options):
        limit = options.get('limit')
        pk = options.get('pk')
        uid = options.get('uid')
        #verbosity = options.get('verbosity')
        #simulate = options.get('simulate')
        create_instances(limit=limit, pk=pk, uid=uid)
