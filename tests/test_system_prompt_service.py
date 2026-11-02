from app.services.identity.system_prompt_service import SystemPromptService

def test_protected_core_survives_updates(tmp_path):
    service=SystemPromptService(tmp_path/'prompt.json')
    before=service.get()['protected_core']
    updated=service.update(user='Be concise.', adaptive='Use verified workflow improvements.')
    assert updated['protected_core']==before
    assert updated['user_instructions']=='Be concise.'
    assert 'verified workflow' in service.render()

def test_no_update_is_rejected(tmp_path):
    service=SystemPromptService(tmp_path/'prompt.json')
    try: service.update()
    except ValueError as exc: assert str(exc)=='no_update_requested'
    else: raise AssertionError('update without a requested layer must fail')
from app.services.command_parser_service import CommandParserService

def test_self_upgrade_request_creates_bounded_capability():
    result=CommandParserService().parse('Lumira, make yourself capable of reading system prompts')
    assert result['success'] is True
    assert result['capability']=='self_upgrade_plan'
