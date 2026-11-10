from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
from app.services.multi_model.model_registry import MultiModelRegistry

@dataclass(frozen=True)
class OrchestrationPolicy:
    mode: str
    max_models: int
    parallel: bool

class MultiModelIntelligenceOrchestrator:
    """Lumira-owned orchestration for replies and coding candidates."""
    MODES = {
        "fast": OrchestrationPolicy("fast",1,False),
        "smart": OrchestrationPolicy("smart",2,True),
        "compare": OrchestrationPolicy("compare",4,True),
        "maximum_quality": OrchestrationPolicy("maximum_quality",8,True),
        "offline": OrchestrationPolicy("offline",4,True),
    }
    TASK_TYPES={"reply","coding","research","planning"}
    MAX_PROMPT=20000
    MAX_CONTEXT_KEYS=50
    TOOL_CATALOG = (
        ("research", (
            "research", "compare", "comparison", "versus", "vs", "investigate",
            "analyze", "analyse", "analysis", "evidence", "summarize", "summarise",
            "extract knowledge", "market research", "technical research",
            "document research", "knowledge retrieval", "find sources",
            "gather sources", "fact check", "fact-check",
        ), "research_agent"),
        ("planning", (
            "plan", "planning", "steps", "roadmap", "prioritize", "prioritise",
            "break down", "decompose", "milestone", "schedule", "sequence tasks", "goal",
        ), "planner_agent"),
        ("coding", (
            "debug", "fix", "repair", "refactor", "implement", "code", "api", "app",
            "website", "software", "program", "script", "compile", "syntax error",
            "bug", "patch", "generate files",
        ), "code_agent"),
    )

    @staticmethod
    def _matches_tool_keyword(normalized: str, keyword: str) -> bool:
        return re.search(rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", normalized) is not None

    @classmethod
    def select_tool(cls, task: str) -> dict[str, Any]:
        if not isinstance(task, str) or not task.strip() or len(task.strip()) > cls.MAX_PROMPT:
            return {"success": False, "code": "invalid_task", "selected_tool": None}
        normalized = " ".join(task.casefold().split())
        for tool, keywords, agent in cls.TOOL_CATALOG:
            if any(cls._matches_tool_keyword(normalized, keyword) for keyword in keywords):
                return {
                    "success": True,
                    "selected_tool": tool,
                    "agent": agent,
                    "reason": "deterministic_task_capability_match",
                    "available_tools": [item[0] for item in cls.TOOL_CATALOG],
                }
        return {
            "success": False,
            "code": "no_matching_tool",
            "selected_tool": None,
            "available_tools": [item[0] for item in cls.TOOL_CATALOG],
        }

    def available_models(self):
        return [{"model_id":p.model_id,"provider":p.provider,"capabilities":sorted(p.capabilities),"enabled":p.enabled,"priority":p.priority} for p in MultiModelRegistry.list()]

    def run(self, *, prompt:str, task_type:str="reply", mode:str="smart", context:dict[str,Any]|None=None):
        prompt=self._prompt(prompt)
        if task_type not in self.TASK_TYPES: raise ValueError("unsupported task_type")
        if mode not in self.MODES: raise ValueError("unsupported orchestration mode")
        context=self._context(context or {})
        policy=self.MODES[mode]
        selected=MultiModelRegistry.eligible(task_type)
        if mode=="offline": selected=[(p,w) for p,w in selected if p.provider.lower() in {"local","ollama","offline"}]
        selected=selected[:policy.max_models]
        if not selected:
            return {"success":False,"code":"no_model_available","mode":mode,"task_type":task_type,"message":"No eligible configured model is available for this request.","candidates":[]}
        results=self._collect(selected,prompt,context,task_type,policy.parallel)
        valid=[x for x in results if x.get("success") and isinstance(x.get("content"),str) and x["content"].strip()]
        if not valid:
            return {"success":False,"code":"all_models_failed","mode":mode,"task_type":task_type,"message":"Configured models did not return a usable response.","candidates":results}
        scored=[self._score(x,prompt,task_type) for x in valid]
        scored.sort(key=lambda x:(-x["score"],x["model_id"]))
        winner=scored[0]
        return {"success":True,"mode":mode,"task_type":task_type,"response":winner["content"],"selected_model":winner["model_id"],"selection":{"score":winner["score"],"reason":winner["reason"],"candidate_count":len(results),"usable_candidate_count":len(valid)},"candidates":scored}

    def _collect(self, selected,prompt,context,task_type,parallel):
        def invoke(profile,worker):
            try:
                response=worker.generate(prompt=prompt,context=dict(context),task_type=task_type)
                if not isinstance(response,dict): return {"model_id":profile.model_id,"provider":profile.provider,"success":False,"code":"invalid_provider_response"}
                content=response.get("content")
                return {"model_id":profile.model_id,"provider":profile.provider,"success":response.get("success",isinstance(content,str)),"content":content if isinstance(content,str) else "","metadata":response.get("metadata",{})}
            except Exception:
                return {"model_id":profile.model_id,"provider":profile.provider,"success":False,"code":"provider_failed"}
        if not parallel or len(selected)==1: return [invoke(p,w) for p,w in selected]
        results=[]
        with ThreadPoolExecutor(max_workers=min(len(selected),8)) as ex:
            futures=[ex.submit(invoke,p,w) for p,w in selected]
            for future in as_completed(futures): results.append(future.result())
        return results

    @staticmethod
    def _score(item,prompt,task_type):
        content=item["content"].strip()
        prompt_terms={x.casefold() for x in prompt.split() if len(x)>=4}
        content_terms={x.casefold() for x in content.split() if len(x)>=4}
        relevance=min(30,len(prompt_terms & content_terms)*3)
        length=min(20,len(content)//120)
        coding_bonus=min(30,sum(token in content for token in ("def ","class ","function ","import "))*7) if task_type=="coding" else 0
        return {**item,"score":50+relevance+length+coding_bonus,"reason":"deterministic relevance and completeness score"}

    def _prompt(self,prompt):
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt.strip())>self.MAX_PROMPT: raise ValueError(f"prompt must contain 1 to {self.MAX_PROMPT} characters")
        return prompt.strip()
    def _context(self,context):
        if not isinstance(context,dict) or len(context)>self.MAX_CONTEXT_KEYS: raise ValueError("context must be an object with at most 50 keys")
        return context
