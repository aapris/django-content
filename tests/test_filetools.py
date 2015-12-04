import os
#import tempfile
#from PIL import Image

from django.test import TestCase
import content.filetools2


TESTCONTENT_DIR = os.path.normpath(os.path.join(
    os.path.normpath(os.path.dirname(__file__)), "testfiles"))
AUDIO_DIR = os.path.join(TESTCONTENT_DIR, 'audio')
VIDEO_DIR = os.path.join(TESTCONTENT_DIR, 'video')
IMAGE_DIR = os.path.join(TESTCONTENT_DIR, 'image')
PDF_DIR = os.path.join(TESTCONTENT_DIR, 'pdf')


class FiletoolsTestCase(TestCase):

    def setUp(self):
        pass

    def testAudioFromTestContentDir(self):
        testdir = AUDIO_DIR
        self.assertTrue(
            os.path.isdir(testdir),
            "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(
            len(files), 0,
            "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            ffp = content.filetools2.FFProbe(path)
            self.assertTrue(ffp.is_audio(), "Error '%s'" % filename)
            self.assertFalse(ffp.is_video(), "Error '%s'" % filename)
            print ffp.get_audioinfo()
        print "Tested %d audio files" % cnt

    def testVideoFromTestContentDir(self):
        testdir = VIDEO_DIR
        self.assertTrue(
            os.path.isdir(testdir),
            "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(
            len(files), 0,
            "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            ffp = content.filetools2.FFProbe(path)
            self.assertTrue(ffp.is_video(), "Error '%s'" % filename)
            self.assertFalse(ffp.is_audio(), "Error '%s'" % filename)
            print ffp.get_videoinfo()
        print "Tested %d video files" % cnt

    def testFFMpegVideoConversion(self):
        testdir = VIDEO_DIR
        self.assertTrue(
            os.path.isdir(testdir),
            "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(
            len(files), 0,
            "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            new_video, cmd_str = content.filetools2.create_videoinstance(path)
            ffp = content.filetools2.FFProbe(new_video)
            print new_video, ffp.get_videoinfo()
            content.filetools2.do_video_thumbnail(new_video, '/tmp/thumb.jpg')
            os.unlink(new_video)
            #self.assertTrue(ffp.is_video(), "Error '%s'" % filename)
            #self.assertFalse(ffp.is_audio(), "Error '%s'" % filename)
        print "Tested %d video files" % cnt
