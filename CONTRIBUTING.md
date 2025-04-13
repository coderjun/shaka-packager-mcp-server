# Contributing to Shaka Packager MCP Server

Thank you for your interest in contributing to the Shaka Packager MCP Server! This document will guide you through the contribution process.

## Code of Conduct

Please be respectful and considerate of others when contributing to this project. We aim to foster an inclusive and welcoming community.

## Development Environment

To set up a development environment:

```bash
# Clone the repository
git clone https://github.com/coderjun/shaka-packager-mcp.git
cd shaka-packager-mcp

# Install development dependencies with pip
pip install -e ".[dev]"
```

## Testing

Run tests with pytest:

```bash
pytest
```

## Code Style

This project uses:
- [Black](https://black.readthedocs.io/) for code formatting
- [isort](https://pycqa.github.io/isort/) for import sorting

Format your code before submitting:

```bash
black .
isort .
```

## Pull Request Process

1. Fork the repository
2. Create a branch for your feature or fix
3. Add tests for your changes
4. Ensure all tests pass
5. Format your code with Black and isort
6. Submit a pull request

## Feature Requests and Bug Reports

Please use GitHub Issues to submit feature requests and bug reports. Include as much detail as possible to help us understand your request or the issue you're experiencing.

## License

By contributing to this project, you agree that your contributions will be licensed under the project's MIT License.