from app.services.multi_model.model_registry import ModelProfile, MultiModelRegistry
from app.services.multi_model.multi_model_orchestrator import MultiModelIntelligenceOrchestrator

class Worker:
    def __init__(self,content): self.content=content
    def generate(self,**kwargs): return {"success":True,"content":self.content}

def setup_function(): MultiModelRegistry.clear()
def teardown_function(): MultiModelRegistry.clear()

def test_selects_best_deterministic_candidate():
    MultiModelRegistry.register(ModelProfile("a","local",frozenset({"reply"}),priority=1),Worker("short"))
    MultiModelRegistry.register(ModelProfile("b","local",frozenset({"reply"}),priority=2),Worker("Lumira robot project planning details "*20))
    result=MultiModelIntelligenceOrchestrator().run(prompt="Help with Lumira robot project",mode="compare")
    assert result["success"] is True
    assert result["selected_model"]=="b"

def test_offline_mode_filters_remote_workers():
    MultiModelRegistry.register(ModelProfile("remote","remote",frozenset({"reply"})),Worker("remote answer"))
    MultiModelRegistry.register(ModelProfile("local","local",frozenset({"reply"})),Worker("local answer"))
    result=MultiModelIntelligenceOrchestrator().run(prompt="hello",mode="offline")
    assert result["success"] is True
    assert result["selected_model"]=="local"

def test_no_model_fails_explicitly():
    result=MultiModelIntelligenceOrchestrator().run(prompt="hello")
    assert result["success"] is False
    assert result["code"]=="no_model_available"
