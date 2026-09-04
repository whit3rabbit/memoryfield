from mf import spec


def test_is_debris_matches_the_spec_list():
    for name in (".DS_Store", "desktop.ini", "Thumbs.db", "page~", "page.sync-conflict-20260901-ABC.md"):
        assert spec.is_debris(name), name
    assert not spec.is_debris("page.md")


def test_walk_field_prunes_and_orders(tmp_path):
    (tmp_path / "b.md").write_text("b")
    (tmp_path / "a.md").write_text("a")
    (tmp_path / ".hidden.md").write_text("h")
    (tmp_path / "page.sync-conflict-1.md").write_text("c")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.md").write_text("c")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.md").write_text("x")
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "r.md").write_text("r")
    (tmp_path / "sub" / "raw").mkdir()
    (tmp_path / "sub" / "raw" / "nested.md").write_text("n")

    rels = [p.relative_to(tmp_path).as_posix() for p in spec.walk_field(tmp_path)]
    assert rels == ["a.md", "b.md", "sub/c.md"]

    rels = [p.relative_to(tmp_path).as_posix() for p in spec.walk_field(tmp_path, include_raw=True)]
    assert rels == ["a.md", "b.md", "raw/r.md", "sub/c.md"]  # only the root raw/

    rels = [p.relative_to(tmp_path).as_posix() for p in spec.walk_field(tmp_path, include_dotfiles=True)]
    assert ".hidden.md" in rels
