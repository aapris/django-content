# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.utils.encoding import python_2_unicode_compatible
"""
Defines all supported different content type classes (image, video, audio etc.)
If file type is not supported, it is saved "as is", without any metadata
about duration, bitrate, dimensions etc.
"""
# TODO: implement Image/Video/Audio Instance classes, which save conversions
# to different formats and sizes (e.g. audio->mp3+ogg, video->mp4+theora).
# TODO: possibility to save more than one thumbnails of a video?
# TODO: make Geo features optional, e.g. create conditional point field


import os
import hashlib
import mimetypes
from PIL import Image as ImagePIL
import string
import random
import tempfile
import sys
if sys.version_info > (3, 0):
    from io import StringIO
else:
    from io import BytesIO as StringIO

from django.core.files.uploadedfile import UploadedFile

from .filetools import deprecated

from django.conf import settings

from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.core.files import File

from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.geos import *
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
# https://stackoverflow.com/a/48894881
from django.db.models import Manager as GeoManager
from django.utils.translation import ugettext_lazy as _

from content.filetools import get_mimetype, do_pdf_thumbnail
from content.filetools import do_video_thumbnail
import content.filetools

# Original files are saved in content_storage
content_storage = FileSystemStorage(location=settings.APP_DATA_DIRS['CONTENT'])
# Generated dynamic files (previews, video and audio instances) are in 'var'
preview_storage = FileSystemStorage(location=settings.APP_VAR_DIRS['PREVIEW'])
video_storage = FileSystemStorage(location=settings.APP_VAR_DIRS['VIDEO'])
audio_storage = FileSystemStorage(location=settings.APP_VAR_DIRS['AUDIO'])
# TODO: change to APP_VAR_DIRS or something
mail_storage = FileSystemStorage(location=settings.MAIL_CONTENT_DIR)

# define this in local_settings, if you want to change this
# TODO: replace with getattr
try:
    THUMBNAIL_PARAMETERS = settings.CONTENT_THUMBNAIL_PARAMETERS
except:
    THUMBNAIL_PARAMETERS = (1000, 1000, 'JPEG', 90)  # w, h, format, quality


def upload_split_by_1000(obj, filename):
    """
    Return the path where the original file will be saved.
    Files are split into a directory hierarchy, which bases on object's id,
    e.g. if obj.id is 12345, fill path will be 000/012/filename
    so there will be max 1000 files in a directory.
    NOTE: if len(id) exeeds 9 (it is 999 999 999) directory hierarchy will
    get one level deeper, e.g. id=10**9 -> 100/000/000/filename
    This should not clash with existings filenames.
    """
    # obj.save()  # save the object to ensure there is obj.id available
    # --> maximum recursion depth exceeded while calling a Python object ???
    if hasattr(obj, 'content'):
        id = obj.content.id
    else:
        id = obj.id
    longid = "%09d" % id  # e.g. '000012345'
    chunkindex = [i for i in range(0, len(longid)-3, 3)]  # -> [0, 3, 6]
    path = os.sep.join([longid[j:j+3] for j in chunkindex] + [filename])
    return path


def get_uid(length=12):
    """
    Generate and return a random string which can be considered unique.
    Default length is 12 characters from set [a-zA-Z0-9].
    """
    alphanum = string.letters + string.digits
    return ''.join([alphanum[random.randint(0, len(alphanum) - 1)] for i in
                    range(length)])

CONTENT_PRIVACY_CHOICES = (
    ("PRIVATE", _("Private")),
    ("RESTRICTED", _("Group")),
    ("PUBLIC", _("Public"))
)

@python_2_unicode_compatible
class Group(models.Model):
    """
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField()
    users = models.ManyToManyField(User, blank=True, editable=True,
                                   related_name='contentgroups')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self):
        return "%s" % self.slug


@python_2_unicode_compatible
class Content(models.Model):
    """
    Common fields for all content files.

    Field info:
    status -
    privacy - PRIVATE, RESTRICTED, PUBLIC
    uid - unique random identifier string
    user - Django User, if relevant
    group -
    originalfilename - original filename
    filesize - file size of original file in bytes
    filetime - creation time of original file (e.g. EXIF timestamp)
    mimetype - Official MIME Media Type (e.g. image/jpeg, video/mp4)
    file - original file object
    preview - thumbnail object if relevant
    md5 - md5 of original file in hex-format
    sha1 - sha1 of original file in hex-format
    created - creation timestamp
    updated - last update timestamp
    opens - optional timestamp after which this Content is available
    expires - optional timestamp after which this object isn't available
    peers = Content's peers, if relevant
    parent - Content's parent Content, if relevant
    linktype - information of the type of child-parent relation
    point = models.PointField(geography=True, blank=True, null=True)

    It would be useful to save
    Uploadinfo, if the content is saved via HTTP like this:
    Uploadinfo.create(c, request).save()

    title - title text of this Content, a few words max
    caption - descriptive text of this Content
    author - Content author's name or nickname
    keywords - comma separated list of keywords/tags
    place - country, state/province, city, address or other textual description
    """

    status = models.CharField(max_length=40, default="UNPROCESSED",
                              editable=False)
    privacy = models.CharField(max_length=40, default="PRIVATE",
                               verbose_name=_('Privacy'),
                               choices=CONTENT_PRIVACY_CHOICES)
    uid = models.CharField(max_length=40, unique=True, db_index=True,
                           default=get_uid, editable=False)
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    group = models.ForeignKey(Group, blank=True, null=True, on_delete=models.SET_NULL)
    originalfilename = models.CharField(max_length=256, null=True,
                                        verbose_name=_('Original file name'),
                                        editable=False)
    filesize = models.IntegerField(null=True, editable=False)
    filetime = models.DateTimeField(blank=True, null=True, editable=False)
    mimetype = models.CharField(max_length=200, null=True, editable=False)
    file = models.FileField(storage=content_storage,
                            upload_to=upload_split_by_1000, editable=False)
    preview = models.ImageField(storage=preview_storage, blank=True,
                                upload_to=upload_split_by_1000, editable=False)
    md5 = models.CharField(max_length=32, null=True, editable=False)
    sha1 = models.CharField(max_length=40, null=True, editable=False)

    # license
    # origin, e.g. City museum, John Smith's photo album
    # Links and relations to other content files
    peers = models.ManyToManyField("self", blank=True,
                                   editable=False)
    parent = models.ForeignKey("self", blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    linktype = models.CharField(max_length=500, blank=True)
    # point (geography) is used for e.g. distance calculations
    point = models.PointField(geography=True, blank=True, null=True)
    # point_geom (geometry) is used to enable e.g. within queries
    point_geom = models.PointField(blank=True, null=True)
    # TODO: to be removed (text fields are implemented elsewhere
    title = models.CharField(max_length=200, blank=True,
                             verbose_name=_('Title'))
    # TODO: to be removed (text fields are implemented elsewhere
    caption = models.TextField(blank=True, verbose_name=_('Caption'))
    # TODO: to be removed (text fields are implemented elsewhere
    author = models.CharField(max_length=200, blank=True,
                              verbose_name=_('Author'))
    # TODO: to be removed (text fields are implemented elsewhere
    keywords = models.CharField(max_length=500, blank=True,
                                verbose_name=_('Keywords'))
    # TODO: to be removed (text fields are implemented elsewhere
    place = models.CharField(max_length=500, blank=True,
                             verbose_name=_('Place'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    opens = models.DateTimeField(blank=True, null=True)
    expires = models.DateTimeField(blank=True, null=True)

    # In referencing model add e.g. `files = GenericRelation(Content)`
    content_type = models.ForeignKey(ContentType, blank=True, null=True, default=None, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    objects = GeoManager()

    # TODO: replace this with property stuff
    def latlon(self):
        # FIXME: should this be lonlat
        return self.point.coords if self.point else None

    def set_latlon(self, lat, lon):
        p = Point(lon, lat)
        self.point = p
        self.point_geom = p

    def save_file(self, originalfilename, filecontent):
        """
        Save filecontent to the filesystem and fill filename, filesize fields.
        filecontent may be
        - open file handle (opened in "rb"-mode)
        - existing file name (full path)
        - raw file data
        """
        # TODO: check functionality with very large files
        self.originalfilename = os.path.basename(originalfilename)
        self.save()  # Must save here to get self.id
        root, ext = os.path.splitext(originalfilename)
        filename = "%09d-%s%s" % (self.id, self.uid, ext.lower())
        if isinstance(filecontent, UploadedFile):  # Is an open file
            self.file.save(filename, File(filecontent))
        elif isinstance(filecontent, file):  # Is open file
            self.file.save(filename, File(filecontent))
        elif len(filecontent) < 1000 and os.path.isfile(filecontent):
            # Is existing file in file system
            with open(filecontent, "rb") as f:
                self.file.save(filename, File(f))
        else:  # Is just something in the memory
            self.file.save(filename, ContentFile(filecontent))
        self.filesize = self.file.size
        self.save()

    def set_file(self, originalfilename, filecontent,
                 mimetype=None, md5=None, sha1=None):
        """
        Save Content.file and all it's related fields
        (filename, filesize, mimetype, md5, sha1).
        'filecontent' may be
        - open file handle (opened in "rb"-mode)
        - existing file name (full path)
        - raw file data
        """
        self.save_file(originalfilename, filecontent)
        if md5 is None or sha1 is None:
            self.md5, self.sha1 = content.filetools.hashfile(self.file.path)
        if mimetype:
            self.mimetype = mimetype
        else:
            info = content.filetools.fileinfo(self.file.path)
            mime = info['mimetype']
            if mime:
                self.mimetype = mime
            else:
                self.mimetype = mimetypes.guess_type(originalfilename)[0]
        self.status = "PROCESSED"
        self.save()

    # NEW! This will replace get_type_instance eventually
    def set_fileinfo(self, mime=None):
        """
        Creates (or updates if it already exists) Content.video/audio/image.
        Saves width, height, duration, bitrate where appropriate.
        """
        if mime is None:
            mime = self.mimetype
        obj = None
        if mime.startswith("image"):
            info = content.filetools.get_imageinfo(self.file.path)
            try:
                obj = self.image
            except Image.DoesNotExist:
                obj = Image(content=self)
        elif mime.startswith("video"):
            ffp = content.filetools.FFProbe(self.file.path)
            info = ffp.get_videoinfo()
            try:
                obj = self.video
            except Video.DoesNotExist:
                obj = Video(content=self)
        elif mime.startswith("audio"):
            ffp = content.filetools.FFProbe(self.file.path)
            info = ffp.get_audioinfo()
            try:
                obj = self.audio
            except Audio.DoesNotExist:
                obj = Audio(content=self)
        if obj:
            obj.set_metadata(info)
            # print "SET_METADATA", info
            obj.save()  # Save new instance to the database
            return obj

    def get_fileinfo(self):
        info = content.filetools.get_imageinfo(self.file.path)
        return info

    def generate_thumbnail(self):
        """
        Generates the file to preview field for Videos, Images and PDFs.

        """
        # TODO: create generic thumbnail functions for video, image and pdf
        if self.mimetype.startswith("image"):
            try:

                im = ImagePIL.open(self.file.path)
                self.image.generate_thumb(im, self.image.thumbnail,
                                          THUMBNAIL_PARAMETERS)
                if self.image.thumbnail:
                    self.preview = self.image.thumbnail
            except Image.DoesNotExist:
                pass
        elif self.mimetype.startswith("video"):
            try:
                if self.video.thumbnail:
                    self.video.thumbnail.delete()
                self.video.generate_thumb()
                if self.video.thumbnail:
                    self.preview = self.video.thumbnail
            except Video.DoesNotExist:
                pass
        elif self.mimetype.startswith("application/pdf"):
            fd, tmp_name = tempfile.mkstemp()  # Remember to close fd!
            tmp_name += '.png'
            #print tmp_name
            if do_pdf_thumbnail(self.file.path, tmp_name):
                postfix = "%s-%s-%sx%s" % THUMBNAIL_PARAMETERS
                filename = "%09d-%s-%s.png" % (self.id, self.uid, postfix)
                if os.path.isfile(tmp_name):
                    with open(tmp_name, "rb") as f:
                        self.preview.save(filename, File(f))
                    self.save()
                    os.unlink(tmp_name)
            os.close(fd)
        else:
            return None


    # TODO REMOVE
    @deprecated
    def get_type_instance(self):
        """
        Return related Image, Video etc. object.
        If object doesn't exist yet, create new one and return it, if possible.
        """
        if self.mimetype.startswith("image"):
            try:
                return self.image
            except Image.DoesNotExist:
                image = Image(content=self)
                image.save()  # Save new instance to the database
                if image.thumbnail:
                    self.preview = image.thumbnail
                return image
        elif self.mimetype.startswith("video"):
            try:
                return self.video
            except Video.DoesNotExist:
                video = Video(content=self)
                video.save()  # Save new instance to the database
                video.generate_thumb()
                if video.thumbnail:
                    self.preview = video.thumbnail
                return video
        elif self.mimetype.startswith("audio"):
            try:
                return self.audio
            except Audio.DoesNotExist:
                audio = Audio(content=self)
                audio.save()  # Save new instance to the database
                return audio
        elif self.mimetype.startswith("application/pdf"):
            fd, tmp_name = tempfile.mkstemp()  # Remember to close fd!
            tmp_name += '.png'
            #print tmp_name
            if do_pdf_thumbnail(self.file.path, tmp_name):
                postfix = "%s-%s-%sx%s" % THUMBNAIL_PARAMETERS
                filename = "%09d-%s-%s.png" % (self.id, self.uid, postfix)
                if os.path.isfile(tmp_name):
                    with open(tmp_name, "rb") as f:
                        self.preview.save(filename, File(f))
                    self.save()
                    os.unlink(tmp_name)
            os.close(fd)
        else:
            return None

    def preview_ext(self):
        """Return the file extension of preview if it exists."""
        if self.preview:
            root, ext = os.path.splitext(self.preview.path)
        else:
            root, ext = os.path.splitext(self.file.path)
        return ext.lstrip('.')

    def thumbnail(self):
        """
        Return thumbnail if it exists.
        Thumbnail is always an image (can be shown with <img> tag).
        """
        if self.preview:
            return self.preview
        if self.mimetype is None:
            return None
        elif self.mimetype.startswith("image"):
            try:
                return self.image.thumbnail
            except Image.DoesNotExist:
                return None
        elif self.mimetype.startswith("video"):  # and self.video.thumbnail:
            try:
                return self.video.thumbnail
            except Video.DoesNotExist:
                return None
        else:
            return None

    def delete(self, *args, **kwargs):
        """
        Set Content.status = "DELETE". Real deletion (referencing Videos and
        Audios, Video and AudioInstances) can be done later e.g. with
        some management command (not implemented yet).
        """
        if kwargs.get('purge', False) is True and self.status == 'DELETED':
            # TODO:
            #for f in [self.file, self.preview]:
            #    if os.path.isfile(f):
            #        os.unlink(f)
            # Delete all instance files too
            print ("REALLY DELETING HERE ALL INSTANCES "
                   "AND FILES FROM FILESYSTEM")
            # Super.delete
        else:
            self.status = 'DELETED'
            self.save()
            #super(Content, self).delete(*args, **kwargs)

    def __str__(self):
        text = self.caption[:50] if self.caption else self.title
        return '"%s" (%s %s B)' % (
            text, self.mimetype, self.filesize)


@python_2_unicode_compatible
class Image(models.Model):
    content = models.OneToOneField(Content, primary_key=True, editable=False, on_delete=models.CASCADE)
    width = models.IntegerField(blank=True, null=True, editable=False)
    height = models.IntegerField(blank=True, null=True, editable=False)
    # "Original image must be rotated n degrees CLOCKWISE before showing."
    rotate = models.IntegerField(blank=True, null=True, default=0,
                                 choices=[(0, 0), (90, 90), (180, 180),
                                          (270, 270)])
    thumbnail = models.ImageField(storage=preview_storage,
                                  upload_to=upload_split_by_1000,
                                  editable=False)

    # FIXME: this is probably not in use
    def orientation(self):
        if self.width > self.height:
            return 'horizontal'
        else:
            return 'vertical'

    def set_metadata(self, info):
        self.width = info.get('width')
        self.height = info.get('height')
        if 'gps' in info:
            if self.content.point is None and 'lat' in info['gps']:
                self.content.set_latlon(info['gps']['lat'], info['gps']['lon'])
        # TODO: put these to Content.set_metadata() or something
        if 'title' in info and not self.content.title:
            self.content.title = info['title']
        if 'caption' in info and not self.content.caption:
            self.content.caption = info['caption']
        if 'keywords' in info and not self.content.keywords:
            self.content.keywords = info['keywords']
        # TODO: check timezone awareness, creation_time is not aware
        if not self.content.filetime:
            if 'gps' in info and 'gpstime' in info['gps']:
                self.content.filetime = info['gps']['gpstime']
            elif 'creation_time' in info:
                self.content.filetime = info['creation_time']  # FIXME
        try:  # Handle exif orientation
            orientation = info['exif']['Image Orientation'].values[0]
            if self.rotate == 0:
                if orientation == 3:
                    self.rotate = 180
                elif orientation == 6:
                    self.rotate = 90
                elif orientation == 8:
                    self.rotate = 270
        except Exception as err:  # No exif orientation available
            # TODO: log error
            pass

    def __str__(self):
        return "Image: %s (%dx%dpx)" % (
            self.content.originalfilename,
            self.width, self.height)

    def generate_thumb(self, image, thumbfield, t):
        # TODO: move the general part outside of the model
        # TODO: do thumbnail out side of save() !
        """
        Generate thumbnail from open Image instance and save it
        into thumb field
        """
        if thumbfield:
            thumbfield.delete()  # Delete possible previous version
        try:
            im = image.copy()
        except IOError:  # Image file is corrupted
            # TODO: use logging! print "ERROR in image file:",
            # self.content.id, self.content.file
            return False
        if im.mode not in ('L', 'RGB'):
            im = im.convert('RGB')
        size = (t[0], t[1])
        if self.rotate == 90:
            im = im.transpose(ImagePIL.ROTATE_270)
        elif self.rotate == 180:
            im = im.transpose(ImagePIL.ROTATE_180)
        elif self.rotate == 270:
            im = im.transpose(ImagePIL.ROTATE_90)
        im.thumbnail(size, ImagePIL.ANTIALIAS)
        # Save resized image to a temporary file
        tmp = StringIO()
        #tmp = tempfile.NamedTemporaryFile()
        im.save(tmp, "jpeg", quality=t[3])
        tmp.seek(0)
        data = tmp.read()
        tmp.close()
        postfix = "%s-%s-%sx%s" % t
        #filename = u"%09d-%s%s" % (self.id, self.uid, ext.lower())
        filename = "%09d-%s-%s.jpg" % (self.content.id, self.content.uid,
                                        postfix)
        thumbfield.save(filename, ContentFile(data))
        return True

    def re_generate_thumb(self):
        im = ImagePIL.open(self.content.file.path)
        self.generate_thumb(im, self.thumbnail, THUMBNAIL_PARAMETERS)

    def save(self, *args, **kwargs):
        im = None
        if self.content.file is not None and \
                (self.width is None or self.height is None):
            try:
                im = ImagePIL.open(self.content.file.path)
                (self.width, self.height) = im.size
            except IOError:
                self.content.status = "INVALID"
                self.content.save()
                return
        #info = get_imageinfo(self.content.file.path)
        #print type(info)
        #print info # NOTE: this print may raise exception below
        # with some images !?!
        # Exception Value: %X format: a number is required, not NoneType
        # Set lat and lon if they exist in info and NOT yet in content
        #if 'lat' in info and info['lat'] and self.content.point is None:
        #    self.content.point = Point(info['lon'], info['lat'])
        #if 'datetime' in info and self.content.filetime is None:
        #    self.content.filetime = info['datetime']
        #elif 'timestamp' in info and self.content.filetime is None:
        #    self.content.filetime = time.strftime("%Y-%m-%d %H:%M:%S",
        # info['timestamp'])
        # if 'title' in info and not self.content.title:
        #     self.content.title = info['title']
        # if 'caption' in info and not self.content.caption:
        #     self.content.caption = info['caption']
        # if 'keywords' in info and not self.content.keywords:
        #     self.content.keywords = info['keywords']
        # try: # Handle exif orientation
        #     orientation = info['exif']['Image Orientation'].values[0]
        #     if self.rotate == 0:
        #         if orientation == 3:   self.rotate = 180
        #         elif orientation == 6: self.rotate = 90
        #         elif orientation == 8: self.rotate = 270
        # except: # No exif orientation available
        #     # TODO: log error
        #     pass
        if im:
            self.generate_thumb(im, self.thumbnail, THUMBNAIL_PARAMETERS)
        # TODO: author and other keys, see filetools.get_imageinfo
        # and iptcinfo.py
        # Call the "real" save() method
        super(Image, self).save(*args, **kwargs)
        self.content.status = "PROCESSED"
        self.content.save()


@python_2_unicode_compatible
class Video(models.Model):
    """
    Dimensions (width, height), duration and bitrate of video media.
    """
    content = models.OneToOneField(Content, primary_key=True, editable=False, on_delete=models.CASCADE)
    width = models.IntegerField(blank=True, null=True, editable=False)
    height = models.IntegerField(blank=True, null=True, editable=False)
    duration = models.FloatField(blank=True, null=True, editable=False)
    bitrate = models.CharField(max_length=256, blank=True, null=True,
                               editable=False)
    thumbnail = models.ImageField(
        storage=preview_storage, upload_to=upload_split_by_1000,
        editable=False)

    def __str__(self):
        return "Video: %s" % self.content.originalfilename
        #return u"Video: %s (%dx%dpx, %.2f sec)" % (
        #         self.content.originalfilename,
        #         self.width, self.height, self.duration)

    def set_metadata(self, data):
        self.width = data.get('width')
        self.height = data.get('height')
        self.duration = data.get('duration')
        self.bitrate = data.get('bitrate')

    def generate_thumb(self):
        if self.content.file is not None:  # and \
           #(self.width is None or self.height is None):
            # Create temporary file for thumbnail
            fd, tmp_name = tempfile.mkstemp()  # Remember to close fd!
            if do_video_thumbnail(self.content.file.path, tmp_name):
                postfix = "%s-%s-%sx%s" % THUMBNAIL_PARAMETERS
                filename = "%09d-%s-%s.jpg" % (
                    self.content.id, self.content.uid, postfix)
                if os.path.isfile(tmp_name):
                    with open(tmp_name, "rb") as f:
                        #self.thumbnail.save(filename, ContentFile(f.read()))
                        self.thumbnail.save(filename, File(f))
                    self.save()
                    os.unlink(tmp_name)
            os.close(fd)


class Videoinstance(models.Model):
    """
    An instance of a video file.
    This can be the video in different formats and  sizes or a thumbnail image.
    Dimensions (width, height), duration and bitrate of video media.
    TODO: images could be in separate model?
    duration - seconds
    bitrate - bits / sec
    extension - file extension, e.g. '.ogg'
    width - pixels
    height - pixels
    framerate - frames / sec
    """
    content = models.ForeignKey(Content, editable=False, on_delete=models.CASCADE,
                                related_name='videoinstances')
    mimetype = models.CharField(max_length=200, editable=False)
    filesize = models.IntegerField(blank=True, null=True, editable=False)
    duration = models.FloatField(blank=True, null=True, editable=False)
    bitrate = models.FloatField(blank=True, null=True, editable=False)
    extension = models.CharField(max_length=16, editable=False)
    width = models.IntegerField(blank=True, null=True, editable=False)
    height = models.IntegerField(blank=True, null=True, editable=False)
    framerate = models.FloatField(blank=True, null=True, editable=False)
    file = models.FileField(storage=video_storage,
                            upload_to=upload_split_by_1000, editable=False)
    command = models.CharField(max_length=2000, editable=False)
    created = models.DateTimeField(auto_now_add=True)

    def set_file(self, filepath, ext):
        """
        """
        self.mimetype = get_mimetype(filepath)
        #ext = self.mimetype.split('/')[1]
        filename = "%09d-%s.%s" % (self.id, self.content.uid, ext)
        # print self.mimetype, filepath, filename
        with open(filepath, 'rb') as f:
            self.file.save(filename, File(f))
            self.filesize = self.file.size
            self.extension = ext
        self.save()
        #f.close()

    def set_metadata(self, data):
        self.width = data.get('width')
        self.height = data.get('height')
        self.duration = data.get('duration')
        self.bitrate = data.get('bitrate')
        self.framerate = data.get('framerate')


@python_2_unicode_compatible
class Audio(models.Model):
    """
    Duration of audio media.
    """
    content = models.OneToOneField(Content, primary_key=True, editable=False, on_delete=models.CASCADE)
    duration = models.FloatField(blank=True, null=True)
    bitrate = models.FloatField(blank=True, null=True, editable=False)

    def set_metadata(self, data):
        self.duration = data.get('duration')
        self.bitrate = data.get('bitrate')

    def __str__(self):
        s = "Audio: %s" % self.content.originalfilename
        s += " (%.2f sec)" % (self.duration if self.duration else -1.0)
        return s


class Audioinstance(models.Model):
    """
    An instance of a audio file.
    This can be the video in different formats and sizes or a thumbnail image.
    Dimensions (width, height), duration and bitrate of video media.
    TODO: images could be in separate model?
    """
    content = models.ForeignKey(Content, editable=False, on_delete=models.CASCADE,
                                related_name='audioinstances')
    mimetype = models.CharField(max_length=200, editable=False)
    filesize = models.IntegerField(blank=True, null=True, editable=False)
    duration = models.FloatField(blank=True, null=True, editable=False)
    bitrate = models.FloatField(blank=True, null=True, editable=False)
    extension = models.CharField(max_length=16, editable=False)
    file = models.FileField(storage=audio_storage,
                            upload_to=upload_split_by_1000, editable=False)
    command = models.CharField(max_length=2000, editable=False)
    created = models.DateTimeField(auto_now_add=True)

    def set_file(self, filepath, ext):
        """
        """
        self.mimetype = get_mimetype(filepath)
        #ext = self.mimetype.split('/')[1]
        filename = "%09d-%s.%s" % (self.id, self.content.uid, ext)
        # print self.mimetype, filepath, filename
        with open(filepath, 'rb') as f:
            self.file.save(filename, File(f))
            self.filesize = self.file.size
            self.extension = ext
        self.save()

    def set_metadata(self, data):
        self.duration = data.get('duration')
        self.bitrate = data.get('bitrate')


class Uploadinfo(models.Model):
    """
    All possible information of the client who uploaded the Content file.
    Usage: Uploadinfo.create(c, request).save()
    """
    content = models.OneToOneField(Content, primary_key=True, editable=False, on_delete=models.CASCADE)
    sessionid = models.CharField(max_length=200, blank=True, editable=False)
    ip = models.GenericIPAddressField(blank=True, null=True, editable=False)
    useragent = models.CharField(max_length=500, blank=True, editable=False)
    info = models.TextField(blank=True, editable=True)

    @classmethod
    def create(cls, content, request):
        """
        Shortcut to create and save Uploadinfo in one line, e.g.
        uli = Uploadinfo.create(c, request)
        Uploadinfo.create(c, request).save()
        """
        uploadinfo = cls(content=content)
        uploadinfo.set_request_data(request)
        return uploadinfo

    def set_request_data(self, request):
        self.sessionid = request.session.session_key \
            if request.session.session_key else ''
        self.ip = request.META.get('REMOTE_ADDR')
        self.useragent = request.META.get('HTTP_USER_AGENT', '')[:500]


class Mail(models.Model):
    """
    Retrieved Mail files
    """
    status = models.CharField(max_length=40, default="UNPROCESSED",
                              editable=True,
                              choices=(("UNPROCESSED", "UNPROCESSED"),
                                       ("PROCESSED", "PROCESSED"),
                                       ("DUPLICATE", "DUPLICATE"),
                                       ("FAILED", "FAILED")))
    filesize = models.IntegerField(null=True, editable=False)
    file = models.FileField(storage=mail_storage,
                            upload_to=upload_split_by_1000, editable=False)
    md5 = models.CharField(max_length=32, db_index=True, editable=False)
    sha1 = models.CharField(max_length=40, db_index=True, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    processed = models.DateTimeField(null=True)

    def set_file(self, filecontent, host):
        """
        Set Content.file and all it's related fields.
        filecontent may be
        - open file handle (opened in "rb"-mode)
        - existing file name (full path)
        - raw file data
        NOTE: this reads all file content into memory
        """
        if isinstance(filecontent, file):
            filecontent.seek(0)
            filedata = filecontent.read()
        elif len(filecontent) < 1000 and os.path.isfile(filecontent):
            f = open(filecontent, "rb")
            filedata = f.read()
            f.close()
        else:
            filedata = filecontent
        self.md5 = hashlib.md5(filedata).hexdigest()
        self.sha1 = hashlib.sha1(filedata).hexdigest()
        self.save()  # Must save here to get self.id
        #root, ext = os.path.splitext(originalfilename)
        filename = "%09d-%s" % (self.id, host)
        self.file.save(filename, ContentFile(filedata))
        self.filesize = self.file.size
        cnt = Mail.objects.filter(md5=self.md5).filter(sha1=self.sha1).count()
        if cnt > 1:
            self.status = 'DUPLICATE'
        self.save()
