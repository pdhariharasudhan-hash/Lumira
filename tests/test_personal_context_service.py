from app.services.personal_context.personal_context_service import PersonalContextService

class Memory:
    def get_all(self):
        return {"experiences": [{"summary": "Build robot"}, {"summary": "Study physics"}]}

class Notes:
    def recent_notes(self, limit):
        return [{"title": "Idea"}][:limit]

def test_context_filters_existing_memory():
    result = PersonalContextService(Memory(), Notes()).snapshot("robot")
    assert result["experience_count"] == 1
    assert result["notes"][0]["title"] == "Idea"
