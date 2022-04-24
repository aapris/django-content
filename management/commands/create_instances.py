import logging
import os

from django.conf import settings
from django.core.management.base import BaseCommand  # CommandError
from django.db.models import Q  # Count, Avg, Max, Min

import content.filetools
from content.filetools import create_videoinstance, create_audioinstance
from content.models import Content
from content.models import Videoinstance, Audioinstance

settings.DEBUG = False  # TODO: remove

log = logging.getLogger("django")


def create_instances(limit: int, pk: int, uid: str, redo: bool):
    qset = Q(mimetype__startswith="video") | Q(mimetype__startswith="audio")
    contents = Content.objects.filter(qset)
    if uid:
        contents = contents.filter(uid=uid)
    if pk:
        contents = contents.filter(pk=pk)
    contents = contents.order_by("-created")
    if limit > 0:
        contents = contents[:limit]
    for c in contents:
        log.info(f"Preparing to handle {c} (created at {c.created.isoformat()})")
        old_instances = list(c.audioinstances.all()) + list(c.videoinstances.all())
        if old_instances:
            if redo:
                for inst in old_instances:
                    if inst.file and os.path.isfile(inst.file.path):
                        log.debug(f"Deleting old instance {inst.file.path}")
                        os.unlink(inst.file.path)
                    inst.delete()
            else:
                log.debug(f"{c} has already {len(old_instances)} instances")
                continue
        ffp = content.filetools.FFProbe(c.file.path)
        if ffp.is_video():
            # scale = "scale=640:trunc(ow/a/2)*2"  # scale width to 640 px
            scale = "scale=trunc(oh*a/2)*2:360"  # scale height to 360 px (360p)
            webm_params = ["-acodec", "libvorbis", "-ac", "2", "-ab", "96k", "-ar", "22050", "-vf", scale]
            mp4_params = ["-vcodec", "libx264", "-preset", "fast", "-vprofile", "baseline", "-vsync", "2"]
            mp4_params += ["-ab", "64k", "-async", "1", "-f", "mp4", "-vf", scale, "-movflags", "faststart"]
            mp4_params += ["-pix_fmt", "yuv420p"]
            params = (
                ("webm", "video/webm", webm_params),
                ("mp4", "video/mp4", mp4_params),
            )
            for x in params:
                ext, mimetype, param = x
                new_video, cmd_str, output = create_videoinstance(c.file.path, param, ext=ext)
                ffp2 = content.filetools.FFProbe(new_video)
                info = ffp2.get_videoinfo()
                if not info:
                    msg = f"ffmpeg video instance command failed: {cmd_str}"
                    log.warning(msg)
                    os.unlink(new_video)
                    continue
                vi = Videoinstance(content=c, command=cmd_str)
                vi.save()
                vi.set_file(new_video, ext)
                ffp2 = content.filetools.FFProbe(vi.file.path)
                info = ffp2.get_videoinfo()
                vi.set_metadata(info)
                vi.save()
                log.debug(f"{vi.mimetype}, {vi.duration}, {vi.width}, {vi.height}")
        elif ffp.is_audio():
            params = (
                ("ogg", "audio/ogg", ["-acodec", "libvorbis", "-ab", "32k"]),
                ("mp3", "audio/mpeg", ["-acodec", "libmp3lame", "-ab", "64k"]),
            )
            for x in params:
                ext, mimetype, param = x
                new_video, cmd_str, output = create_audioinstance(c.file.path, param, ext=ext)
                ffp2 = content.filetools.FFProbe(new_video)
                info = ffp2.get_audioinfo()
                if not info:
                    msg = f"ffmpeg audio instance command failed: {cmd_str}"
                    log.warning(msg)
                    os.unlink(new_video)
                    continue

                ai = Audioinstance(content=c, command=cmd_str)
                ai.save()
                ai.set_file(new_video, ext)

                ffp2 = content.filetools.FFProbe(ai.file.path)
                info = ffp2.get_audioinfo()
                ai.set_metadata(info)
                if "mimetype" in info:
                    ai.mimetype = info["mimetype"]
                ai.save()


class Command(BaseCommand):
    help = "Create different video and audio instances from original " "media file"

    def add_arguments(self, parser):
        parser.add_argument(
            "-r",
            "--redo",
            action="store_true",
            dest="redo",
            default=False,
            help="Redo all instances, delete existing ones",
        )
        parser.add_argument(
            "--limit", action="store", dest="limit", type=int, default=0, help="Limit the number of contents to handle"
        )
        parser.add_argument(
            "--types",
            action="store_true",
            dest="simulate",
            help="Process content but do not flag it processed, also " "do not save actual files to the database",
        )
        parser.add_argument("--pk", action="store", dest="pk", help="Process only Content with given PK (id)")
        parser.add_argument("--uid", action="store", dest="uid", help="Process only Content with given UID")

    def handle(self, *args, **options):
        limit = options.get("limit")
        pk = options.get("pk")
        uid = options.get("uid")
        redo = options.get("redo")
        # verbosity = options.get('verbosity')
        # simulate = options.get('simulate')
        create_instances(limit=limit, pk=pk, uid=uid, redo=redo)
