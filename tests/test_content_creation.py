"""
Tests for Content object creation with different file types.

Tests that Content objects can be created successfully from various file types
and that basic metadata is extracted correctly.
"""

import pytest

from content.models import Content

from .conftest import ContentTestMixin


@pytest.mark.django_db
class TestContentCreation(ContentTestMixin):
    """Test Content object creation from different file types."""

    def test_create_content_from_heic_image(self, sample_heic_file, content_cleanup, create_test_content):
        """Test creating Content from HEIC image file."""
        content = create_test_content(sample_heic_file, "Test HEIC image")
        content_cleanup(content)

        # Basic assertions
        self.assert_content_basic_fields(content, "IMG_6584.HEIC")

        # HEIC-specific assertions
        assert content.mimetype.startswith("image/")
        assert hasattr(content, "image")
        assert content.image is not None

        # Should have image metadata
        assert content.image.width > 0
        assert content.image.height > 0

    def test_create_content_from_mp4_video(self, sample_mp4_file, content_cleanup, create_test_content):
        """Test creating Content from MP4 video file."""
        content = create_test_content(sample_mp4_file, "Test MP4 video")
        content_cleanup(content)

        # Basic assertions
        self.assert_content_basic_fields(content, "mutanen-kohta.mp4")

        # Video-specific assertions
        assert content.mimetype.startswith("video/")
        assert hasattr(content, "video")
        assert content.video is not None

        # Should have video metadata
        assert content.video.width > 0
        assert content.video.height > 0
        assert content.video.duration > 0

    def test_create_content_from_mp3_audio(self, sample_mp3_file, content_cleanup, create_test_content):
        """Test creating Content from MP3 audio file."""
        content = create_test_content(sample_mp3_file, "Test MP3 audio")
        content_cleanup(content)

        # Basic assertions
        self.assert_content_basic_fields(content, "Pohjois-Karjala.mp3")

        # Audio-specific assertions
        assert content.mimetype.startswith("audio/")
        assert hasattr(content, "audio")
        assert content.audio is not None

        # Should have audio metadata
        assert content.audio.duration > 0

    def test_create_content_from_pdf(self, sample_pdf_file, content_cleanup, create_test_content):
        """Test creating Content from PDF file."""
        content = create_test_content(sample_pdf_file, "Test PDF document")
        content_cleanup(content)

        # Basic assertions
        self.assert_content_basic_fields(content, "test_pdf.pdf")

        # PDF-specific assertions
        assert content.mimetype == "application/pdf"

    def test_create_content_from_complex_pdf(self, sample_pdf_file2, content_cleanup, create_test_content):
        """Test creating Content from PDF with complex filename."""
        content = create_test_content(sample_pdf_file2, "Test complex PDF")
        content_cleanup(content)

        # Basic assertions
        self.assert_content_basic_fields(content, "CRF1100-A-A2-A4-D2-D4-20YM-.pdf")

        # PDF-specific assertions
        assert content.mimetype == "application/pdf"

    @pytest.mark.parametrize(
        "file_fixture,expected_filename,expected_mimetype_prefix",
        [
            ("sample_heic_file", "IMG_6584.HEIC", "image/"),
            ("sample_mp4_file", "mutanen-kohta.mp4", "video/"),
            ("sample_mp3_file", "Pohjois-Karjala.mp3", "audio/"),
            ("sample_pdf_file", "test_pdf.pdf", "application/pdf"),
        ],
    )
    def test_content_creation_parametrized(
        self, request, file_fixture, expected_filename, expected_mimetype_prefix, content_cleanup, create_test_content
    ):
        """Parametrized test for content creation from different file types."""
        file_path = request.getfixturevalue(file_fixture)
        content = create_test_content(file_path, f"Test {expected_filename}")
        content_cleanup(content)

        self.assert_content_basic_fields(content, expected_filename)

        if expected_mimetype_prefix.endswith("/"):
            assert content.mimetype.startswith(expected_mimetype_prefix)
        else:
            assert content.mimetype == expected_mimetype_prefix

    def test_content_file_storage(self, sample_heic_file, content_cleanup, create_test_content):
        """Test that Content files are stored correctly in the file system."""
        content = create_test_content(sample_heic_file, "Storage test")
        content_cleanup(content)

        # File should exist in storage
        assert content.file.storage.exists(content.file.name)

        # File size should match
        stored_size = content.file.storage.size(content.file.name)
        assert stored_size == content.file_size
        assert stored_size > 0

    def test_content_sha1_consistency(self, sample_pdf_file, content_cleanup, create_test_content):
        """Test that SHA1 hash is calculated consistently."""
        # Create two Content objects from same file
        content1 = create_test_content(sample_pdf_file, "SHA1 test 1")
        content2 = create_test_content(sample_pdf_file, "SHA1 test 2")

        content_cleanup(content1)
        content_cleanup(content2)

        # SHA1 should be identical for same file
        assert content1.sha1 == content2.sha1
        assert len(content1.sha1) == 40  # SHA1 hex length

        # But Content objects should be different
        assert content1.id != content2.id

    def test_content_with_invalid_file_path(self, content_cleanup):
        """Test that FileNotFoundError is raised for short strings that look like file paths."""
        test_data = "This is test data, not a file path"  # Short string, treated as file path

        content = Content(caption="Invalid file path test")

        # Should raise FileNotFoundError when trying to set a non-existent file
        with pytest.raises(FileNotFoundError, match="File not found: This is test data, not a file path"):
            content.set_file("test_data.txt", test_data)

        # Content should not be saved to cleanup since set_file failed
        # content_cleanup(content)  # Not needed since set_file failed

    def test_content_with_long_string_data(self, content_cleanup):
        """Test Content creation with long string data that gets treated as file content."""
        # Make test data longer than FILE_PATH_CHECK_THRESHOLD (1000 chars)
        # so it's treated as file content, not a file path
        test_data = "This is actual file content data. " * 30  # ~1050 chars

        content = Content(caption="Long string data test")
        content.set_file("test_data.txt", test_data)
        content_cleanup(content)

        # The string becomes the content, so file size equals string length
        assert content.file_size == len(test_data)
        assert content.original_filename == "test_data.txt"

        # Should be able to set fileinfo without errors
        content.set_fileinfo()

        # MIME type should be detected from content
        assert content.mimetype is not None

    def test_content_mimetype_detection(self, sample_heic_file, content_cleanup):
        """Test that MIME type is detected correctly."""
        content = Content(caption="MIME test")
        content.set_file(sample_heic_file.name, str(sample_heic_file))

        content_cleanup(content)

        # HEIC files should be detected as image
        assert content.mimetype.startswith("image/")
        # Specific HEIC MIME type might vary by system
        assert "heic" in content.mimetype.lower() or "heif" in content.mimetype.lower()
