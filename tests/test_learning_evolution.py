from app.services.learning.learning_evolution_service import LearningEvolutionService


def test_learning_evolution_persists_approved_skill_and_knowledge_evidence(tmp_path):
    service = LearningEvolutionService(tmp_path / "learning.json")
    skill = service.register_skill("bounded planning", ["verified workflow run"], approved=True)
    knowledge = service.improve_knowledge(
        "workflow", "Dependency ordering is required", "verified workflow run", approved=True
    )
    assert skill["approved"] is True
    assert knowledge["approved"] is True


def test_learning_evolution_rejects_unapproved_or_duplicate_skill(tmp_path):
    service = LearningEvolutionService(tmp_path / "learning.json")
    service.register_skill("bounded planning", ["test evidence"])
    try:
        service.register_skill("bounded planning", ["new evidence"])
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("duplicate skills must be rejected")
    assert service.improve_knowledge("topic", "observation", "source", approved=False)["approved"] is False
