"""Pytest configuration file for Shaka Packager MCP server tests."""

import os
import sys
from pathlib import Path

import pytest

# Add parent directory to path so we can import the server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


@pytest.fixture
def test_video_path():
    """Provide a path to a test video file."""
    return str(Path(__file__).parent / "fixtures" / "test_video.mp4")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    import tempfile

    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)

    # Clean up
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)
