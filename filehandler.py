# -*- coding: utf-8 -*-

import tempfile


def handle_uploaded_file(request, destination=None):
    """
    Save all files found in request.FILES to filesystem.
    If destination is not None, it must be an open ('wb') file handle.
    """
    for inputfile in request.FILES:
        tmp_file, tmp_name = tempfile.mkstemp()
        filedata = request.FILES[inputfile]
        # original_filename = filedata.name
        if destination is None:
            destination = open(tmp_name, 'wb')
        for chunk in filedata.chunks():
            destination.write(chunk)
        destination.close()
        yield inputfile, tmp_name
