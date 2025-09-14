# Django-Content Test Suite

This directory contains comprehensive tests for the Django Content app, covering file handling, metadata extraction, and thumbnail generation for various file types.

## Test Structure

- `conftest.py` - Pytest configuration and shared fixtures
- `test_content_creation.py` - Tests for Content object creation from different file types
- `test_thumbnail_generation.py` - Tests for thumbnail/preview generation
- `test_metadata_extraction.py` - Tests for EXIF, video, and audio metadata extraction
- `test_file_handling.py` - Tests for error handling and edge cases

## Running Tests

### Using pytest (recommended)
```bash
# Activate virtual environment and set Django settings
cd /path/to/homepage-of-things
source venv/bin/activate
cd django_server

# Run all content tests
DJANGO_SETTINGS_MODULE=config.settings python -m pytest content/tests

# Run specific test file
DJANGO_SETTINGS_MODULE=config.settings pytest content/tests/test_content_creation.py

# Run tests with specific markers
DJANGO_SETTINGS_MODULE=config.settings pytest content/tests/ -m thumbnail
DJANGO_SETTINGS_MODULE=config.settings pytest content/tests/ -m metadata
DJANGO_SETTINGS_MODULE=config.settings pytest content/tests/ -m "not slow"

# Run with verbose output
DJANGO_SETTINGS_MODULE=config.settings pytest content/tests/ -v

# Run specific test
DJANGO_SETTINGS_MODULE=config.settings pytest content/tests/test_content_creation.py::TestContentCreation::test_create_content_from_heic_image

# Using the convenience script
./run_tests.sh content/tests/
```

### Using Django test runner (legacy)
```bash
# Run all content tests
python manage.py test content

# Run specific test file
python manage.py test content.tests.test_content_creation

# Run single test method
python manage.py test content.tests.test_filetools.FiletoolsTestCase.testVideoFromTestContentDir
```

## Test Files

The `testfiles/` directory contains sample files for testing:
- `IMG_6584.HEIC` - HEIC image file
- `mutanen-kohta.mp4` - MP4 video file
- `Pohjois-Karjala.mp3` - MP3 audio file
- `test_pdf.pdf` - PDF document
- `CRF1100-A-A2-A4-D2-D4-20YM-.pdf` - PDF with complex filename

## Test Coverage

The tests cover:
- ✅ Image files (HEIC, JPG, PNG, GIF, WebP)
- ✅ Video files (MP4, MOV)
- ✅ Audio files (MP3, OGG)
- ✅ Document files (PDF)
- ✅ Unsupported file types
- ✅ Thumbnail generation for supported formats
- ✅ Metadata extraction (EXIF, video info, audio info)
- ✅ Error handling and edge cases
- ✅ File storage and cleanup

## Test Status

✅ **All Tests Passing**: All tests in the content test suite now pass successfully.

**Test Files:**
- ✅ `test_content_creation.py` - Content object creation tests
- ✅ `test_metadata_extraction.py` - Metadata extraction tests
- ✅ `test_file_handling.py` - File handling and error tests
- ✅ `test_thumbnail_generation.py` - Thumbnail generation tests

## Markers

- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.thumbnail` - Thumbnail generation tests
- `@pytest.mark.metadata` - Metadata extraction tests

## Troubleshooting

### Django Settings Error
If you get "ImproperlyConfigured" errors, make sure to set the Django settings module:
```bash
export DJANGO_SETTINGS_MODULE=config.settings
# or use it inline
DJANGO_SETTINGS_MODULE=config.settings pytest content/tests/
```

### Missing Dependencies
Install required packages:
```bash
source venv/bin/activate
uv pip install pytest pytest-django
```
