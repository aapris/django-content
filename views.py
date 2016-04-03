# -*- coding: utf-8 -*-

# from django.conf import settings
# from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import Http404
# from django.template import Context
from django.template import RequestContext
from django.shortcuts import render_to_response
from django.utils.translation import ugettext_lazy as _
# from django.utils.encoding import smart_unicode, force_unicode
from wsgiref.util import FileWrapper
from django.core.urlresolvers import reverse
from django.db.models import Q

from django.contrib.gis.geos import Point

import os
import StringIO
from PIL import Image as ImagePIL
from PIL import ImageDraw, ImageFont
import json

from filehandler import handle_uploaded_file
from models import Content, Uploadinfo, Videoinstance, Audioinstance
from forms import UploadForm, SearchForm, ContentModelForm

import logging
logger = logging.getLogger('django')

"""
TODO: make GeoIP work!
TODO: try to make PyExiv2 work
"""


def _render_to_response(request, template, variables):
    """
    Wrapper for render_to_response() shortcut.
    Puts user, perms and some other common variables available in template.
    """
    variables['request'] = request
    variables['uploadform'] = UploadForm()
    variables['searchform'] = SearchForm(request.GET)
    return render_to_response(
        template, variables, context_instance=RequestContext(request),
    )


@login_required
def index(request):
    """
    Renders the index page of Content.

    Args:
        request: the request object

    Returns:
        response: a http response object
    """
    if request.user.is_superuser:
        latest_objects = Content.objects.all()
    else:
        latest_objects = Content.objects.filter(user=request.user)
    q = request.GET.get('q')
    if q and len(q) >= 2:
        qset = Q(title__icontains = q)
        qset |= Q(caption__icontains = q)
        qset |= Q(mimetype__icontains = q)
        qset |= Q(originalfilename__icontains = q)
        latest_objects = latest_objects.filter(qset)
    latest_objects = latest_objects.order_by('-id')[:20]
    return _render_to_response(request, 'content_base.html', {
        'latest_objects': latest_objects,
    })


@login_required
def upload(request):
    """
    Renders the upload form page.

    Args:
        request: the request object

    Returns:
        response: a http response object
    """
    if request.method == 'POST':  # If the form has been submitted...
        form = UploadForm(request.POST, request.FILES)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            for filefield, tmpname in handle_uploaded_file(request):
                c = Content()
                originalname = str(request.FILES["file"])
                c.user = request.user  # Only authenticated users can use this view
                c.set_file(originalname, tmpname)  # Save uploaded file to filesystem
                c.get_type_instance()  # Create thumbnail if it is supported
                c.save()
                Uploadinfo.create(c, request)
                # uli.set_request_data(request)
                # uli.save()
            return HttpResponseRedirect(reverse('content:edit', args=[c.uid]))
    else:
        form = UploadForm(initial={})  # An unbound form
    return _render_to_response(request, 'content_upload.html', {
                                  'uploadform' : form,
                               })


@csrf_exempt
def api_upload(request):
    """
    Renders the upload form page.

    Args:
        request: the request object

    Returns:
        response: a http response object
    """
    if request.method == 'POST':  # If the form has been submitted...
        # for header in request.META.keys():
        #    if header.startswith('HTTP'):
        #        print header, request.META[header]
        # print request.raw_post_data[:1000]
        if request.user.is_authenticated() is False:
            return HttpResponse(status=401)
        form = UploadForm(request.POST, request.FILES)  # A form bound to the POST data
        if form.is_valid():  # All validation rules pass
            for filefield, tmpname in handle_uploaded_file(request):
                SUPPORTED_FIELDS = ['title', 'caption', 'author']
                kwargs = {}
                for field in SUPPORTED_FIELDS:
                    kwargs[field] = request.POST.get(field)
                try:
                    kwargs['point'] = Point(float(request.POST.get('lon')), float(request.POST.get('lat')))
                except:
                    # raise
                    pass
                print kwargs
                c = Content(**kwargs)
                originalname = str(request.FILES["file"])
                # Only authenticated users can use this view
                c.user = request.user
                # Save uploaded file to filesystem
                c.set_file(originalname, tmpname)
                # Create thumbnail if it is supported
                c.get_type_instance()
                c.save()
                Uploadinfo.create(c, request)
                break  # We save only the first file
            response = HttpResponse(status=201)
            # response.status_code = 201
            # FIXME: use reverse()
            response['Location'] = '/content/api/v1/content/%s/' % c.uid
            return response
            # return HttpResponseRedirect(reverse('content:edit', args=[c.uid]))
        else:
            response = HttpResponse(status=204)
            return response
    else:
        raise Http404


@login_required
def html5upload(request):
    """
    Renders the upload form page.

    Args:
        request: the request object

    Returns:
        response: a http response object
    """
    if request.method == 'POST':  # If the form has been submitted...
        result = []
        for filefield, tmpname in handle_uploaded_file(request):
            c = Content()
            originalname = str(request.FILES["file"])
            c.user = request.user  # Only authenticated users can use this view
            c.set_file(originalname, tmpname)  # Save uploaded file to filesystem
            c.get_type_instance()  # Create thumbnail if it is supported
            c.save()
            Uploadinfo.create(c, request).save()
            # print originalname
            # generating json response array
            result.append({"name": originalname,
                           "size": c.filesize,
                           "url": reverse('content:edit', args=[c.uid]),
                           "thumbnail_url": '/content/instance/%s-200x200.jpg' % c.uid,
                           "delete_url": reverse('content:edit', args=[c.uid]),
                           "delete_type":"POST",})
        # print result
        response_data = json.dumps(result)
        # print response_data
        # checking for json data type
        # big thanks to Guy Shapiro
        if "application/json" in request.META['HTTP_ACCEPT_ENCODING']:
            mimetype = 'application/json'
        else:
            mimetype = 'text/plain'
        return HttpResponse(response_data, mimetype=mimetype)
    return _render_to_response(request, 'content_html5upload.html', {
                               })


@login_required
def edit(request, uid):
    """
    Renders the edit form page.

    Args:
        request: the request object
        uid: Content object uid

    Returns:
        response: a http response object
    """
    # Check that object exists and user is allowed to edit it
    try:
        object = Content.objects.get(uid=uid)
    except Content.DoesNotExist:
        raise Http404
    if object.user != request.user and not request.user.is_superuser:
        raise Http404  # FIXME: unauthorized instead
    # Create form instance
    if request.method == 'POST':  # If the form has been submitted...
        form = ContentModelForm(request.POST, instance=object)
        if form.is_valid():  # All validation rules pass
            new_object = form.save(commit=False)
            if form.cleaned_data['latlon']:
                lat, lon = [float(x) for x in form.cleaned_data['latlon'].split(',')]
                new_object.point = Point(lon, lat)
                # print lat, lon, new_object.point
            else:
                new_object.point = None
            msg = _(u'Form was saved successfully')
            messages.success(request, msg)
            new_object.save()
            return HttpResponseRedirect(reverse('content:edit', args=[new_object.uid]))
        # else:
        #    form = UploadForm(initial={})  # An unbound form
    else:
        initial = {}
        if object and object.point:
            initial['latlon'] = u'%.8f,%.8f' % (object.point.coords[1], object.point.coords[0])
        form = ContentModelForm(instance=object, initial=initial)
    return _render_to_response(request, 'content_edit.html', {
                                  'editform' : form,
                                  'object': object,
                               })


@login_required
def search(request):
    form = SearchForm()
    return _render_to_response(request, 'content_search.html', {
                                  'searchform' : form,
                               })


def _get_placeholder_instance(c, text=None):
    imsize = (160, 80)
    immode = 'RGBA'
    imfont = os.path.join('mestadb', 'Arial.ttf')
    imfontsize = 22
    imtext = c.mimetype if text is None else text
    if imtext:
        imtext = imtext.replace('/', ' ').split(' ')
    else:
        imtext = [u'Broken', u'file']
    if len(imtext) == 1:
        imtext.append(u'')
    im = ImagePIL.new(immode, imsize, '#eeeeee')
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype(imfont, imfontsize, encoding='unic')
    except IOError, err:
        logger.warning("Could not find font? %s" % str(err))
        font = ImageFont.load_default()
        # raise
    
    draw.text((5,10), imtext[0], font=font, fill='#333333')
    draw.text((5,35), imtext[1], font=font, fill='#333333')
    # corners = [(0,0), 
    #           (imsize[0], 0), 
    #           (imsize[0], imsize[1]),
    #           (0, imsize[1]),
    #           (0,0)
    #           ]
    # for i in range(0,len(corners)-1):
    #    draw.line((corners[i], corners[i+1]), width=3, fill='#000000')
    del draw
    # im.save("/tmp/text.png", "PNG")
    return im 


# @cache_page(60 * 60)  # FIXME: this value should in settings.py
@cache_page(60 * 60)
def instance(request, uid, width, height, action, ext):
    """
    Return scaled JPEG instance of the Content, which type is image.
    New size is determined from URL.
    action can be '-crop'
    """
    # w, h = width, height
    response = HttpResponse()
    try:
        c = Content.objects.get(uid=uid)
    except Content.DoesNotExist:
        raise Http404
    if c.mimetype:
        contenttype = c.mimetype.split("/")[0]
    else:
        # FIXME: no mimetype, content may be broken?
        # Check where contenttype is set and make sure there is
        # some meaningful value always! Perhaps required field?
        contenttype = None
    # Return image if type is image or video
    # if contenttype in ['image', 'video']:
    if True or contenttype in ['image', 'video']:
        thumbnail = None
        # FIXME: check does the content have a thumbnail here!
        try:
            if contenttype == 'image' and c.image:
                thumbnail = c.image.thumbnail
            elif contenttype == 'video':
                thumbnail = c.video.thumbnail
        except Exception, err:
            logger.warning(str(err))
        try:
            im = ImagePIL.open(thumbnail.path)
        except AttributeError, err:
            print "No thumbnail in non-video/image Content ", c.uid, str(err)
            im = _get_placeholder_instance(c)
        except IOError, err:
            msg = "IOERROR in Content %s: %s" % (c.uid, str(err))
            logger.error(msg)
            return HttpResponse('ERROR: This Content has no thumbnail.', status=404)
        except ValueError, err:
            msg = "ValueERROR in Content, missing thumbnail %s: %s" % (c.uid, str(err))
            logger.warning(msg)
            im = _get_placeholder_instance(c, text=u'Missing thumbnail')
            # return HttpResponse('ERROR: This Content has no thumbnail.', status=404)
        size = int(width), int(height)
        if action == '-crop':
            shorter_side = min(im.size)
            side_divider = 1.0 * shorter_side / min(size)
            crop_size = int(max(im.size) / side_divider) + 1
            # print shorter_side, side_divider, im.size, crop_size
            size = (crop_size, crop_size)
            im.thumbnail(size, ImagePIL.ANTIALIAS)
            margin = (max(im.size) - min(im.size)) / 2
            crop_size = min(im.size)
            if im.size[0] > im.size[1]:  # horizontal
                crop = [0 + margin, 0, margin + crop_size, crop_size]
            else:
                crop = [0, 0 + margin, crop_size, margin + crop_size]
            im = im.crop(crop)
        else:
            im.thumbnail(size, ImagePIL.ANTIALIAS)
        tmp = StringIO.StringIO()
        im.save(tmp, "jpeg", quality=90)
        data = tmp.getvalue()
        tmp.close()
        response = HttpResponse()
        response.write(data)
        response["Content-Type"] = "image/jpeg"
        response["Content-Length"] = len(data)
        response["Accept-Ranges"] = "bytes"
        if 'attachment' in request.GET:
            response["Content-Disposition"] = "attachment; filename=%s-%s.jpg" % (c.originalfilename, c.uid)
        # Use 'updated' time in Last-Modified header (cache_page uses caching page)
        response['Last-Modified'] = c.updated.strftime('%a, %d %b %Y %H:%M:%S GMT')
        return response
    else:
        data = "Requested %s %s %s %s %s " % (c.mimetype, uid, width, height, ext)
        response.write(data)
        response["Content-Type"] = "text/plain"  # content_item.mime
        response["Content-Length"] = len(data)
        return response


@cache_page(60 * 60)
def view(request, uid, width, height, action, ext):
    """
    Return scaled JPEG/PNG instance of the Content, which has preview available
    New size is determined from URL.
    action can be '-crop'
    """
    # w, h = width, height
    # response = HttpResponse()
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
            if content.mimetype.startswith('image') and content.image:
                thumbnail = content.image.thumbnail
            elif content.mimetype.startswith('video'):
                thumbnail = content.video.thumbnail
        except Exception, err:
            logger.warning(str(err))
    thumb_format = "png"
    # Handle errors if thumbnail is not found or is not readable etc.
    try:
        im = ImagePIL.open(thumbnail.path)
        if thumbnail.path.endswith('png') is False:
            thumb_format = "jpeg"
    except AttributeError, err:
        print "No thumbnail in non-video/image Content ", content.uid, str(err)
        im = _get_placeholder_instance(content)
    except IOError, err:
        msg = "IOERROR in Content %s: %s" % (content.uid, str(err))
        logger.error(msg)
        return HttpResponse('ERROR: This Content has no thumbnail.', status=404)
    except ValueError, err:
        msg = "ValueERROR in Content, missing thumbnail %s: %s" % (content.uid, str(err))
        logger.warning(msg)
        im = _get_placeholder_instance(content, text=u'Missing thumbnail')
    # If we got here, we should have some kind of Image object.
    # Width and height may be %d if the client uses preview_uri literally
    # (it should replace them with integer).
    if width in ['%d', '%(width)d'] and height in ['%d', '%(height)d']:
        # size = 320, 240
        size = 640, 480
    else:
        size = int(width), int(height)
    # Crop image if requested so
    if action == '-crop':
        shorter_side = min(im.size)
        side_divider = 1.0 * shorter_side / min(size)
        crop_size = int(max(im.size) / side_divider) + 1
        # print shorter_side, side_divider, im.size, crop_size
        size = (crop_size, crop_size)
        im.thumbnail(size, ImagePIL.ANTIALIAS)
        margin = (max(im.size) - min(im.size)) / 2
        crop_size = min(im.size)
        if im.size[0] > im.size[1]:  # horizontal
            crop = [0 + margin, 0, margin + crop_size, crop_size]
        else:
            crop = [0, 0 + margin, crop_size, margin + crop_size]
        im = im.crop(crop)
    else:
        im.thumbnail(size, ImagePIL.ANTIALIAS)
    response = HttpResponse()
    tmp = StringIO.StringIO()
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
    if 'attachment' in request.GET:
        response["Content-Disposition"] = "attachment; filename=%s-%s.jpg" % (content.originalfilename, content.uid)
    # Use 'updated' time in Last-Modified header (cache_page uses caching page)
    response['Last-Modified'] = content.updated.strftime('%a, %d %b %Y %H:%M:%S GMT')
    return response


# @cache_page(60 * 60)
def foobar(request, uid, id, ext):
    """
    Return converted version of Content, if the format is video or audio
    # TODO: rewrite
    """
    # w, h = width, height
    response = HttpResponse()
    try:
        c = Content.objects.get(uid=uid)
    except Content.DoesNotExist:
        raise Http404
    ais = Audioinstance.objects.filter(content=c).filter(id=id)
    vis = Videoinstance.objects.filter(content=c).filter(id=id)
    if ais.count() > 0:
        inst = ais[0]
    elif vis.count() > 0:
        inst = vis[0]
    else:
        raise Http404
    response = HttpResponse()
    with open(inst.file.path, 'rb') as f:
        response.write(f.read())
    response["Content-Type"] = inst.mimetype
    response["Content-Length"] = inst.filesize
    # These are needed to make <video> allow restarting the video
    # Content-Range: bytes 0-318464/318465
    # Accept-Ranges: bytes
    response["Content-Range"] = "bytes 0-%d/%d" % (inst.filesize - 1, inst.filesize)
    response["Accept-Ranges"] = "bytes"
    if 'attachment' in request.GET:
        response["Content-Disposition"] = "attachment; filename=%s-%s.%s" % (c.originalfilename, c.uid, ext)
        # Use 'updated' time in Last-Modified header (cache_page uses caching page)
    response['Last-Modified'] = c.updated.strftime('%a, %d %b %Y %H:%M:%S GMT')
    return response


# @login_required
# @cache_page(60 * 60)
def original(request, uid, filename = None):
    """
    Return original file.
    """
    # FIXME: this doesn't authenticate!
    uid = uid.split('.')[0]  # remove possible extension
    try:
        c = Content.objects.get(uid=uid)
    except Content.DoesNotExist:
        raise Http404
    wrapper = FileWrapper(file(c.file.path))
    response = HttpResponse(wrapper)
    response["Content-Type"] = c.mimetype
    response['Content-Length'] = os.path.getsize(c.file.path)
    if 'attachment' in request.GET:
        if filename:
            response["Content-Disposition"] = "attachment"
        else:  # FIXME: this will fail if filename contains non-ascii chars
            response["Content-Disposition"] = "attachment; filename=%s" % (c.originalfilename)
    # tmp = open(c.file.path, "rb")
    # data = tmp.read()
    # tmp.close()
    # response = HttpResponse()
    # response.write(data)
    # response["Content-Type"] = c.mimetype
    # response["Content-Length"] = len(data)
    return response


@login_required
def metadata(request, uid):
    """
    Return scaled JPEG instance of the Content, which type is image.
    New size is determined from URL.
    """
    response = HttpResponse()
    try:
        c = Content.objects.get(uid=uid)
    except Content.DoesNotExist:
        raise Http404
    data = []
    data.append(u"Author: %s" % c.author)
    data.append(u"Caption: %s" % c.caption)
#    data.append(u"City: %s" %  c.region.all()[0].name)
#    data.append(u"Decade: %s" %  c.decade.all()[0].name)
    data = "\n".join(data)
    response = HttpResponse()
    response.write(data)
    response["Content-Type"] = "text/plain"  # content_item.mime
    response["Content-Length"] = len(data)
    response["Content-disposition"] = "attachment; filename=fotorally-%s.txt" % (c.uid)
    return response
