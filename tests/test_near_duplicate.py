from __future__ import annotations

from architec.code_review.near_duplicate import near_duplicate_concerns, near_duplicate_scan


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
    assert concern["concern_id"].startswith("code-review:duplication:")
    assert concern["location"]["path"] == "src/b.py"
    assert concern["location"]["symbol"] == "second"
    assert concern["location"]["symbol_kind"] == "function"
    assert any(item.startswith("near_duplicate.reference=src/a.py:") for item in concern["evidence"])
    assert concern["references"] == [
        {
            "role": "reference",
            "path": "src/a.py",
            "line": 2,
            "symbol": "first",
            "symbol_kind": "function",
        }
    ]


def test_near_duplicate_concern_id_is_stable_for_same_duplicate_reference(tmp_path) -> None:
    (tmp_path / "a.py").write_text(
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
    (tmp_path / "b.py").write_text(
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

    first = near_duplicate_concerns(tmp_path)
    second = near_duplicate_concerns(tmp_path)

    assert first[0]["concern_id"] == second[0]["concern_id"]
    assert first[0]["concern_id"].startswith("code-review:duplication:")


def test_near_duplicate_concerns_ignores_small_boilerplate(tmp_path) -> None:
    (tmp_path / "a.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def b():\n    return 2\n", encoding="utf-8")

    assert near_duplicate_concerns(tmp_path) == []


def test_near_duplicate_concerns_ignore_thin_wrappers_with_different_targets(tmp_path) -> None:
    (tmp_path / "api.py").write_text(
        """
def extract_signatures(target='.', *, verbose=False):
    project_root, output_dir = _resolve_target(target)
    return run_sig_extract(project_root, output_dir, verbose=verbose)


def build_tree(target='.', *, verbose=False):
    project_root, output_dir = _resolve_target(target)
    return run_tree_gen(project_root, output_dir, verbose=verbose)
""",
        encoding="utf-8",
    )

    assert near_duplicate_concerns(tmp_path) == []


def test_near_duplicate_concerns_keep_wrappers_with_same_target(tmp_path) -> None:
    (tmp_path / "api.py").write_text(
        """
def first_entry(target='.', *, verbose=False):
    project_root, output_dir = _resolve_target(target)
    return run_shared(project_root, output_dir, verbose=verbose)


def second_entry(target='.', *, verbose=False):
    project_root, output_dir = _resolve_target(target)
    return run_shared(project_root, output_dir, verbose=verbose)
""",
        encoding="utf-8",
    )

    concerns = near_duplicate_concerns(tmp_path)

    assert len(concerns) == 1
    assert concerns[0]["location"]["symbol"] == "second_entry"
    assert concerns[0]["references"][0]["symbol"] == "first_entry"


def test_near_duplicate_scoped_ignores_changed_thin_wrapper_with_different_target(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "existing.py").write_text(
        """
def extract_signatures(target='.', *, verbose=False):
    project_root, output_dir = _resolve_target(target)
    return run_sig_extract(project_root, output_dir, verbose=verbose)
""",
        encoding="utf-8",
    )
    (source / "changed.py").write_text(
        """
def build_tree(target='.', *, verbose=False):
    project_root, output_dir = _resolve_target(target)
    return run_tree_gen(project_root, output_dir, verbose=verbose)
""",
        encoding="utf-8",
    )

    scan = near_duplicate_scan(tmp_path, changed_files=["src/changed.py"])

    assert scan["scoped_to_changed_files"] is True
    assert scan["candidate_total_before_scope"] == 1
    assert scan["concerns"] == []


def test_near_duplicate_groups_same_file_phase_prompt_family(tmp_path) -> None:
    (tmp_path / "prompts.py").write_text(
        """
def build_phase_1_messages(context):
    messages = []
    for section in context.sections:
        if section.enabled:
            messages.append({"role": "user", "content": section.text})
        else:
            messages.append({"role": "system", "content": "skipped"})
    if context.note:
        messages.append({"role": "system", "content": context.note})
    return messages


def build_phase_2a_messages(context):
    messages = []
    for section in context.sections:
        if section.enabled:
            messages.append({"role": "user", "content": section.text})
        else:
            messages.append({"role": "system", "content": "skipped"})
    if context.note:
        messages.append({"role": "system", "content": context.note})
    return messages


def build_phase3_messages(context):
    messages = []
    for section in context.sections:
        if section.enabled:
            messages.append({"role": "user", "content": section.text})
        else:
            messages.append({"role": "system", "content": "skipped"})
    if context.note:
        messages.append({"role": "system", "content": context.note})
    return messages
""",
        encoding="utf-8",
    )

    concerns = near_duplicate_concerns(tmp_path)

    assert len(concerns) == 1
    concern = concerns[0]
    assert concern["kind"] == "duplication"
    assert concern["location"]["path"] == "prompts.py"
    assert "near_duplicate.variant_family=build phase messages" in concern["evidence"]
    assert "near_duplicate.variant_member_total=3" in concern["evidence"]
    assert concern["references"][0]["symbol"] == "build_phase_1_messages"


def test_near_duplicate_groups_same_file_phase_cache_family(tmp_path) -> None:
    (tmp_path / "cache.py").write_text(
        """
def save_phase1_cache(cache, key, payload):
    serialized = json.dumps(payload, sort_keys=True)
    target = cache.root / key
    target.parent.mkdir(parents=True, exist_ok=True)
    if cache.enabled:
        target.write_text(serialized, encoding="utf-8")
    return target


def save_phase2_cache(cache, key, payload):
    serialized = json.dumps(payload, sort_keys=True)
    target = cache.root / key
    target.parent.mkdir(parents=True, exist_ok=True)
    if cache.enabled:
        target.write_text(serialized, encoding="utf-8")
    return target


def save_phase3_cache(cache, key, payload):
    serialized = json.dumps(payload, sort_keys=True)
    target = cache.root / key
    target.parent.mkdir(parents=True, exist_ok=True)
    if cache.enabled:
        target.write_text(serialized, encoding="utf-8")
    return target
""",
        encoding="utf-8",
    )

    concerns = near_duplicate_concerns(tmp_path)

    assert len(concerns) == 1
    assert "near_duplicate.variant_family=save phase cache" in concerns[0]["evidence"]
    assert "near_duplicate.variant_member_total=3" in concerns[0]["evidence"]


def test_near_duplicate_same_file_non_family_duplicate_still_reports(tmp_path) -> None:
    (tmp_path / "logic.py").write_text(
        """
def summarize_primary(records):
    total = 0
    for record in records:
        if record.enabled:
            total += record.value * 2
        else:
            total += record.value
    if total > 100:
        total -= 5
    return total


def calculate_secondary(items):
    result = 0
    for item in items:
        if item.enabled:
            result += item.value * 2
        else:
            result += item.value
    if result > 100:
        result -= 5
    return result
""",
        encoding="utf-8",
    )

    concerns = near_duplicate_concerns(tmp_path)

    assert len(concerns) == 1
    assert concerns[0]["location"]["symbol"] == "calculate_secondary"
    assert all("variant_family" not in item for item in concerns[0]["evidence"])


def test_near_duplicate_scoped_variant_family_does_not_flood_changed_file(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "prompts.py").write_text(
        """
def build_phase_1_messages(context):
    messages = []
    for section in context.sections:
        if section.enabled:
            messages.append({"role": "user", "content": section.text})
        else:
            messages.append({"role": "system", "content": "skipped"})
    if context.note:
        messages.append({"role": "system", "content": context.note})
    return messages


def build_phase_2_messages(context):
    messages = []
    for section in context.sections:
        if section.enabled:
            messages.append({"role": "user", "content": section.text})
        else:
            messages.append({"role": "system", "content": "skipped"})
    if context.note:
        messages.append({"role": "system", "content": context.note})
    return messages


def build_phase_3_messages(context):
    messages = []
    for section in context.sections:
        if section.enabled:
            messages.append({"role": "user", "content": section.text})
        else:
            messages.append({"role": "system", "content": "skipped"})
    if context.note:
        messages.append({"role": "system", "content": context.note})
    return messages
""",
        encoding="utf-8",
    )

    scan = near_duplicate_scan(tmp_path, changed_files=["src/prompts.py"])

    assert scan["scoped_to_changed_files"] is True
    assert len(scan["concerns"]) == 1
    assert scan["concerns"][0]["location"]["path"] == "src/prompts.py"
    assert "near_duplicate.variant_member_total=3" in scan["concerns"][0]["evidence"]


def test_near_duplicate_variant_family_id_is_stable(tmp_path) -> None:
    (tmp_path / "prompts.py").write_text(
        """
def build_phase_1_messages(context):
    messages = []
    for section in context.sections:
        if section.enabled:
            messages.append({"role": "user", "content": section.text})
        else:
            messages.append({"role": "system", "content": "skipped"})
    if context.note:
        messages.append({"role": "system", "content": context.note})
    return messages


def build_phase_2_messages(context):
    messages = []
    for section in context.sections:
        if section.enabled:
            messages.append({"role": "user", "content": section.text})
        else:
            messages.append({"role": "system", "content": "skipped"})
    if context.note:
        messages.append({"role": "system", "content": context.note})
    return messages
""",
        encoding="utf-8",
    )

    first = near_duplicate_concerns(tmp_path)
    second = near_duplicate_concerns(tmp_path)

    assert first[0]["concern_id"] == second[0]["concern_id"]
    assert first[0]["concern_id"].startswith("code-review:duplication:")


def test_near_duplicate_concerns_ignore_generated_state_dirs(tmp_path) -> None:
    ccb_dir = tmp_path / ".ccb" / "agents" / "agent1" / "provider-state"
    generated_dir = tmp_path / "generated"
    src_dir = tmp_path / "src"
    ccb_dir.mkdir(parents=True)
    generated_dir.mkdir()
    src_dir.mkdir()
    duplicate = """
def duplicated_impl(value):
    total = 0
    for item in value:
        if item > 10:
            total += item * 2
        else:
            total += item
    if total > 100:
        total -= 5
    return total
"""
    (ccb_dir / "a.py").write_text(duplicate, encoding="utf-8")
    (ccb_dir / "b.py").write_text(duplicate.replace("duplicated_impl", "duplicated_copy"), encoding="utf-8")
    (generated_dir / "a.py").write_text(duplicate, encoding="utf-8")
    (generated_dir / "b.py").write_text(duplicate.replace("duplicated_impl", "generated_copy"), encoding="utf-8")
    (src_dir / "normal.py").write_text("def unique_impl(value):\n    return value\n", encoding="utf-8")

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


def test_near_duplicate_scoped_changed_file_is_primary_even_when_sorted_first(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a_changed.py").write_text(
        """
def changed_impl(value):
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
    (source / "z_existing.py").write_text(
        """
def existing_impl(records):
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

    scan = near_duplicate_scan(tmp_path, changed_files=["src/a_changed.py"])

    assert scan["scoped_to_changed_files"] is True
    assert scan["changed_file_total"] == 1
    assert scan["candidate_total_before_scope"] == 1
    concerns = scan["concerns"]
    assert len(concerns) == 1
    concern = concerns[0]
    assert concern["location"]["path"] == "src/a_changed.py"
    assert concern["location"]["symbol"] == "changed_impl"
    assert concern["references"][0]["path"] == "src/z_existing.py"
    assert concern["references"][0]["symbol"] == "existing_impl"
