# Makefile for alembic-viewer development
.PHONY: help run lint lint-fix format format-check typecheck test test-cov check build build-exe clean install dev

# Default target
help:
	@echo "Alembic Viewer - Development Commands"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup:"
	@echo "  install      Install production dependencies"
	@echo "  dev          Install all dependencies (including dev)"
	@echo ""
	@echo "Run:"
	@echo "  run          Run the application"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint         Run linter (ruff check)"
	@echo "  lint-fix     Run linter and fix issues"
	@echo "  format       Format code (ruff format)"
	@echo "  format-check Check code formatting"
	@echo "  typecheck    Run type checker (pyright)"
	@echo "  check        Run all quality checks (lint + format-check + typecheck)"
	@echo ""
	@echo "Testing:"
	@echo "  test         Run tests"
	@echo "  test-cov     Run tests with coverage report"
	@echo ""
	@echo "Build:"
	@echo "  build        Build Python package"
	@echo "  build-exe    Build standalone executable (GUI mode)"
	@echo "  build-exe-console  Build standalone executable (console mode)"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean        Remove build artifacts"

# Setup
install:
	uv sync

dev:
	uv sync --dev

# Run
run:
	uv run python alembic_viewer.py

# Code Quality
lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

typecheck:
	uv run pyright

check: lint format-check typecheck

# Testing
test:
	uv run pytest

test-cov:
	uv run pytest --cov=. --cov-report=html --cov-report=term-missing

# Build
build:
	uv build

build-exe:
	uv run pyinstaller --noconfirm AlembicViewer.spec

build-exe-console:
	uv run pyinstaller --onefile --name AlembicViewer --icon=alembic_viewer.ico --noconfirm alembic_viewer.py

# Maintenance
clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .ruff_cache/ htmlcov/ .coverage
	rm -rf *.spec
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
