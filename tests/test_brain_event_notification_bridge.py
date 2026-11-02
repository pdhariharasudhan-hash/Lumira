from app.services.brain.brain_service import BrainService


class FakeEvents:
    def __init__(self): self.calls=[]
    def record(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"event_record":{"event":args[0],"source":args[1],"core_context":{"context":{}}}}

class FakeNotifications:
    def __init__(self): self.events=[]
    def create_from_core_event(self, event):
        self.events.append(event)
        return {"success":True}


def test_brain_outcome_publishes_core_event_and_notification():
    brain=BrainService()
    brain.core_events=FakeEvents()
    brain.notifications=FakeNotifications()

    state=type("State",(),{"execution_context":type("Context",(),{"execution_id":"run-1"})()})()
    session={"session_id":"s1","active_project":"p1","goal_id":"g1"}

    brain._publish_execution_outcome(state,session,True)

    assert brain.core_events.calls[0][0][0]=="brain_execution_completed"
    assert len(brain.notifications.events)==1
