# python-template

A Copier template for Python libraries/projects with a modern, `uv`-first workflow.

## Quickstart

### 1) Install tools

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first.
Then run Copier through `uvx` (no global install required).

### 2) Generate a project

Into a new folder:

```shell
uvx copier copy https://github.com/MFDI-hub/python-template my-package
cd my-package
```

Into the current folder (an empty git repo you already created on GitHub, for example):

```shell
uvx copier copy https://github.com/MFDI-hub/python-template .
```

Copier will prompt if a file already exists (`.gitignore` is a common conflict). Answer `Yes` to overwrite, or `No` to keep what is there. Do not run this inside the `python-template` source repo itself.

### 3) Start developing

```shell
make install   # uv sync + pre-commit install
make lint
make test
```

## Updating an existing project from the template

In a project generated from this template:

```shell
uvx copier update
```

## Scaffolded project includes

### Core

- **uv** - env, sync, run, build, publish
- **Copier** - generate/update from this template
- **Hatchling** + **uv-dynamic-versioning** - build, version from git tags
- **Ruff** - lint + format
- **ty** - type check (`ty check`)
- **pytest** + **pytest-sugar** - tests
- **codespell** - spelling (via `devtools/lint.py`)
- **MkDocs** + **Material for MkDocs** - docs (`mkdocs serve` / `build`)
- **rich** + **funlog** - devtools lint script output
- **Makefile** - `install`, `lint`, `test`, `docs`, `docs-build`, `build`, `clean`, `upgrade`, `pre-commit`
- **GitHub Actions** - CI (lint, pytest+coverage, docs, Trivy) and PyPI publish (OIDC)

### Quality & testing

- **pre-commit** - git hooks (ruff, codespell, ty, vulture)
- **pytest-cov** - coverage reports in local/`make test` and CI
- **pytest-xdist** - parallel tests (`-n auto`)
- **vulture** - dead code detection
- **commitizen** - Conventional Commits (`cz commit`)

### Security & deps

- **Dependabot** - weekly updates for Actions + Python deps
- **Trivy** - filesystem vulnerability scan in CI

### Release & docs hosting

- **semantic-release** - auto GitHub Releases from Conventional Commits (`.releaserc.yml` + `release.yml`)
- **Read the Docs** - `.readthedocs.yaml` + `docs/requirements-rtd.txt`

### DevEx

- **devcontainer.json** - Codespaces / VS Code Dev Containers
- **VS Code Tasks** - install, lint, test, docs, build
- **Optional extras** - `structlog` + `tqdm` via `uv sync --extra observability`
- Documented: **act** (local Actions), **httpie** (`uvx httpie`), GitHub milestones/projects
