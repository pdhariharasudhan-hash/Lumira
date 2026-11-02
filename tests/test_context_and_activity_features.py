from app.services.memory.decision_context_service import DecisionContextService
from app.services.system.core_activity_summary_service import CoreActivitySummaryService

class FakeMemory:
    def _read_cognitive_memory(self):
        return {'decisions': [{'id': 'd1'}, {'id': 'd2'}]}

class FakeEvents:
    def recent(self, limit):
        return {'events': [{'source': 'brain'}, {'source': 'brain'}, {'source': 'tasks'}]}

def test_context_and_activity_features():
    context = DecisionContextService(FakeMemory()).recent(1)
    assert context['count'] == 1
    activity = CoreActivitySummaryService(FakeEvents()).summary()
    assert activity['event_count'] == 3
    assert activity['sources']['brain'] == 2
