from __future__ import annotations

import io
import logging
import os

import PIL.Image
from PIL import ImageDraw, ImageFont
from django.http import Http404, HttpResponse, FileResponse
from rest_framework import mixins, viewsets
from rest_framework import parsers
from rest_framework.response import Response
# from rest_framework import permissions

from content.models import Content
from content.serializers import ContentSerializer


# TODO: add authentication and authorization


class ContentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    API endpoint that allows Contents to be created, viewed or edited.
    """

    queryset = Content.objects.all().order_by("-created")
    serializer_class = ContentSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.FileUploadParser]

    # permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if "file" not in request.data:
            return Response("'file' argument is missing", status=400)
        try:
            f = request.data.pop("file")[0]
        except Exception as err:
            logging.warning(f"Failed to get 'file' from request: {err}")
            raise
        # Use get_serializer here, because ContentSerializer(data=request.data)
        # doesn't contain self.context["request"] in all cases,
        # e.g. when returning serializer.data in post
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        c: Content = serializer.save()
        c.set_file(f.name, f)
        c.set_fileinfo()
        c.generate_thumbnail()
        return Response(serializer.data, status=201)


def _get_placeholder_instance(c, text=None):
    imsize = (160, 80)
    imfont = os.path.join('mestadb', 'Arial.ttf')
    imfontsize = 22
    try:
        font = ImageFont.truetype(imfont, imfontsize, encoding='unic')
    except IOError as err:
        logging.warning("Could not find font? %s" % str(err))
        font = ImageFont.load_default()
    imtext = c.mimetype if text is None else text
    if imtext:
        imtext = imtext.replace('/', ' ').split(' ')
    else:
        imtext = [u'Broken', u'file']
    if len(imtext) == 1:
        imtext.append('')
    im = PIL.Image.new('RGBA', imsize, '#eeeeee')
    draw = ImageDraw.Draw(im)
    draw.text((5, 10), imtext[0], font=font, fill='#333333')
    draw.text((5, 35), imtext[1], font=font, fill='#333333')
    del draw
    return im


def preview(request, uid: str, width: int | str, height: int | str, action=None, ext=None):
    """
    Return scaled JPEG/PNG instance of the Content, which has preview available
    New size is determined from URL.
    action can be '-crop'
    """
    thumbnail = None
    try:
        content = Content.objects.get(uid=uid)
    except Content.DoesNotExist:
        raise Http404
    # Find thumbnail, currently new place is content.preview, but content.image.thumbnail is still in use
    if content.preview:
        thumbnail = content.preview
    else:  # TODO: to be removed after image.thumbnails are converted to content.preview
        try:
            if content.mimetype.startswith("image") and content.image:
                thumbnail = content.image.thumbnail
            elif content.mimetype.startswith("video"):
                thumbnail = content.video.thumbnail
        except Exception as err:
            logging.warning(str(err))
    thumb_format = "png"

    # Handle errors if thumbnail is not found or is not readable etc.
    try:
        im = PIL.Image.open(thumbnail.path)
        if thumbnail.path.endswith("png") is False:
            thumb_format = "jpeg"
    except AttributeError as err:
        print("No thumbnail in non-video/image Content ", content.uid, str(err))
        im = _get_placeholder_instance(content)
    except IOError as err:
        msg = "IOERROR in Content %s: %s" % (content.uid, str(err))
        logging.error(msg)
        return HttpResponse("ERROR: This Content has no thumbnail.", status=404)
    except ValueError as err:
        msg = "ValueERROR in Content, missing thumbnail %s: %s" % (content.uid, str(err))
        logging.warning(msg)
        im = _get_placeholder_instance(content, text="Missing thumbnail")
    # If we got here, we should have some kind of Image object.
    # Width and height may be W/H if the client uses preview_uri literally
    # (it should replace them with integer).
    if width in ["W", "%d", "%(width)d"] and height in ["H", "%d", "%(height)d"]:
        size = 640, 480
    else:
        size = int(width), int(height)
    # Crop image if requested so
    if action == "-crop":
        shorter_side = min(im.size)
        side_divider = 1.0 * shorter_side / min(size)
        crop_size = int(max(im.size) / side_divider) + 1
        # print shorter_side, side_divider, im.size, crop_size
        size = (crop_size, crop_size)
        im.thumbnail(size, PIL.Image.ANTIALIAS)
        margin = (max(im.size) - min(im.size)) / 2
        crop_size = min(im.size)
        if im.size[0] > im.size[1]:  # horizontal
            crop = [0 + margin, 0, margin + crop_size, crop_size]
        else:
            crop = [0, 0 + margin, crop_size, margin + crop_size]
        im = im.crop(crop)
    else:
        im.thumbnail(size, PIL.Image.ANTIALIAS)
    response = HttpResponse()
    tmp = io.BytesIO()
    if thumb_format == "png":
        im.save(tmp, thumb_format)
        response["Content-Type"] = "image/png"
    else:
        im.save(tmp, thumb_format, quality=90)
        response["Content-Type"] = "image/jpeg"
    data = tmp.getvalue()
    tmp.close()
    response.write(data)
    response["Content-Length"] = len(data)
    response["Accept-Ranges"] = "bytes"
    if "attachment" in request.GET:
        response["Content-Disposition"] = "attachment; filename=%s-%s.jpg" % (content.originalfilename, content.uid)
    # Use 'updated' time in Last-Modified header (cache_page uses caching page)
    response["Last-Modified"] = content.updated.strftime("%a, %d %b %Y %H:%M:%S GMT")
    return response


def original(request, uid: str, filename: str) -> FileResponse:
    """
    Return original file.
    """
    try:
        c = Content.objects.get(uid=uid)
    except Content.DoesNotExist:
        raise Http404
    response = FileResponse(open(c.file.path, "rb"))
    response["Content-Type"] = c.mimetype
    disp = "attachment" if "attachment" in request.GET else "inline"
    response["Content-Disposition"] = f'{disp}; filename="{c.originalfilename}"'
    return response


def instance(request, uid: str, extension: str) -> FileResponse:
    """
    Return one of video or audio instances.
    """
    try:
        c = Content.objects.get(uid=uid)
    except Content.DoesNotExist:
        raise Http404
    instances = c.videoinstances.filter(extension=extension)
    if instances:
        response = FileResponse(open(instances[0].file.path, "rb"))
        response["Content-Type"] = instances[0].mimetype
        return response
    else:
        raise Http404
