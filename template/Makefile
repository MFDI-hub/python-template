# Makefile for easy development workflows.
# See docs/development.md for docs.
# Note GitHub Actions call uv directly, not this Makefile.

.DEFAULT_GOAL := default

.PHONY: default install lint test docs docs-build upgrade build clean

default: install lint test 

install:
	uv sync --all-extras

lint:
	uv run python devtools/lint.py

test:
	uv run pytest

docs:
	uv run mkdocs serve

docs-build:
	uv run mkdocs build

upgrade:
	uv sync --upgrade --all-extras --dev

build:
	uv build

clean:
	-rm -rf dist/
	-rm -rf site/
	-rm -rf *.egg-info/
	-rm -rf .pytest_cache/
	-rm -rf .mypy_cache/
	-rm -rf .venv/
	-find . -type d -name "__pycache__" -exec rm -rf {} +
