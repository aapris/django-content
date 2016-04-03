# -*- coding: utf-8 -*-
import os
import time
import logging
from optparse import make_option
from django.db.models import Q  # Count, Avg, Max, Min
from django.core.management.base import BaseCommand  # CommandError
from django.conf import settings

import content.filetools
from content.filetools import create_videoinstance, create_audioinstance
from content.models import Videoinstance, Audioinstance
from content.models import Content

settings.DEBUG = False

log = logging.getLogger('django')

# FIXME: handle mailed files elsewhere, e.g. in comeup app


def create_instances2(limit, pk, uid, redo):
    qset = Q(mimetype__startswith='video') | Q(mimetype__startswith='audio')
    contents = Content.objects.filter(qset)
    if uid:
        contents = contents.filter(uid=uid)
    if pk:
        contents = contents.filter(pk=pk)
    contents = contents.order_by('-created')
    if limit > 0:
        contents = contents[:limit]
    for c in contents:
        print c, c.created
        old_instances = list(c.audioinstances.all()) + \
                        list(c.videoinstances.all())
        if old_instances:
            if redo:
                for inst in old_instances:
                    if inst.file and os.path.isfile(inst.file.path):
                        print "DELETING", inst.file.path
                        os.unlink(inst.file.path)
                    inst.delete()
            else:
                print "%s has already %d instances" % (c, len(old_instances))
                continue
        ffp = content.filetools.FFProbe(c.file.path)
        if ffp.is_video():
            finfo = ffp.get_videoinfo()
            # print finfo
            params = (
                ('webm', 'video/webm', ['-acodec', 'libvorbis', '-ac', '2',
                                        '-ab', '96k', '-ar', '22050', '-vf',
                                        'scale=320:trunc(ow/a/2)*2']),
                ('mp4', 'video/mp4', ['-vcodec', 'libx264', '-preset', 'fast',
                                      '-vprofile', 'baseline', '-vsync', '2',
                                      '-ab', '64k', '-async', '1', '-f', 'mp4',
                                      '-vf', 'scale=320:trunc(ow/a/2)*2',
                                      '-movflags', 'faststart']),
            )
            for x in params:
                ext, mimetype, param = x
                new_video, cmd_str = create_videoinstance(c.file.path, param,
                                                          ext=ext)
                # print cmd_str
                ffp2 = content.filetools.FFProbe(new_video)
                info = ffp2.get_videoinfo()
                if not info:
                    msg = "FFMPEG/VIDEOINSTANCE FAILED: %s" % cmd_str
                    log.warn(msg)
                    os.unlink(new_video)
                    continue
                vi = Videoinstance(content=c, command=cmd_str)
                vi.save()
                vi.set_file(new_video, ext)
                ffp2 = content.filetools.FFProbe(vi.file.path)
                info = ffp2.get_videoinfo()
                vi.set_metadata(info)
                vi.save()
                print vi.mimetype, vi.duration, vi.width, vi.height
        elif ffp.is_audio():
            params = (
                ('ogg', 'audio/ogg', ['-acodec', 'libvorbis', '-ab', '32k']),
                ('mp3', 'audio/mpeg', ['-acodec', 'libmp3lame', '-ab', '64k']),
            )
            for x in params:
                ext, mimetype, param = x
                new_video, cmd_str = create_audioinstance(c.file.path,
                                                          param, ext=ext)
                ffp2 = content.filetools.FFProbe(new_video)
                info = ffp2.get_audioinfo()
                if not info:
                    msg = "FFMPEG/AUDIOINSTANCE FAILED: %s" % cmd_str
                    log.warn(msg)
                    os.unlink(new_video)
                    continue

                ai = Audioinstance(content=c, command=cmd_str)
                ai.save()
                ai.set_file(new_video, ext)

                ffp2 = content.filetools.FFProbe(ai.file.path)
                info = ffp2.get_audioinfo()
                # print info
                ai.set_metadata(info)
                if 'mimetype' in info:
                    ai.mimetype = info['mimetype']
                ai.save()
                print ai.mimetype, ai.duration


class Command(BaseCommand):

    help = 'Create different video and audio instances from original ' \
           'media file'

    def add_arguments(self, parser):

        parser.add_argument(
            '-r', '--redo',
            action='store_true',
            dest='redo',
            default=False,
            help=u'Redo all instances, delete existing ones')

        parser.add_argument(
            '--limit',
            action='store',
            dest='limit',
            type=int,
            default=0,
            help='Limit the number of contents to handle')

        parser.add_argument(
            '--types',
            action='store_true',
            dest='simulate',
            help=u'Process content but do not flag it processed, also '
                 u'do not save actual files to the database')

        parser.add_argument(
            '--pk',
            action='store',
            dest='pk',
            help=u'Process only Content with given PK (id)')

        parser.add_argument(
            '--uid',
            action='store',
            dest='uid',
            help=u'Process only Content with given UID')

    def handle(self, *args, **options):
        limit = options.get('limit')
        pk = options.get('pk')
        uid = options.get('uid')
        redo = options.get('redo')
        # verbosity = options.get('verbosity')
        # simulate = options.get('simulate')
        create_instances2(limit=limit, pk=pk, uid=uid, redo=redo)
