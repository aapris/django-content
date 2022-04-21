import os

from django.test import TestCase

import content.filetools

TESTCONTENT_DIR = os.path.normpath(os.path.join(os.path.normpath(os.path.dirname(__file__)), "testfiles"))
AUDIO_DIR = os.path.join(TESTCONTENT_DIR, "audio")
VIDEO_DIR = os.path.join(TESTCONTENT_DIR, "video")
IMAGE_DIR = os.path.join(TESTCONTENT_DIR, "image")
PDF_DIR = os.path.join(TESTCONTENT_DIR, "pdf")


class FiletoolsTestCase(TestCase):
    def setUp(self):
        pass

    def testAudioFromTestContentDir(self):
        testdir = AUDIO_DIR
        self.assertTrue(os.path.isdir(testdir), "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(len(files), 0, "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            ffp = content.filetools.FFProbe(path)
            self.assertTrue(ffp.is_audio(), "Error '%s'" % filename)
            self.assertFalse(ffp.is_video(), "Error '%s'" % filename)
            print(ffp.get_audioinfo())
        print(f"Tested {cnt} audio files")

    def testVideoFromTestContentDir(self):
        testdir = VIDEO_DIR
        self.assertTrue(os.path.isdir(testdir), "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(len(files), 0, "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            ffp = content.filetools.FFProbe(path)
            self.assertTrue(ffp.is_video(), "Error '%s'" % filename)
            self.assertFalse(ffp.is_audio(), "Error '%s'" % filename)
            print(ffp.get_videoinfo())
        print(f"Tested {cnt} video files")

    def testFFMpegVideoConversion(self):
        testdir = VIDEO_DIR
        self.assertTrue(os.path.isdir(testdir), "Directory '%s' containing test files does not exist." % testdir)
        files = os.listdir(testdir)
        self.assertGreater(len(files), 0, "Directory '%s' containing test files is empty." % testdir)
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(testdir, filename)
            new_video, cmd_str, output = content.filetools.create_videoinstance(path)
            ffp = content.filetools.FFProbe(new_video)
            print(new_video, ffp.get_videoinfo())
            content.filetools.do_video_thumbnail(new_video, "/tmp/thumb.jpg")
            os.unlink(new_video)
            # self.assertTrue(ffp.is_video(), "Error '%s'" % filename)
            # self.assertFalse(ffp.is_audio(), "Error '%s'" % filename)
        print(f"Tested {cnt} video files")
