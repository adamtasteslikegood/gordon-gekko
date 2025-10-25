import json
import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import repo_mapper


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    fixture_root = Path(__file__).parent / "fixtures" / "sample_project"
    target = tmp_path / "sample_project"
    shutil.copytree(fixture_root, target)
    return target


def test_analyzer_generates_artifacts(sample_repo: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    repo_mapper.analyze(sample_repo, output_dir)

    json_path = output_dir / "repo-map.json"
    md_path = output_dir / "repo-map.md"
    graph_path = output_dir / "dependency-graph.mmd"
    summary_dir = output_dir / "module-summaries"

    assert json_path.exists(), "JSON output missing"
    assert md_path.exists(), "Markdown output missing"
    assert graph_path.exists(), "Mermaid graph missing"
    assert summary_dir.is_dir(), "Module summaries directory missing"

    data = json.loads(json_path.read_text())
    assert data["modules"], "Expected module data"

    languages = data["languages"]
    assert "Python" in languages
    modules = data["modules"]
    core_module = next((m for m in modules if m["path"].endswith("src/sample_pkg/core.py")), None)
    assert core_module is not None
    assert core_module["tests"]["present"] is True
    assert core_module["annotations"].get("todo") == 1

    summary_files = list(summary_dir.glob("*.md"))
    assert summary_files, "Expected per-module summaries"
