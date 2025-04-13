# Changelog

All notable changes to the Shaka Packager MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-04-12

### Added
- Initial release of the Shaka Packager MCP Server created with copilots Claude Desktop and Claude Code CLI
- Core MCP tools:
  - `analyze_video`: Tool for extracting video stream information
  - `run_shaka_packager`: Tool for executing custom Shaka Packager commands
  - `get_shaka_options`: Tool for retrieving Shaka Packager options and version info
  - `get_shaka_documentation`: Tool for accessing comprehensive Shaka Packager documentation
- Path translation between Docker and host environments
- Robust error handling with structured error responses
- Multiple prompt templates for common operations
  - MP4 to TS conversion
  - VOD packaging in HLS and DASH
  - Live streaming packaging
  - Content encryption
  - Ad insertion
  - Video analysis
- Comprehensive configuration options via environment variables
- Basic test suite for core functionality