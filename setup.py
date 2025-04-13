"""Setup script for the Shaka Packager MCP server."""

from setuptools import setup

setup(
    name="shaka-packager-mcp",
    version="0.1.0",
    description="MCP server for Shaka Packager integration",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Jun Heider",
    author_email="junheider@gmail.com",
    py_modules=["shaka_packager_mcp"],
    install_requires=[
        "mcp[cli]>=1.5.0",
        "python-dotenv",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Video :: Conversion",
    ],
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "shaka-packager-mcp=shaka_packager_mcp:main",
        ],
    },
)
