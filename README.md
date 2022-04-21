# django-content

This Django application was part of CoMeUP, Albumit auki and Plok.in projects years ago.
Currently I'm porting this to support Python 3.9+ and Django 4.0+.

Django-content can store any kind of files,
providing previews for video, image and PDF files.

## Objectives

* Python 3.9 and newer supported
* Django 4.0 and newer supported
* Installable python module, perhaps with pip from pypi
* Sample Django Rest Framework API, ready to use
* Sufficient test coverage
* Find alternatives for ImageMagick, Ghostscript and other dependencies

# Prerequisites

Applications and libraries listed below must be installed
before content app can work:

* PostgreSQL & PostGIS as a database backend
* libpq-dev to compile psycopg2
* ffmpeg & ffprobe for converting video and audio files and creating thumbnails 
* libmagic to determine file types
* libheif to open HEIF image files
* python3-dev
* gdal-bin, python3-gdal
