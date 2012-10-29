# -*- coding: utf-8 -*-

"""
Test cases for Content
NOTE: this requires Django 1.3

Try to write one-line assert commands for readability.
"""

import os
import tempfile
import Image

from django.utils import unittest
from django.db import connection, transaction, IntegrityError
from django.contrib.auth.models import User
from content.filetools import get_ffmpeg_videoinfo, get_videoinfo, get_audioinfo
from content.filetools import create_videoinstance, create_audioinstance
from content.filetools import is_audio, is_video

from content.models import Content
from content.models import Videoinstance, Audioinstance
from content.models import content_storage, preview_storage

TESTCONTENT_DIR = os.path.normpath(os.path.join(os.path.normpath(os.path.dirname(__file__)), "testfiles"))

class ContentTestCase(unittest.TestCase):

    def setUp(self):
        self.all_content = []
        pass

    def tearDown(self):
        # Delete all files from file system
        for c in self.all_content:
            content_storage.delete(c.file.path)
            if hasattr(c, 'image'):
                preview_storage.delete(c.image.thumbnail.path)
            if hasattr(c, 'video'):
                preview_storage.delete(c.video.thumbnail.path)

    def testNewContentFromTestContentDir(self):
        self.assertTrue(os.path.isdir(TESTCONTENT_DIR), "Directory '%s' containing test files does not exist." % TESTCONTENT_DIR)
        files = os.listdir(TESTCONTENT_DIR)
        self.assertGreater(len(files), 0,  "Directory '%s' containing test files is empty." % TESTCONTENT_DIR)
        cnt = 0
        for filename in files:
            cnt += 1
            c = Content(caption=u'New content #%d' % cnt)
            full_path = os.path.join(TESTCONTENT_DIR, filename)
            c.set_file(filename, full_path)
            c.save()
            maintype = c.mimetype.split('/')[0]
            if maintype in ['video', 'audio']:
                finfo = get_ffmpeg_videoinfo(c.file.path)
                print finfo
                if is_video(finfo):
                    new_video = create_videoinstance(c.file.path)
                    vi = Videoinstance(content=c)
                    vi.save()
                    vi.set_file(new_video, 'webm')
                    info = get_videoinfo(get_ffmpeg_videoinfo(vi.file.path))
                    print info
                    vi.set_metadata(info)
                    vi.save()
                    print u'%s %.1f sec %dx%d pix' % (vi.mimetype, vi.duration, vi.width, vi.height)
                if is_audio(finfo):
                    new_video = create_audioinstance(c.file.path)
                    ai = Audioinstance(content=c)
                    ai.save()
                    ai.set_file(new_video, 'ogg')
                    info = get_audioinfo(get_ffmpeg_videoinfo(ai.file.path))
                    print info
                    ai.set_metadata(info)
                    ai.save()
                    print u'%s %.1f sec' % (vi.mimetype, vi.duration)
            #print c.get_type_instance()
            #print c.caption
            self.all_content.append(c)
            #self.assertEqual(c.file.path, "sd", c.file.path)
        #import time
        #time.sleep(20)
        self.assertEqual(Content.objects.count(), len(self.all_content), "1 or more files failed")


"""


    def testNewContentFromOpenFile(self):
        c = Content()
        tmp = tempfile.NamedTemporaryFile()
        im.save(tmp, "jpeg", quality=t[3])
        tmp.seek(0)
        data = tmp.read()
        tmp.close()

        c.set_file()
        c.save()
        self.assertEqual(foo, bar, "")
        self.assertIs(c.user, None, "New Contact's user should be None.")
        self.assertIsNot(c.user, None, "Contact on userlevel B should have a user account.")


    def testNewContent(self):
        c = Content()
        c.save()
        self.assertEqual(foo, bar, "")
        self.assertIs(c.user, None, "New Contact's user should be None.")
        self.assertIsNot(c.user, None, "Contact on userlevel B should have a user account.")

    def testCreateExisting(self):
        kwargs = { 'foo': 'bar', }
        with self.assertRaises(IntegrityError):
            c1 = Content(**kwargs)
            c1.save()
        transaction.rollback()
"""
