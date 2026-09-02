import json

from mf import cli


def test_claim_without_init_fails(tmp_path, capsys):
    exit_code = cli.main(["claim", "some-slug", "--by", "agent-a", "--field", str(tmp_path)])
    assert exit_code == 1
    assert "mf init" in capsys.readouterr().err


def test_claim_first_call_succeeds(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()

    exit_code = cli.main(["claim", "some-slug", "--by", "agent-a", "--field", str(tmp_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Claimed 'some-slug' for agent-a" in out


def test_claim_second_call_by_different_writer_loses(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()
    cli.main(["claim", "some-slug", "--by", "agent-a", "--field", str(tmp_path)])
    capsys.readouterr()

    exit_code = cli.main(["claim", "some-slug", "--by", "agent-b", "--field", str(tmp_path)])
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "already claimed by agent-a" in out


def test_claim_json_output(tmp_path, capsys):
    cli.main(["init", str(tmp_path)])
    capsys.readouterr()

    exit_code = cli.main(["claim", "some-slug", "--by", "agent-a", "--field", str(tmp_path), "--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed == {
        "slug": "some-slug",
        "claimed": True,
        "claimed_by": "agent-a",
        "claimed_at": parsed["claimed_at"],
    }
