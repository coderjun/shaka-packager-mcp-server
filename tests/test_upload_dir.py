"""
Tests for the upload directory and cleanup() when TEMP_DIR is set.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import shaka_packager_mcp


class TestUploadDir(unittest.TestCase):
    """TEMP_DIR is a parent location only. cleanup() removes just the server's subdirectory."""

    def setUp(self):
        # Stand-in for a user-set TEMP_DIR that already exists and holds the user's files
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.sentinel = self.temp_dir / "keep-me.txt"
        self.sentinel.write_text("user data")

        self.upload_dir = shaka_packager_mcp.create_upload_dir(str(self.temp_dir))
        patcher = patch.object(shaka_packager_mcp, "UPLOAD_DIR", self.upload_dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_upload_dir_is_created_inside_temp_dir(self):
        self.assertEqual(self.upload_dir.parent, self.temp_dir)
        self.assertTrue(self.upload_dir.name.startswith("shaka-mcp-"))
        self.assertTrue(self.upload_dir.is_dir())

        saved = shaka_packager_mcp.save_uploaded_file(b"video", "video.mp4")
        self.assertEqual(saved.parent, self.upload_dir)

    def test_cleanup_keeps_temp_dir_and_its_files(self):
        shaka_packager_mcp.save_uploaded_file(b"video", "video.mp4")

        shaka_packager_mcp.cleanup()

        self.assertTrue(self.temp_dir.is_dir())
        self.assertEqual(self.sentinel.read_text(), "user data")

    def test_cleanup_removes_upload_dir(self):
        saved = shaka_packager_mcp.save_uploaded_file(b"video", "video.mp4")

        shaka_packager_mcp.cleanup()

        self.assertFalse(saved.exists())
        self.assertFalse(self.upload_dir.exists())


if __name__ == "__main__":
    unittest.main()
