"""
Pytest configuration and fixtures for content tests.
"""

from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from content.models import Content, content_storage, preview_storage


# Test file paths
TEST_FILES_DIR = Path(__file__).parent / "testfiles"
HEIC_FILE = TEST_FILES_DIR / "IMG_6584.HEIC"
MP4_FILE = TEST_FILES_DIR / "mutanen-kohta.mp4"
MP3_FILE = TEST_FILES_DIR / "Pohjois-Karjala.mp3"
PDF_FILE = TEST_FILES_DIR / "test_pdf.pdf"
PDF_FILE2 = TEST_FILES_DIR / "CRF1100-A-A2-A4-D2-D4-20YM-.pdf"
IPTC_JPG_FILE = TEST_FILES_DIR / "iptc-hamburger.jpg"


@pytest.fixture
def test_files_dir():
    """Path to test files directory."""
    return TEST_FILES_DIR


@pytest.fixture
def sample_heic_file():
    """Path to sample HEIC image file."""
    if not HEIC_FILE.exists():
        pytest.skip(f"Test file {HEIC_FILE} not found")
    return HEIC_FILE


@pytest.fixture
def sample_mp4_file():
    """Path to sample MP4 video file."""
    if not MP4_FILE.exists():
        pytest.skip(f"Test file {MP4_FILE} not found")
    return MP4_FILE


@pytest.fixture
def sample_mp3_file():
    """Path to sample MP3 audio file."""
    if not MP3_FILE.exists():
        pytest.skip(f"Test file {MP3_FILE} not found")
    return MP3_FILE


@pytest.fixture
def sample_pdf_file():
    """Path to sample PDF file."""
    if not PDF_FILE.exists():
        pytest.skip(f"Test file {PDF_FILE} not found")
    return PDF_FILE


@pytest.fixture
def sample_pdf_file2():
    """Path to second sample PDF file."""
    if not PDF_FILE2.exists():
        pytest.skip(f"Test file {PDF_FILE2} not found")
    return PDF_FILE2


@pytest.fixture
def sample_iptc_jpg_file():
    """Path to sample JPEG image file with IPTC metadata."""
    if not IPTC_JPG_FILE.exists():
        pytest.skip(f"Test file {IPTC_JPG_FILE} not found")
    return IPTC_JPG_FILE


@pytest.fixture
def temp_uploaded_file():
    """Create a temporary uploaded file for testing."""

    def _create_uploaded_file(file_path: Path, content_type: str = None):
        """Create SimpleUploadedFile from a real file."""
        with open(file_path, "rb") as f:
            content = f.read()
        return SimpleUploadedFile(name=file_path.name, content=content, content_type=content_type)

    return _create_uploaded_file


@pytest.fixture
def content_cleanup():
    """Fixture to track and cleanup created Content objects."""
    created_content = []

    def track_content(content_obj):
        """Add content object to cleanup list."""
        created_content.append(content_obj)
        return content_obj

    yield track_content

    # Cleanup after test
    for content in created_content:
        try:
            # Remove files from storage
            try:
                if content.file:
                    content_storage.delete(content.file.name)
            except Exception as e:
                print(f"Warning: Failed to delete content file for {content.id}: {e}")

            try:
                if content.preview:
                    preview_storage.delete(content.preview.name)
            except Exception as e:
                print(f"Warning: Failed to delete preview file for {content.id}: {e}")

            # Remove related instances
            try:
                if hasattr(content, "video") and content.video:
                    if content.video.thumbnail and content.video.thumbnail.name:
                        # Use storage.delete instead of field.delete to avoid _file attribute error
                        preview_storage.delete(content.video.thumbnail.name)
            except Exception as e:
                print(f"Warning: Failed to delete video thumbnail for {content.id}: {e}")

            try:
                if hasattr(content, "audio") and content.audio:
                    # Audio model doesn't have file field, only content.file
                    pass
            except Exception as e:
                print(f"Warning: Failed to handle audio cleanup for {content.id}: {e}")

            try:
                if hasattr(content, "image") and content.image:
                    if content.image.thumbnail and content.image.thumbnail.name:
                        # Use storage.delete instead of field.delete to avoid _file attribute error
                        preview_storage.delete(content.image.thumbnail.name)
            except Exception as e:
                print(f"Warning: Failed to delete image thumbnail for {content.id}: {e}")

            # Delete the content object
            try:
                content.delete()
            except Exception as e:
                print(f"Warning: Failed to delete content object {content.id}: {e}")

        except Exception as e:
            # Log error but don't fail test cleanup
            print(f"Warning: Failed to cleanup content {content.id}: {e}")


@pytest.fixture
def create_test_content():
    """Factory fixture for creating test Content objects."""

    def _create_content(file_path: Path, caption: str = "Test content"):
        """Create Content object from file path."""
        content = Content(caption=caption)
        content.set_file(file_path.name, str(file_path))
        content.set_fileinfo()
        content.save()
        return content

    return _create_content


class ContentTestMixin:
    """Mixin class with common test utilities for Content testing."""

    def assert_content_basic_fields(self, content: Content, expected_filename: str):
        """Assert basic Content fields are set correctly."""
        assert content.original_filename == expected_filename
        assert content.file_size > 0
        assert content.mimetype is not None
        assert content.sha1 is not None
        assert len(content.sha1) == 40  # SHA1 hex length
        assert content.file is not None

    def assert_thumbnail_exists(self, content: Content):
        """Assert that content has a valid thumbnail."""
        assert content.preview is not None
        assert content.preview.name
        # Check that thumbnail file actually exists
        assert preview_storage.exists(content.preview.name)

    def assert_no_thumbnail(self, content: Content):
        """Assert that content has no thumbnail."""
        assert content.preview is None or not content.preview.name
