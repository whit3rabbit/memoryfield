"""The skill ships inside the wheel as `mf/templates/skill/`, and the
repo dogfoods a copy at `.claude/skills/mf/`. The two must stay
byte-identical, or `mf setup` installs something the docs never
describe."""
from importlib import resources
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FILES = ("SKILL.md", "reference.md")


def test_dogfood_copy_matches_packaged_template():
    for name in FILES:
        packaged = (REPO / "mf" / "templates" / "skill" / name).read_bytes()
        mirror = (REPO / ".claude" / "skills" / "mf" / name).read_bytes()
        assert packaged == mirror, f"{name}: .claude/skills/mf/ and mf/templates/skill/ differ"


def test_templates_load_as_package_resources():
    for name in FILES:
        text = resources.files("mf").joinpath("templates", "skill", name).read_text(encoding="utf-8")
        assert text.strip()


def test_skill_frontmatter_names_mf():
    # `name: mf` is how `mf setup` tells its own skill dir from a foreign one.
    head = resources.files("mf").joinpath("templates", "skill", "SKILL.md").read_text(encoding="utf-8")
    assert head.startswith("---\nname: mf\n")
