"""Guard the copier.yml contract that the repo depends on."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _copier_yml() -> str:
    return (ROOT / "copier.yml").read_text(encoding="utf-8")


def test_copier_yml_declares_required_questions() -> None:
    text = _copier_yml()
    for question in (
        "package_name",
        "package_module",
        "package_description",
        "package_author_name",
        "package_author_email",
        "package_github_org",
        "copyright_year",
    ):
        assert re.search(rf"^{question}:", text, re.MULTILINE), question


def test_package_module_default_has_no_hyphens() -> None:
    text = _copier_yml()
    default_line = next(
        line
        for line in text.splitlines()
        if line.startswith("    default:") and "package_name" in line
    )
    assert "replace('-', '_')" in default_line


def test_template_requires_same_python_as_repo() -> None:
    pyproject = (ROOT / "template" / "pyproject.toml.jinja").read_text(encoding="utf-8")
    repo = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'requires-python = ">=([0-9.]+)"', pyproject)
    assert m is not None, "template pyproject must pin requires-python"
    minor = m.group(1)
    assert f'python-version = "{minor}"' in pyproject, "ty/ruff python-version must match"
    assert f'target-version = "py{minor.replace(".", "")}"' in pyproject
    assert f'requires-python = ">={minor}"' in repo


def test_ci_matrix_matches_requires_python() -> None:
    ci = (ROOT / "template" / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pyproject = (ROOT / "template" / "pyproject.toml.jinja").read_text(encoding="utf-8")
    requires_python = re.search(r'requires-python = ">=([0-9.]+)"', pyproject)
    assert requires_python is not None
    minor = requires_python.group(1)
    matrix = re.search(r"python-version: \[(.*?)\]", ci)
    assert matrix, "ci.yml must define a python-version matrix"
    versions = [v.strip().strip('"') for v in matrix.group(1).split(",")]
    assert versions[0] == minor, f"matrix starts at {versions[0]}, requires-python is >={minor}"


def test_copyright_year_defaults_to_the_current_year() -> None:
    text = _copier_yml()
    assert "jinja2_time.TimeExtension" in text
    assert "{% now 'utc', '%Y' %}" in text


def test_copyright_year_tag_renders_a_year() -> None:
    from jinja2 import Environment
    from jinja2_time import TimeExtension

    env = Environment(autoescape=True, extensions=[TimeExtension])
    year = env.from_string("{% now 'utc', '%Y' %}").render()
    assert len(year) == 4
    assert year.isdigit()


def test_workflows_pin_one_uv_version() -> None:
    versions: set[str] = set()
    workflows = list((ROOT / "template" / ".github" / "workflows").glob("*.yml"))
    workflows.append(ROOT / ".github" / "workflows" / "ci.yml")
    for workflow in workflows:
        found = re.findall(r'version: "(\d+\.\d+\.\d+)"', workflow.read_text(encoding="utf-8"))
        versions.update(found)
    assert versions == {"0.13.8"}


def test_setup_uv_is_pinned_to_a_full_version() -> None:
    # From v8 on, astral-sh/setup-uv only resolves full tags like @v10.3.3.
    workflows = list((ROOT / "template" / ".github" / "workflows").glob("*.yml"))
    workflows.append(ROOT / ".github" / "workflows" / "ci.yml")
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        for ref in re.findall(r"astral-sh/setup-uv@(\S+)", text):
            assert re.fullmatch(r"v\d+\.\d+\.\d+", ref), (
                f"{workflow.name}: @{ref} is not a full version"
            )
