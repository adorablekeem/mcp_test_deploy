# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project called `scalapay_mcp_kam` that provides sales automation for Scalapay merchants. It's built as a Model Context Protocol (MCP) server that integrates with Google Slides API, OpenAI, and data analytics tools to generate automated business intelligence reports and presentations.

## Development Setup

### Prerequisites
- Python 3.12.0 (managed via pyenv)
- Poetry ~2.0 (must be version 2.0 or higher)
- Docker (for some make targets)
- Google API credentials in `./scalapay/scalapay_mcp_kam/credentials.json`

### Initial Setup
```bash
# Install and set Python version
pyenv install 3.12.0  
pyenv local 3.12.0

# Configure poetry environment
poetry env use ~/.pyenv/versions/3.12.0/bin/python
poetry install
```

## Common Commands

### Development Workflow
- `make check` - Run all checks (formatting, linting, type checking, security, tests)
- `make fmt` - Format code with black and isort
- `make lint` - Lint code with flake8
- `make mypy` - Run type checking
- `make test` - Run tests with pytest
- `make bandit` - Security scanning

### Individual Commands
- `poetry run pytest` - Run tests
- `poetry run flake8` - Lint only
- `poetry run mypy` - Type check only
- `poetry run black .` - Format only
- `poetry run isort .` - Sort imports only

### Environment Management
- `make clean` - Clean all build artifacts and caches
- `make .venv` - Set up poetry virtual environment

## Architecture Overview

### Core Components

**MCP Server (`company_intelligence.py`)**
- FastMCP-based server running on port 8002
- Main entry point for slide generation workflows
- Handles merchant token validation and date range processing

**Slide Generation (`slides_test.py`)**
- Orchestrates the complete slide creation pipeline
- Integrates with Google Slides API and Drive API
- Uses OpenAI GPT-4 models for content generation
- Coordinates with Alfred MCP server for data retrieval

**Chart Generation (`charts.py`, `plot_chart.py`)**
- Matplotlib-based chart creation
- Automated data visualization from merchant analytics
- Integration with Google Drive for chart storage

**Tools Directory (`tools/`)**
- Modular utilities for specific functionality
- Chart utilities, Alfred automation, error handling
- Reusable schemas and processing components

### Key Integrations

- **Google APIs**: Slides, Drive, and authentication via oauth2client
- **OpenAI**: GPT-4 models for content analysis and generation  
- **Alfred MCP**: External data source (runs on localhost:8000)
- **FastMCP**: MCP server framework for tool orchestration

### Data Flow

1. User requests slides via `create_slides_wrapper()` with merchant token and date range
2. System connects to Alfred MCP server to retrieve merchant data
3. Data is processed and structured using OpenAI models
4. Charts are generated using matplotlib and uploaded to Google Drive
5. Google Slides presentation is created and populated with data and charts
6. Final PDF export is generated and served via MCP resource endpoint

## Configuration Notes

- Line length: 120 characters (Black/isort)
- Python version: 3.12.0
- Test coverage is enabled and tracked
- Google credentials path: `./scalapay/scalapay_mcp_kam/credentials.json`
- Environment variables loaded via python-dotenv

## MCP Server Usage

Start the server:
```python
# In company_intelligence.py
mcp.run(transport="streamable-http", host="0.0.0.0", port=8002)
```

The server exposes:
- `create_slides_wrapper()` tool for slide generation
- `serve_pdf()` resource for PDF file serving