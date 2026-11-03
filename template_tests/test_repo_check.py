"""Tests for the repo tooling (not shipped to generated projects)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# repo_check.py lives at the repo root, outside this test package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import repo_check
from repo_check import Answers, CheckFailed, strip_jsonc

if TYPE_CHECKING:
    from collections.abc import Iterator


def test_strip_jsonc_removes_line_comments() -> None:
    text = '{\n  // comment\n  "a": 1\n}'
    assert strip_jsonc(text) == '{\n  \n  "a": 1\n}'


def test_strip_jsonc_keeps_comment_markers_inside_strings() -> None:
    text = '{"url": "https://example.com//x", "glob": "/*not a comment*/"}'
    assert strip_jsonc(text) == text


def test_strip_jsonc_removes_block_comments() -> None:
    assert strip_jsonc('{\n/* a\nb */\n"k": 2\n}') == '{\n\n"k": 2\n}'


@pytest.fixture
def scratch() -> Iterator[Path]:
    """A throwaway tree inside the repo (CI temp dirs vary by platform)."""
    root = Path(__file__).resolve().parent / "_scratch" / "module_of"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_module_of_reads_generated_module(scratch: Path) -> None:
    (scratch / "src" / "demo_pkg").mkdir(parents=True)
    assert repo_check.module_of(scratch) == "demo_pkg"


def test_module_of_rejects_ambiguous_layout(scratch: Path) -> None:
    (scratch / "src" / "a").mkdir(parents=True)
    (scratch / "src" / "b").mkdir(parents=True)
    with pytest.raises(CheckFailed, match="expected one module"):
        repo_check.module_of(scratch)


def test_answer_sets_are_distinct() -> None:
    labels = [a.label for a in repo_check.ANSWER_SETS]
    assert len(labels) == len(set(labels))
    assert all(isinstance(a, Answers) for a in repo_check.ANSWER_SETS)
