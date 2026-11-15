# Updating This Template

This doc covers the full cycle for keeping the
[python-template](https://github.com/MFDI-hub/python-template) template's dependencies
and tools up to date, then verifying the changes end-to-end.

There are two repos involved:

- **Template repo** (`MFDI-hub/python-template`): The Copier template source. All version
  changes start here. `.github/workflows/ci.yml` renders the template and runs lint and
  tests on a generated project. Downstream projects still cover the full Python matrix.
- **Downstream project(s)**: Projects created from the template (your libraries or apps on
  GitHub under `MFDI-hub` or elsewhere). These pull updates via `copier update` and have CI
  configured to run linting and tests across the Python version matrix.

## Step 1: Check Latest Versions

From the template repo, see what is current on PyPI:

```shell
uvx --from "pip>=24" pip index versions ruff ty pytest pre-commit codespell \
  vulture commitizen mkdocs mkdocs-material funlog rich structlog tqdm
```

Also check for new major versions of the GitHub Actions used by the workflows:

- `actions/checkout` — <https://github.com/actions/checkout/releases>
- `astral-sh/setup-uv` — <https://github.com/astral-sh/setup-uv/releases>
  (pin a **full** version: from v8 on, major tags such as `@v10` do not resolve)
- `actions/setup-node`, `cycjimmy/semantic-release-action`
- `actions/configure-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages`

And decide whether a new Python version should join the CI matrix — the matrix,
the classifiers in `template/pyproject.toml.jinja`, `[tool.ruff] target-version`,
`[tool.ty.environment] python-version`, and `requires-python` must all agree.

## Step 2: Update the Template Files

Edit these as needed:

- **Dev dependency pins** in `template/pyproject.toml.jinja` (`[dependency-groups]`)
- **uv version** in `template/.github/workflows/*.yml` (the `version:` input of
  `astral-sh/setup-uv`) and the **Actions versions** in the same files
- **Python version** in `requires-python`, classifiers, the CI matrix,
  `.python-version`, `[tool.ruff] target-version` and `[tool.ty.environment]`
- **Pre-commit hook `rev:` values** in `template/.pre-commit-config.yaml`

## Step 2b: Verify the Template Renders and Passes Its Own Checks

This repo ships Jinja, so nothing above is caught by ordinary lint. Run the gate,
which renders the template twice, validates the generated files, and is the only
thing that catches a broken `pyproject.toml.jinja` or a stray `${{ }}`:

```shell
git add -A                      # the gate renders the git index
uv run --with copier python repo_check.py

# Then lint/test the intended output as a real project:
uv run --with copier python repo_check.py --keep /tmp/tmpl
cd /tmp/tmpl/dash-name && uv sync
uv run python devtools/lint.py && uv run pytest -n auto --cov
uv run mkdocs build --strict && uv build
```

Also lint this repo's own tooling: `uv run ruff check .` and `uv run pytest`.

## Step 3: Commit, Tag, and Push the Template

Copier requires a new Git tag to recognize an update. Increment the version from the
last tag (check with `git tag -l | sort -V | tail -1`):

```shell
git add -A
git commit -m "Update dependencies and tool versions."
git tag v0.X.Y
git push origin main --tags
```

## Step 4: Update a Downstream Project

In a downstream project (e.g. `my-package`), pull the template update.
The working tree must be clean before running `copier update`:

```shell
# Ensure a clean working tree:
git stash --include-untracked  # if needed

# Pull template changes:
uvx --with jinja2-time copier update --defaults --trust --vcs-ref HEAD
# Drop --vcs-ref HEAD once you want to follow only released template tags.

# Restore stash if needed:
git stash pop
```

## Step 5: Verify Locally

After the copier update, confirm everything works locally:

```shell
uv sync --upgrade
uv run pre-commit install
uv run python devtools/lint.py
uv run pytest -n auto --cov --cov-report=term-missing
uv run mkdocs build --strict
uv build
```

## Step 6: Push Downstream and Confirm CI

Commit and push the downstream project:

```shell
git add -A
git commit -m "Update from MFDI-hub/python-template vX.Y.Z."
git push origin main
```

Then check that **CI passes on GitHub** for this repo and for the downstream project.
This repo's workflow renders the template once. Downstream CI runs the full lint and
test suite across the Python matrix (3.11, 3.12, 3.13, 3.14, 3.15).

If CI fails, fix issues in the template repo and repeat from Step 2.

## Step 7: Create a Release on the Template Repo

Once CI passes here and downstream, create a GitHub release on the template repo.
Downstream CI is still the check that covers every Python version in the matrix.

```shell
# From the template repo:
gh release create v0.X.Y --title "v0.X.Y" --notes "$(cat <<'EOF'
## What's Changed

- **Updated dev dependencies**: ruff X.Y.Z, ty X.Y.Z, mkdocs X.Y.Z, etc.
- **Updated uv** to X.Y.Z in CI workflows
- Any other changes

**Full Changelog**: https://github.com/MFDI-hub/python-template/compare/vPREVIOUS...v0.X.Y
EOF
)"
```

This makes the release visible to users and provides clear release notes on what was
updated.