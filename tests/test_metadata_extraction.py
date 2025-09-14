"""
Tests for metadata extraction from different file types.

Tests that metadata (EXIF, video info, audio info) is extracted correctly
from various file formats.
"""

from datetime import datetime

import pytest

from content.filetools import FFProbe
from content.models import Content

from .conftest import ContentTestMixin


@pytest.mark.django_db
class TestMetadataExtraction(ContentTestMixin):
    """Test metadata extraction from different file types."""

    def test_heic_image_metadata(self, sample_heic_file, content_cleanup, create_test_content):
        """Test EXIF metadata extraction from HEIC image."""
        content = create_test_content(sample_heic_file, "HEIC metadata test")
        content_cleanup(content)

        # Should have image metadata
        assert hasattr(content, "image")
        assert content.image is not None

        # Basic image properties
        assert content.image.width > 0
        assert content.image.height > 0

        # EXIF data might be available
        # Check if EXIF data is available through the filetools
        from content.filetools import get_imageinfo

        image_info = get_imageinfo(str(sample_heic_file))
        if "exif" in image_info and image_info["exif"]:
            # EXIF data should be available
            assert image_info["exif"] is not None

    def test_mp4_video_metadata(self, sample_mp4_file, content_cleanup, create_test_content):
        """Test video metadata extraction from MP4 file."""
        content = create_test_content(sample_mp4_file, "MP4 metadata test")
        content_cleanup(content)

        # Should have video metadata
        assert hasattr(content, "video")
        assert content.video is not None

        # Basic video properties
        assert content.video.width > 0
        assert content.video.height > 0
        assert content.video.duration > 0

        # Video should have reasonable dimensions
        assert 100 <= content.video.width <= 10000
        assert 100 <= content.video.height <= 10000

        # Duration should be reasonable (not negative, not extremely long)
        assert 0.1 <= content.video.duration <= 86400  # Max 24 hours

    def test_mp3_audio_metadata(self, sample_mp3_file, content_cleanup, create_test_content):
        """Test audio metadata extraction from MP3 file."""
        content = create_test_content(sample_mp3_file, "MP3 metadata test")
        content_cleanup(content)

        # Should have audio metadata
        assert hasattr(content, "audio")
        assert content.audio is not None

        # Basic audio properties
        assert content.audio.duration > 0

        # Duration should be reasonable
        assert 0.1 <= content.audio.duration <= 86400  # Max 24 hours

    def test_ffprobe_video_detection(self, sample_mp4_file):
        """Test FFProbe correctly identifies video files."""
        ffp = FFProbe(str(sample_mp4_file))

        assert ffp.is_video() is True
        assert ffp.is_audio() is False

        # Should have video info
        video_info = ffp.get_videoinfo()
        assert video_info is not None
        assert "width" in video_info
        assert "height" in video_info
        assert "duration" in video_info

    def test_ffprobe_audio_detection(self, sample_mp3_file):
        """Test FFProbe correctly identifies audio files."""
        ffp = FFProbe(str(sample_mp3_file))

        assert ffp.is_audio() is True
        assert ffp.is_video() is False

        # Should have audio info
        audio_info = ffp.get_audioinfo()
        assert audio_info is not None
        assert "duration" in audio_info

    def test_pdf_file_properties(self, sample_pdf_file, content_cleanup, create_test_content):
        """Test PDF file properties are set correctly."""
        content = create_test_content(sample_pdf_file, "PDF properties test")
        content_cleanup(content)

        # PDF should have correct MIME type
        assert content.mimetype == "application/pdf"

        # File size should be reasonable
        assert content.file_size > 100  # PDFs are typically larger than 100 bytes

    def test_file_timestamp_extraction(self, sample_heic_file, content_cleanup, create_test_content):
        """Test that file timestamps are extracted when available."""
        content = create_test_content(sample_heic_file, "Timestamp test")
        content_cleanup(content)

        # HEIC files often have creation time in EXIF
        if hasattr(content, "image") and content.image:
            # filetime might be set from EXIF data
            if content.filetime:
                assert isinstance(content.filetime, datetime)
                # Should be a reasonable date (not in future, not too old)
                assert content.filetime.year >= 2000
                # Make datetime.now() timezone-aware for comparison
                now = datetime.now(content.filetime.tzinfo) if content.filetime.tzinfo else datetime.now()
                assert content.filetime <= now

    def test_sha1_hash_calculation(self, sample_pdf_file, content_cleanup, create_test_content):
        """Test that SHA1 hash is calculated correctly."""
        content = create_test_content(sample_pdf_file, "SHA1 test")
        content_cleanup(content)

        # Should have SHA1 hash
        assert content.sha1 is not None
        assert len(content.sha1) == 40  # SHA1 hex string length

        # Should be valid hex
        int(content.sha1, 16)  # Will raise ValueError if not valid hex

    def test_mimetype_consistency(self, sample_heic_file, content_cleanup):
        """Test that MIME type detection is consistent."""
        # Create content without explicit MIME type
        content1 = Content(caption="MIME test 1")
        content1.set_file(sample_heic_file.name, str(sample_heic_file))
        content1.set_fileinfo()
        content1.save()
        content_cleanup(content1)

        # Create another content from same file
        content2 = Content(caption="MIME test 2")
        content2.set_file(sample_heic_file.name, str(sample_heic_file))
        content2.set_fileinfo()
        content2.save()
        content_cleanup(content2)

        # MIME types should be identical
        assert content1.mimetype == content2.mimetype

    @pytest.mark.parametrize(
        "file_fixture,expected_type",
        [
            ("sample_heic_file", "image"),
            ("sample_mp4_file", "video"),
            ("sample_mp3_file", "audio"),
            ("sample_pdf_file", "application"),
        ],
    )
    def test_mimetype_categories(self, request, file_fixture, expected_type, content_cleanup, create_test_content):
        """Test that MIME types are categorized correctly."""
        file_path = request.getfixturevalue(file_fixture)
        content = create_test_content(file_path, f"MIME category test {expected_type}")
        content_cleanup(content)

        assert content.mimetype.startswith(f"{expected_type}/")

    def test_video_aspect_ratio(self, sample_mp4_file, content_cleanup, create_test_content):
        """Test video aspect ratio calculation."""
        content = create_test_content(sample_mp4_file, "Aspect ratio test")
        content_cleanup(content)

        if hasattr(content, "video") and content.video:
            width = content.video.width
            height = content.video.height

            # Calculate aspect ratio
            aspect_ratio = width / height

            # Should be a reasonable aspect ratio
            assert 0.1 <= aspect_ratio <= 10  # Very wide range for safety

            # Common aspect ratios are around 1.33, 1.78, etc.
            # But we'll just check it's positive and reasonable

    def test_audio_duration_accuracy(self, sample_mp3_file, content_cleanup, create_test_content):
        """Test that audio duration is reasonably accurate."""
        content = create_test_content(sample_mp3_file, "Duration accuracy test")
        content_cleanup(content)

        if hasattr(content, "audio") and content.audio:
            duration = content.audio.duration

            # Duration should be positive
            assert duration > 0

            # For MP3 files, duration should typically be more than 1 second
            # but less than an hour for test files
            assert 0.1 <= duration <= 3600

    def test_file_size_consistency(self, sample_pdf_file, content_cleanup, create_test_content):
        """Test that file size is calculated consistently."""
        content = create_test_content(sample_pdf_file, "File size test")
        content_cleanup(content)

        # File size should match actual file size
        actual_size = sample_pdf_file.stat().st_size
        assert content.file_size == actual_size

        # Stored file should have same size
        stored_size = content.file.storage.size(content.file.name)
        assert stored_size == actual_size

    def test_metadata_extraction_workflow(self, sample_mp4_file, content_cleanup):
        """Integration test for complete metadata extraction workflow."""
        # Test the complete workflow: create -> set_file -> set_fileinfo -> save
        content = Content(caption="Workflow test")

        # Step 1: Set file
        content.set_file(sample_mp4_file.name, str(sample_mp4_file))
        assert content.original_filename == sample_mp4_file.name
        assert content.file_size > 0
        assert content.mimetype.startswith("video/")
        assert content.sha1 is not None

        # Step 2: Set file info (creates Video object)
        video_obj = content.set_fileinfo()
        assert video_obj is not None
        assert hasattr(content, "video")

        # Step 3: Save
        content.save()
        content_cleanup(content)

        # Verify everything is properly set
        assert content.id is not None
        assert content.video.width > 0
        assert content.video.height > 0
        assert content.video.duration > 0

    def test_iptc_metadata_extraction(self, sample_iptc_jpg_file, content_cleanup, create_test_content):
        """Test IPTC metadata extraction from JPEG image with IPTC tags."""
        content = create_test_content(sample_iptc_jpg_file, "IPTC metadata test")
        content_cleanup(content)

        # Should have image metadata
        assert hasattr(content, "image")
        assert content.image is not None

        # Basic image properties
        assert content.image.width > 0
        assert content.image.height > 0

        # Test IPTC metadata extraction using get_imageinfo directly
        from content.filetools import get_imageinfo

        image_info = get_imageinfo(str(sample_iptc_jpg_file))

        # Test IPTC Caption/Abstract (tag 2:120)
        assert "caption" in image_info
        assert image_info["caption"] == "A tasty hamburger in a pocket on the table"

        # Test IPTC Headline (tag 2:105)
        assert "headline" in image_info
        assert image_info["headline"] == "A hamburger on the table"

        # Test IPTC Copyright Notice (tag 2:116)
        assert "copyright" in image_info
        assert image_info["copyright"] == "aapris@gmail.com"

        # Test IPTC Keywords (tag 2:25)
        assert "keywords" in image_info
        assert "tags" in image_info
        assert image_info["keywords"] == "hamburger,food"
        assert image_info["tags"] == ["hamburger", "food"]

        # Verify keywords are properly parsed as list
        assert isinstance(image_info["tags"], list)
        assert len(image_info["tags"]) == 2
        assert "hamburger" in image_info["tags"]
        assert "food" in image_info["tags"]

    def test_gps_data_validation(self, sample_iptc_jpg_file, content_cleanup, create_test_content):
        """Test that GPS data from IPTC image looks reasonable."""
        content = create_test_content(sample_iptc_jpg_file, "GPS validation test")
        content_cleanup(content)

        from content.filetools import get_imageinfo

        image_info = get_imageinfo(str(sample_iptc_jpg_file))

        # Should have GPS data
        assert "gps" in image_info
        assert "lat" in image_info
        assert "lon" in image_info

        gps_data = image_info["gps"]
        lat = image_info["lat"]
        lon = image_info["lon"]

        # Verify GPS coordinates are reasonable (Helsinki area)
        # Latitude should be around 60.2 (Helsinki is ~60.17°N)
        assert 59.0 <= lat <= 61.0, f"Latitude {lat} seems unreasonable for Helsinki area"

        # Longitude should be around 24.9 (Helsinki is ~24.95°E)
        assert 23.0 <= lon <= 26.0, f"Longitude {lon} seems unreasonable for Helsinki area"

        # GPS data should have lat/lon in the GPS dict too
        assert "lat" in gps_data
        assert "lon" in gps_data
        assert gps_data["lat"] == lat
        assert gps_data["lon"] == lon

        # Check altitude if present
        if "altitude" in gps_data:
            altitude = gps_data["altitude"]
            # Helsinki altitude should be reasonable (sea level to ~100m)
            assert -10 <= altitude <= 200, f"Altitude {altitude}m seems unreasonable for Helsinki area"

        # Check GPS timestamp if present
        if "gpstime" in gps_data:
            from datetime import datetime

            gps_time = gps_data["gpstime"]
            assert isinstance(gps_time, (str, datetime))

        # Check direction if present
        if "direction" in gps_data:
            direction = gps_data["direction"]
            assert 0 <= direction <= 360, f"Direction {direction} should be between 0-360 degrees"
