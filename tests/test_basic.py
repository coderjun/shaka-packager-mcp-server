"""
Basic tests for the Shaka Packager MCP server.
"""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path so we can import the server module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the server module
import shaka_packager_mcp


class TestShakaPackagerMCP(unittest.TestCase):
    """Basic tests for the Shaka Packager MCP server."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock Context
        self.ctx = MagicMock()
        self.ctx.read_resource = AsyncMock(return_value=(b"test_data", "video/mp4"))
        self.ctx.info = MagicMock()
        self.ctx.warning = MagicMock()
        self.ctx.error = MagicMock()

    @patch("shaka_packager_mcp.run_command")
    @patch("shaka_packager_mcp.save_uploaded_file")
    async def test_analyze_video(self, mock_save, mock_run_command):
        """Test analyze_video tool."""
        # Set up mocks
        mock_save.return_value = Path("/tmp/test.mp4")
        mock_run_command.return_value = {
            "command": "packager --dump_stream_info /tmp/test.mp4",
            "stdout": "Test stream info output",
            "stderr": "",
            "exit_code": 0,
            "execution_time": 1.5,
        }

        # Call the function
        result = await shaka_packager_mcp.analyze_video(self.ctx, "file:///test.mp4")

        # Check the result
        self.assertIn("Test stream info output", result)
        self.assertIn("Execution time: 1.5", result)

        # Verify mocks were called
        self.ctx.read_resource.assert_called_once_with("file:///test.mp4")
        mock_save.assert_called_once()
        mock_run_command.assert_called_once()

    @patch("shaka_packager_mcp.run_command")
    @patch("shaka_packager_mcp.save_uploaded_file")
    async def test_run_shaka_packager(self, mock_save, mock_run_command):
        """Test run_shaka_packager tool."""
        # Set up mocks
        mock_save.return_value = Path("/tmp/test.mp4")
        mock_run_command.return_value = {
            "command": "packager --test_flag /tmp/test.mp4",
            "stdout": "Test command output",
            "stderr": "",
            "exit_code": 0,
            "execution_time": 2.5,
        }

        # Call the function
        result = await shaka_packager_mcp.run_shaka_packager(
            self.ctx, "file:///test.mp4", "--test_flag {input}"
        )

        # Check the result
        self.assertIn("Test command output", result)
        self.assertIn("Execution time: 2.5", result)

        # Verify mocks were called
        self.ctx.read_resource.assert_called_once_with("file:///test.mp4")
        mock_save.assert_called_once()
        mock_run_command.assert_called_once()

    @patch("shaka_packager_mcp.run_command")
    async def test_get_shaka_options(self, mock_run_command):
        """Test get_shaka_options tool."""
        # Set up mocks
        # First call is for --help, second for --version
        mock_run_command.side_effect = [
            {
                "command": "packager --help",
                "stdout": "Help text here",
                "stderr": "",
                "exit_code": 0,
                "execution_time": 0.5,
            },
            {
                "command": "packager --version",
                "stdout": "Shaka Packager version 2.6.0",
                "stderr": "",
                "exit_code": 0,
                "execution_time": 0.5,
            },
        ]

        # Call the function
        result = await shaka_packager_mcp.get_shaka_options(self.ctx)

        # Check the result
        self.assertIn("Help text here", result)
        self.assertIn("Shaka Packager version 2.6.0", result)

        # Verify mocks were called
        self.assertEqual(mock_run_command.call_count, 2)


def run_async_test(coro):
    """Run an async test function."""
    return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
