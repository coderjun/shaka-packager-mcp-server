[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/coderjun-shaka-packager-mcp-server-badge.png)](https://mseep.ai/app/coderjun-shaka-packager-mcp-server)

# Shaka Packager MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Status: Alpha](https://img.shields.io/badge/Status-Alpha%20%7C%20Experimental-red)](https://github.com/coderjun/shaka-packager-mcp)

> **⚠️ EXPERIMENTAL STATUS DISCLAIMER**
> 
> This project is in early alpha stage and is highly experimental. It is not recommended for production use. It is also likely **MESSY!**
> 
> **Current limitations:**
> - You may run into inconsistent behavior
> - Advanced features (packaging, conversion, etc.) are still under active development
> - Path translation between Docker and host environments may require manual configuration
> - Expect frequent breaking changes and potential instability
>
> Please report any issues you encounter to help improve the project.

An MCP (Model Context Protocol) server that integrates [Shaka Packager](https://shaka-project.github.io/shaka-packager/) with Claude AI applications for video transcoding, packaging, and analysis.

This server works with the [Filesystem MCP Server](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) to enable Claude Desktop to access and process video files on your computer, turning Claude into a powerful assistant for media processing tasks.

## Features

- **Video Analysis**: Analyze video files to extract detailed stream information, codecs, bitrates, and more
- **Media Packaging**: Convert videos for streaming in HLS and DASH formats with support for VOD and live streaming
- **Advanced Options**: 
  - Apply DRM encryption (Widevine, PlayReady, FairPlay)
  - Configure ad insertion markers
  - Convert between formats (MP4, TS, etc.)
- **Intelligent Path Handling**: Automatically translates paths between Docker and host environments
- **Robust Error Management**: Provides meaningful error analysis with suggestions for resolution
- **Command Assistance**: Helps correctly format Shaka Packager commands for optimal results
- **Interactive Documentation**: Built-in help and examples to guide users through complex operations
- **Detailed Outputs**: Comprehensive summaries and execution details for all operations

## Prerequisites

- Python 3.10 or higher
- Shaka Packager installed and available in your PATH
  - [Download from GitHub](https://github.com/shaka-project/shaka-packager/releases)
  - Or build from source following [these instructions](https://shaka-project.github.io/shaka-packager/html/build_instructions.html)
- An MCP-compatible client (like Claude Desktop)

## Installation

### Using pip or uv (coming soon)

Install the package with pip:

```bash
pip install shaka-packager-mcp
```

Or with uv:

```bash
uv pip install shaka-packager-mcp
```

### From source (recommended)

```bash
git clone https://github.com/coderjun/shaka-packager-mcp.git
cd shaka-packager-mcp
pip install -e .
```

Or with uv:

```bash
git clone https://github.com/coderjun/shaka-packager-mcp.git
cd shaka-packager-mcp
uv pip install -e .
```

## Claude Desktop Integration

Since Claude Desktop doesn't directly support uploading video files, we'll use a two-server approach:
1. A simplified **filesystem MCP server** to access video files on your computer
2. The **Shaka Packager MCP server** to analyze and process those videos

### Step 1: Set Up the MCP Filesystem Server

Use the official MCP filesystem server to allow Claude to access your video files:

1. Install the official filesystem server with Docker:
   ```bash
   docker pull mcp/filesystem
   ```

2. Alternatively, you can build it from source following the instructions in the [Filesystem MCP Server repository](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)

### Step 2: Find the Configuration File

Locate your Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

If the file doesn't exist, create it.

### Step 3: Add Both Servers to the Configuration

Add the following configuration, making sure to use absolute paths:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--mount", "type=bind,src=/PATH/TO/VIDEOS/DIRECTORY,dst=/projects/video-drop",
        "mcp/filesystem",
        "/projects"
      ]
    },
    "shaka-packager": {
      "command": "/ABSOLUTE/PATH/TO/uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "/ABSOLUTE/PATH/TO/shaka_packager_mcp.py"
      ],
      "env": {
        "VIDEO_PATH": "/PATH/TO/VIDEOS/DIRECTORY",
        "SHAKA_PACKAGER_PATH": "/PATH/TO/PACKAGER"
      }
    }
  }
}
```

Replace:
- `/PATH/TO/VIDEOS/DIRECTORY` with the path to the directory containing your video files
- `/ABSOLUTE/PATH/TO/uv` with the full path to your uv executable
- `/ABSOLUTE/PATH/TO/shaka_packager_mcp.py` with the full path to the script file
- `/PATH/TO/PACKAGER` with the full path to your Shaka Packager executable

For example:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--mount", "type=bind,src=/Users/username/Videos,dst=/projects/video-drop",
        "mcp/filesystem",
        "/projects"
      ]
    },
    "shaka-packager": {
      "command": "/Users/username/.local/bin/uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "/Users/username/Development/shaka-packager-mcp/shaka_packager_mcp.py"
      ],
      "env": {
        "VIDEO_PATH": "/Users/username/Videos",
        "SHAKA_PACKAGER_PATH": "/Users/username/.shaka/packager"
      }
    }
  }
}
```

### Step 4: Restart Claude Desktop

After editing the configuration file, restart Claude Desktop to apply the changes.

### How to Use the Two-Server Approach

1. First, browse your video files using the simplified filesystem server:
   - Ask Claude to "List the files in my video directory"
   - Navigate to the video file you want to analyze or process

2. Once you've found your video file, use its path with the Shaka Packager tools:
   - For analysis: "Please analyze this video: /Users/username/Videos/example.mp4"
   - For processing: "Please package this video for HLS: /Users/username/Videos/example.mp4"

### Troubleshooting

If you encounter any issues:

1. Make sure both servers are properly configured with absolute paths
2. Verify that Shaka Packager is installed and accessible
3. Ensure the directory specified for the filesystem server exists and contains videos
4. Check Claude Desktop logs for errors at:
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Windows: `%APPDATA%\Claude\logs\mcp*.log`

## Usage

Once both the Filesystem MCP server and the Shaka Packager MCP server are running in Claude Desktop:

1. **Access your video files**:
   ```
   Please show me the files in my Videos directory
   ```

2. **Navigate to your video file**:
   ```
   Please show me the files in the Movies subdirectory
   ```

3. **Copy the file:// URI path of the video** you want to process

4. **Use the Shaka Packager tools with the file path**:
   ```
   Please analyze this video: file:///Users/username/Videos/my_video.mp4
   ```
   or
   ```
   Please package this video for HLS and DASH streaming: file:///Users/username/Videos/my_video.mp4
   ```

5. The server will execute the appropriate Shaka Packager command and provide a detailed summary of the results

You can also use direct file paths if you know the exact location of your video files:
```
Please analyze this video: /Users/username/Videos/my_video.mp4
```

## Tools

The server provides these tools:

1. **analyze_video**: Examines a video file and provides detailed stream information with intelligent error handling
2. **run_shaka_packager**: Executes any Shaka Packager command with custom arguments and proper path handling
3. **get_shaka_options**: Retrieves available command options and version information
4. **get_shaka_documentation**: Provides comprehensive documentation and examples for using Shaka Packager

## Prompts

The server includes these prompt templates:

- MP4 to TS conversion
- VOD packaging in HLS and DASH
- Live streaming packaging
- Content encryption
- Ad insertion preparation
- Video analysis
- Command format reminder
- Error interpretation guidance

## Configuration

The server can be configured using environment variables:

- `SHAKA_PACKAGER_PATH`: Path to the Shaka Packager executable (highly recommended for Claude Desktop)
- `VIDEO_PATH`: Path to your local video directory (used for translating paths between Docker and host)
- `DOCKER_PATH`: Docker container mount path (default: "/projects/video-drop")
- `TEMP_DIR`: Custom temporary directory for file uploads
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `COMMAND_TIMEOUT`: Timeout in seconds for Shaka Packager commands (default: 300)

You can set these in:
1. Your Claude Desktop configuration file (preferred for `SHAKA_PACKAGER_PATH` and `VIDEO_PATH`)
2. Your environment variables
3. A `.env` file in the same directory as the script

Example `.env` file:
```
SHAKA_PACKAGER_PATH=/usr/local/bin/packager
VIDEO_PATH=/Users/yourusername/Videos
LOG_LEVEL=DEBUG
```

## Development

### Setting up a development environment

```bash
# Clone the repository
git clone https://github.com/coderjun/shaka-packager-mcp.git
cd shaka-packager-mcp

# Install development dependencies with pip
pip install -e ".[dev]"

# Or with uv
uv pip install -e ".[dev]"
```

### Running tests

```bash
pytest
```

### Code formatting

```bash
black .
isort .
```

### Understanding the Code Structure

The main components of the Shaka Packager MCP server are:

- `shaka_packager_mcp.py`: Main server implementation with MCP tools and prompts
- `tests/`: Test suite for verifying functionality

This server is designed to work with the official MCP filesystem server for accessing video files.

### Key Features in the Implementation

- **Robust path handling**: Automatically translates paths between Docker and host environments
- **Smart error handling**: Provides meaningful error messages and suggestions
- **Command syntax assistance**: Helps correctly format Shaka Packager commands
- **Documentation integration**: Provides comprehensive documentation and examples

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Getting Help

Feel free to use an AI code copilot, the author does.

If you encounter any issues or have questions:

1. Check the troubleshooting section in this README
2. Review the [Shaka Packager documentation](https://shaka-project.github.io/shaka-packager/html/index.html)
3. Use the `get_shaka_documentation` tool for interactive help within Claude
4. [Open an issue](https://github.com/coderjun/shaka-packager-mcp/issues) on GitHub

## Acknowledgements

- [Shaka Packager](https://github.com/shaka-project/shaka-packager) for the powerful video processing capabilities
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) for the communication framework
- [Claude](https://claude.ai) for the AI assistant capabilities
- [Anthropic](https://www.anthropic.com/) for developing Claude and the MCP standard