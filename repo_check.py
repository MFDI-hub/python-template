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
    "src/{m}/py.typed",
    "tests/test_placeholder.py",
    "devtools/lint.py",
    "docs/development.md",
    ".github/workflows/ci.yml",
    ".github/workflows/publish.yml",
    ".vscode/settings.json",
    ".devcontainer/devcontainer.json",
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
        "package_github_org=demo-org",
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


def check_pyproject(dest: Path, _answers: Answers) -> None:
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
    if project["scripts"].get(module) != f"{module}:main":
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
    if data["tool"]["pytest"]["ini_options"]["testpaths"] != ["tests"]:
        raise CheckFailed("[tool.pytest.ini_options] testpaths must be ['tests']")

    for group in ("docs", "property-testing", "profiling"):
        if group not in groups:
            raise CheckFailed(f"missing dependency group {group!r}")
    if not any("mkdocstrings" in d for d in groups["docs"]):
        raise CheckFailed("docs group must include mkdocstrings")

    defaults = data["tool"]["uv"].get("default-groups")
    if defaults != ["dev", "docs"]:
        # Without this, splitting docs out of dev silently stops `uv sync`
        # installing MkDocs, and every `uv run mkdocs ...` fails.
        raise CheckFailed(f"[tool.uv] default-groups should be ['dev', 'docs'], got {defaults!r}")

    if "deptry" not in data["tool"]:
        raise CheckFailed("missing [tool.deptry] configuration")
    if "S" not in ruff["lint"]["select"]:
        raise CheckFailed("ruff should select the S (bandit) security rules")
    if data["tool"]["coverage"]["report"].get("fail_under") != 80:
        raise CheckFailed("[tool.coverage.report] fail_under should be 80")

    if not any("uv-dynamic-versioning" in req for req in data["build-system"]["requires"]):
        raise CheckFailed("build-system requires uv-dynamic-versioning")

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


def check_json_files(dest: Path, _answers: Answers) -> None:
    """Editor and devcontainer JSON must parse comments stripped."""
    for rel in (".vscode/settings.json", ".vscode/tasks.json", ".devcontainer/devcontainer.json"):
        text = (dest / rel).read_text(encoding="utf-8")
        try:
            json.loads(strip_jsonc(text))
        except json.JSONDecodeError as exc:
            raise CheckFailed(f"{rel} is not valid JSON: {exc}") from exc


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
