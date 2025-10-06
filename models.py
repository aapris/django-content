"""
Defines all supported different content type classes (image, video, audio etc.)
If file type is not supported, it is saved "as is", without any metadata
about duration, bitrate, dimensions etc.
"""

# TODO: implement Image/Video/Audio Instance classes, which save conversions
# to different formats and sizes (e.g. audio->mp3+ogg, video->mp4+theora).
# TODO: possibility to save more than one thumbnails of a video?

import io
import logging
import mimetypes
import os
import random
import shutil
import string
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

# Because we have local class Image, we can't import literally Image from PIL
import PIL.Image
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Manager  # https://stackoverflow.com/a/48894881
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from pillow_heif import register_heif_opener

# Import metadata extraction and file utilities
from content import filemetadata
from content.filetools import do_pdf_thumbnail, do_video_thumbnail


# Original files are saved in content_storage
content_storage = FileSystemStorage(location=settings.APP_DATA_DIRS["CONTENT"])
# Generated dynamic files (previews, video and audio instances) are in 'var'
preview_storage = FileSystemStorage(location=settings.APP_VAR_DIRS["PREVIEW"])
video_storage = FileSystemStorage(location=settings.APP_VAR_DIRS["VIDEO"])
audio_storage = FileSystemStorage(location=settings.APP_VAR_DIRS["AUDIO"])
# TODO: change to APP_VAR_DIRS or something
mail_storage = FileSystemStorage(location=settings.MAIL_CONTENT_DIR)

# define this in local_settings, if you want to change this
# TODO: replace with getattr
THUMBNAIL_PARAMETERS = getattr(
    settings, "CONTENT_THUMBNAIL_PARAMETERS", (1600, 1600, "JPEG", 90)
)  # w, h, format, quality

CONTENT_PRIVACY_CHOICES = (("PRIVATE", _("Private")), ("RESTRICTED", _("Group")), ("PUBLIC", _("Public")))

register_heif_opener()

# Constants
DEFAULT_UID_LENGTH = 12
FILE_PATH_CHECK_THRESHOLD = 1000  # Threshold for determining if content is file path vs file data
TEMP_DIR_NAME = "temp"


def upload_split_by_1000(obj: Any, filename: str) -> str:
    """
    Return the path where the original file will be saved.
    Files are split into a directory hierarchy, which bases on object's id,
    e.g. if obj.id is 12345, fill path will be 000/012/filename
    so there will be max 1000 files in a directory.
    NOTE: if len(id) exceeds 9 (it is 999 999 999) directory hierarchy will
    get one level deeper, e.g. id=10**9 -> 100/000/000/filename
    This should not clash with existing filenames.
    """
    # Validate filename for security
    if not filename or ".." in filename or filename.startswith("/"):
        raise ValueError(f"Invalid filename: {filename}")

    # Sanitize filename - remove path separators and control characters
    filename = Path(filename).name
    if not filename:
        raise ValueError("Filename cannot be empty after sanitization")
    if hasattr(obj, "content"):
        id_ = obj.content.id
        uid = obj.content.uid
    else:
        id_ = obj.id
        uid = obj.uid

    if id_ is None:
        # Use UID for new objects that haven't been saved yet
        # This creates a temporary path that will be corrected by post_save signal
        return f"{TEMP_DIR_NAME}/{uid}/{filename}"

    # Create proper filename: {id:09d}-{uid}.ext
    # But preserve quality parameters if they exist (for preview/thumbnail files)
    path_obj = Path(filename)
    ext = path_obj.suffix

    # Check if filename already has quality parameters (e.g. "000000002-uid-1600-1600-JPEGx90.jpg")
    # This happens when Image/Video models explicitly set thumbnail filename
    if f"{id_:09d}-{uid}" in filename:
        # Filename already properly formatted, use as is
        proper_filename = filename
    else:
        # Standard content file, create proper filename
        proper_filename = f"{id_:09d}-{uid}{ext.lower()}"

    long_id = f"{id_:09d}"  # e.g. '000012345'
    chunk_indices = [i for i in range(0, len(long_id) - 3, 3)]  # -> [0, 3, 6]
    path = Path(*[long_id[j : j + 3] for j in chunk_indices], proper_filename)  # -> '000/012/000012345-uid.ext'
    return str(path)


def get_uid(length: int = DEFAULT_UID_LENGTH) -> str:
    """
    Generate and return a random string which can be considered unique.
    Default length is 12 characters from set [a-zA-Z0-9].
    """
    alphanumeric_chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphanumeric_chars) for _ in range(length))


class Group(models.Model):
    """Content group model for organizing content access permissions.

    Groups allow organizing users and controlling access to content files.
    Each group has a name, slug, description and associated users.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField()
    users = models.ManyToManyField(User, blank=True, editable=True, related_name="contentgroups")
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self) -> str:
        return self.slug


class Content(models.Model):
    """
    Common fields for all content files.

    Field info:
    status -
    privacy - PRIVATE, RESTRICTED, PUBLIC
    uid - unique random identifier string
    user - Django User, if relevant
    group -
    original_filename - original filename
    file_size - file size of original file in bytes
    filetime - creation time of original file (e.g. EXIF timestamp)
    mimetype - Official MIME Media Type (e.g. image/jpeg, video/mp4)
    file - original file object
    preview - thumbnail object if relevant
    sha1 - sha1 of original file in hex-format
    created_at - creation timestamp
    updated_at - last update timestamp
    opens - optional timestamp after which this Content is available
    expires - optional timestamp after which this object isn't available
    peers = Content's peers, if relevant
    parent - Content's parent Content, if relevant
    linktype - information of the type of child-parent relation
    point = models.PointField(geography=True, blank=True, null=True)

    title - title text of this Content, a few words max
    caption - descriptive text of this Content
    author - Content author's name or nickname
    keywords - comma separated list of keywords/tags
    place - country, state/province, city, address or other textual description
    """

    status = models.CharField(max_length=40, default="UNPROCESSED", editable=False)
    privacy = models.CharField(
        max_length=40, default="PRIVATE", verbose_name=_("Privacy"), choices=CONTENT_PRIVACY_CHOICES
    )
    uid = models.CharField(max_length=40, unique=True, db_index=True, default=get_uid, editable=False)
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    group = models.ForeignKey(Group, blank=True, null=True, on_delete=models.SET_NULL)
    original_filename = models.CharField(
        max_length=256, null=True, verbose_name=_("Original file name"), editable=False
    )
    file_size = models.IntegerField(null=True, editable=False)
    filetime = models.DateTimeField(blank=True, null=True, editable=False)
    mimetype = models.CharField(max_length=200, null=True, editable=False)
    file = models.FileField(storage=content_storage, upload_to=upload_split_by_1000)  # , editable=False)
    preview = models.ImageField(storage=preview_storage, blank=True, upload_to=upload_split_by_1000, editable=False)
    sha1 = models.CharField(max_length=40, null=True, editable=False)

    # Links and relations to other content files
    peers = models.ManyToManyField("self", blank=True, editable=False)
    parent = models.ForeignKey("self", blank=True, null=True, editable=False, on_delete=models.SET_NULL)
    linktype = models.CharField(max_length=500, blank=True)
    # point (geography) is used for e.g. distance calculations
    point = models.PointField(geography=True, blank=True, null=True)
    # point_geom (geometry) is used to enable e.g. within queries
    point_geom = models.PointField(blank=True, null=True)
    title = models.CharField(max_length=200, blank=True, verbose_name=_("Title"))
    caption = models.TextField(blank=True, verbose_name=_("Caption"))
    author = models.CharField(max_length=200, blank=True, verbose_name=_("Author"))
    keywords = models.CharField(max_length=500, blank=True, verbose_name=_("Keywords"))
    place = models.CharField(max_length=500, blank=True, verbose_name=_("Place"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    opens = models.DateTimeField(blank=True, null=True)
    expires = models.DateTimeField(blank=True, null=True)

    # In referencing model add e.g. `files = GenericRelation(Content)`
    content_type = models.ForeignKey(ContentType, blank=True, null=True, default=None, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey("content_type", "object_id")

    objects = Manager()

    # TODO: replace this with property stuff
    def latlon(self) -> Optional[Tuple[float, float]]:
        # FIXME: should this be lonlat?
        if self.point and hasattr(self.point, "coords"):
            coords = self.point.coords
            if len(coords) >= 2:
                return (coords[0], coords[1])
        return None

    def set_latlon(self, lat: float, lon: float) -> None:
        p = Point(lon, lat)
        self.point = p
        self.point_geom = p

    def save_file(self, original_filename: str, filecontent: Union[UploadedFile, io.IOBase, str]) -> None:
        """
        Save filecontent to the filesystem and fill filename, file_size fields.
        filecontent may be
        - open file handle (opened in "rb"-mode)
        - existing file name (full path)
        - raw file data
        """
        # TODO: check functionality with very large files
        path_obj = Path(original_filename)
        self.original_filename = path_obj.name
        self.save()  # Must save here to get self.id
        ext = path_obj.suffix
        filename = "{:09d}-{}{}".format(self.id, self.uid, ext.lower())
        if isinstance(filecontent, UploadedFile):  # Is an open file
            self.file.save(filename, File(filecontent))
        elif isinstance(filecontent, io.IOBase):  # Is open file
            # Type ignore for Django File constructor compatibility
            self.file.save(filename, File(filecontent))  # type: ignore[arg-type]
        elif len(filecontent) < FILE_PATH_CHECK_THRESHOLD and Path(filecontent).is_file():
            # Is existing file in file system
            with open(filecontent, "rb") as f:
                self.file.save(filename, File(f))
        elif len(filecontent) < FILE_PATH_CHECK_THRESHOLD:
            # Looks like a file path but file doesn't exist
            raise FileNotFoundError(f"File not found: {filecontent}")
        else:  # Is just something in the memory
            self.file.save(filename, ContentFile(filecontent))
        self.file_size = self.file.size
        self.save()

    def set_file(
        self,
        original_filename: str,
        filecontent: Union[UploadedFile, io.IOBase, str],
        mimetype: Optional[str] = None,
        sha1: Optional[str] = None,
    ) -> None:
        """
        Save Content.file and all it's related fields
        (filename, file_size, mimetype, sha1).
        'filecontent' may be
        - open file handle (opened in "rb"-mode)
        - existing file name (full path)
        - raw file data
        """
        self.save_file(original_filename, filecontent)
        if sha1 is None:
            self.sha1 = filemetadata.hashfile(self.file.path)
        if mimetype:
            self.mimetype = mimetype
        else:
            mime = filemetadata.get_mimetype(self.file.path)
            if mime:
                self.mimetype = mime
            else:
                self.mimetype = mimetypes.guess_type(original_filename)[0]
        self.status = "PROCESSED"
        self.save()

    def set_fileinfo(self, mime: Optional[str] = None) -> Optional[Union["Image", "Video", "Audio"]]:
        """Create or update Content metadata objects (Image/Video/Audio).

        Args:
            mime: MIME type of the file. If None, uses self.mimetype.

        Returns:
            Created or updated Image, Video, or Audio object, or None if not applicable.
        """
        if mime is None:
            mime = self.mimetype
        obj: Optional[Union["Image", "Video", "Audio"]] = None
        info: Optional[Dict[str, Any]] = None
        try:
            # Use unified metadata extraction
            info = filemetadata.get_metadata(self.file.path, mime)

            # Create appropriate model based on MIME type
            if mime and mime.startswith("image"):
                try:
                    obj = self.image
                except Image.DoesNotExist:
                    obj = Image(content=self)
            elif mime and mime.startswith("video"):
                try:
                    obj = self.video
                except Video.DoesNotExist:
                    obj = Video(content=self)
            elif mime and mime.startswith("audio"):
                try:
                    obj = self.audio
                except Audio.DoesNotExist:
                    obj = Audio(content=self)
        except Exception as e:
            # Log error but continue gracefully
            logging.error(f"Error extracting file metadata for {self.file.path}: {e}")
            return None

        if obj and info:
            obj.set_metadata(info)
            obj.save()  # Save new instance to the database
            # Save common data into self
            if "gps" in info:
                if self.point is None and "lat" in info["gps"]:
                    self.set_latlon(info["gps"]["lat"], info["gps"]["lon"])
            if self.filetime is None:
                if "gps" in info and "gpstime" in info["gps"]:
                    self.filetime = info["gps"]["gpstime"]
                elif "creation_time" in info:
                    self.filetime = info.get("creation_time")
            self.save()
            return obj
        return None

    def get_fileinfo(self):
        info = filemetadata.get_metadata(self.file.path)
        return info

    def generate_thumbnail(self) -> None:
        """Generate preview thumbnail for the content file.

        Creates thumbnails for images, videos, and PDF files and saves them
        to the preview field. The thumbnail generation method depends on the
        file's MIME type.

        Note:
            TODO: use only content.preview for thumbnails, not video/image.thumbnail
        """
        # TODO: create generic thumbnail functions for video, image and pdf
        try:
            if self.mimetype and self.mimetype.startswith("image"):
                try:
                    im = PIL.Image.open(self.file.path)
                    self.image.generate_thumb(im, self.image.thumbnail, THUMBNAIL_PARAMETERS)
                    if self.image.thumbnail:
                        self.preview = self.image.thumbnail
                        self.save()
                except Image.DoesNotExist:
                    pass
            elif self.mimetype and self.mimetype.startswith("video"):
                try:
                    if self.video.thumbnail:
                        self.video.thumbnail.delete()
                    self.video.generate_thumb()
                    if self.video.thumbnail:
                        self.preview = self.video.thumbnail
                        self.save()
                except Video.DoesNotExist:
                    pass
            elif self.mimetype and self.mimetype.startswith("application/pdf"):
                fd, tmp_name = tempfile.mkstemp()  # Remember to close fd!
                tmp_name += ".png"
                if do_pdf_thumbnail(self.file.path, tmp_name):
                    t = THUMBNAIL_PARAMETERS
                    postfix = "{}-{}-{}x{}".format(t[0], t[1], t[2], t[3])
                    # print(THUMBNAIL_PARAMETERS)
                    # postfix = "{}-{}-{}x{}".format(THUMBNAIL_PARAMETERS)  # noqa
                    filename = "{:09d}-{}-{}.png".format(self.id, self.uid, postfix)
                    tmp_path = Path(tmp_name)
                    if tmp_path.is_file():
                        with open(tmp_name, "rb") as f:
                            self.preview.save(filename, File(f))
                        self.save()
                        tmp_path.unlink()
                os.close(fd)
            else:
                return None
        except Exception as e:
            # Log error but don't crash
            logging.error(f"Error generating thumbnail for {self.file.path}: {e}")
            return None

    def preview_ext(self) -> str:
        """Return the file extension of preview if it exists."""
        # TODO: use pathlib
        if self.preview:
            path_obj = Path(self.preview.path)
            ext = path_obj.suffix
        else:
            path_obj = Path(self.file.path)
            ext = path_obj.suffix
        return ext.lstrip(".")

    def thumbnail(self) -> Optional[Any]:
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

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Override save() to automatically process file metadata when a new file is uploaded.
        This ensures that set_fileinfo() and generate_thumbnail() are called regardless
        of how the Content object is saved (admin, API, etc.).
        """
        # Check if this is a new object or if the file has changed
        file_changed = False
        is_new = self.pk is None

        if not is_new:
            # Check if file has changed by comparing with database version
            try:
                old_file_name = Content.objects.values_list("file", flat=True).get(pk=self.pk)
                file_changed = old_file_name != self.file.name if self.file else False
            except Content.DoesNotExist:
                file_changed = True
        else:
            # New object with a file
            file_changed = bool(self.file)

        # Call the original save method first
        super().save(*args, **kwargs)

        # Process file metadata if file is new or changed
        if file_changed and self.file:
            try:
                # Extract and save file metadata
                info = filemetadata.get_metadata(self.file.path)

                # Set GPS coordinates if available
                if "gps" in info:
                    if "lat" in info["gps"] and self.point is None:
                        self.set_latlon(info["gps"]["lat"], info["gps"]["lon"])
                    if "gpstime" in info["gps"] and self.filetime is None:
                        self.filetime = info["gps"]["gpstime"]

                # Set creation time if not already set
                if self.filetime is None and "creation_time" in info:
                    self.filetime = info.get("creation_time")

                # Get and set mimetype
                mime = info.get("mimetype")
                if mime and not self.mimetype:
                    self.mimetype = mime
                elif not self.mimetype:
                    self.mimetype = mimetypes.guess_type(self.original_filename or "")[0]

                # Set original filename if not already set
                if not self.original_filename and self.file:
                    self.original_filename = Path(self.file.name).name

                # Set file size if not already set
                if not self.file_size and self.file:
                    self.file_size = self.file.size

                # Generate hash values if not already set
                if not self.sha1:
                    self.sha1 = filemetadata.hashfile(self.file.path)

                # Set file info (creates Image/Video/Audio objects)
                self.set_fileinfo(mime=mime)

                # Generate thumbnail
                self.generate_thumbnail()

                # Update status
                if self.status == "UNPROCESSED":
                    self.status = "PROCESSED"

                # Save again if we made changes
                super().save(
                    update_fields=[
                        "original_filename",
                        "file_size",
                        "filetime",
                        "mimetype",
                        "sha1",
                        "status",
                        "point",
                        "point_geom",
                    ]
                )

            except (IOError, OSError, ValueError, AttributeError) as e:
                # Log error but don't prevent saving
                logging.error(
                    f"Error processing file metadata for Content {self.pk} "
                    f"({self.original_filename or 'unknown'}): {e}",
                    exc_info=True,
                )
                self.status = "FAILED"
                super().save(update_fields=["status"])

    def delete(self, *args: Any, **kwargs: Any) -> None:
        """
        Set Content.status = "DELETE". Real deletion (referencing Videos and
        Audios, Video and AudioInstances) can be done later e.g. with
        some management command (not implemented yet).
        """
        if kwargs.get("purge", False) is True and self.status == "DELETED":
            # TODO:
            # for f in [self.file, self.preview]:
            #    if Path(f).is_file():
            #        Path(f).unlink()
            # Delete all instance files too
            print("REALLY DELETING HERE ALL INSTANCES AND FILES FROM FILESYSTEM")
            # Super.delete
        else:
            self.status = "DELETED"
            self.save()

    def __str__(self) -> str:
        text = self.caption[:50] if self.caption else self.title
        return f'"{text}" {self.mimetype}  ({self.file_size}B)'


class Image(models.Model):
    content = models.OneToOneField(Content, primary_key=True, editable=False, on_delete=models.CASCADE)
    width = models.IntegerField(blank=True, null=True, editable=False)
    height = models.IntegerField(blank=True, null=True, editable=False)
    # "Original image must be rotated n degrees CLOCKWISE before showing."
    rotate = models.IntegerField(blank=True, null=True, default=0, choices=[(0, 0), (90, 90), (180, 180), (270, 270)])
    thumbnail = models.ImageField(storage=preview_storage, upload_to=upload_split_by_1000, editable=False)

    # FIXME: this is probably not in use
    def orientation(self) -> str:
        if self.width and self.height and self.width > self.height:
            return "horizontal"
        else:
            return "vertical"

    def set_metadata(self, info: Dict[str, Any]) -> None:
        self.width = info.get("width")
        self.height = info.get("height")
        # if "gps" in info:
        #     if self.content.point is None and "lat" in info["gps"]:
        #         self.content.set_latlon(info["gps"]["lat"], info["gps"]["lon"])
        # TODO: put these to Content.set_metadata() or something
        # TODO: check timezone awareness, creation_time is not aware
        # if not self.content.filetime:
        #     if "gps" in info and "gpstime" in info["gps"]:
        #         self.content.filetime = info["gps"]["gpstime"]
        #     elif "creation_time" in info:
        #         self.content.filetime = info["creation_time"]  # FIXME
        if "title" in info and not self.content.title:
            self.content.title = info["title"]
        if "caption" in info and not self.content.caption:
            self.content.caption = info["caption"]
        if "keywords" in info and not self.content.keywords:
            self.content.keywords = info["keywords"]
        try:  # Handle exif orientation
            orientation = info["exif"]["Image Orientation"].values[0]
            if self.rotate == 0:
                if orientation == 3:
                    self.rotate = 180
                elif orientation == 6:
                    self.rotate = 90
                elif orientation == 8:
                    self.rotate = 270
        except (KeyError, AttributeError, IndexError) as e:  # No exif orientation available
            # EXIF orientation data not available or malformed
            logging.debug(
                f"No EXIF orientation data available for content {self.content.id} "
                f"({self.content.original_filename}): {e}"
            )
            pass

    def __str__(self) -> str:
        return "Image: {} ({}x{}px)".format(self.content.original_filename, self.width, self.height)

    def generate_thumb(self, image: PIL.Image.Image, thumbfield: Any, t: Tuple[int, int, str, int]) -> bool:
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
        except IOError as e:  # Image file is corrupted
            logging.warning(
                f"Failed to generate thumbnail for content {self.content.id} ({self.content.original_filename}): {e}"
            )
            return False
        if im.mode not in ("L", "RGB"):
            im = im.convert("RGB")
        size = (t[0], t[1])
        if self.rotate == 90:
            im = im.transpose(PIL.Image.ROTATE_270)
        elif self.rotate == 180:
            im = im.transpose(PIL.Image.ROTATE_180)
        elif self.rotate == 270:
            im = im.transpose(PIL.Image.ROTATE_90)
        im.thumbnail(size, PIL.Image.LANCZOS)
        # Save resized image to a temporary buffer
        tmp = io.BytesIO()
        im.save(tmp, "jpeg", quality=t[3])
        tmp.seek(0)
        data = tmp.read()
        tmp.close()
        postfix = "{}-{}-{}x{}".format(t[0], t[1], t[2], t[3])
        filename = "{:09d}-{}-{}.jpg".format(self.content.id, self.content.uid, postfix)
        thumbfield.save(filename, ContentFile(data))
        return True

    def re_generate_thumb(self) -> None:
        im = PIL.Image.open(self.content.file.path)
        self.generate_thumb(im, self.thumbnail, THUMBNAIL_PARAMETERS)

    def save(self, *args: Any, **kwargs: Any) -> None:
        im = None
        if self.content.file is not None and (self.width is None or self.height is None):
            try:
                im = PIL.Image.open(self.content.file.path)
                (self.width, self.height) = im.size
            except IOError:
                self.content.status = "INVALID"
                self.content.save()
                return
        if im:
            self.generate_thumb(im, self.thumbnail, THUMBNAIL_PARAMETERS)
        # TODO: author and other keys, see filetools.get_imageinfo
        super().save(*args, **kwargs)
        self.content.status = "PROCESSED"
        self.content.save()


class Video(models.Model):
    """
    Dimensions (width, height), duration and bitrate of video media.
    """

    content = models.OneToOneField(Content, primary_key=True, editable=False, on_delete=models.CASCADE)
    width = models.IntegerField(blank=True, null=True, editable=False)
    height = models.IntegerField(blank=True, null=True, editable=False)
    duration = models.FloatField(blank=True, null=True, editable=False)
    bitrate = models.CharField(max_length=256, blank=True, null=True, editable=False)
    thumbnail = models.ImageField(storage=preview_storage, upload_to=upload_split_by_1000, editable=False)

    def __str__(self) -> str:
        return f"Video: {self.content.original_filename}"

    def set_metadata(self, data: Dict[str, Any]) -> None:
        # if "gps" in data:
        #     if self.content.point is None and "lat" in data["gps"]:
        #         self.content.set_latlon(data["gps"]["lat"], data["gps"]["lon"])
        self.content.filetime = data.get("creation_time")
        self.width = data.get("width")
        self.height = data.get("height")
        self.duration = data.get("duration")
        self.bitrate = data.get("bitrate")

    def generate_thumb(self) -> None:
        if self.content.file is not None:  # and \
            # (self.width is None or self.height is None):
            # Create temporary file for thumbnail
            fd, tmp_name = tempfile.mkstemp()  # Remember to close fd!
            if do_video_thumbnail(self.content.file.path, tmp_name):
                t = THUMBNAIL_PARAMETERS
                postfix = "{}-{}-{}x{}".format(t[0], t[1], t[2], t[3])
                filename = "{:09d}-{}-{}.jpg".format(self.content.id, self.content.uid, postfix)
                tmp_path = Path(tmp_name)
                if tmp_path.is_file():
                    with open(tmp_name, "rb") as f:
                        self.thumbnail.save(filename, File(f))
                    self.save()
                    tmp_path.unlink()
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

    content = models.ForeignKey(Content, editable=False, on_delete=models.CASCADE, related_name="videoinstances")
    mimetype = models.CharField(max_length=200, editable=False)
    file_size = models.IntegerField(blank=True, null=True, editable=False)
    duration = models.FloatField(blank=True, null=True, editable=False)
    bitrate = models.FloatField(blank=True, null=True, editable=False)
    extension = models.CharField(max_length=16, editable=False)
    width = models.IntegerField(blank=True, null=True, editable=False)
    height = models.IntegerField(blank=True, null=True, editable=False)
    framerate = models.FloatField(blank=True, null=True, editable=False)
    file = models.FileField(storage=video_storage, upload_to=upload_split_by_1000, editable=False)
    command = models.CharField(max_length=2000, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_file(self, filepath, ext):
        """Copy temporary file to video storage."""
        self.mimetype = filemetadata.get_mimetype(filepath)
        filename = "{:09d}-{}.{}".format(self.id, self.content.uid, ext)
        with open(filepath, "rb") as f:
            self.file.save(filename, File(f))
            self.file_size = self.file.size
            self.extension = ext
        self.save()

    def set_metadata(self, data):
        self.width = data.get("width")
        self.height = data.get("height")
        self.duration = data.get("duration")
        self.bitrate = data.get("bitrate")
        self.framerate = data.get("framerate")


class Audio(models.Model):
    """
    Duration of audio media.
    """

    content = models.OneToOneField(Content, primary_key=True, editable=False, on_delete=models.CASCADE)
    duration = models.FloatField(blank=True, null=True)
    bitrate = models.FloatField(blank=True, null=True, editable=False)

    def set_metadata(self, data: Dict[str, Any]) -> None:
        self.duration = data.get("duration")
        self.bitrate = data.get("bitrate")

    def __str__(self) -> str:
        s = "Audio: {}".format(self.content.original_filename)
        s += " ({:.2f} sec)".format(self.duration if self.duration else -1.0)
        return s


class Audioinstance(models.Model):
    """
    An instance of a audio file.
    This can be the video in different formats and sizes or a thumbnail image.
    Dimensions (width, height), duration and bitrate of video media.
    TODO: images could be in separate model?
    """

    content = models.ForeignKey(Content, editable=False, on_delete=models.CASCADE, related_name="audioinstances")
    mimetype = models.CharField(max_length=200, editable=False)
    file_size = models.IntegerField(blank=True, null=True, editable=False)
    duration = models.FloatField(blank=True, null=True, editable=False)
    bitrate = models.FloatField(blank=True, null=True, editable=False)
    extension = models.CharField(max_length=16, editable=False)
    file = models.FileField(storage=audio_storage, upload_to=upload_split_by_1000, editable=False)
    command = models.CharField(max_length=2000, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_file(self, filepath, ext):
        self.mimetype = filemetadata.get_mimetype(filepath)
        filename = "{:09d}-{}.{}".format(self.id, self.content.uid, ext)
        with open(filepath, "rb") as f:
            self.file.save(filename, File(f))
            self.file_size = self.file.size
            self.extension = ext
        self.save()

    def set_metadata(self, data):
        self.duration = data.get("duration")
        self.bitrate = data.get("bitrate")


# Signal handlers
@receiver(post_save, sender=Content)
def move_file_to_correct_location(sender, instance, created, **kwargs):
    """
    Move file from temp location to correct ID-based location after save.
    Uses pathlib for all file operations.
    """
    if created and instance.file:
        current_path = Path(instance.file.path)

        # Check if file is in temp location
        if "temp" in current_path.parts:
            # Generate correct path now that we have ID
            # Use original filename to generate proper path with correct naming
            original_filename = instance.original_filename or current_path.name
            correct_path = upload_split_by_1000(instance, original_filename)

            # Create new file path using pathlib
            storage_location = Path(instance.file.storage.location)
            new_file_path = storage_location / correct_path

            # Create directories if needed
            new_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file using shutil
            shutil.move(str(current_path), str(new_file_path))

            # Update file field (without triggering save recursion)
            instance.file.name = correct_path
            Content.objects.filter(pk=instance.pk).update(file=correct_path)

            # Clean up temp directory if empty
            try:
                temp_dir = current_path.parent
                # Only remove if directory is empty
                temp_dir.rmdir()
                # Also try to remove parent temp directory if empty
                if temp_dir.parent.name == "temp":
                    temp_dir.parent.rmdir()
            except OSError:
                # Directory not empty or other error - ignore
                pass
