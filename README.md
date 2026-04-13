# python-template

A Copier template for Python libraries/projects.

**Scaffolded project includes**

- **uv** — env, sync, run
- **Copier** — generate/update from this template
- **Hatchling** + **uv-dynamic-versioning** — build, version from git
- **Ruff** — lint + format
- **ty** — type check (`ty check`)
- **pytest** + **pytest-sugar** — tests
- **codespell** — spelling (via `devtools/lint.py`)
- **MkDocs** + **Material for MkDocs** — docs (`mkdocs serve` / `build`)
- **rich** + **funlog** — devtools lint script output
- **Makefile** — `install`, `lint`, `test`, `docs`, `docs-build`, `build`, `clean`, `upgrade`
- **GitHub Actions** — CI (lint, pytest, strict docs build); publish workflow for PyPI (OIDC)
