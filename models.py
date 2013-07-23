# -*- coding: utf-8 -*-
"""
Defines all supported different content type classes (image, video, audio etc.).
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
import Image as ImagePIL
import string
import random
import tempfile
import StringIO

from django.conf import settings

from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.core.files import File

from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.geos import *

from django.utils.translation import ugettext_lazy as _

from content.filetools import get_videoinfo, get_imageinfo, get_mimetype, do_pdf_thumbnail
from content.filetools import do_video_thumbnail

# Original files are saved in content_storage
content_storage = FileSystemStorage(location=settings.APP_DATA_DIRS['CONTENT'])
# Generated dynamic files (previews, video and audio instances) are in 'var'
preview_storage = FileSystemStorage(location=settings.APP_VAR_DIRS['PREVIEW'])
video_storage = FileSystemStorage(location=settings.APP_VAR_DIRS['VIDEO'])
audio_storage = FileSystemStorage(location=settings.APP_VAR_DIRS['AUDIO'])
# TODO: change to APP_VAR_DIRS or something
mail_storage = FileSystemStorage(location=settings.MAIL_CONTENT_DIR)

# define this in local_settings, if you want to change this
try:
    THUMBNAIL_PARAMETERS = settings.CONTENT_THUMBNAIL_PARAMETERS
except:
    THUMBNAIL_PARAMETERS = (1000, 1000, 'JPEG', 90) # w, h, format, quality

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
    #obj.save() # save the object to ensure there is obj.id available
    if hasattr(obj, 'content'):
        id = obj.content.id
    else:
        id = obj.id
    longid = "%09d" % (id) # e.g. '000012345'
    chunkindex = [i for i in range(0, len(longid)-3, 3)] # -> [0, 3, 6]
    path = os.sep.join([longid[j:j+3] for j in chunkindex] + [filename])
    return path


def get_uid(length=12):
    """
    Generate and return a random string which can be considered unique.
    Default length is 12 characters from set [a-zA-Z0-9].
    """
    alphanum = string.letters + string.digits
    return ''.join([alphanum[random.randint(0, len(alphanum) - 1)] for i in
                    xrange(length)])

CONTENT_PRIVACY_CHOICES = (
    ("PRIVATE", _(u"Private")),
    ("RESTRICTED", _(u"Group")),
    ("PUBLIC", _(u"Public"))
)

class Group(models.Model):
    """
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField()
    users = models.ManyToManyField(User, blank=True, editable=True, related_name='contentgroups')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    def __unicode__(self):
        return "%s" % (self.slug)


class Content(models.Model):
    """
    Common fields for all content files. It would be useful to save
    Uploadinfo, if the content is saved via HTTP like this:
    Uploadinfo.create(c, request).save()
    """
    status = models.CharField(max_length=40, default="UNPROCESSED",
                              editable=False)
    privacy = models.CharField(max_length=40, default="PRIVATE",
                               verbose_name=_(u'Privacy'),
                               choices=CONTENT_PRIVACY_CHOICES)
    uid = models.CharField(max_length=40, unique=True, db_index=True,
                           default=get_uid, editable=False)
    "Unique identifier for current Content"
    user = models.ForeignKey(User, blank=True, null=True)
    "The owner of this Content (Django User)"
    group = models.ForeignKey(Group, blank=True, null=True)
    "The Content.Group for this Content"
    originalfilename = models.CharField(max_length=256, null=True,
                                        verbose_name=_(u'Original file name'),
                                        editable=False)
    "Original filename of the uploaded file"
    filesize = models.IntegerField(null=True, editable=False)
    "Size of original file"
    filetime = models.DateTimeField(blank=True, null=True, editable=False)
    "Creation time of original file (e.g. EXIF timestamp)"
    mimetype = models.CharField(max_length=200, null=True, editable=False)
    "Official MIME Media Type (e.g. image/jpeg, video/mp4)"
    file = models.FileField(storage=content_storage,
                            upload_to=upload_split_by_1000, editable=False)
    "Actual Content"
    preview = models.ImageField(storage=preview_storage, blank=True,
                            upload_to=upload_split_by_1000, editable=False)
    "Generated preview (available for images, videos and PDF files)"
    md5 = models.CharField(max_length=32, null=True, editable=False)
    "MD5 hash of original file in hex-format"
    sha1 = models.CharField(max_length=40, null=True, editable=False)
    "SHA1 hash of original file in hex-format"
    created = models.DateTimeField(auto_now_add=True)
    "Timestamp when current Content was added to the system."
    updated = models.DateTimeField(auto_now=True)
    "Timestamp of last update of current Content."
    opens = models.DateTimeField(blank=True, null=True)
    "Timestamp when current Content is available for others than owner."
    expires = models.DateTimeField(blank=True, null=True)
    "Timestamp when current Content is not anymore available for others than owner."

    # Static fields (for human use)
    title = models.CharField(max_length=200, blank=True, verbose_name=_(u'Title'))
    "Short title for Content, a few words max."
    caption = models.TextField(blank=True, verbose_name=_(u'Caption'))
    "Longer description of Content."
    author = models.CharField(max_length=200, blank=True, verbose_name=_(u'Author'))
    "Content author's name or nickname."
    keywords = models.CharField(max_length=500, blank=True, verbose_name=_(u'Keywords'))
    "Comma separated list of keywords/tags."
    place = models.CharField(max_length=500, blank=True, verbose_name=_(u'Place'))
    "Country, state/province, city, address or other textual description."
    # license
    # origin, e.g. City museum, John Smith's photo album
    # Links and relations to other content files
    peers = models.ManyToManyField("self", blank=True, null=True, editable=False)
    parent = models.ForeignKey("self", blank=True, null=True, editable=False)
    linktype = models.CharField(max_length=500, blank=True)
    "Information of the type of child-parent relation."
    #point = models.CharField(max_length=500, blank=True, null=True, editable=False)
    point = models.PointField(geography=True, blank=True, null=True)
    objects = models.GeoManager()

    def latlon(self):
        return self.point.coords if self.point else None

    def set_latlon(self, lat, lon):
        self.point = Point(lon, lat)

    def set_file(self, originalfilename, filecontent,
                 mimetype=None,
                 md5=None,
                 sha1=None):
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
            # FIXME: this shouldn't read all into the memory
            # TODO: COPY FILE INSTEAD
            f = open(filecontent, "rb")
            filedata = f.read()
            f.close()
        else:
            filedata = filecontent
        self.originalfilename = os.path.basename(originalfilename)
        # TODO: use chunk based function instead
        self.md5 = md5 if md5 else hashlib.md5(filedata).hexdigest()
        self.sha1 = sha1 if sha1 else hashlib.sha1(filedata).hexdigest()
        self.save() # Must save here to get self.id
        root, ext = os.path.splitext(originalfilename)
        filename = u"%09d-%s%s" % (self.id, self.uid, ext.lower())
        self.file.save(filename, ContentFile(filedata))
        self.filesize = self.file.size
        if mimetype:
            self.mimetype = mimetype
        else:
            mime = get_mimetype(self.file.path)
            if mime:
                self.mimetype = mime
            else:
                self.mimetype = mimetypes.guess_type(originalfilename)[0]
        # TODO: if file is PDF, create thumbnail:
        # convert -thumbnail x800 file.pdf[0] thumbnail.png
        self.status = "PROCESSED"
        self.save()


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
                image.save() # Save new instance to the database
                if image.thumbnail:
                    self.preview = image.thumbnail
                return image
        elif self.mimetype.startswith("video"):
            try:
                return self.video
            except Video.DoesNotExist:
                video = Video(content=self)
                video.save() # Save new instance to the database
                video.generate_thumb()
                if video.thumbnail:
                    self.preview = video.thumbnail
                return video
        elif self.mimetype.startswith("application/pdf"):
            tmp_file, tmp_name = tempfile.mkstemp()
            tmp_name += '.png'
            #print tmp_name
            if do_pdf_thumbnail(self.file.path, tmp_name):
                postfix = "%s-%s-%sx%s" % (THUMBNAIL_PARAMETERS)
                filename = u"%09d-%s-%s.png" % (self.id, self.uid, postfix)
                if os.path.isfile(tmp_name):
                    with open(tmp_name, "rb") as f:
                        #self.thumbnail.save(filename, ContentFile(f.read()))
                        self.preview.save(filename, File(f))
                    self.save()
                    os.unlink(tmp_name)

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
        elif self.mimetype.startswith("video"): # and self.video.thumbnail:
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
            print "REALLY DELETING HERE ALL INSTANCES AND FILES FROM FILESYSTEM"
        else:
            self.status = 'DELETED'
            self.save()
            #super(Content, self).delete(*args, **kwargs)

    def __unicode__(self):
        text = self.caption[:50] if self.caption else self.title
        return u'"%s" (%s %s B)' % (
                 text, self.mimetype, self.filesize)

class Image(models.Model):
    content = models.OneToOneField(Content, primary_key=True, editable=False)
    width = models.IntegerField(blank=True, null=True, editable=False)
    height = models.IntegerField(blank=True, null=True, editable=False)
    rotate = models.IntegerField(blank=True, null=True, default=0, choices=[(0,0), (90,90), (180,180), (270,270)])
    "Original image must be rotated n degrees CLOCKWISE before showing."
    thumbnail = models.ImageField(storage=preview_storage, upload_to=upload_split_by_1000, editable=False)

    # FIXME: this is probably not in use
    def orientation(self):
        if self.width > self.height:
            return u'horizontal'
        else:
            return u'vertical'

    def __unicode__(self):
        return u"Image: %s (%dx%dpx)" % (
                 self.content.originalfilename,
                 self.width, self.height)

    def generate_thumb(self, image, thumbfield, t):
        """
        TODO: move the general part outside of the model
        """
        if thumbfield:
            thumbfield.delete() # Delete possible previous version
        try:
            im = image.copy()
        except IOError: # Image file is corrupted
            # TODO: use logging! print "ERROR in image file:", self.content.id, self.content.file
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
        # TODO: use StringIO
        tmp = StringIO.StringIO()
        #tmp = tempfile.NamedTemporaryFile()
        im.save(tmp, "jpeg", quality=t[3])
        tmp.seek(0)
        data = tmp.read()
        tmp.close()
        postfix = "%s-%s-%sx%s" % (t)
        #filename = u"%09d-%s%s" % (self.id, self.uid, ext.lower())
        filename = u"%09d-%s-%s.jpg" % (self.content.id, self.content.uid, postfix)
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
        info = get_imageinfo(self.content.file.path)
        #print type(info)
        #print info # NOTE: this print may raise exception below with some images !?!
        # Exception Value: %X format: a number is required, not NoneType
        # Set lat and lon if they exist in info and NOT yet in content
        if 'lat' in info and info['lat'] and self.content.point is None:
            self.content.point = Point(info['lon'], info['lat'])
        if 'datetime' in info and self.content.filetime is None:
            self.content.filetime = info['datetime']
        #elif 'timestamp' in info and self.content.filetime is None:
        #    self.content.filetime = time.strftime("%Y-%m-%d %H:%M:%S", info['timestamp'])
        if 'title' in info and not self.content.title:
            self.content.title = info['title']
        if 'caption' in info and not self.content.caption:
            self.content.caption = info['caption']
        if 'keywords' in info and not self.content.keywords:
            self.content.keywords = info['keywords']
        try: # Handle exif orientation
            orientation = info['exif']['Image Orientation'].values[0]
            if self.rotate == 0:
                if orientation == 3:   self.rotate = 180
                elif orientation == 6: self.rotate = 90
                elif orientation == 8: self.rotate = 270
        except: # No exif orientation available
            # TODO: log error
            pass
        if im:
            self.generate_thumb(im, self.thumbnail, THUMBNAIL_PARAMETERS)
        # TODO: author and other keys, see filetools.get_imageinfo and iptcinfo.py
        super(Image, self).save(*args, **kwargs) # Call the "real" save() method.
        self.content.status = "PROCESSED"
        self.content.save()

class Video(models.Model):
    """
    Dimensions (width, height), duration and bitrate of video media.
    """
    content = models.OneToOneField(Content, primary_key=True, editable=False)
    width = models.IntegerField(blank=True, null=True, editable=False)
    height = models.IntegerField(blank=True, null=True, editable=False)
    duration = models.FloatField(blank=True, null=True, editable=False)
    bitrate = models.CharField(max_length=256, blank=True, null=True, editable=False)
    thumbnail = models.ImageField(storage=preview_storage, upload_to=upload_split_by_1000, editable=False)

    def __unicode__(self):
        return u"Video: %s" % (self.content.originalfilename)
        #return u"Video: %s (%dx%dpx, %.2f sec)" % (
        #         self.content.originalfilename,
        #         self.width, self.height, self.duration)

    def set_metadata(self, data):
        self.width = data.get('width')
        self.height = data.get('height')
        self.duration = data.get('duration')
        self.bitrate = data.get('bitrate')

    #def save(self, *args, **kwargs):
    #    """ Save Video object and in addition:
    #    - use ffmpeg to extract some information of the video file
    #    - use ffmpeg to extract and save one thumbnail image from the file
    #    """
    #    super(Video, self).save(*args, **kwargs) # Call the "real" save() method.
    #    self.content.status = "PROCESSED"
    #    self.content.save()

    def generate_thumb(self):
        if self.content.file is not None and \
           (self.width is None or self.height is None):
            # Create temporary file for thumbnail
            tmp_file, tmp_name = tempfile.mkstemp()
            if do_video_thumbnail(self.content.file.path, tmp_name):
                postfix = "%s-%s-%sx%s" % (THUMBNAIL_PARAMETERS)
                filename = u"%09d-%s-%s.jpg" % (self.content.id, self.content.uid, postfix)
                if os.path.isfile(tmp_name):
                    with open(tmp_name, "rb") as f:
                        #self.thumbnail.save(filename, ContentFile(f.read()))
                        self.thumbnail.save(filename, File(f))
                    self.save()
                    os.unlink(tmp_name)
        #super(Video, self).save(*args, **kwargs) # Call the "real" save() method.
        #self.content.status = "PROCESSED"
        #self.content.save()

class Videoinstance(models.Model):
    """
    An instance of a video file.
    This can be the video in different formats and  sizes or a thumbnail image.
    Dimensions (width, height), duration and bitrate of video media.
    TODO: images could be in separate model?
    """
    content = models.ForeignKey(Content, editable=False, related_name='videoinstances')
    mimetype = models.CharField(max_length=200, editable=False)
    filesize = models.IntegerField(blank=True, null=True, editable=False) # pixels
    duration = models.FloatField(blank=True, null=True, editable=False) # seconds
    bitrate = models.FloatField(blank=True, null=True, editable=False)  # bits / sec
    extension = models.CharField(max_length=16, editable=False)
    width = models.IntegerField(blank=True, null=True, editable=False)  # pixels
    height = models.IntegerField(blank=True, null=True, editable=False) # pixels
    framerate = models.FloatField(blank=True, null=True, editable=False)  # frames / sec
    file = models.FileField(storage=video_storage,
                            upload_to=upload_split_by_1000, editable=False)
    created = models.DateTimeField(auto_now_add=True)

    def set_file(self, filepath, ext):
        """
        """
        self.mimetype = get_mimetype(filepath)
        #ext = self.mimetype.split('/')[1]
        filename = u"%09d-%s.%s" % (self.id, self.content.uid, ext)
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

class Audio(models.Model):
    """
    Duration of audio media.
    """
    content = models.OneToOneField(Content, primary_key=True)
    duration = models.FloatField(blank=True, null=True) # seconds
    def __unicode__(self):
        s = u"Audio: %s" % (self.content.originalfilename)
        s += u" (%.2f sec)" % (self.duration if self.duration else -1.0)
        return s

class Audioinstance(models.Model):
    """
    An instance of a audio file.
    This can be the video in different formats and sizes or a thumbnail image.
    Dimensions (width, height), duration and bitrate of video media.
    TODO: images could be in separate model?
    """
    content = models.ForeignKey(Content, editable=False, related_name='audioinstances')
    mimetype = models.CharField(max_length=200, editable=False)
    filesize = models.IntegerField(blank=True, null=True, editable=False) # pixels
    duration = models.FloatField(blank=True, null=True, editable=False) # seconds
    bitrate = models.FloatField(blank=True, null=True, editable=False)  # bits / sec
    extension = models.CharField(max_length=16, editable=False)
    file = models.FileField(storage=audio_storage,
                            upload_to=upload_split_by_1000, editable=False)
    created = models.DateTimeField(auto_now_add=True)

    def set_file(self, filepath, ext):
        """
        """
        self.mimetype = get_mimetype(filepath)
        #ext = self.mimetype.split('/')[1]
        filename = u"%09d-%s.%s" % (self.id, self.content.uid, ext)
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
    content = models.OneToOneField(Content, primary_key=True, editable=False)
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
        self.sessionid = request.session.session_key if request.session.session_key else ''
        self.ip = request.META.get('REMOTE_ADDR')
        self.useragent = request.META.get('HTTP_USER_AGENT', '')[:500]


class Mail(models.Model):
    """
    Retrieved Mail files
    """
    status = models.CharField(max_length=40, default="UNPROCESSED", editable=True,
                              choices=(("UNPROCESSED", "UNPROCESSED"),
                                        ("PROCESSED", "PROCESSED"),
                                        ("DUPLICATE", "DUPLICATE"),
                                        ("FAILED", "FAILED")))
    filesize = models.IntegerField(null=True, editable=False)
    file = models.FileField(storage=mail_storage, upload_to=upload_split_by_1000, editable=False)
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
        self.save() # Must save here to get self.id
        #root, ext = os.path.splitext(originalfilename)
        filename = u"%09d-%s" % (self.id, host)
        self.file.save(filename, ContentFile(filedata))
        self.filesize = self.file.size
        if Mail.objects.filter(md5=self.md5).filter(sha1=self.sha1).count() > 1:
            self.status = 'DUPLICATE'
        self.save()
