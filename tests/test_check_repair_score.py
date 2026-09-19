from __future__ import annotations

from check_repair.score import extract_localizations, score_localization, score_repair


def test_extract_localizations_uses_last_item_of_last_valid_object() -> None:
    text = """
    <think>{\"localizations\":[{\"reason_code\":\"private-thought\"}]}</think>
    first {"localizations":[{"check_item":"A","reason_code":"wrong"}]}
    final {"localizations":[
      {"check_item":"B","reason_code":"also-wrong"},
      {"check_item":"target","reason_code":"material_grade"}
    ]}
    """
    assert extract_localizations(text) == [
        {"check_item": "target", "reason_code": "material_grade"}
    ]


def test_localization_score_compares_only_final_reason_code() -> None:
    text = '{"localizations":[{"check_item":"unrelated","reason_code":"material_grade"}]}'
    result = score_localization(text, "material_grade")
    assert result["parse_ok"] is True
    assert result["localization_score"] == 1.0
    assert score_localization("not json", "material_grade")["localization_score"] == 0.0


def test_repair_pass_requires_target_removed_and_no_new_ng() -> None:
    seeded = ["target", "pre-existing"]
    assert score_repair(["pre-existing"], "target", seeded)["repair_pass"] is True
    assert score_repair(["target"], "target", seeded)["repair_pass"] is False
    result = score_repair(["pre-existing", "new failure"], "target", seeded)
    assert result["repair_pass"] is False
    assert result["new_ng"] == ["new failure"]


def test_repair_normalizes_whitespace_and_duplicates() -> None:
    result = score_repair([" A ", "A"], "target", ["target", "A"])
    assert result["repair_pass"] is True
    assert result["ng_after"] == ["A"]
