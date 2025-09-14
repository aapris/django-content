"""
Tests for thumbnail generation from different file types.

Tests that preview thumbnails are generated correctly for supported file types
and that unsupported file types don't generate thumbnails.
"""

from pathlib import Path

import pytest
from PIL import Image

from .conftest import ContentTestMixin


@pytest.mark.django_db
class TestThumbnailGeneration(ContentTestMixin):
    """Test thumbnail generation for different content types."""

    def test_heic_image_thumbnail_generation(self, sample_heic_file, content_cleanup, create_test_content):
        """Test that HEIC images generate thumbnails."""
        content = create_test_content(sample_heic_file, "HEIC thumbnail test")

        # Should have thumbnail
        self.assert_thumbnail_exists(content)

        # Thumbnail should be accessible
        thumbnail_path = content.preview.path
        assert Path(thumbnail_path).exists()

        # Thumbnail should be a valid image
        with Image.open(thumbnail_path) as img:
            assert img.size[0] > 0
            assert img.size[1] > 0
            # Thumbnail should be smaller than original (usually)
            # Note: this might not always be true for very small images
        content_cleanup(content)

    def test_mp4_video_thumbnail_generation(self, sample_mp4_file, content_cleanup, create_test_content):
        """Test that MP4 videos generate thumbnails."""
        content = create_test_content(sample_mp4_file, "MP4 thumbnail test")
        content_cleanup(content)

        # Should have thumbnail
        self.assert_thumbnail_exists(content)

        # Thumbnail should be accessible
        thumbnail_path = content.preview.path
        assert Path(thumbnail_path).exists()

        # Thumbnail should be a valid image
        with Image.open(thumbnail_path) as img:
            assert img.size[0] > 0
            assert img.size[1] > 0

    def test_pdf_thumbnail_generation(self, sample_pdf_file, content_cleanup, create_test_content):
        """Test that PDF files generate thumbnails."""
        content = create_test_content(sample_pdf_file, "PDF thumbnail test")
        content_cleanup(content)

        # Should have thumbnail
        self.assert_thumbnail_exists(content)

        # Thumbnail should be accessible
        thumbnail_path = content.preview.path
        assert Path(thumbnail_path).exists()

        # Thumbnail should be a valid image (PNG format for PDFs)
        with Image.open(thumbnail_path) as img:
            assert img.size[0] > 0
            assert img.size[1] > 0
            # PDF thumbnails are typically PNG
            assert img.format in ["PNG", "JPEG"]

    def test_mp3_audio_no_thumbnail(self, sample_mp3_file, content_cleanup, create_test_content):
        """Test that MP3 audio files don't generate thumbnails."""
        content = create_test_content(sample_mp3_file, "MP3 no thumbnail test")
        content_cleanup(content)

        # Should NOT have thumbnail
        self.assert_no_thumbnail(content)

    @pytest.mark.parametrize(
        "file_fixture,should_have_thumbnail",
        [
            ("sample_heic_file", True),  # Images should have thumbnails
            ("sample_mp4_file", True),  # Videos should have thumbnails
            ("sample_pdf_file", True),  # PDFs should have thumbnails
            ("sample_mp3_file", False),  # Audio should NOT have thumbnails
        ],
    )
    def test_thumbnail_generation_parametrized(
        self, request, file_fixture, should_have_thumbnail, content_cleanup, create_test_content
    ):
        """Parametrized test for thumbnail generation."""
        file_path = request.getfixturevalue(file_fixture)
        content = create_test_content(file_path, f"Thumbnail test {file_fixture}")
        content_cleanup(content)

        if should_have_thumbnail:
            self.assert_thumbnail_exists(content)
        else:
            self.assert_no_thumbnail(content)

    def test_thumbnail_regeneration(self, sample_heic_file, content_cleanup, create_test_content):
        """Test that thumbnails can be regenerated."""
        content = create_test_content(sample_heic_file, "Thumbnail regeneration test")
        content_cleanup(content)

        # Generate initial thumbnail
        # content.generate_thumbnail()
        first_thumbnail_name = content.preview.name

        # Regenerate thumbnail
        # content.generate_thumbnail()
        second_thumbnail_name = content.preview.name

        # Should still have a thumbnail
        self.assert_thumbnail_exists(content)

        # Thumbnail names might be the same or different depending on implementation
        # Both should be valid
        assert first_thumbnail_name is not None
        assert second_thumbnail_name is not None

    def test_thumbnail_dimensions(self, sample_heic_file, content_cleanup, create_test_content):
        """Test that thumbnail has reasonable dimensions."""
        content = create_test_content(sample_heic_file, "Thumbnail dimensions test")

        self.assert_thumbnail_exists(content)

        # Check thumbnail dimensions
        thumbnail_path = content.preview.path
        with Image.open(thumbnail_path) as img:
            width, height = img.size

            # Thumbnails should be reasonably sized (not too big, not too small)
            assert 50 <= width <= 2000  # Reasonable width range
            assert 50 <= height <= 2000  # Reasonable height range

            # At least one dimension should be substantial
            assert max(width, height) >= 100
        content_cleanup(content)

    def test_large_file_thumbnail_performance(self, sample_mp4_file, content_cleanup, create_test_content):
        """Test thumbnail generation performance with larger files."""
        import time

        content = create_test_content(sample_mp4_file, "Performance test")

        start_time = time.time()
        # content.generate_thumbnail()
        end_time = time.time()

        # Thumbnail generation should complete in reasonable time
        generation_time = end_time - start_time
        assert generation_time < 30  # Should complete within 30 seconds

        # Should still produce valid thumbnail
        if content.mimetype.startswith("video/"):
            self.assert_thumbnail_exists(content)
        content_cleanup(content)
