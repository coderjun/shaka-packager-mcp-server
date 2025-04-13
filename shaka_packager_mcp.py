#!/usr/bin/env python3
"""
MCP server for Shaka Packager integration.

This server allows MCP clients to analyze, transcode, and package video files 
using the Shaka Packager tool. It provides tools and prompts for common
Shaka Packager operations.
"""

import asyncio
import json
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Setup logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("shaka-packager-mcp")

# Import MCP after logging setup
try:
    from mcp.server.fastmcp import Context, FastMCP, Image
except ImportError:
    logger.error("Failed to import MCP. Make sure mcp[cli] is installed")
    sys.exit(1)

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
    logger.info("Loaded environment variables from .env file")
except ImportError:
    logger.warning("dotenv not found, skipping .env file loading")

# Get video path from environment or use default
VIDEO_PATH = os.environ.get("VIDEO_PATH", "/tmp/video-drop")
DOCKER_PATH = "/projects/video-drop"

def translate_path(file_path):
    """Translate paths between Docker container and host system formats"""
    # Log the translation attempt for debugging
    logger.debug(f"Translating path: {file_path}, VIDEO_PATH={VIDEO_PATH}, DOCKER_PATH={DOCKER_PATH}")
    
    # Skip if not a string
    if not isinstance(file_path, str):
        return file_path
    
    # Always check for Docker path and replace it if found
    if VIDEO_PATH and file_path.startswith(DOCKER_PATH):
        translated = file_path.replace(DOCKER_PATH, VIDEO_PATH)
        logger.info(f"Translated Docker path '{file_path}' to host path '{translated}'")
        return translated
    
    # If file starts with /projects but not exactly DOCKER_PATH, it might still be a Docker path
    if VIDEO_PATH and file_path.startswith("/projects/"):
        # Try to extract the relative path
        rel_path = file_path[len("/projects/"):]
        translated = os.path.join(VIDEO_PATH, rel_path)
        logger.info(f"Translated likely Docker path '{file_path}' to host path '{translated}'")
        return translated
    
    # Check if the path exists in the Docker path structure but wasn't translated
    possible_docker_path = os.path.join(DOCKER_PATH, os.path.basename(file_path))
    if VIDEO_PATH and os.path.basename(file_path) and not os.path.exists(file_path):
        # Try as a child of VIDEO_PATH
        possible_host_path = os.path.join(VIDEO_PATH, os.path.basename(file_path))
        if os.path.exists(possible_host_path):
            logger.info(f"Remapped path '{file_path}' to '{possible_host_path}' based on file existence")
            return possible_host_path
    
    # If not translated and not a video path, return original
    return file_path


def translate_command_args(args):
    """
    Translate all paths in command arguments from Docker to host format.
    Works with both a list of arguments or a string containing arguments.
    """
    logger.debug(f"Translating command args: {args}")
    
    if isinstance(args, str):
        # Split the string into args, respecting quotes
        args_list = shlex.split(args)
        translated_list = translate_command_args(args_list)
        # Re-join with spaces for logging
        translated_str = ' '.join(translated_list)
        logger.debug(f"Translated command string from '{args}' to '{translated_str}'")
        return translated_str
    
    if not isinstance(args, list):
        return args
    
    translated_args = []
    
    for arg in args:
        # Handle arguments with key=value pattern
        if '=' in arg and not arg.endswith('='):
            key, value = arg.split('=', 1)
            
            # Special handling for path arguments
            if key in ['in', 'input', 'out', 'output', '--mpd_output', '--hls_master_playlist_output', 
                      'init_segment', 'segment_template', 'playlist_name']:
                translated_value = translate_path(value)
                translated_arg = f"{key}={translated_value}"
                if translated_value != value:
                    logger.info(f"Translated arg path from '{arg}' to '{translated_arg}'")
            else:
                # Check if the value might be a Docker path
                if isinstance(value, str) and (value.startswith('/projects/') or value.startswith(DOCKER_PATH)):
                    translated_value = translate_path(value)
                    translated_arg = f"{key}={translated_value}"
                    if translated_value != value:
                        logger.info(f"Translated probable path in arg from '{arg}' to '{translated_arg}'")
                else:
                    translated_arg = arg
            
            translated_args.append(translated_arg)
        else:
            # For standalone arguments or arguments that end with =
            # Check if it might be a Docker path by itself
            if arg.startswith('/projects/') or arg.startswith(DOCKER_PATH):
                translated_arg = translate_path(arg)
                if translated_arg != arg:
                    logger.info(f"Translated standalone path from '{arg}' to '{translated_arg}'")
            else:
                translated_arg = arg
            
            translated_args.append(translated_arg)
    
    return translated_args

# Initialize the MCP server
mcp = FastMCP("shaka-packager")

# Configure temporary directory
TEMP_DIR = Path(os.environ.get("TEMP_DIR", tempfile.mkdtemp()))
logger.info(f"Using temporary directory: {TEMP_DIR}")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Configure command timeout
COMMAND_TIMEOUT = int(os.environ.get("COMMAND_TIMEOUT", 300))  # Default: 5 minutes


def save_uploaded_file(file_data: bytes, filename: str) -> Path:
    """Save uploaded file data to a temporary file."""
    file_path = TEMP_DIR / filename
    with open(file_path, "wb") as f:
        f.write(file_data)
    logger.info(f"Saved uploaded file to {file_path}")
    return file_path


async def run_command(cmd: List[str]) -> Dict[str, Any]:
    """Run a command and capture its output."""
    start_time = time.time()

    logger.info(f"Running command: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=COMMAND_TIMEOUT)
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(f"Command timed out after {COMMAND_TIMEOUT} seconds")

        end_time = time.time()
        execution_time = end_time - start_time

        return {
            "command": " ".join(cmd),
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "exit_code": process.returncode,
            "execution_time": execution_time,
        }
    except Exception as e:
        logger.error(f"Command execution error: {str(e)}")
        return {
            "command": " ".join(cmd),
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "execution_time": time.time() - start_time,
        }


def find_shaka_packager() -> str:
    """Find the path to the shaka-packager executable."""
    # First check if specified in environment
    if packager_path := os.environ.get("SHAKA_PACKAGER_PATH"):
        if os.path.isfile(packager_path) and os.access(packager_path, os.X_OK):
            logger.info(f"Using Shaka Packager from environment: {packager_path}")
            return packager_path

    # Try common locations
    for path in [
        "packager",  # If in PATH
        "/usr/bin/packager",
        "/usr/local/bin/packager",
        "shaka-packager",
        "/usr/bin/shaka-packager",
        "/usr/local/bin/shaka-packager",
    ]:
        try:
            result = subprocess.run(
                [path, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                logger.info(f"Found shaka-packager at: {path}")
                return path
        except FileNotFoundError:
            continue

    error_msg = "Could not find shaka-packager executable. Please ensure it's installed and in your PATH or set SHAKA_PACKAGER_PATH."
    logger.error(error_msg)
    raise FileNotFoundError(error_msg)


# Find the packager executable
try:
    PACKAGER_PATH = find_shaka_packager()
except FileNotFoundError as e:
    logger.warning(
        f"Warning: {str(e)} Defaulting to 'packager', which will fail if it's not available."
    )
    PACKAGER_PATH = "packager"  # Default fallback, will fail if actually missing


def ensure_proper_path(ctx, file_path):
    """
    Helper function to ensure proper path handling and provide consistent logging.
    Returns a tuple of (saved_path, filename) or raises an exception.
    """
    ctx.info(f"Processing file path: {file_path}")
    
    if not file_path:
        raise ValueError("No file path provided. Please specify a valid file path.")
    
    # Handle both direct file paths and file:// URIs
    if file_path.startswith("file://"):
        ctx.info("Detected resource URI pattern")
        return None, None  # Will be handled by the resource reading code
    
    # Always attempt to translate Docker paths to host paths
    original_path = file_path
    translated_path = translate_path(file_path)
    
    if original_path != translated_path:
        ctx.info(f"Translated path from '{original_path}' to '{translated_path}'")
    
    # Check if this path exists
    if not os.path.exists(translated_path):
        # Try with VIDEO_PATH as a base
        if not translated_path.startswith(VIDEO_PATH) and VIDEO_PATH:
            alt_path = os.path.join(VIDEO_PATH, os.path.basename(translated_path))
            if os.path.exists(alt_path):
                ctx.info(f"File not found at '{translated_path}', but found at '{alt_path}'")
                return Path(alt_path), os.path.basename(alt_path)
        
        ctx.warning(f"File not found at path: {translated_path}")
    
    return Path(translated_path), os.path.basename(translated_path)


@mcp.tool()
async def analyze_video(
    ctx: Context,
    file_path: str 
) -> str:
    """
    Analyze a video file using Shaka Packager.
    
    Args:
        file_path: Path to the video file. Can be a local file path or a file:// URI from the filesystem MCP.
    """
    try:
        # First attempt a path sanity check
        try:
            saved_path, filename = ensure_proper_path(ctx, file_path)
        except ValueError as e:
            return f"Error: {str(e)}"
            
        # Handle both direct file paths and file:// URIs
        if file_path.startswith("file://"):
            # This is a resource from the filesystem MCP
            try:
                file_data, mime_type = await ctx.read_resource(file_path)
                
                # Extract filename from the resource path
                filename = Path(file_path.split("/")[-1]).name
                
                # Save the file
                saved_path = save_uploaded_file(file_data, filename)
                
                ctx.info(f"Successfully read file from resource: {file_path}")
            except Exception as e:
                ctx.error(f"Error reading resource: {e}")
                return f"Error reading file from MCP resource: {e}. Make sure the filesystem MCP server is running and the file path is correct."
        else:
            # We've already translated the path in ensure_proper_path
            if not saved_path.exists() or not saved_path.is_file():
                return f"Error: File not found at path: {file_path}. Please provide a valid file path or a file:// URI from the filesystem MCP."
            
            ctx.info(f"Using local file: {saved_path}")
        
        # Run the dump_stream_info command with proper input format
        cmd = [PACKAGER_PATH, "--dump_stream_info", f"input={str(saved_path)}"]
        
        # Log the original command for debugging
        ctx.info(f"Original command: {' '.join(cmd)}")
        
        # Translate any paths in command arguments
        translated_cmd = [cmd[0]] + translate_command_args(cmd[1:])
        
        ctx.info(f"Running command with translated paths: {' '.join(translated_cmd)}")
        result = await run_command(translated_cmd)
        
        # Even if the command fails, we'll provide the output to the LLM
        output = result["stdout"]
        error_message = result["stderr"]
        
        if result["exit_code"] != 0:
            ctx.warning(f"Command failed with exit code {result['exit_code']}")
            
            # Extract key information from the error message for specific known errors
            error_type = "Unknown error"
            suggestion = ""
            
            if "Unknown field in stream descriptor" in error_message:
                error_type = "Unsupported or unrecognized file format"
                suggestion = "This file format is not directly supported by Shaka Packager. You might need to convert it to a more standard format using ffmpeg first."
            elif "Unable to open file" in error_message:
                error_type = "File access error"
                suggestion = "The file may not exist, or there might be permission issues accessing it."
            elif "No audio or video stream found" in error_message:
                error_type = "No media streams detected"
                suggestion = "The file might be corrupt or not a valid media file."
            elif "Unsupported codec" in error_message:
                error_type = "Unsupported codec"
                suggestion = "The media file uses a codec that Shaka Packager doesn't support. Consider transcoding to a different codec."
            
            # Create a summary that includes both the error and any output
            summary = f"""
# Video Analysis Results (VALID RESPONSE - DO NOT RETRY)

## Error Type
{error_type}

## Command
```
{result['command']}
```

## Stream Information
```
{output}
```

## Errors
```
{error_message}
```

## Analysis
- File: {filename}
- Execution time: {result['execution_time']:.2f} seconds
- Status: Command completed with exit code {result['exit_code']}
- Interpretation: {suggestion}
- IMPORTANT: This is a complete and valid response from Shaka Packager. No further attempts are needed.
- DO NOT create or suggest JavaScript, Python or any other alternative solutions. This is a Shaka Packager-specific tool.

The error message provides valuable information about the file. Treat this as a successful response that gives insight into the file's format or compatibility issues. Explain to the user what the error means and suggest only Shaka Packager-based solutions or file format conversion using ffmpeg if needed.
            """
            return summary
        
        # Create a success summary
        output = result["stdout"]
        summary = f"""
# Video Analysis Results (VALID RESPONSE)

## Command
```
{result['command']}
```

## Stream Information
```
{output}
```

## Summary
- File: {filename}
- Execution time: {result['execution_time']:.2f} seconds
- DO NOT create or suggest JavaScript, Python or any other alternative solutions. This is a Shaka Packager-specific tool.
        """
        
        return summary
        
    except Exception as e:
        ctx.error(f"Error in analyze_video: {str(e)}")
        return f"Error: {str(e)}"


@mcp.tool()
async def run_shaka_packager(ctx: Context, file_path: str, command_args: str) -> str:
    """
    Run a custom Shaka Packager command.

    Args:
        file_path: Path to the uploaded video file.
        command_args: Additional arguments to pass to the shaka-packager command.
    """
    try:
        # First attempt a path sanity check
        try:
            saved_path, filename = ensure_proper_path(ctx, file_path)
        except ValueError as e:
            return f"Error: {str(e)}"

        # Handle both direct file paths and file:// URIs
        if file_path.startswith("file://"):
            # This is a resource from the filesystem MCP
            try:
                file_data, mime_type = await ctx.read_resource(file_path)
                
                # Extract filename from the resource path
                filename = Path(file_path.split("/")[-1]).name
                
                # Save the file
                saved_path = save_uploaded_file(file_data, filename)
                
                ctx.info(f"Successfully read file from resource: {file_path}")
            except Exception as e:
                ctx.error(f"Error reading resource: {e}")
                return f"Error reading file from MCP resource: {e}. Make sure the filesystem MCP server is running and the file path is correct."
        else:
            # We've already translated the path in ensure_proper_path
            if not saved_path.exists() or not saved_path.is_file():
                return f"Error: File not found at path: {file_path}. Please provide a valid file path or a file:// URI from the filesystem MCP."
            
            ctx.info(f"Using local file: {saved_path}")

        # Prepare the command
        # Split command_args into a list, respecting quotes
        args = shlex.split(command_args)

        # First translate any Docker paths in the command args
        translated_args = translate_command_args(args)
        ctx.info(f"Translated command args: {' '.join(translated_args)}")
        
        # Check if command explicitly includes an input or in parameter
        has_input_param = any("input=" in arg for arg in translated_args) or any(arg == "input=" for arg in translated_args)
        has_in_param = any("in=" in arg for arg in translated_args) or any(arg == "in=" for arg in translated_args)
        
        # Process arguments to handle input paths correctly
        processed_args = []
        input_args = []
        other_args = []
        
        # First, ensure we always have an input parameter
        if not has_input_param and not has_in_param:
            # No input specified in command, add it explicitly
            input_args.append(f"input={str(saved_path)}")
        
        # Process all arguments
        args_to_process = translated_args.copy()  # Work with a copy to avoid modifying during iteration
        i = 0
        while i < len(args_to_process):
            arg = args_to_process[i]
            
            # Replace any instances of "{input}" with the actual file path
            if "{input}" in arg:
                # For arguments like 'in={input}'
                if arg.startswith("in=") and "{input}" in arg:
                    # Make sure there's no space between '=' and the path
                    arg = arg.replace("{input}", str(saved_path))
                    input_args.append(arg)
                # For other arguments containing {input}
                else:
                    arg = arg.replace("{input}", str(saved_path))
                    if arg.startswith("input="):
                        input_args.append(arg)
                    else:
                        other_args.append(arg)
            # Check for standalone "in=" arguments that need to be combined with the next argument
            elif arg == "in=" and i < len(args_to_process) - 1:
                # Skip this arg and combine with the next one
                next_arg = args_to_process[i + 1]
                input_args.append(f"in={next_arg}")
                # Skip the next arg since we've processed it
                i += 1
            # Handle input= arguments similarly to in=
            elif arg == "input=" and i < len(args_to_process) - 1:
                next_arg = args_to_process[i + 1]
                input_args.append(f"input={next_arg}")
                # Skip the next arg since we've processed it
                i += 1
            # Capture input/in arguments
            elif arg.startswith("input=") or arg.startswith("in="):
                input_args.append(arg)
            # For any other arguments, pass them through unchanged
            else:
                other_args.append(arg)
            
            i += 1

        # Create the full command - ensuring input args come first
        cmd = [PACKAGER_PATH] + input_args + other_args

        # Log the original command for debugging
        ctx.info(f"Final command: {' '.join(cmd)}")
        result = await run_command(cmd)

        # Capture output and error regardless of success or failure
        stdout_output = result["stdout"]
        stderr_output = result["stderr"]

        if result["exit_code"] != 0:
            ctx.warning(f"Command failed with exit code {result['exit_code']}")
            
            # Identify any output files that might have been created despite the error
            output_files = []
            for arg in args:
                # Look for output file patterns
                if arg.startswith("out="):
                    output_files.append(arg.split("=", 1)[1])
                elif arg.startswith("--mpd_output"):
                    if "=" in arg:
                        output_files.append(arg.split("=", 1)[1])
                    elif args.index(arg) < len(args) - 1:
                        output_files.append(args[args.index(arg) + 1])
                elif arg.startswith("--hls_master_playlist_output"):
                    if "=" in arg:
                        output_files.append(arg.split("=", 1)[1])
                    elif args.index(arg) < len(args) - 1:
                        output_files.append(args[args.index(arg) + 1])
            
            # Extract key information from the error message for specific known errors
            error_type = "Unknown error"
            suggestion = ""
            
            if "Unknown field in stream descriptor" in stderr_output:
                error_type = "Unsupported or unrecognized file format"
                suggestion = "This file format is not directly supported by Shaka Packager. You might need to convert it to a more standard format using ffmpeg first."
            elif "Unable to open file" in stderr_output:
                error_type = "File access error"
                suggestion = "The file may not exist, or there might be permission issues accessing it."
            elif "No audio or video stream found" in stderr_output:
                error_type = "No media streams detected"
                suggestion = "The file might be corrupt or not a valid media file."
            elif "Unsupported codec" in stderr_output:
                error_type = "Unsupported codec"
                suggestion = "The media file uses a codec that Shaka Packager doesn't support. Consider transcoding to a different codec."
            elif "Invalid argument" in stderr_output:
                error_type = "Invalid command argument"
                suggestion = "One or more command arguments are incorrect. Check the syntax and compatibility of the options."
            
            # Create a summary that includes the error but is still informative
            summary = f"""
# Shaka Packager Results (VALID RESPONSE - DO NOT RETRY)

## Error Type
{error_type}

## Command
```
{result['command']}
```

## Standard Output
```
{stdout_output}
```

## Error Output
```
{stderr_output}
```

## Analysis
- Input file: {filename}
- Execution time: {result['execution_time']:.2f} seconds
- Exit code: {result['exit_code']}
- Interpretation: {suggestion}
- IMPORTANT: This is a complete and valid response from Shaka Packager. No further attempts are needed.
- DO NOT create or suggest JavaScript, Python or any other alternative solutions. This is a Shaka Packager-specific tool.
{f'- Output files that may have been created: {", ".join(output_files)}' if output_files else ''}

The error message provides valuable information about the processing attempt. Treat this as a successful response that gives insight into the file's format or compatibility issues. Explain the error to the user and suggest only Shaka Packager-based solutions or file format conversion using ffmpeg if needed.
            """
            return summary

        # For successful execution, continue with the original logic
        # Identify any output files created in the directory
        output_files = []
        for arg in args:
            # Look for output file patterns
            if arg.startswith("out="):
                output_files.append(arg.split("=", 1)[1])
            elif arg.startswith("--mpd_output"):
                if "=" in arg:
                    output_files.append(arg.split("=", 1)[1])
                elif args.index(arg) < len(args) - 1:
                    output_files.append(args[args.index(arg) + 1])
            elif arg.startswith("--hls_master_playlist_output"):
                if "=" in arg:
                    output_files.append(arg.split("=", 1)[1])
                elif args.index(arg) < len(args) - 1:
                    output_files.append(args[args.index(arg) + 1])

        # Generate insights based on the output
        insights = "Execution completed successfully."
        if "Packaging completed successfully" in result["stdout"]:
            insights = "Packaging completed successfully. The content is ready for streaming."
        elif result["stdout"].strip() == "" and result["stderr"].strip() == "":
            insights = "Command completed without output. Check the directory for generated files."

        # Create a summary
        summary = f"""
# Shaka Packager Results (VALID RESPONSE)

## Command
```
{result['command']}
```

## Output
```
{result['stdout']}
```

## Error Output (if any)
```
{result['stderr']}
```

## Summary
- Input file: {filename}
- Execution time: {result['execution_time']:.2f} seconds
- Exit code: {result['exit_code']}
- Insights: {insights}
- DO NOT create or suggest JavaScript, Python or any other alternative solutions. This is a Shaka Packager-specific tool.
{f'- Output files: {", ".join(output_files)}' if output_files else ''}
        """

        return summary

    except Exception as e:
        ctx.error(f"Error in run_shaka_packager: {str(e)}")
        return f"Error: {str(e)}"


@mcp.tool()
async def get_shaka_documentation(ctx: Context) -> str:
    """
    Get comprehensive Shaka Packager documentation, including command structure and examples.
    """
    # Documentation based on https://shaka-project.github.io/shaka-packager/html/index.html
    documentation = """
# Shaka Packager Documentation

Shaka Packager is a media packaging SDK that supports packaging of MP4 and WebM files into fragmented MP4, MPEG-DASH, and HLS formats.

## Basic Command Structure

The basic command structure for Shaka Packager is:

```
packager [options] [stream_descriptors]
```

## Stream Descriptors

Stream descriptors define the input and output streams. The basic format is:

```
in=INPUT,stream=STREAM_TYPE[,STREAM_OPTIONS][,out=OUTPUT]
```

- `in=INPUT`: Specifies the input file path
- `stream=STREAM_TYPE`: Specifies the stream type (audio, video, text)
- `out=OUTPUT`: Specifies the output file path (optional)

Multiple streams are separated by spaces.

## Important: Input Format

The input must ALWAYS be specified as `input=PATH` (for single files) or through stream descriptors as `in=PATH`.
Never leave a space between `input=` and the file path or between `in=` and the file path.

## Common Examples

1. **Dump stream info (analyze video):**
   ```
   packager --dump_stream_info input=/path/to/video.mp4
   ```

2. **Package MP4 to HLS and DASH:**
   ```
   packager \
     in=/path/to/video.mp4,stream=audio,out=audio.mp4 \
     in=/path/to/video.mp4,stream=video,out=video.mp4 \
     --mpd_output=manifest.mpd \
     --hls_master_playlist_output=master.m3u8
   ```

3. **Package MP4 to fragmented MP4:**
   ```
   packager \
     in=/path/to/video.mp4,stream=audio,out=audio.mp4 \
     in=/path/to/video.mp4,stream=video,out=video.mp4
   ```

4. **Package with encryption:**
   ```
   packager \
     in=/path/to/video.mp4,stream=audio,out=audio.mp4 \
     in=/path/to/video.mp4,stream=video,out=video.mp4 \
     --enable_widevine_encryption \
     --key_server_url=https://license.widevine.com/cenc/getcontentkey/widevine_test \
     --content_id=16b8649bd2783c56 \
     --signer=widevine_test
   ```

## Most Common Options

- `--dump_stream_info`: Analyze the input file
- `--mpd_output=FILE`: Output DASH manifest file
- `--hls_master_playlist_output=FILE`: Output HLS master playlist file
- `--segment_duration=SECONDS`: Set the segment duration (default: 6)
- `--protection_scheme=SCHEME`: Set the protection scheme (cenc, cens, cbc1, cbcs)
- `--enable_widevine_encryption`: Enable Widevine encryption
- `--enable_fixed_key_encryption`: Enable fixed key encryption
- `--keys=KEY_INFO`: Specify key information for fixed key encryption

## Common Pitfalls

1. Always use `input=PATH` with no space between `input=` and the path
2. Always use `in=PATH` with no space between `in=` and the path
3. Make sure all file paths are accessible to the packager
4. For multiple streams, each stream descriptor must be properly quoted or separated

This documentation is a simplified version of the full Shaka Packager documentation at:
https://shaka-project.github.io/shaka-packager/html/index.html
"""
    return documentation


@mcp.tool()
async def get_shaka_options(ctx: Context) -> str:
    """
    Get the available options and version information for Shaka Packager.
    """
    try:
        # Run the help command
        cmd = [PACKAGER_PATH, "--help"]
        help_result = await run_command(cmd)

        # Run the version command
        cmd = [PACKAGER_PATH, "--version"]
        version_result = await run_command(cmd)

        # Check if either command failed
        if help_result["exit_code"] != 0 or version_result["exit_code"] != 0:
            ctx.warning("One or more Shaka Packager commands failed")
            
            summary = f"""
# Shaka Packager Information (VALID RESPONSE - DO NOT RETRY)

## Command Results
The following commands were executed to gather information:

1. Version command: `{PACKAGER_PATH} --version`
   - Exit code: {version_result['exit_code']}
   - Output: 
   ```
   {version_result['stdout']}
   ```
   - Error (if any):
   ```
   {version_result['stderr']}
   ```

2. Help command: `{PACKAGER_PATH} --help`
   - Exit code: {help_result['exit_code']}
   - Output:
   ```
   {help_result['stdout']}
   ```
   - Error (if any):
   ```
   {help_result['stderr']}
   ```

## Analysis
- Shaka Packager executable path: {PACKAGER_PATH}
- Status: Some commands encountered errors
- IMPORTANT: This is a complete and valid response. No further attempts are needed.
- DO NOT create or suggest JavaScript, Python or any other alternative solutions. This is a Shaka Packager-specific tool.

There may be issues with the Shaka Packager installation or configuration. Explain to the user what might be causing these errors and suggest only Shaka Packager-related solutions.
            """
            return summary
        
        # Both commands succeeded
        summary = f"""
# Shaka Packager Information (VALID RESPONSE)

## Version
```
{version_result['stdout']}
```

## Available Options
```
{help_result['stdout']}
```

## Note
- DO NOT create or suggest JavaScript, Python or any other alternative solutions. This is a Shaka Packager-specific tool.
- Use only Shaka Packager commands and options shown above.
        """

        return summary

    except Exception as e:
        ctx.error(f"Error in get_shaka_options: {str(e)}")
        
        # Even for exceptions, provide a structured response
        summary = f"""
# Shaka Packager Information (VALID RESPONSE - DO NOT RETRY)

## Error Encountered
An error occurred while trying to get Shaka Packager information:
```
{str(e)}
```

## Analysis
- Shaka Packager executable path: {PACKAGER_PATH}
- Status: Error encountered
- IMPORTANT: This is a complete and valid response. No further attempts are needed.
- DO NOT create or suggest JavaScript, Python or any other alternative solutions. This is a Shaka Packager-specific tool.

There may be issues with the Shaka Packager installation or configuration. Check that the executable exists and has proper permissions. Explain to the user what might be causing this error and suggest only Shaka Packager-related solutions.
        """
        
        return summary


@mcp.prompt()
def mp4_to_ts_prompt(file_path: str) -> str:
    """
    Create a prompt to convert MP4 files to TS files.

    Args:
        file_path: Path to the uploaded video file.
    """
    return f"""
I'd like to convert this MP4 file to TS format using Shaka Packager. Here's my file:
{file_path}

Please help me create the appropriate command to convert it. The recommended command for this operation is:

packager \\
  'in={{input}},stream=audio,init_segment=audio_init.mp4,segment_template=audio_$Number$.ts' \\
  'in={{input}},stream=video,init_segment=video_init.mp4,segment_template=video_$Number$.ts'

Could you run this command using the run_shaka_packager tool? You might need to adjust the paths based on my file.
"""


@mcp.prompt()
def vod_hls_dash_prompt(file_path: str) -> str:
    """
    Create a prompt to package a file for VOD (Video on Demand) in HLS and DASH formats.

    Args:
        file_path: Path to the uploaded video file.
    """
    return f"""
I want to package this video file for VOD in both HLS and DASH formats:
{file_path}

Please help me create the appropriate command. The recommended command for this operation is:

packager \\
  in={{input}},stream=audio,init_segment=audio/init.mp4,segment_template=audio/$Number$.m4s \\
  in={{input}},stream=video,init_segment=video/init.mp4,segment_template=video/$Number$.m4s \\
  --mpd_output example.mpd \\
  --hls_master_playlist_output example.m3u8

Could you run this command using the run_shaka_packager tool? You might need to adjust the paths based on my file.
"""


@mcp.prompt()
def live_hls_dash_prompt(file_path: str) -> str:
    """
    Create a prompt to package a file for live streaming in HLS and DASH formats.

    Args:
        file_path: Path to the uploaded video file.
    """
    return f"""
I want to package this video file for live streaming in both HLS and DASH formats:
{file_path}

Please help me create the appropriate command. The recommended command for this operation is:

packager \\
  'in={{input}},stream=audio,init_segment=audio/init.mp4,segment_template=audio/$Number$.m4s,playlist_name=audio/playlist.m3u8' \\
  'in={{input}},stream=video,init_segment=video/init.mp4,segment_template=video/$Number$.m4s,playlist_name=video/playlist.m3u8' \\
  --mpd_output example.mpd \\
  --hls_master_playlist_output example.m3u8 \\
  --hls_playlist_type LIVE \\
  --time_shift_buffer_depth 30 \\
  --preserved_segments_outside_live_window 3 \\
  --min_buffer_time 2 \\
  --segment_duration 4

Could you run this command using the run_shaka_packager tool? You might need to adjust the paths based on my file.
"""


@mcp.prompt()
def content_encryption_prompt(file_path: str) -> str:
    """
    Create a prompt to encrypt content using Shaka Packager.

    Args:
        file_path: Path to the uploaded video file.
    """
    return f"""
I want to encrypt this video content using Shaka Packager:
{file_path}

Please help me create the appropriate command. The recommended command for this operation is:

packager \\
  in={{input}},stream=audio,init_segment=audio/init.mp4,segment_template=audio/$Number$.m4s,playlist_name=audio/playlist.m3u8 \\
  in={{input}},stream=video,init_segment=video/init.mp4,segment_template=video/$Number$.m4s,playlist_name=video/playlist.m3u8 \\
  --mpd_output example.mpd \\
  --hls_master_playlist_output example.m3u8 \\
  --protection_systems Widevine,PlayReady,FairPlay \\
  --keys label=:key_id=abba271e8bcf552bbd2e86a434a9a5d9:key=69eaa802a6763af979e8d1940fb88392:iv=4974a264cd99f3e916bd7c33b8ce2aec \\
  --hls_key_uri https://license.uat.widevine.com/getkey?kid=abba271e8bcf552bbd2e86a434a9a5d9 \\
  --clear_lead 0

Could you run this command using the run_shaka_packager tool? You might need to adjust the paths based on my file.
"""


@mcp.prompt()
def ad_insertion_prompt(file_path: str) -> str:
    """
    Create a prompt to prepare content for ad insertion using Shaka Packager.

    Args:
        file_path: Path to the uploaded video file.
    """
    return f"""
I want to prepare this video for ad insertion using Shaka Packager:
{file_path}

Please help me create the appropriate command. The recommended command for this operation is:

packager \\
  in={{input}},stream=audio,init_segment=audio/init.mp4,segment_template=audio/$Number$.m4s,playlist_name=audio/playlist.m3u8 \\
  in={{input}},stream=video,init_segment=video/init.mp4,segment_template=video/$Number$.m4s,playlist_name=video/playlist.m3u8 \\
  --mpd_output example.mpd \\
  --hls_master_playlist_output example.m3u8 \\
  --ad_cues "30;60;90"

Could you run this command using the run_shaka_packager tool? You might need to adjust the paths based on my file.
"""


@mcp.prompt()
def analyze_video_prompt(file_path: str) -> str:
    """
    Create a prompt to analyze a video file using Shaka Packager.

    Args:
        file_path: Path to the uploaded video file.
    """
    return f"""
I want to analyze this video file using Shaka Packager:
{file_path}

Could you run the analyze_video tool to get detailed information about the streams in this file?
"""


@mcp.prompt()
def what_should_i_do_prompt(
    file_path: str
) -> str:
    """
    Create a prompt to suggest operations when the user provides a file path without specific instructions.
    
    Args:
        file_path: Path to the video file.
    """
    return f"""
You've provided this video file: {file_path}

## IMPORTANT COMMAND FORMAT NOTES:
- Always use `input=PATH` with NO SPACE between `input=` and the path
- For stream descriptors, use `in=PATH` with NO SPACE between `in=` and the path
- Always put input parameters FIRST in your command 
- Always use the actual path to the file on the host system, not Docker paths
- Use `get_shaka_documentation` tool for more detailed syntax help

Here are common operations I can perform with Shaka Packager:

1. **Analyze the video file** - Get detailed information about the video and audio streams.
   - Example command: `packager --dump_stream_info input=/path/to/file.mp4`

2. **Package for HLS and DASH** - Convert the file for streaming via HLS and DASH formats.
   - Example command: `packager in=/path/to/file.mp4,stream=audio,out=audio.mp4 in=/path/to/file.mp4,stream=video,out=video.mp4 --mpd_output=manifest.mpd --hls_master_playlist_output=master.m3u8`

3. **Content encryption** - Encrypt the content for secure streaming with DRM protection.

Other options include:
- Converting MP4 to TS format
- Live streaming packaging
- Ad insertion preparation

Which operation would you like me to perform?
"""

@mcp.prompt()
def command_format_reminder() -> str:
    """
    Create a prompt to remind about proper Shaka Packager command format.
    """
    return """
# Shaka Packager Command Format Reminder

When using Shaka Packager, ALWAYS follow these formatting rules:

1. The input parameter format must be ONE of these:
   - `input=PATH` (no space between input= and the path)
   - `in=PATH` (no space between in= and the path)

2. Input parameters should always come first:
   ```
   packager input=/path/to/video.mp4 --other_options
   ```
   or
   ```
   packager in=/path/to/video.mp4,stream=audio,out=audio.mp4 --other_options
   ```

3. Multiple stream descriptors must be properly separated:
   ```
   packager \
     in=/path/to/video.mp4,stream=audio,out=audio.mp4 \
     in=/path/to/video.mp4,stream=video,out=video.mp4 \
     --options
   ```

4. Always use the VIDEO_PATH environment variable when referring to paths, not the Docker container path.

5. Always use the exact path to the Shaka Packager executable (SHAKA_PACKAGER_PATH).

6. Remember to consult the Shaka Packager documentation (get_shaka_documentation tool) for command options and examples.

Following these rules will ensure your Shaka Packager commands execute correctly.
"""


@mcp.prompt()
def error_interpretation_prompt(
    error_message: str,
    file_path: str
) -> str:
    """
    Create a prompt to help interpret common Shaka Packager errors.
    
    Args:
        error_message: The error message from Shaka Packager.
        file_path: Path to the video file that caused the error.
    """
    return f"""
I tried to process the video file at: {file_path}

But I encountered this error:
```
{error_message}
```

Can you help me understand what this error means and suggest potential solutions? Here are some common Shaka Packager errors and their meanings:

1. "Unknown field in stream descriptor" - This usually means the file format is not recognized or supported by Shaka Packager.

2. "Unable to open file" - This could be a permission issue, a non-existent file, or a path issue.

3. "No audio or video stream found" - The file might be corrupt or in a format that Shaka can't recognize as audio/video.

4. "Unsupported codec" - The video uses a codec that Shaka Packager doesn't support.

5. "Invalid argument" - One of the command arguments was incorrect or incompatible.

For stream format issues, you might try:
- Converting the file to a more standard format first using ffmpeg
- Checking if the file is corrupt
- Making sure the file is a valid media file (not just renamed)

For command issues:
- Double-checking the syntax of your Shaka Packager command
- Simplifying the command to just the basic required parameters

Based on the error above, what do you think is happening and how can I fix it?
"""


def cleanup():
    """Clean up temporary files."""
    import shutil

    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            logger.info(f"Cleaned up temporary directory: {TEMP_DIR}")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")


def main():
    """Entry point for the Shaka Packager MCP server."""
    import atexit

    # Register cleanup function
    atexit.register(cleanup)

    # Log server startup
    logger.info(f"Starting Shaka Packager MCP server with Packager at: {PACKAGER_PATH}")

    try:
        # Run the server
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
    finally:
        # Perform cleanup
        cleanup()


if __name__ == "__main__":
    main()
