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


def test_actions_are_pinned_to_a_commit_sha() -> None:
    # A version comment on the same line is what Dependabot's github-actions
    # ecosystem uses when it bumps a SHA pin.
    workflows = list((ROOT / "template" / ".github" / "workflows").glob("*.yml"))
    workflows.append(ROOT / ".github" / "workflows" / "ci.yml")
    found = False
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8")
        for line in text.splitlines():
            match = re.search(r"uses: [\w.-]+/[\w.-]+@(\S+)", line)
            if match is None:
                continue
            found = True
            ref = match.group(1)
            assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{workflow.name}: @{ref} is not a SHA"
            assert re.search(r"# v\d+\.\d+\.\d+\s*$", line), (
                f"{workflow.name}: {line.strip()} needs a trailing version comment"
            )
    assert found


def test_precommit_revs_match_pyproject_floors() -> None:
    pyproject = (ROOT / "template" / "pyproject.toml.jinja").read_text(encoding="utf-8")
    hooks = (ROOT / "template" / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    for package, repo in (
        ("ruff", "astral-sh/ruff-pre-commit"),
        ("codespell", "codespell-project/codespell"),
        ("commitizen", "commitizen-tools/commitizen"),
    ):
        floor = re.search(rf'"{package}>=([0-9.]+)"', pyproject)
        assert floor is not None, package
        block = hooks.split(f"https://github.com/{repo}", 1)[1].split("hooks:", 1)[0]
        assert f"rev: v{floor.group(1)}" in block, (
            f"{package} pre-commit rev drifted from >={floor.group(1)}"
        )


def test_python_version_file_is_in_the_ci_matrix() -> None:
    pinned = (ROOT / "template" / ".python-version").read_text(encoding="utf-8").strip()
    ci = (ROOT / "template" / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert f'"{pinned}"' in ci


def _hook_body(text: str, hook_id: str, nxt: str | None) -> str:
    start = text.index(f"- id: {hook_id}")
    end = text.index(f"- id: {nxt}") if nxt else len(text)
    return text[start:end]


def test_slow_hooks_run_on_pre_push() -> None:
    text = (ROOT / "template" / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "stages: [pre-push]" in _hook_body(text, "vulture", "deptry")
    assert "stages: [pre-push]" in _hook_body(text, "deptry", None)
    assert "stages:" not in _hook_body(text, "ty", "vulture")


def test_lint_script_runs_deptry_and_vulture() -> None:
    text = (ROOT / "template" / "devtools" / "lint.py").read_text(encoding="utf-8")
    assert '["deptry", "."]' in text
    assert '["vulture"' in text or '["vulture",' in text


def test_git_tasks_run_only_on_copy() -> None:
    text = _copier_yml()
    assert text.count("_copier_operation == 'copy'") >= 3
    assert "_message_after_update:" in text
    assert "uv sync" in text.split("_message_after_update:", 1)[1]
    for name in (
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "docs/index.md",
        "CHANGELOG.md",
    ):
        assert re.search(rf"^\s*- {re.escape(name)}$", text, re.MULTILINE), name


def test_placeholder_contacts_are_rejected() -> None:
    text = _copier_yml()
    email = re.search(
        r"^package_author_email:\n(.*?)(?=^[a-z_]+:|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert email is not None
    assert "default:" not in email.group(1)
    assert "changeme@example.com" in email.group(1)
    name = re.search(
        r"^package_name:\n(.*?)(?=^[a-z_]+:|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert name is not None
    assert "validator:" in name.group(1)
    assert "changeme" in name.group(1)
