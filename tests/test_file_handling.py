"""
Tests for file handling, error conditions, and edge cases.

Tests various file handling scenarios including error conditions,
unsupported file types, and edge cases.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from content.models import Content

from .conftest import ContentTestMixin


@pytest.mark.django_db
class TestFileHandling(ContentTestMixin):
    """Test file handling and error conditions."""

    def test_unsupported_file_type_handling(self, content_cleanup, temp_uploaded_file):
        """Test handling of unsupported file types."""
        # Create a simple text file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is a test text file.")
            temp_path = Path(f.name)

        try:
            content = Content(caption="Unsupported file test")
            content.set_file(temp_path.name, str(temp_path))
            content.set_fileinfo()
            content.save()

            content_cleanup(content)

            # Should have basic file properties
            self.assert_content_basic_fields(content, temp_path.name)

            # MIME type should be text/plain
            assert content.mimetype == "text/plain"

            # Should NOT have image/video/audio objects
            assert not hasattr(content, "image") or content.image is None
            assert not hasattr(content, "video") or content.video is None
            assert not hasattr(content, "audio") or content.audio is None

            # Should NOT generate thumbnail
            content.generate_thumbnail()
            self.assert_no_thumbnail(content)

        finally:
            temp_path.unlink(missing_ok=True)

    def test_empty_file_handling(self, content_cleanup):
        """Test handling of empty files."""
        # Create empty file
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_path = Path(f.name)

        try:
            content = Content(caption="Empty file test")
            content.set_file(temp_path.name, str(temp_path))
            content.set_fileinfo()
            content.save()

            content_cleanup(content)

            # Should have basic properties
            assert content.original_filename == temp_path.name
            assert content.file_size == 0
            assert content.mimetype is not None

        finally:
            temp_path.unlink(missing_ok=True)

    def test_very_large_filename_handling(self, sample_pdf_file, content_cleanup):
        """Test handling of files with very long names."""
        # Create a very long filename
        long_name = "a" * 200 + ".pdf"

        content = Content(caption="Long filename test")
        content.set_file(long_name, str(sample_pdf_file))
        content.set_fileinfo()
        content.save()

        content_cleanup(content)

        # Should handle long filename gracefully
        assert content.original_filename == long_name
        self.assert_content_basic_fields(content, long_name)

    def test_special_characters_in_filename(self, sample_pdf_file, content_cleanup):
        """Test handling of filenames with special characters."""
        special_name = "test_file_åäö_!@#$%^&()_+.pdf"

        content = Content(caption="Special chars test")
        content.set_file(special_name, str(sample_pdf_file))
        content.set_fileinfo()
        content.save()

        content_cleanup(content)

        # Should handle special characters
        assert content.original_filename == special_name
        self.assert_content_basic_fields(content, special_name)

    def test_duplicate_content_creation(self, sample_heic_file, content_cleanup, create_test_content):
        """Test creating multiple Content objects from the same file."""
        content1 = create_test_content(sample_heic_file, "Duplicate test 1")
        content2 = create_test_content(sample_heic_file, "Duplicate test 2")

        content_cleanup(content1)
        content_cleanup(content2)

        # Both should be valid but separate objects
        assert content1.id != content2.id
        assert content1.sha1 == content2.sha1  # Same file, same hash
        assert content1.file_size == content2.file_size
        assert content1.mimetype == content2.mimetype

    def test_corrupted_image_handling(self, content_cleanup):
        """Test handling of corrupted image files."""
        # Create a fake image file (just text with image extension)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jpg", delete=False) as f:
            f.write("This is not a real image file.")
            temp_path = Path(f.name)

        try:
            content = Content(caption="Corrupted image test")
            content.set_file(temp_path.name, str(temp_path))
            content.set_fileinfo()
            content.save()

            content_cleanup(content)

            # Should create Content object
            self.assert_content_basic_fields(content, temp_path.name)

            # MIME type should be detected as text, not image
            assert not content.mimetype.startswith("image/")

            # Thumbnail generation should not crash
            content.generate_thumbnail()
            self.assert_no_thumbnail(content)

        finally:
            temp_path.unlink(missing_ok=True)

    @patch("content.filetools.FFProbe")
    def test_ffprobe_failure_handling(self, mock_ffprobe, sample_mp4_file, content_cleanup):
        """Test handling when FFProbe fails."""
        # Mock FFProbe to raise exception
        mock_ffprobe.side_effect = Exception("FFProbe failed")

        content = Content(caption="FFProbe failure test")
        content.set_file(sample_mp4_file.name, str(sample_mp4_file))

        # Should not crash even if FFProbe fails
        content.set_fileinfo()

        # Should handle gracefully without crashing
        content.save()
        content_cleanup(content)

    def test_thumbnail_generation_failure_handling(self, sample_heic_file, content_cleanup, create_test_content):
        """Test handling when thumbnail generation fails."""
        content = create_test_content(sample_heic_file, "Thumbnail failure test")
        content_cleanup(content)

        # Mock PIL.Image.open to fail
        with patch("PIL.Image.open", side_effect=Exception("PIL failed")):
            # Should not crash
            content.generate_thumbnail()

            # Should gracefully handle failure
            # (might or might not have thumbnail depending on implementation)

    def test_storage_permission_error_handling(self, sample_pdf_file, content_cleanup):
        """Test handling of storage permission errors."""
        content = Content(caption="Permission error test")

        # Mock storage to raise permission error
        with patch.object(content.file.storage, "save", side_effect=PermissionError("No permission")):
            with pytest.raises(PermissionError):
                content.set_file(sample_pdf_file.name, str(sample_pdf_file))

    def test_file_deletion_during_processing(self, content_cleanup):
        """Test handling when source file is deleted during processing."""
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Temporary content")
            temp_path = Path(f.name)

        content = Content(caption="File deletion test")

        # Delete the file before processing
        temp_path.unlink()

        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            content.set_file(temp_path.name, str(temp_path))

    def test_content_with_django_uploaded_file(self, sample_pdf_file, content_cleanup, temp_uploaded_file):
        """Test Content creation with Django UploadedFile."""
        uploaded_file = temp_uploaded_file(sample_pdf_file, "application/pdf")

        content = Content(caption="Uploaded file test")
        content.set_file(uploaded_file.name, uploaded_file)
        content.set_fileinfo()
        content.save()

        content_cleanup(content)

        # Should work the same as with file path
        self.assert_content_basic_fields(content, uploaded_file.name)
        assert content.mimetype == "application/pdf"

    def test_concurrent_content_creation(self, sample_heic_file, content_cleanup):
        """Test creating multiple Content objects concurrently."""
        import threading

        results = []
        errors = []

        def create_content(index):
            try:
                content = Content(caption=f"Concurrent test {index}")
                content.set_file(f"test_{index}_{sample_heic_file.name}", str(sample_heic_file))
                content.set_fileinfo()
                content.save()
                results.append(content)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_content, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Cleanup all created content
        for content in results:
            content_cleanup(content)

        # Should not have errors
        assert len(errors) == 0, f"Concurrent creation errors: {errors}"
        assert len(results) == 5, f"Expected 5 content objects, got {len(results)}"

        # All should have different IDs but same SHA1
        ids = [c.id for c in results]
        assert len(set(ids)) == 5  # All unique IDs

        sha1s = [c.sha1 for c in results]
        assert len(set(sha1s)) == 1  # All same SHA1

    def test_file_size_limits(self, content_cleanup):
        """Test handling of very small and reasonably large files."""
        # Test very small file (1 byte)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("x")
            small_file = Path(f.name)

        try:
            content = Content(caption="Small file test")
            content.set_file(small_file.name, str(small_file))
            content.set_fileinfo()
            content.save()

            content_cleanup(content)

            assert content.file_size == 1
            self.assert_content_basic_fields(content, small_file.name)

        finally:
            small_file.unlink(missing_ok=True)
