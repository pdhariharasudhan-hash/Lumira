from app.services.identity.system_prompt_service import SystemPromptService


def test_default_prompt_requires_human_readable_output_and_hides_transport_json(tmp_path):
    prompt = SystemPromptService(tmp_path / "system_prompt.json").render()

    assert "natural, readable language" in prompt
    assert "Never expose raw JSON" in prompt
    assert "only when the user explicitly asks" in prompt
    assert "actual media artifact" in prompt


def test_output_contract_remains_protected_when_user_instructions_are_added(tmp_path):
    service = SystemPromptService(tmp_path / "system_prompt.json")
    service.update(user="Be concise and practical.")

    prompt = service.render()
    assert "Never expose raw JSON" in prompt
    assert "Be concise and practical." in prompt
