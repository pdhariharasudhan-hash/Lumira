import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _load(name):
    return json.loads((DOCS / name).read_text(encoding="utf-8"))


def test_authoritative_source_inventory_counts_are_stable():
    atomic = _load("lumira_master_prompt_atomic_requirements_2026-11-13.json")
    governance = _load("lumira_master_prompt_governance_requirements_2026-11-13.json")
    section9 = _load("lumira_source_scope_requirements_2026-11-13.json")
    assert atomic["part_count"] == 39
    assert atomic["numbered_requirement_count"] == 727
    assert sum(x["source_kind"] == "numbered_build_requirement" for x in atomic["requirements"]) == 727
    assert sum(x["source_kind"] == "specialist_agent_coverage" for x in atomic["requirements"]) == 9
    assert governance["governance_item_count"] == 97
    assert section9["source_bullet_count"] == 428
    assert len(section9["requirements"]) == 428


def test_every_master_prompt_requirement_has_one_canonical_ledger_row():
    atomic = _load("lumira_master_prompt_atomic_requirements_2026-11-13.json")
    ledger = _load("lumira_master_requirement_inventory.json")
    ledger_ids = {row["requirement_id"] for row in ledger["requirements"]}
    canonical_ids = [
        row["canonical_ledger_id"]
        for row in atomic["requirements"]
        if row["source_kind"] == "numbered_build_requirement"
    ]
    assert len(canonical_ids) == 727
    assert len(set(canonical_ids)) == 727
    assert set(canonical_ids) <= ledger_ids


def test_part_parents_link_all_atomic_children():
    atomic = _load("lumira_master_prompt_atomic_requirements_2026-11-13.json")
    ledger = _load("lumira_master_requirement_inventory.json")
    by_id = {row["requirement_id"]: row for row in ledger["requirements"]}
    for part in range(4, 43):
        parent = by_id[f"SCOPE-PART-{part}"]
        expected = [
            row["canonical_ledger_id"]
            for row in atomic["requirements"]
            if row["source_kind"] == "numbered_build_requirement" and row["part"] == part
        ]
        assert parent["child_requirement_ids"] == expected


def test_exact_source_aliases_are_attached_without_duplicate_source_ids():
    ledger = _load("lumira_master_requirement_inventory.json")
    aliases = [
        alias
        for row in ledger["requirements"]
        for alias in row.get("source_aliases", [])
    ]
    old_prompt = [a for a in aliases if a.get("source_file") == "Pasted text(20261112-150057).txt"]
    section9 = [a for a in aliases if a.get("source_id", "").startswith("SRC9-")]
    assert len(old_prompt) == 162
    assert len(section9) == 148
    assert len({a["source_id"] for a in old_prompt}) == 162
    assert len({a["source_id"] for a in section9}) == 148


def test_ledger_counts_match_actual_records_and_statuses():
    ledger = _load("lumira_master_requirement_inventory.json")
    rows = ledger["requirements"]
    actual = dict(Counter(row["implementation_status"] for row in rows))
    assert ledger["counts"]["records_total"] == len(rows) == 914
    assert ledger["counts"]["status_counts"] == actual
    assert ledger["counts"]["prompt_subrequirements_itemized"] == 738
    assert actual == {
        "IMPLEMENTED": 64,
        "BLOCKED": 27,
        "IN_PROGRESS": 821,
        "NOT_STARTED": 1,
        "VERIFIED": 1,
    }


def test_mapping_is_not_misreported_as_full_scope_reconciliation():
    ledger = _load("lumira_master_requirement_inventory.json")
    metadata = ledger["source_scope_reconciliation"]
    assert metadata["full_scope_reconciled"] is False
    assert metadata["canonical_denominator_frozen"] is False
    assert metadata["atomic_requirements_in_ledger"] == 727
    assert metadata["new_atomic_requirement_rows_created"] == 565
    assert metadata["atomic_requirements_reused_from_existing_rows"] == 162
    assert metadata["unmatched_existing_prompt_rows_retained_for_review"] == 11


def test_legacy_catalog_and_feature_area_crosswalk_is_candidate_only():
    crosswalk = _load("lumira_legacy_catalog_and_feature_area_crosswalk_candidates_2026-11-14.json")
    ledger = _load("lumira_master_requirement_inventory.json")
    atomic = _load("lumira_master_prompt_atomic_requirements_2026-11-13.json")
    ledger_by_id = {row["requirement_id"]: row for row in ledger["requirements"]}
    source_ids = {row["source_id"] for row in atomic["requirements"]}
    assert crosswalk["candidate_only"] is True
    assert crosswalk["denominator_change_authorized"] is False
    assert len(crosswalk["legacy_catalog"]) == 99
    assert len(crosswalk["approved_feature_areas"]) == 30
    assert len({row["legacy_id"] for row in crosswalk["legacy_catalog"]}) == 99
    assert len({row["area_id"] for row in crosswalk["approved_feature_areas"]}) == 30
    for row in crosswalk["legacy_catalog"] + crosswalk["approved_feature_areas"]:
        if row in crosswalk["legacy_catalog"] and row.get("mapping_state") == "confirmed_exact_text_alias":
            assert row["semantic_review_required"] is False
        else:
            assert row["semantic_review_required"] is True
        for candidate in row["requirement_candidates"]:
            assert candidate["source_requirement_id"] in source_ids
            assert candidate["canonical_ledger_id"] in ledger_by_id
    exact_aliases = [
        row for row in crosswalk["legacy_catalog"]
        if row["requirement_candidates"]
        and row["requirement_candidates"][0]["normalized_exact_phrase_match"]
    ]
    assert len(exact_aliases) == 44
    alias_ids = [row["legacy_id"] for row in exact_aliases]
    target_ids = [row["requirement_candidates"][0]["canonical_ledger_id"] for row in exact_aliases]
    assert len(set(alias_ids)) == len(set(target_ids)) == 44
    for row in exact_aliases:
        legacy_id = row["legacy_id"]
        target_id = row["requirement_candidates"][0]["canonical_ledger_id"]
        legacy = ledger_by_id[legacy_id]
        target = ledger_by_id[target_id]
        assert legacy["semantic_reconciliation"]["review_status"] == "EXACT_TEXT_ALIAS_CONFIRMED"
        assert legacy["semantic_reconciliation"]["target_requirement_id"] == target_id
        assert any(alias["source_id"] == legacy_id for alias in target["source_aliases"])
    metadata = ledger["source_scope_reconciliation"]["semantic_reconciliation_with_99_legacy_and_30_areas"]
    assert metadata["legacy_exact_text_aliases_confirmed"] == 44
    assert metadata["legacy_records_remaining_for_semantic_review"] == 55
    assert metadata["canonical_rows_merged"] == 0
    assert metadata["canonical_rows_deleted"] == 0
    assert metadata["implementation_statuses_changed"] == 0
    assert metadata["canonical_denominator_frozen"] is False
    assert metadata["full_scope_reconciled"] is False
