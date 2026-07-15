# Makefile for easy development workflows.
# See docs/development.md for docs.
# Note GitHub Actions call uv directly, not this Makefile.

.DEFAULT_GOAL := default

.PHONY: default install lint test docs docs-build upgrade build clean pre-commit

default: install lint test 

install:
	uv sync --all-extras
	uv run pre-commit install

lint:
	uv run python devtools/lint.py

test:
	uv run pytest -n auto --cov --cov-report=term-missing

docs:
	uv run mkdocs serve

docs-build:
	uv run mkdocs build --strict

upgrade:
	uv sync --upgrade --all-extras --dev

build:
	uv build

pre-commit:
	uv run pre-commit run --all-files

clean:
	-rm -rf dist/
	-rm -rf site/
	-rm -rf *.egg-info/
	-rm -rf .pytest_cache/
	-rm -rf .mypy_cache/
	-rm -rf .ruff_cache/
	-rm -rf .coverage
	-rm -rf coverage.xml
	-rm -rf htmlcov/
	-rm -rf .venv/
	-find . -type d -name "__pycache__" -exec rm -rf {} +
