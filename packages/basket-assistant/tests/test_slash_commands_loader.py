"""Tests for declarative slash command loader."""

from pathlib import Path

from basket_assistant.core.loader.slash_commands_loader import (
    SlashCommandSpec,
    collect_slash_commands,
    expand_slash_body,
)


def test_expand_slash_body_args() -> None:
    assert expand_slash_body("Hello {{args}} end", "world") == "Hello world end"


def test_expand_slash_body_empty_args() -> None:
    assert expand_slash_body("X{{args}}Y", "") == "XY"


def test_collect_skips_invalid_stem(tmp_path: Path) -> None:
    (tmp_path / "Bad_Name.md").write_text(
        "---\ndescription: d\n---\nbody", encoding="utf-8"
    )
    assert collect_slash_commands([tmp_path]) == {}


def test_collect_requires_description(tmp_path: Path) -> None:
    (tmp_path / "good.md").write_text("---\n---\nno desc", encoding="utf-8")
    assert collect_slash_commands([tmp_path]) == {}


def test_collect_loads_spec(tmp_path: Path) -> None:
    (tmp_path / "review.md").write_text(
        "---\ndescription: Review code\nskill: my-skill\ndisable-model-invocation: false\n---\nDo {{args}}",
        encoding="utf-8",
    )
    out = collect_slash_commands([tmp_path])
    assert "review" in out
    spec = out["review"]
    assert spec.description == "Review code"
    assert spec.skill_id == "my-skill"
    assert spec.disable_model_invocation is False
    assert spec.body_template == "Do {{args}}"
    assert isinstance(spec, SlashCommandSpec)


def test_later_dir_overwrites(tmp_path: Path) -> None:
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    (d1 / "foo.md").write_text("---\ndescription: first\n---\none", encoding="utf-8")
    (d2 / "foo.md").write_text("---\ndescription: second\n---\ntwo", encoding="utf-8")
    out = collect_slash_commands([d1, d2])
    assert out["foo"].body_template == "two"
    assert out["foo"].description == "second"


def test_invalid_skill_in_frontmatter(tmp_path: Path) -> None:
    (tmp_path / "x.md").write_text(
        "---\ndescription: d\nskill: INVALID\n---\nbody", encoding="utf-8"
    )
    assert collect_slash_commands([tmp_path]) == {}


def test_skips_underscore_prefix(tmp_path: Path) -> None:
    (tmp_path / "_hidden.md").write_text("---\ndescription: d\n---\nb", encoding="utf-8")
    assert collect_slash_commands([tmp_path]) == {}


def test_stem_normalized_lower(tmp_path: Path) -> None:
    (tmp_path / "Foo-Bar.md").write_text("---\ndescription: d\n---\nx", encoding="utf-8")
    out = collect_slash_commands([tmp_path])
    assert list(out.keys()) == ["foo-bar"]
