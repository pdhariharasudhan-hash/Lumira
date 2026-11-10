from __future__ import annotations
import json
from pathlib import Path
from threading import RLock

class SystemPromptService:
    """Versioned Lumira instructions with an immutable runtime safety core."""
    MAX_LENGTH = 50_000
    CORE = (
        "You are Lumira, the user's private personal AI assistant. You are not SAP Lumira, a BI product, or any other company or product. Never identify yourself as SAP Lumira. "
        "Preserve security boundaries and fail closed. "
        "Never claim an action, test, upgrade, or external operation succeeded unless it actually did. "
        "Validate changes before execution, protect user data, and report uncertainty honestly. "
        "By default, answer people in natural, readable language. Never expose raw JSON, Python dictionaries, "
        "internal schemas, or transport envelopes as a normal answer. Provide structured JSON only when the "
        "user explicitly asks for JSON, an API payload, or a machine-readable schema. Respond in the same language "
        "as the user whenever possible, including Tamil in Unicode or romanized form and Tamil-English mixed input. "
        "Preserve technical terms and meaning; do not translate unless asked. If romanized Tamil is ambiguous, "
        "ask a concise clarification instead of guessing. For generated media, create or attach the actual media "
        "artifact instead of presenting its metadata as the output."
    )
    def __init__(self, path: str | Path = "memory/system_prompt.json"):
        self.path = Path(path); self._lock = RLock()
    def _load(self):
        default={"version":1,"user":"","adaptive":""}
        if not self.path.exists(): return default
        try: data=json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError): return default
        if not isinstance(data,dict): return default
        return {"version":max(1,int(data.get("version",1))),"user":str(data.get("user", ""))[:self.MAX_LENGTH],"adaptive":str(data.get("adaptive", ""))[:self.MAX_LENGTH]}
    def get(self):
        with self._lock:
            data=self._load()
            return {"protected_core":self.CORE,"user_instructions":data["user"],"adaptive_instructions":data["adaptive"],"version":data["version"]}
    def render(self):
        data=self.get(); parts=[data["protected_core"]]
        if data["user_instructions"].strip(): parts.append("User-controlled instructions:\n"+data["user_instructions"].strip())
        if data["adaptive_instructions"].strip(): parts.append("Verified adaptive instructions:\n"+data["adaptive_instructions"].strip())
        return "\n\n".join(parts)
    def update(self, *, user=None, adaptive=None):
        if user is None and adaptive is None: raise ValueError("no_update_requested")
        with self._lock:
            data=self._load()
            if user is not None:
                if not isinstance(user,str) or len(user)>self.MAX_LENGTH: raise ValueError("invalid_user_instructions")
                data["user"]=user.strip()
            if adaptive is not None:
                if not isinstance(adaptive,str) or len(adaptive)>self.MAX_LENGTH: raise ValueError("invalid_adaptive_instructions")
                data["adaptive"]=adaptive.strip()
            data["version"]+=1; self.path.parent.mkdir(parents=True,exist_ok=True)
            tmp=self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(self.path)
            return self.get()
