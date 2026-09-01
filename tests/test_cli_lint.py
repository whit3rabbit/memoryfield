import json

from mf import cli

GOOD = """\
---
uuid: good
title: "Deploy - how to roll back"
summary: "Run `kubectl rollout undo deployment/<svc>`; takes about 90 seconds end to end."
source: runbooks/deploy.md
---

## Answer

Run `kubectl rollout undo deployment/<svc>`. It re-deploys the previous image.
"""


def test_lint_without_index_still_runs(tmp_path, capsys):
    (tmp_path / "good.md").write_text(GOOD)
    assert cli.main(["lint", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "1 pages: 0 errors, 0 warnings" in out
    assert "orphan" not in out  # info hidden by default


def test_lint_all_shows_info(tmp_path, capsys):
    (tmp_path / "good.md").write_text(GOOD)
    cli.main(["lint", str(tmp_path), "--all"])
    assert "info: orphan" in capsys.readouterr().out


def test_lint_check_fails_on_warning(tmp_path, capsys):
    (tmp_path / "t.md").write_text(GOOD + "\nDeployed yesterday.\n")
    assert cli.main(["lint", str(tmp_path)]) == 0
    assert cli.main(["lint", str(tmp_path), "--check"]) == 1
    assert "copied-state" in capsys.readouterr().out


def test_lint_json(tmp_path, capsys):
    (tmp_path / "a.md").write_text(GOOD)
    (tmp_path / "b.md").write_text(GOOD)
    cli.main(["lint", str(tmp_path), "--json"])
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["errors"] == 1
    assert any(f["code"] == "duplicate-uuid" for f in parsed["findings"])
