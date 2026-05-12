from __future__ import annotations

from architec.code_review.near_duplicate import near_duplicate_concerns


def test_near_duplicate_concerns_detects_normalized_duplicate_functions(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.py").write_text(
        """
def first(value):
    total = 0
    for item in value:
        if item > 10:
            total += item * 2
        else:
            total += item
    return total
""",
        encoding="utf-8",
    )
    (source / "b.py").write_text(
        """
def second(records):
    result = 0
    for row in records:
        if row > 99:
            result += row * 2
        else:
            result += row
    return result
""",
        encoding="utf-8",
    )

    concerns = near_duplicate_concerns(tmp_path)

    assert len(concerns) == 1
    concern = concerns[0]
    assert concern["kind"] == "duplication"
    assert concern["location"]["path"] == "src/b.py"
    assert concern["location"]["symbol"] == "second"
    assert concern["location"]["symbol_kind"] == "function"
    assert any(item.startswith("near_duplicate.reference=src/a.py:") for item in concern["evidence"])


def test_near_duplicate_concerns_ignores_small_boilerplate(tmp_path) -> None:
    (tmp_path / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")

    assert near_duplicate_concerns(tmp_path) == []


def test_near_duplicate_fingerprinting_does_not_mutate_nested_symbol_names(tmp_path) -> None:
    (tmp_path / "a.py").write_text(
        """
def outer_one(records):
    def inner_one(value):
        total = 0
        for item in value:
            if item > 10:
                total += item * 2
            else:
                total += item
        return total
    return inner_one(records)
""",
        encoding="utf-8",
    )
    (tmp_path / "b.py").write_text(
        """
def outer_two(records):
    def inner_two(value):
        result = 0
        for row in value:
            if row > 99:
                result += row * 2
            else:
                result += row
        return result
    return inner_two(records)
""",
        encoding="utf-8",
    )

    concerns = near_duplicate_concerns(tmp_path)

    symbols = {concern["location"]["symbol"] for concern in concerns}
    assert "outer_two.inner_two" in symbols
    assert all(not symbol.startswith("_fn.") for symbol in symbols)
