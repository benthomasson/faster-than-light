# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Faster Than Light (FTL) is an experimental automation framework built for speed and scalability as a high-performance alternative to Ansible using Python asyncio. The project focuses on performance research and benchmarking of infrastructure automation tools.

## Commands

### Development Commands
- `pytest` - Run tests (configured with asyncio_mode=strict)
- `pytest tests/` - Run all tests in tests directory
- `make test` - Run tests via Makefile
- `make test-all` - Run tests across all Python versions with tox
- `tox` - Run tests in isolated environments

### Code Quality
- `make lint` - Run flake8 linting on faster_than_light and tests
- `flake8 faster_than_light tests` - Direct linting command
- `mypy` - Type checking (configured in mypy.ini with strict settings)
- `ruff` - Modern Python linter (available as dev dependency)

### Build and Distribution
- `make clean` - Remove all build artifacts, test files, and Python cache
- `make dist` - Build source and wheel packages
- `python setup.py sdist` - Build source distribution
- `python setup.py bdist_wheel` - Build wheel distribution
- `make install` - Install package to active Python environment

### Testing and Performance
- `make coverage` - Run tests with coverage reporting and open HTML report
- Performance test scripts in `performance-test/python-asyncio/local/`:
  - `./run_perf.sh` - Local performance benchmarks
  - `./run_perf_async.sh` - Async performance benchmarks
- Remote performance tests in `performance-test/python-asyncio/remote/`

### CLI Tools
- `ftl` - Main automation CLI (faster_than_light.cli:entry_point)
- `ftl-gate-builder` - Build FTL gates for remote execution
- `ftl-localhost` - Inventory management for localhost

## Architecture

### Core Components
- **faster_than_light/**: Main package directory
  - `cli.py` - Command line interface entry point
  - `module.py` - Module execution system (sync and async)
  - `ssh.py` - SSH operations and gate management
  - `inventory.py` - Ansible-compatible inventory parsing
  - `gate.py` - Persistent SSH connection management
  - `local.py` - Local execution functionality
  - `builder.py` - FTL gate building functionality

### Key Architecture Features
- **Gate System**: Persistent SSH connections in `ftl_gate/` for efficient remote execution
- **Async-First Design**: Built with Python asyncio for maximum concurrency
- **Module Compatibility**: Supports both FTL-optimized modules (`ftl_modules/`) and Ansible modules
- **Dual Execution Modes**: Local and remote execution with seamless switching

### Module System
- Standard modules in `tests/modules/` for testing
- FTL-optimized modules in `tests/ftl_modules/`
- Performance test modules in `performance-test/*/modules/`

### Testing Structure
- `tests/` - Main test suite with comprehensive coverage
- `compatibility-test/` - Compatibility testing with different environments
- `performance-test/` - Benchmarking and performance analysis
- Inventory files: `inventory.yml`, `inventory2.yml`, `inventory3.yml`

## Development Environment

### Dependencies
- Python 3.13+ required (specified in pyproject.toml)
- Key dependencies: asyncssh, pyyaml, click, jinja2, aiomultiprocess
- Dev dependencies: pytest, black, isort, mypy, ruff

### Performance Focus
The project includes extensive performance testing infrastructure comparing FTL against Ansible 2.10.9. Results and analysis are documented in Jupyter notebooks in the `blog/` directory.