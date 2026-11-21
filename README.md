# python-template

A [Copier](https://copier.readthedocs.io/) template for Python libraries and apps with a
modern, [`uv`](https://docs.astral.sh/uv/)-first workflow, [Ruff](https://docs.astral.sh/ruff/),
and [ty](https://docs.astral.sh/ty/) type checking.

## Quickstart

### 1) Install tools

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/) first.
Then run Copier through `uvx` (no global install required). Nothing else is needed:
`uv sync` inside the generated project provides Python and every tool.

### 2) Generate a project

Into a new folder:

```shell
uvx --with jinja2-time copier copy --trust --vcs-ref HEAD https://github.com/MFDI-hub/python-template my-package
cd my-package
```

Into the current folder (for example an empty git repo you already created on GitHub):

```shell
uvx --with jinja2-time copier copy --trust --vcs-ref HEAD https://github.com/MFDI-hub/python-template .
```

`jinja2-time` supplies the copyright-year default. `--trust` allows the template's
git-init task and that Jinja extension.

### 3) Start developing

```shell
uv sync
uv run pre-commit install && uv run pre-commit install --hook-type commit-msg
uv run pytest -n auto --cov   # or: make install && make
```

> **Why `--vcs-ref HEAD`?** Copier reads the template's tags with `git ls-remote`. If no
> `vX.Y.Z` tag exists yet it falls back to HEAD — but the `git` call can still fail on
> machines where Git cannot reach the template (offline, corporate proxy, SSH prompts).
> Passing `--vcs-ref HEAD` makes Copier skip tag resolution entirely and use the latest
> main. Once this template publishes a release tag, you can drop the flag.

Copier prompts if a file already exists (`.gitignore` is a common conflict). Answer
`Yes` to overwrite or `No` to keep it. Do not run `copier copy` inside this
`python-template` source repo itself.

## Updating an existing project from the template

```shell
uvx --with jinja2-time copier update --trust --vcs-ref HEAD
```

The working tree must be clean first. Your answers are re-used; conflicts are written
into the files and must be resolved and committed.

## Working on this template

This repo is itself a small Python project, so templates are checked before they ship:

```shell
uv sync
uv run ruff check .          # lint this repo's tooling
uv run pytest                # tests for the repo tooling
python repo_check.py         # render the template + verify every generated file
```

## Scaffolded project includes

### Core

- **uv** — env, lockfile, `uv run`, `uv build`, `uv publish`
- **Copier** — generate/update from this template
- **Hatchling** + **uv-dynamic-versioning** — build, version from git tags
- **Ruff** — lint + format (single tool, single config in `pyproject.toml`)
- **ty** — type checking (`[tool.ty]` in `pyproject.toml`)
- **pytest** + **pytest-cov** + **pytest-xdist** — tests, coverage, parallelism
- **MkDocs** + **Material for MkDocs** — docs
- **Makefile** — `install`, `lint`, `test`, `docs`, `build`, `clean`, `upgrade`
- **[tool-shed](https://github.com/MFDI-hub/tool-shed)** — dev-group CLI tools (`sync_chosen_files`, `watch_run`, and the rest), installed from PyPI as `tools-shed`
- **GitHub Actions** — CI (lint, pytest matrix, docs, Trivy, uv audit) and PyPI publish (OIDC)



### Quality & testing

- **ruff** — lint **and** format, including the `S` (flake8-bandit) security rules
- **ty** — type checking
- **deptry** — flags unused, missing and misplaced dependencies
- **vulture** — dead code
- **codespell** — spelling
- **pytest** + **pytest-cov** (80% gate) + **pytest-xdist** + **pytest-sugar**
- **pytest-timeout**, **pytest-asyncio**, **pytest-mock** — hung tests, async tests, mocking
- **hypothesis** — property-based tests (opt-in `property-testing` group)
- **pre-commit** — git hooks (ruff, codespell, ty, vulture, deptry, commitizen)
- **commitizen** — Conventional Commits (`uv run cz commit`)

### Security & deps

- **Dependabot** — weekly updates for Actions and the uv lockfile
- **Trivy** — filesystem scan in CI
- **uv audit** — vulnerability audit of `uv.lock` (`make security` and CI)
- **deptry** — dependency hygiene on every lint run
- **ruff `S` rules** — bandit-equivalent security checks inline in the linter

### Release & docs hosting

- **MkDocs** + **Material** + **mkdocstrings** — docs with API reference generated from docstrings
- **semantic-release** — GitHub Releases from Conventional Commits; `release.yml` then dispatches `publish.yml` (a `GITHUB_TOKEN` release does not start that workflow on its own)
- **Read the Docs** and **GitHub Pages** configs

### Extras and optional groups

- `docs` — MkDocs stack (uv **default group**, so `uv sync` installs it)
- `property-testing` — `hypothesis` (`uv sync --group property-testing`)
- `profiling` — `py-spy` + `snakeviz` (`uv sync --group profiling`)
### DevEx

- **.python-version** — pins the default interpreter for `uv`
- **devcontainer.json** — Codespaces / VS Code Dev Containers
- **VS Code tasks + settings** — ruff format on save, ty, `install`/`lint`/`test` tasks

## License

MIT — see [LICENSE](LICENSE).