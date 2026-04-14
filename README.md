# python-template

A Copier template for Python libraries/projects with a modern, `uv`-first workflow.

## Quickstart

### 1) Install tools

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first.
Then run Copier through `uvx` (no global install required).

### 2) Generate a project

```shell
uvx copier copy https://github.com/MFDI-hub/python-template my-package
cd my-package
```

### 3) Start developing

```shell
uv sync --all-extras
uv run pytest
uv run python devtools/lint.py
```

## Updating an existing project from the template

In a project generated from this template:

```shell
uvx copier update
```

## Scaffolded project includes

- **uv** - env, sync, run, build, publish
- **Copier** - generate/update from this template
- **Hatchling** + **uv-dynamic-versioning** - build, version from git tags
- **Ruff** - lint + format
- **ty** - type check (`ty check`)
- **pytest** + **pytest-sugar** - tests
- **codespell** - spelling (via `devtools/lint.py`)
- **MkDocs** + **Material for MkDocs** - docs (`mkdocs serve` / `build`)
- **rich** + **funlog** - devtools lint script output
- **Makefile** - `install`, `lint`, `test`, `docs`, `docs-build`, `build`, `clean`, `upgrade`
- **GitHub Actions** - CI (lint, pytest, strict docs build) and publish workflow for PyPI (OIDC)
