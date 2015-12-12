import os
from django.test import TestCase
import unittest

import content.filetools
from content.filetools import create_videoinstance, create_audioinstance

from content.models import Content
from content.models import Videoinstance, Audioinstance
from content.models import content_storage, preview_storage

TESTCONTENT_DIR = os.path.normpath(os.path.join(
    os.path.normpath(os.path.dirname(__file__)), "testfiles"))
AUDIO_DIR = os.path.join(TESTCONTENT_DIR, 'audio')
VIDEO_DIR = os.path.join(TESTCONTENT_DIR, 'video')
IMAGE_DIR = os.path.join(TESTCONTENT_DIR, 'image')
PDF_DIR = os.path.join(TESTCONTENT_DIR, 'pdf')


class ContentTestCase(unittest.TestCase):

    def setUp(self):
        self.all_content = []
        pass

    def tearDown(self):
        # Delete all files from file system
        for c in self.all_content:
            content_storage.delete(c.file.path)
            # FIXME: this won't remove audio/videoinstances
            if hasattr(c, 'image') and c.image.thumbnail:
                preview_storage.delete(c.image.thumbnail.path)
            if hasattr(c, 'video') and c.video.thumbnail:
                preview_storage.delete(c.video.thumbnail.path)


    def testNewContentSaving(self):
        self.assertTrue(os.path.isdir(TESTCONTENT_DIR), "Directory '%s' containing test files does not exist." % TESTCONTENT_DIR)
        files = os.listdir(TESTCONTENT_DIR)
        self.assertGreater(len(files), 0,  "Directory '%s' containing test files is empty." % TESTCONTENT_DIR)
        cnt = 0
        for filename in files:
            cnt += 1
            c = Content(caption=u'New content #%d' % cnt)
            full_path = os.path.join(TESTCONTENT_DIR, filename)
            if not os.path.isfile(full_path):
                continue
            c.set_file(filename, full_path)
            c.set_fileinfo()
            c.generate_thumbnail()
            c.save()
            maintype = c.mimetype.split('/')[0]
            print "MIMETYYPPI", c.mimetype, c.preview
            if maintype in ['video', 'audio']:
                ffp = content.filetools.FFProbe(c.file.path)
                info = content.filetools.fileinfo(c.file.path)
                print info
                #finfo = get_ffmpeg_videoinfo(c.file.path)
                #print finfo
                if ffp.is_video():
                    new_video, cmd_str = create_videoinstance(c.file.path)
                    vi = Videoinstance(content=c)
                    vi.save()
                    vi.set_file(new_video, 'webm')
                    #info = get_videoinfo(get_ffmpeg_videoinfo(vi.file.path))
                    vi.set_metadata(info)
                    vi.save()
                    print u'%s %.1f sec %dx%d pix' % (vi.mimetype, vi.duration, vi.width, vi.height)
                if ffp.is_audio():
                    new_audio, cmd_str = create_audioinstance(c.file.path)
                    ai = Audioinstance(content=c)
                    ai.save()
                    ai.set_file(new_audio, 'ogg')
                    #info = get_audioinfo(get_ffmpeg_videoinfo(ai.file.path))
                    #print info
                    ai.set_metadata(info)
                    ai.save()
                    print u'%s %.1f sec' % (ai.mimetype, ai.duration)
            #print c.get_type_instance()
            #print c.caption
            self.all_content.append(c)
            #self.assertEqual(c.file.path, "sd", c.file.path)
        #import time
        #time.sleep(20)
        self.assertEqual(Content.objects.count(), len(self.all_content), "1 or more files failed")




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
            c.set_fileinfo()
            c.generate_thumbnail()
            c.save()
            maintype = c.mimetype.split('/')[0]
            print "MIMETYYPPI", c.mimetype, c.preview
            if maintype in ['video', 'audio']:
                ffp = content.filetools.FFProbe(c.file.path)
                info = content.filetools.fileinfo(c.file.path)
                print info
                #finfo = get_ffmpeg_videoinfo(c.file.path)
                #print finfo
                if ffp.is_video():
                    new_video, cmd_str = create_videoinstance(c.file.path)
                    vi = Videoinstance(content=c)
                    vi.save()
                    vi.set_file(new_video, 'webm')
                    #info = get_videoinfo(get_ffmpeg_videoinfo(vi.file.path))
                    vi.set_metadata(info)
                    vi.save()
                    print u'%s %.1f sec %dx%d pix' % (vi.mimetype, vi.duration, vi.width, vi.height)
                if ffp.is_audio():
                    new_audio, cmd_str = create_audioinstance(c.file.path)
                    ai = Audioinstance(content=c)
                    ai.save()
                    ai.set_file(new_audio, 'ogg')
                    #info = get_audioinfo(get_ffmpeg_videoinfo(ai.file.path))
                    #print info
                    ai.set_metadata(info)
                    ai.save()
                    print u'%s %.1f sec' % (ai.mimetype, ai.duration)
            #print c.get_type_instance()
            #print c.caption
            self.all_content.append(c)
            #self.assertEqual(c.file.path, "sd", c.file.path)
        #import time
        #time.sleep(20)
        self.assertEqual(Content.objects.count(), len(self.all_content), "1 or more files failed")




class FiletoolsTestCase(TestCase):

    def setUp(self):
        pass

    def testAudioFromTestContentDir(self):
        testdir = AUDIO_DIR
        self.assertTrue(os.path.isdir(testdir), "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(len(files), 0,  "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            ffp = content.filetools.FFProbe(path)
            self.assertTrue(ffp.is_audio(), "Error '%s'" % filename)
            self.assertFalse(ffp.is_video(), "Error '%s'" % filename)
        print "Tested %d audio files" % cnt

    def testVideoFromTestContentDir(self):
        testdir = VIDEO_DIR
        self.assertTrue(os.path.isdir(testdir), "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(len(files), 0,  "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            ffp = content.filetools.FFProbe(path)
            self.assertTrue(ffp.is_video(), "Error '%s'" % filename)
            self.assertFalse(ffp.is_audio(), "Error '%s'" % filename)
        print "Tested %d video files" % cnt

    def testFFMpegVideoConversion(self):
        testdir = VIDEO_DIR
        self.assertTrue(os.path.isdir(testdir), "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(len(files), 0,  "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            new_video, cmd_str = content.filetools.create_videoinstance(path)
            ffp = content.filetools.FFProbe(new_video)
            print new_video, ffp.get_videoinfo()
            os.unlink(new_video)
            #self.assertTrue(ffp.is_video(), "Error '%s'" % filename)
            #self.assertFalse(ffp.is_audio(), "Error '%s'" % filename)
        print "Tested %d video files" % cnt


