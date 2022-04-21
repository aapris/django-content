import os
import unittest
from pathlib import Path

from django.test import TestCase

import content.filetools
from content.filetools import create_videoinstance, create_audioinstance
from content.models import Content
from content.models import Videoinstance, Audioinstance
from content.models import content_storage, preview_storage

TEST_CONTENT_DIR = Path(__file__).resolve().parent / Path("testfiles")
AUDIO_DIR = TEST_CONTENT_DIR / Path("audio")
VIDEO_DIR = TEST_CONTENT_DIR / Path("video")
IMAGE_DIR = TEST_CONTENT_DIR / Path("image")
PDF_DIR = TEST_CONTENT_DIR / Path("pdf")


class ContentTestCase(unittest.TestCase):
    def setUp(self):
        self.all_content = []
        pass

    def tearDown(self):
        # Delete all files from file system
        for c in self.all_content:
            content_storage.delete(c.file.path)
            # FIXME: this won't remove audio/videoinstances
            if hasattr(c, "image") and c.image.thumbnail:
                preview_storage.delete(c.image.thumbnail.path)
            if hasattr(c, "video") and c.video.thumbnail:
                preview_storage.delete(c.video.thumbnail.path)

    def testNewContentSaving(self):
        self.assertTrue(
            os.path.isdir(TEST_CONTENT_DIR), f"Directory '{TEST_CONTENT_DIR}' containing test files does not exist."
        )
        files = os.listdir(TEST_CONTENT_DIR)
        self.assertGreater(len(files), 0, f"Directory '{TEST_CONTENT_DIR}' containing test files is empty.")
        cnt = 0
        for filename in files:
            full_path = os.path.join(TEST_CONTENT_DIR, str(filename))
            if os.path.isfile(full_path) is False:
                print(f"Skip {full_path}, not a file")
                continue
            cnt += 1
            c = Content(caption="New content #%d" % cnt)
            c.set_file(str(filename), full_path)
            c.set_fileinfo()
            c.generate_thumbnail()
            c.save()
            maintype = c.mimetype.split("/")[0]

            if maintype in ["video", "audio"]:
                ffp = content.filetools.FFProbe(c.file.path)
                info = content.filetools.fileinfo(c.file.path)
                print(info)
                if ffp.is_video():
                    new_video, cmd_str, output = create_videoinstance(c.file.path)
                    vi = Videoinstance(content=c)
                    vi.save()
                    vi.set_file(new_video, "webm")
                    vi.set_metadata(info)
                    vi.save()
                    print(f"{c.mimetype} {c.preview} {vi.mimetype} {vi.duration:.1f} sec {vi.width}x{vi.height} px")
                if ffp.is_audio():
                    new_audio, cmd_str, output = create_audioinstance(c.file.path)
                    ai = Audioinstance(content=c)
                    ai.save()
                    ai.set_file(new_audio, "ogg")
                    ai.set_metadata(info)
                    ai.save()
                    print(f"{c.mimetype} {c.preview} {ai.mimetype} {ai.duration:.1f} sec")
            self.all_content.append(c)
            # self.assertEqual(c.file.path, "sd", c.file.path)
        # self.assertEqual(Content.objects.count(), len(self.all_content), "1 or more files failed")

    def testNewContentFromTestContentDir(self):
        self.assertTrue(
            os.path.isdir(TEST_CONTENT_DIR), "Directory '%s' containing test files does not exist." % TEST_CONTENT_DIR
        )
        files = os.listdir(TEST_CONTENT_DIR)
        print("\n\nFAILEJA", TEST_CONTENT_DIR, files)
        self.assertGreater(len(files), 0, "Directory '%s' containing test files is empty." % TEST_CONTENT_DIR)
        cnt = 0
        for filename in files:
            cnt += 1
            c = Content(caption="New content #%d" % cnt)
            full_path = os.path.join(TEST_CONTENT_DIR, str(filename))
            c.set_file(str(filename), full_path)
            c.set_fileinfo()
            c.generate_thumbnail()
            c.save()
            maintype = c.mimetype.split("/")[0]
            print("MIMETYYPPI", c.mimetype, c.preview)

            if maintype in ["video", "audio"]:
                ffp = content.filetools.FFProbe(c.file.path)
                info = content.filetools.fileinfo(c.file.path)
                print(info)

                if ffp.is_video():
                    new_video, cmd_str, output = create_videoinstance(c.file.path)
                    vi = Videoinstance(content=c)
                    vi.save()
                    vi.set_file(new_video, "webm")
                    vi.set_metadata(info)
                    vi.save()
                    print("%s %.1f sec %dx%d pix" % (vi.mimetype, vi.duration, vi.width, vi.height))

                if ffp.is_audio():
                    new_audio, cmd_str, output = create_audioinstance(c.file.path)
                    ai = Audioinstance(content=c)
                    ai.save()
                    ai.set_file(new_audio, "ogg")
                    ai.set_metadata(info)
                    ai.save()
                    print("%s %.1f sec" % (ai.mimetype, ai.duration))

            self.all_content.append(c)
            # self.assertEqual(c.file.path, "sd", c.file.path)
        # import time
        # time.sleep(20)
        self.assertEqual(Content.objects.count(), len(self.all_content), "1 or more files failed")


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
        print("Tested %d audio files" % cnt)

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
            self.assertTrue(ffp.is_video(), f"Error '{filename}'")
            self.assertFalse(ffp.is_audio(), f"Error '{filename}'")
        print(f"Tested {cnt} video files")

    def testFFMpegVideoConversion(self):
        test_dir = VIDEO_DIR
        self.assertTrue(os.path.isdir(test_dir), f"Directory '{test_dir}' containing test files does not exist.")
        files = os.listdir(test_dir)
        self.assertGreater(len(files), 0, f"Directory '{test_dir}' containing test files is empty.")
        cnt = 0
        for filename in files:
            cnt += 1
            path = os.path.join(test_dir, str(filename))
            new_video, cmd_str, output = content.filetools.create_videoinstance(path)
            ffp = content.filetools.FFProbe(new_video)
            print(new_video, ffp.get_videoinfo())
            os.unlink(new_video)
            # self.assertTrue(ffp.is_video(), "Error '%s'" % filename)
            # self.assertFalse(ffp.is_audio(), "Error '%s'" % filename)
        print(f"Tested {cnt} video files")
