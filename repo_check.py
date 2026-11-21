"""Render this Copier template and verify the generated project.

Usage:  uv run --with copier python repo_check.py [--keep DIR]

This repository ships Jinja templates, so ordinary lint and tests only ever
see .jinja text. This gate renders the template for a couple of common answer
sets and validates what a user actually receives:

  * every file renders and keeps no leftover "{{" / "{%" tokens
  * the generated pyproject.toml parses and carries the promised config
  * GitHub Actions ${{ }} expressions in copied workflows survive intact
  * JSON files (VS Code, devcontainer) parse after comments are stripped

The template is copied to a scratch directory *without* its git metadata before
rendering, so Copier never clones the repo or resolves refs. That keeps the
gate hermetic: it verifies the working tree, including uncommitted edits.

Stdlib only: the caller supplies copier (e.g. uv run --with copier).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT = Path(__file__).resolve().parent

# Copier renders this file with {{ }} placeholders by design.
_SKIP_RENDER_CHECK = {".copier-answers.yml"}

# GitHub Actions expressions live only in the workflows, which are copied as-is.
_GHA_EXPR = re.compile(r"\$\{\{[^}]*\}\}")


@dataclass(frozen=True)
class Answers:
    """One answer set to render the template with."""

    label: str
    package_name: str
    package_module: str
    package_github_org: str = "demo-org"


ANSWER_SETS = (
    Answers("dash-name", "demo-pkg", "demo_pkg"),
    Answers("snake-name", "demo_pkg", "demo_pkg"),
)

# Paths every generated project must contain; {m} is the module name.
REQUIRED_FILES = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "Makefile",
    "mkdocs.yml",
    ".pre-commit-config.yaml",
    ".python-version",
    ".gitignore",
    ".copier-answers.yml",
    "src/{m}/__init__.py",
    "src/{m}/__main__.py",
    "src/{m}/py.typed",
    "tests/test_placeholder.py",
    "devtools/lint.py",
    "docs/development.md",
    ".github/workflows/ci.yml",
    ".github/workflows/publish.yml",
    ".github/workflows/release.yml",
    ".github/dependabot.yml",
    "CHANGELOG.md",
    ".vscode/settings.json",
    ".devcontainer/devcontainer.json",
)

# Dev, docs, and profiling tools that a generated project never imports.
# deptry reports each of them as DEP002 unless they are ignored.
_DEP002_REQUIRED = (
    "pytest",
    "pytest-cov",
    "pytest-xdist",
    "pytest-sugar",
    "pytest-timeout",
    "pytest-asyncio",
    "pytest-mock",
    "pytest-randomly",
    "pre-commit",
    "commitizen",
    "ruff",
    "ty",
    "codespell",
    "vulture",
    "deptry",
    "rich",
    "funlog",
    "mkdocs",
    "mkdocs-material",
    "mkdocs-git-revision-date-localized-plugin",
    "mkdocstrings",
    "hypothesis",
    "py-spy",
    "snakeviz",
    "tools-shed",
)


def remove_tree(path: Path) -> None:
    """Delete a tree, coping with the read-only files git writes.

    Git writes pack files and objects read-only, and on Windows `shutil.rmtree`
    cannot unlink those. Clear the write bit on each failing entry and retry.
    Anything still locked is left behind rather than raised: a stray scratch
    directory must not turn a passing verification into a stack trace.
    """

    def _on_error(func, target, _exc):
        with contextlib.suppress(OSError):
            Path(target).chmod(stat.S_IWRITE | stat.S_IREAD)
        with contextlib.suppress(OSError):
            func(target)

    kwargs = {"onexc": _on_error} if sys.version_info >= (3, 12) else {"onerror": _on_error}
    shutil.rmtree(path, **kwargs)


class CheckFailed(Exception):
    """A rendered project does not satisfy the template contract."""


def stage_template(dest: Path) -> Path:
    """Extract copier.yml and template/ into dest, without git metadata.

    Copier treats a local directory as a VCS template only when it *is* a git
    work tree; a plain directory is rendered in place. Taking the files from
    the git index also means new template files must be staged (`git add`, as
    the tests do) before they can ship, and build artifacts never leak in.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode != 0:
        raise CheckFailed(f"git ls-files failed (is this a git repo?): {listed.stderr.strip()}")

    selected = [
        name
        for name in listed.stdout.split("\0")
        if name == "copier.yml" or name.startswith("template/")
    ]
    if not selected:
        raise CheckFailed("no template files found in the git index; run git add first")

    for name in selected:
        blob = subprocess.run(
            ["git", "show", f":{name}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob.stdout)
    return dest


def render(staged: Path, answers: Answers, dest: Path) -> None:
    """Render the staged template into dest with the copier CLI."""
    cmd = [
        sys.executable,
        "-m",
        "copier",
        "copy",
        "--defaults",
        "--quiet",
        # Required because copier.yml declares _tasks (git init + commit).
        "--trust",
        "-d",
        f"package_name={answers.package_name}",
        "-d",
        f"package_module={answers.package_module}",
        "-d",
        "package_description=Demo package for template verification.",
        "-d",
        "package_author_name=Demo Author",
        "-d",
        "package_author_email=demo@example.com",
        "-d",
        f"package_github_org={answers.package_github_org}",
        "-d",
        "copyright_year=2026",
        str(staged),
        str(dest),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-15:]
        raise CheckFailed("copier copy failed:\n" + "\n".join(tail))


def module_of(dest: Path) -> str:
    """Return the module name from the single directory generated under src/."""
    modules = [p.name for p in (dest / "src").iterdir() if p.is_dir()]
    if len(modules) != 1:
        raise CheckFailed(f"expected one module under src/, found {modules}")
    return modules[0]


def check_files_exist(dest: Path, _answers: Answers) -> None:
    """Files users rely on must actually be generated."""
    module = module_of(dest)
    missing = [p for p in REQUIRED_FILES if not (dest / p.format(m=module)).exists()]
    if missing:
        raise CheckFailed(f"missing generated files: {missing}")


def check_no_jinja_leftovers(dest: Path, _answers: Answers) -> None:
    """Rendered files must be free of Jinja syntax Copier failed to process."""
    problems: list[str] = []
    for path in sorted(dest.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        rel = path.relative_to(dest)
        if rel.as_posix() in _SKIP_RENDER_CHECK:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "{{" not in text and "{%" not in text:
            continue
        # Workflows are copied verbatim, so their ${{ matrix.x }} is expected.
        if rel.parts[:2] == (".github", "workflows"):
            text = _GHA_EXPR.sub("", text)
        if "{{" in text or "{%" in text:
            problems.append(rel.as_posix())
    if problems:
        raise CheckFailed(f"unrendered Jinja syntax in: {problems}")


def check_pyproject(dest: Path, answers: Answers) -> None:
    """The generated pyproject.toml must be valid and carry the promised config."""
    data = tomllib.loads((dest / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    module = module_of(dest)

    if project["license"] != "MIT":
        raise CheckFailed("project.license should be the SPDX string 'MIT'")
    if project["requires-python"] != ">=3.11":
        raise CheckFailed(f"unexpected requires-python: {project['requires-python']}")
    if project.get("dynamic") != ["version"]:
        raise CheckFailed("project.dynamic must be ['version']")
    if project["scripts"].get(module) != f"{module}.{module}:main":
        raise CheckFailed(f"console script for {module} is wrong: {project['scripts']}")

    groups = data["dependency-groups"]
    dev = [d.lower() for d in groups["dev"]]
    for tool in (
        "ruff",
        "ty",
        "pytest",
        "codespell",
        "pre-commit",
        "vulture",
        "deptry",
        "pytest-asyncio",
        "pytest-timeout",
        "pytest-randomly",
        "tools-shed",
    ):
        if not any(d.startswith(tool) for d in dev):
            raise CheckFailed(f"dev dependency group is missing {tool}")

    ruff = data["tool"]["ruff"]
    if "line-length" not in ruff or "target-version" not in ruff:
        raise CheckFailed("[tool.ruff] needs line-length and target-version")
    if not ruff["lint"]["select"]:
        raise CheckFailed("[tool.ruff.lint] select must not be empty")
    ty_python = data["tool"].get("ty", {}).get("environment", {}).get("python-version")
    if ty_python != "3.11":
        # ty's schema puts python-version under [tool.ty.environment], not [tool.ty].
        raise CheckFailed(
            f"[tool.ty.environment] python-version must match requires-python, got {ty_python!r}"
        )
    pytest_ini = data["tool"]["pytest"]["ini_options"]
    if pytest_ini["testpaths"] != ["tests"]:
        raise CheckFailed("[tool.pytest.ini_options] testpaths must be ['tests']")
    if pytest_ini.get("python_files") != ["test_*.py", "*_test.py"]:
        raise CheckFailed("pytest python_files must be the default test-module globs")
    if "pythonpath" in pytest_ini:
        raise CheckFailed("drop pytest pythonpath; uv sync installs the project under test")

    for group in ("docs", "property-testing", "profiling"):
        if group not in groups:
            raise CheckFailed(f"missing dependency group {group!r}")
    if not any("mkdocstrings" in d for d in groups["docs"]):
        raise CheckFailed("docs group must include mkdocstrings")

    uv_tool = data["tool"]["uv"]
    defaults = uv_tool.get("default-groups")
    if defaults != ["dev", "docs"]:
        # Without this, splitting docs out of dev silently stops `uv sync`
        # installing MkDocs, and every `uv run mkdocs ...` fails.
        raise CheckFailed(f"[tool.uv] default-groups should be ['dev', 'docs'], got {defaults!r}")
    git_keys = [
        item.get("git", {}) for item in uv_tool.get("cache-keys", []) if isinstance(item, dict)
    ]
    if not any(item.get("commit") and item.get("tags") for item in git_keys):
        raise CheckFailed("[tool.uv] cache-keys must include git commit and tags")
    if "scripts" in data["tool"]["uv"]:
        raise CheckFailed("[tool.uv.scripts] is not a uv feature; invoke scripts directly")

    if "deptry" not in data["tool"]:
        raise CheckFailed("missing [tool.deptry] configuration")
    ignored = data["tool"]["deptry"].get("per_rule_ignores", {}).get("DEP002", [])
    missing_ignores = [name for name in _DEP002_REQUIRED if name not in ignored]
    if missing_ignores:
        raise CheckFailed(f"DEP002 ignore list is missing {missing_ignores}")
    if "S" not in ruff["lint"]["select"]:
        raise CheckFailed("ruff should select the S (bandit) security rules")
    if "TC" not in ruff["lint"]["select"]:
        raise CheckFailed("ruff select must include TC")
    if "TCH" in ruff["lint"]["select"]:
        raise CheckFailed("ruff select still uses the retired TCH code")
    if data["tool"]["coverage"]["report"].get("fail_under") != 80:
        raise CheckFailed("[tool.coverage.report] fail_under should be 80")

    if not any("uv-dynamic-versioning" in req for req in data["build-system"]["requires"]):
        raise CheckFailed("build-system requires uv-dynamic-versioning")
    if data["tool"]["uv-dynamic-versioning"].get("fallback-version") != "0.0.0":
        raise CheckFailed('set [tool.uv-dynamic-versioning] fallback-version = "0.0.0"')

    docs_url = project.get("urls", {}).get("Documentation", "")
    expected_docs = f"https://{answers.package_github_org}.github.io/{answers.package_name}/"
    if docs_url != expected_docs:
        raise CheckFailed(f"Documentation URL should be {expected_docs}, got {docs_url!r}")

    _check_uv_accepts(dest)


def _check_uv_accepts(dest: Path) -> None:
    """Ask uv to parse pyproject.toml so invalid [tool.uv] values fail the gate.

    `tomllib` proves the TOML is well formed, not that uv understands it; a bad
    enum like add-bounds = ">=lower" otherwise only shows up on a user's first
    `uv sync`, as a warning that every tool reading the file then repeats.
    """
    if shutil.which("uv") is None:
        return  # uv is optional for this repo; CI installs it via setup-uv.
    result = subprocess.run(
        ["uv", "lock", "--offline", "--quiet"],
        cwd=dest,
        capture_output=True,
        text=True,
        check=False,
    )
    if "unknown variant" in result.stderr or "invalid" in result.stderr.lower():
        raise CheckFailed(f"uv rejects pyproject.toml: {result.stderr.strip()[:400]}")


def check_workflows(dest: Path, _answers: Answers) -> None:
    """GitHub Actions expressions must survive the copy untouched."""
    ci = (dest / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for expr in ("${{ matrix.os }}", "${{ matrix.python-version }}"):
        if expr not in ci:
            raise CheckFailed(f"ci.yml lost the GitHub Actions expression {expr}")
    if 'python-version: ["3.10"' in ci:
        raise CheckFailed("ci.yml still tests 3.10 while requires-python is >=3.11")
    if "devtools/lint.py --check" not in ci:
        raise CheckFailed("ci.yml must lint with --check so rewrites cannot hide failures")
    if "uv audit --locked" not in ci:
        raise CheckFailed("ci.yml must audit uv.lock with uv audit --locked")
    if "pip-audit" in ci:
        raise CheckFailed("ci.yml must audit with uv audit")
    if '"3.15"' not in ci:
        raise CheckFailed("ci.yml matrix must include Python 3.15")

    if "cancel-in-progress:" not in ci:
        raise CheckFailed("ci.yml must cancel superseded runs")
    if "timeout-minutes:" not in ci:
        raise CheckFailed("ci.yml jobs need a timeout")
    pinned = _unpinned_actions(dest)
    if pinned:
        raise CheckFailed(f"pin actions to a commit SHA: {pinned}")

    publish = (dest / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    if "enable-cache: false" not in publish:
        raise CheckFailed("publish.yml must leave the uv cache disabled")
    if "uv build --no-sources" not in publish:
        raise CheckFailed("publish.yml must build with uv build --no-sources")
    if "Smoke-test the wheel" not in publish:
        raise CheckFailed("publish.yml must import the built wheel before publishing")
    if "environment:" not in publish or "'pypi'" not in publish:
        raise CheckFailed("publish.yml must publish through a pypi GitHub environment")

    release = (dest / ".github/workflows/release.yml").read_text(encoding="utf-8")
    if "gh workflow run publish.yml" not in release:
        raise CheckFailed(
            "release.yml must dispatch publish.yml; a GITHUB_TOKEN release does not trigger it"
        )
    if "actions: write" not in release:
        raise CheckFailed("release.yml needs actions: write to dispatch publish.yml")

    dependabot = (dest / ".github/dependabot.yml").read_text(encoding="utf-8")
    if 'package-ecosystem: "uv"' not in dependabot:
        raise CheckFailed('dependabot must use package-ecosystem: "uv" so uv.lock updates')
    if re.search(r'package-ecosystem:\s*"?pip"?', dependabot):
        raise CheckFailed("dependabot pip ecosystem leaves uv.lock stale under --locked")

    makefile = (dest / "Makefile").read_text(encoding="utf-8")
    if "uv run sync-chosen-files" in makefile:
        raise CheckFailed("Makefile calls uv run sync-chosen-files; uv has no script table")
    if "uv run sync_chosen_files" not in makefile:
        raise CheckFailed("Makefile must invoke tools-shed via uv run sync_chosen_files")
    if "python scripts/sync_chosen_files.py" in makefile:
        raise CheckFailed("Makefile still calls the removed scripts/sync_chosen_files.py")
    if "pre-commit install --hook-type pre-push" not in makefile:
        raise CheckFailed("make install must register the pre-push hook")


def _unpinned_actions(dest: Path) -> list[str]:
    """Action refs that are still a mutable tag rather than a commit SHA."""
    problems: list[str] = []
    workflows = dest / ".github" / "workflows"
    for path in sorted(workflows.glob("*.yml")):
        for ref in re.findall(r"uses: [\w.-]+/[\w.-]+@(\S+)", path.read_text(encoding="utf-8")):
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                problems.append(f"{path.name}@{ref}")
    return problems


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments that sit outside of string literals."""
    out: list[str] = []
    i = 0
    in_string = False
    while i < len(text):
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
        elif ch == '"':
            in_string = True
            out.append(ch)
            i += 1
        elif text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def check_json_files(dest: Path, answers: Answers) -> None:
    """Editor and devcontainer JSON must parse comments stripped."""
    for rel in (".vscode/settings.json", ".vscode/tasks.json", ".devcontainer/devcontainer.json"):
        text = (dest / rel).read_text(encoding="utf-8")
        try:
            json.loads(strip_jsonc(text))
        except json.JSONDecodeError as exc:
            raise CheckFailed(f"{rel} is not valid JSON: {exc}") from exc

    devcontainer = (dest / ".devcontainer/devcontainer.json").read_text(encoding="utf-8")
    if "astral-sh/uv-feature" in devcontainer:
        raise CheckFailed("devcontainer references a uv feature Astral does not publish")
    if "ghcr.io/va-h/devcontainers-features/uv:1" not in devcontainer:
        raise CheckFailed("devcontainer must install uv from a published feature")

    module = module_of(dest)
    init_py = (dest / "src" / module / "__init__.py").read_text(encoding="utf-8")
    if f'version("{answers.package_name}")' not in init_py:
        raise CheckFailed("__version__ must come from importlib.metadata.version(package name)")
    if "PackageNotFoundError" not in init_py:
        raise CheckFailed("__version__ needs a PackageNotFoundError fallback")
    main_py = (dest / "src" / module / "__main__.py").read_text(encoding="utf-8")
    if "main()" not in main_py:
        raise CheckFailed("__main__.py must call main()")
    rtd = (dest / "docs" / "requirements-rtd.txt").read_text(encoding="utf-8")
    if "mkdocstrings" not in rtd:
        raise CheckFailed("docs/requirements-rtd.txt must install mkdocstrings")
    mkdocs = (dest / "mkdocs.yml").read_text(encoding="utf-8")
    if "paths: [src]" not in mkdocs:
        raise CheckFailed("mkdocs python handler needs paths: [src]")


CHECKS: tuple[Callable[[Path, Answers], None], ...] = (
    check_files_exist,
    check_no_jinja_leftovers,
    check_pyproject,
    check_workflows,
    check_json_files,
)


def verify(dest: Path, answers: Answers) -> None:
    """Run every structural check against one rendered project."""
    for check in CHECKS:
        check(dest, answers)


def main(argv: list[str] | None = None) -> int:
    """Render every answer set, verify it, and report."""
    parser = argparse.ArgumentParser(description="Render and verify the Copier template.")
    parser.add_argument("--keep", metavar="DIR", help="render into DIR and keep the output")
    args = parser.parse_args(argv)

    failures = 0
    # A plain, uniquely named directory inside the project: mkdtemp() can create
    # directories that Windows then refuses to write into under restrictive ACLs.
    workdir = ROOT / ".template-check" / f"run-{os.getpid()}"
    remove_tree(workdir)
    workdir.mkdir(parents=True)
    try:
        staged = stage_template(workdir / "template")
        for answers in ANSWER_SETS:
            target = Path(args.keep) / answers.label if args.keep else workdir / answers.label
            try:
                render(staged, answers, target)
                verify(target, answers)
            except CheckFailed as exc:
                failures += 1
                print(f"[FAIL] {answers.label}: {exc}", file=sys.stderr)
                if args.keep:
                    print(f"       kept rendered project at {target}", file=sys.stderr)
            else:
                print(f"[ok] {answers.label}: rendered and verified")
    finally:
        if not args.keep:
            remove_tree(workdir)
            if not workdir.exists():  # keep the repo tidy
                with contextlib.suppress(OSError):
                    workdir.parent.rmdir()

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
