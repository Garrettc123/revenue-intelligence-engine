"""Contract tests for non-duplicating, read-only revenue intelligence workflow."""
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "revenue-intelligence.yml"


def load():
    source = WORKFLOW.read_text(encoding="utf-8")
    data = yaml.safe_load(source)
    assert isinstance(data, dict)
    assert isinstance(data.get("jobs"), dict)
    return source, data


def test_workflow_has_no_auto_repo_write_permission():
    source, data = load()
    assert data["permissions"]["contents"] == "read"
    assert "git push" not in source
    assert "git commit" not in source
    assert "upload-artifact" in source


def test_only_explicit_dispatch_can_use_rhns_correlation():
    source, data = load()
    triggers = data.get("on", data.get(True))
    assert triggers["schedule"] == [{"cron": "0 * * * *"}]
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert inputs["rhns_dispatch_id"]["required"] is False
    assert inputs["rhns_dispatch_id"]["type"] == "string"
    assert "RHNS/{0}" in data["run-name"]
    assert "Scheduled Revenue" in data["run-name"]
    assert source.count("workflow_dispatch:") == 1


def test_schedule_keeps_intelligence_read_path():
    source, data = load()
    steps = data["jobs"]["intelligence-cycle"]["steps"]
    names = [step.get("name", "") for step in steps]
    assert "Run RHNS Revenue Intelligence" in names
    assert "Install dependencies" in names
    assert "Commit intelligence output" not in names
    assert "pip install -r requirements.txt" in source
