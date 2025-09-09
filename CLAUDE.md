# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python project called `scalapay_mcp_kam` that provides automated business intelligence slide generation for Scalapay merchants. It's an MCP (Model Context Protocol) server that orchestrates the complete pipeline from user elicitation to slide delivery through integration with multiple specialized MCP servers and APIs.

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

## Core Architecture

### Primary MCP Server (`mcp_server.py`)
- FastMCP-based orchestrator running on port 8002
- Handles user elicitation for merchant token and date ranges
- Exposes `create_slides_wrapper()` tool as main entry point
- Serves generated PDF files via resource endpoints

### Agent-Based Processing (`agents/`)
- **Google Slides Agent**: Template management and slide assembly
- **Alfred Agent**: Data retrieval coordination with Snowflake MCP
- **Chart Agent**: Matplotlib visualization generation

### Tools System (`tools/`)
- Modular query builders for structured data requests
- Chart-specific utilities with dynamic prompt generation
- Schema definitions for data validation and processing
- Error handling and retry mechanisms

## Key Integrations

### External MCP Servers
- **Alfred MCP** (localhost:8000): Snowflake data warehouse interface
- **Charts MCP**: Specialized matplotlib chart generation service

### Google APIs
- **Google Slides API**: Template-based presentation creation
- **Google Drive API**: Chart storage and sharing management
- **OAuth2 Authentication**: Secure API access management

### AI Services
- **OpenAI GPT-4**: Dynamic content generation and data analysis
- **Dynamic Prompting**: Context-aware chart and text generation

## Configuration Notes

- Line length: 120 characters (Black/isort)
- Python version: 3.12.0
- Test coverage is enabled and tracked
- Google credentials path: `./scalapay/scalapay_mcp_kam/credentials.json`
- Environment variables loaded via python-dotenv

## MCP Server Usage

Start the server:
```bash
python scalapay/scalapay_mcp_kam/mcp_server.py
```

The server exposes:
- `create_slides_wrapper(merchant_token, starting_date, end_date)` - Main slide generation tool
- `serve_pdf(path)` - PDF file serving resource

## Development Notes

- Each chart type has specific data structure requirements
- Slide templates use placeholder-based content replacement
- Dynamic prompt generation adapts to chart types and data contexts
- Error handling includes retry mechanisms for API failures
- All generated artifacts are stored with unique identifiers