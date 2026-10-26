from pathlib import Path

import pytest
from fastapi import HTTPException

import app.routes.project_insights as route


@pytest.fixture
def project_tree(tmp_path, monkeypatch):
    root = tmp_path / "generated"
    project = root / "demo_api"
    v1 = project / "v1"
    v2 = project / "v2"
    v1.mkdir(parents=True)
    v2.mkdir(parents=True)
    (v1 / "main.py").write_text("print('v1')", encoding="utf-8")
    (v1 / "only_v1.txt").write_text("old", encoding="utf-8")
    (v2 / "main.py").write_text("print('v2')", encoding="utf-8")
    (v2 / "only_v2.txt").write_text("new", encoding="utf-8")
    (v2 / ".env").write_text("secret", encoding="utf-8")
    (v2 / "node_modules").mkdir()
    (v2 / "node_modules" / "large.js").write_text("ignored", encoding="utf-8")
    project_record = {
        "project": "demo_api", "versions": 2,
        "latest": {"idea": "Demo API", "project_type": "api", "entity": "demo_api", "version": "v2", "status": "generated"},
    }

    class FakeDiscovery:
        def get_projects(self):
            return [project_record]

        def get_versions(self, project_name):
            return [project_record["latest"]] if project_name == "demo_api" else []

    def resolve(*parts):
        candidate = root.joinpath(*parts).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        return candidate

    monkeypatch.setattr(route, "ProjectDiscoveryService", FakeDiscovery)
    monkeypatch.setattr(route, "resolve_project_path", resolve)
    return project_record, project, v1, v2


def test_project_summary_counts_types_and_versions(project_tree):
    result = route.project_summary()
    assert result["project_count"] == 1
    assert result["version_count"] == 2
    assert result["project_type_counts"] == {"api": 1}


def test_project_search_matches_idea_case_insensitively(project_tree):
    result = route.search_projects(q="DEMO API")
    assert result["total"] == 1
    assert result["projects"][0]["project"] == "demo_api"


def test_project_health_reports_metadata_gaps(project_tree, monkeypatch):
    record, _, _, _ = project_tree

    class EmptyVersions:
        def get_versions(self, project_name):
            return []

    monkeypatch.setattr(route, "ProjectDiscoveryService", lambda: type("Discovery", (), {
        "get_projects": lambda self: [record], "get_versions": lambda self, name: []
    })())
    result = route.project_health("demo_api")
    assert result["is_healthy"] is False
    assert "no_valid_versions" in [item["code"] for item in result["findings"]]


def test_manifest_excludes_hidden_and_dependency_directories(project_tree):
    result = route.project_manifest("demo_api", version="v2")
    names = [item["path"] for item in result["files"]]
    assert "main.py" in names
    assert ".env" not in names
    assert not any(name.startswith("node_modules/") for name in names)


def test_version_comparison_reports_path_differences(project_tree):
    result = route.compare_project_versions("demo_api", left="v1", right="v2")
    assert result["only_in_left"] == ["only_v1.txt"]
    assert result["only_in_right"] == ["only_v2.txt"]
    assert result["common_file_count"] == 1


def test_project_manifest_rejects_unknown_project(project_tree):
    with pytest.raises(HTTPException) as error:
        route.project_manifest("../outside", version="v1")
    assert error.value.status_code == 404


def test_version_comparison_hashes_changed_common_files_with_bounded_reads(project_tree):
    result = route.compare_project_versions("demo_api", left="v1", right="v2")
    changed = {item["path"] for item in result["changed_common_files"]}
    assert "main.py" in changed
    assert result["changed_common_files"][0]["left_sha256"] != result["changed_common_files"][0]["right_sha256"]
    assert result["comparison_budget"]["max_file_bytes"] == 2 * 1024 * 1024



def test_project_integrity_skips_hidden_and_dependency_paths(project_tree):
    result = route.project_integrity("demo_api", version="v2")
    assert result["success"] is True
    assert result["files_scanned"] >= 1
    assert result["note"].find("does not execute") >= 0


def test_project_integrity_rejects_unknown_version(project_tree):
    with pytest.raises(HTTPException) as error:
        route.project_integrity("demo_api", version="../outside")
    assert error.value.status_code == 404


def test_security_review_flags_heuristic_source_patterns_without_source_snippets(project_tree):
    _, _, _, v2 = project_tree
    (v2 / "review.py").write_text("value = eval(user_input)\nsubprocess.run(cmd, shell=True)\n", encoding="utf-8")
    result = route.project_security_review("demo_api", version="v2")
    rules = {item["rule"] for item in result["findings"]}
    assert "dynamic_code_execution" in rules
    assert "process_launch" in rules
    assert all("source" not in item for item in result["findings"])
    assert "do not prove safety" in result["disclaimer"]


def test_security_review_rejects_unknown_version(project_tree):
    with pytest.raises(HTTPException) as error:
        route.project_security_review("demo_api", version="../outside")
    assert error.value.status_code == 404



def test_project_readiness_audit_returns_bounded_static_checks(project_tree):
    result = route.project_readiness_audit("demo_api", version="v2")
    assert result["success"] is True
    assert result["check_count"] >= 28
    assert len(result["checks"]) == result["check_count"]
    assert len({item["id"] for item in result["checks"]}) == result["check_count"]
    assert 0 <= result["readiness_score"] <= 100
    assert "does not execute code" in result["note"]


def test_project_readiness_audit_rejects_unknown_version(project_tree):
    with pytest.raises(HTTPException) as error:
        route.project_readiness_audit("demo_api", version="../outside")
    assert error.value.status_code == 404


def test_project_readiness_audit_handles_package_manifest_without_duplicate_check_ids(project_tree):
    _, _, _, v2 = project_tree
    (v2 / "package.json").write_text('{"name":"demo","scripts":{"test":"node test.js"}}', encoding="utf-8")
    result = route.project_readiness_audit("demo_api", version="v2")
    ids = [item["id"] for item in result["checks"]]
    assert len(ids) == len(set(ids))
    by_id = {item["id"]: item for item in result["checks"]}
    assert by_id["package_json_valid"]["status"] == "pass"
    assert by_id["package_scripts"]["status"] == "pass"
