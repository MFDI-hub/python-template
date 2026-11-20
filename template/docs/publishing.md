## Publishing Releases

This is how to publish a Python package to [**PyPI**](https://pypi.org/) from GitHub
Actions, when using the
[**python-template**](https://github.com/MFDI-hub/python-template) template.

Thanks to
[the dynamic versioning plugin](https://github.com/ninoseki/uv-dynamic-versioning/),
the [`release.yml`](https://github.com/MFDI-hub/python-template/blob/main/template/.github/workflows/release.yml)
workflow (semantic-release), and the [`publish.yml`](https://github.com/MFDI-hub/python-template/blob/main/template/.github/workflows/publish.yml)
workflow, tagged GitHub Releases publish the matching version to PyPI.

You can release in either way:

1. **Automatic (recommended):** push Conventional Commits to `main`/`master`.
   `release.yml` runs semantic-release, which creates a GitHub Release and a
   `vX.Y.Z` tag when commits warrant a bump. It then dispatches `publish.yml`
   on that tag.
2. **Manual:** create a tagged release yourself in the GitHub UI or with `gh`
   (below). That `release: published` event starts `publish.yml`.

Why the automatic path dispatches instead of waiting for the release event:
GitHub does not start a new workflow from an event created with the default
`GITHUB_TOKEN`. semantic-release uses that token, so the release it creates
never triggers `publish.yml` on its own. `workflow_dispatch` is one of the two
exceptions, which is why `release.yml` calls `gh workflow run`. Leave that job
on `GITHUB_TOKEN`. A PAT or a GitHub App token would also fire the release
event, and `publish.yml` would run twice.

`publish.yml` can also be started with **Run workflow**. Start it from the release
tag (the workflow input defaults to PyPI; choose TestPyPI for a dry upload).
A dispatch from a branch has no `vX.Y.Z` tag, so uv-dynamic-versioning produces
a local version that PyPI rejects.

### First-Time Setup

This part is a little confusing the first time.
Here is the simplest way to do it.
For the purposes of this example replace OWNER and PROJECT with the right values.

**Note:** These steps assume you already have a GitHub repo with your code pushed. If
you're setting up manually, create an **empty** GitHub repo (no
README, no .gitignore, no license — the template already provides these) and push your
code to it. See the
[python-template README](https://github.com/MFDI-hub/python-template)
for Copier usage and repo layout.

1. **Get a PyPI account** at [pypi.org](https://pypi.org/) and sign in.

2. **Pick a name for the project** that isn’t already taken.

   - Go to `https://pypi.org/project/PROJECT` to see if another project with that name
     already exists.

   - If needed, update your `pyproject.toml` with the correct name.

3. **Authorize** your repository to publish to PyPI:

   - In the GitHub repo, create an Environment named `pypi`
     (**Settings → Environments → New environment**). Optional: add required
     reviewers so a publish waits for approval. The name has to match the
     `environment:` key in `publish.yml`.

   - Go to [the publishing settings page](https://pypi.org/manage/account/publishing/).

   - Find “Trusted Publisher Management” and register your GitHub repo as a new
     “pending” trusted publisher.

   - Enter the project name, repo owner, repo name, workflow filename
     `publish.yml`, and environment name `pypi`.

     The workflow filename is `publish.yml`, including for automatic releases.
     `release.yml` only dispatches it. PyPI does not accept a reusable workflow
     as the trusted publisher, so the publish job stays in `publish.yml`.

   - **TestPyPI (optional).** Repeat the trusted-publisher step on
     [test.pypi.org](https://test.pypi.org/manage/account/publishing/) and create
     a GitHub Environment named `testpypi`. Then use **Run workflow** on
     `publish.yml` and choose `testpypi`. That run uploads to
     `https://test.pypi.org/legacy/` and does not touch production PyPI.

4. **Create a first release** so versioning starts on `0.x` (optional but recommended):

   semantic-release’s first release is `1.0.0` if no tags exist. To stay on `0.x`, create
   an initial tag once after setup:

   ```shell
   git tag v0.1.0
   git push origin v0.1.0
   gh release create v0.1.0 --generate-notes
   ```

   Later bumps follow Conventional Commits automatically.

5. **Confirm it publishes to PyPI**

   - Watch `release.yml` and the `publish.yml` run it starts (or the run started
     by a manual release) in the GitHub Actions tab.

   - If it succeeds, you should see it appear at `https://pypi.org/project/PROJECT`.

### What the publish job checks

`publish.yml` tests the tree, builds with `uv build --no-sources` (so the wheel
does not depend on a local path), imports the package from that wheel, then
uploads with `uv publish --trusted-publishing always`.

`uv publish` uploads attestation files that are already next to the artifacts.
It does not generate them. PyPI provenance therefore stays absent unless you add
a generation step (for example `actions/attest-build-provenance`) or switch the
upload to `pypa/gh-action-pypi-publish`, which can attest as it publishes. The
trusted-publisher workflow filename would still be `publish.yml` if that step
lives in this file.

### Publishing Subsequent Releases

Follow this checklist for each new release.

#### Pre-Release Checklist

1. **Verify all changes are committed and pushed:**

   ```shell
   git status
   git log origin/main..HEAD  # should be empty if pushed
   ```

2. **Run linting and tests locally:**

   ```shell
   make lint
   make test
   ```

3. **Confirm CI is passing:**

   ```shell
   gh run list --limit 3
   ```

   Or check the Actions tab on GitHub.

4. **Determine the new version number** (manual releases only):

   ```shell
   # Check current/latest version:
   gh release list --limit 1
   ```

   Use [semantic versioning](https://semver.org/) / Conventional Commits:

   - **fix:** → patch (e.g. `v0.5.8` → `v0.5.9`)
   - **feat:** → minor (e.g. `v0.5.9` → `v0.6.0`)
   - **BREAKING CHANGE** / `!` → major (e.g. `v0.6.0` → `v1.0.0`)

#### Create the Release

5. **Automatic:** merge Conventional Commits to `main` and let `release.yml` create the
   GitHub Release and dispatch `publish.yml`. If the release exists but the
   upload failed, re-run `publish.yml` from the tag. Re-running `release.yml`
   does not publish again: semantic-release finds nothing new to release and
   skips the dispatch.

6. **Manual — create the release with `gh`:**

   ```shell
   NEW_TAG="vX.Y.Z"  # Replace with actual version
   LAST_TAG=$(gh release list --limit 1 --json tagName -q '.[0].tagName')
   
   gh release create "${NEW_TAG}" \
     --title "${NEW_TAG}" \
     --notes "$(cat <<'EOF'
   ## What's Changed
   
   [Summarize changes here--see format guide below]
   
   ### Full Changelog
   
   https://github.com/OWNER/PROJECT/compare/${LAST_TAG}...${NEW_TAG}
   EOF
   )"
   ```

   Alternatively, use `--generate-notes` for GitHub’s auto-generated notes, or
   `--notes-file FILENAME` to read from a file.

7. **Verify the release published successfully:**

   ```shell
   # Check the release workflow:
   gh run list --workflow=publish.yml --limit 1
   
   # Verify on PyPI (may take a minute):
   # https://pypi.org/project/PROJECT
   ```

### Release Notes Format

Use this structure for release notes (manual releases):

```markdown
## What's Changed

### Bug Fixes

**Short title of fix**

Description of what was fixed and why it matters.

### New Features

**Short title of feature**

Description of the new capability.

### Breaking Changes

**Short title of breaking change**

Description of what changed and how to migrate.

### Full Changelog

https://github.com/OWNER/PROJECT/compare/vPREVIOUS...vNEW
```

Guidelines:

- Use `## What's Changed` as the top-level heading.

- Group changes under `### Bug Fixes`, `### New Features`, `### Breaking Changes`, etc.
  as appropriate.

- Use `**bold**` for short titles of individual changes.

- Include technical details only when helpful for users.

- Always include the Full Changelog compare link at the end.

- For small releases, a simple bullet list is acceptable instead of full sections.

* * *

*This file was built with
[python-template](https://github.com/MFDI-hub/python-template).*
