from __future__ import annotations
import json, os, urllib.error, urllib.request
from threading import Lock
from urllib.parse import urlparse
from app.services.resources.resource_budget_service import ResourceBudgetService
from app.services.identity.system_prompt_service import SystemPromptService
class OllamaChatProvider:
    MAX_INPUT_CHARS=10000; MAX_OUTPUT_CHARS=12000; _request_lock=Lock()
    def __init__(self, *, base_url=None, model=None, timeout=90):
        self.base_url=(base_url or os.getenv('LUMIRA_OLLAMA_BASE_URL','http://127.0.0.1:11434/v1')).rstrip('/')
        self.model=model or os.getenv('LUMIRA_OLLAMA_CHAT_MODEL',os.getenv('LUMIRA_OLLAMA_MODEL','qwen2.5-coder:3b')); self.timeout=max(5,min(int(timeout),120))
        p=urlparse(self.base_url)
        try: p.port
        except ValueError: raise ValueError('Local chat provider requires a valid local endpoint.') from None
        if p.scheme!='http' or p.hostname not in {'localhost','127.0.0.1','::1'} or p.username or p.password or p.query or p.fragment: raise ValueError('Local chat provider must use a local HTTP endpoint without credentials.')
    def chat(self,message):
        if not isinstance(message,str) or not message.strip(): raise ValueError('Message must not be empty.')
        if len(message)>self.MAX_INPUT_CHARS: raise ValueError('Message exceeds the local chat input limit.')
        try: guidance=ResourceBudgetService().execution_guidance()
        except Exception: guidance={}
        if guidance.get('resource_pressure')=='critical': raise RuntimeError('Local conversation is deferred because system memory pressure is critical.')
        payload={'model':self.model,'messages':[{'role':'system','content':SystemPromptService().render()},{'role':'user','content':message.strip()}],'temperature':0.4,'max_tokens':768 if guidance.get('resource_profile')=='low_memory' else 1536,'stream':False}
        req=urllib.request.Request(f'{self.base_url}/chat/completions',data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST')
        if not self._request_lock.acquire(timeout=1): raise RuntimeError('Another local model request is active; conversation was deferred to protect RAM.')
        try:
            try:
                with urllib.request.urlopen(req,timeout=self.timeout) as response: raw=response.read(self.MAX_OUTPUT_CHARS*4+1)
            except urllib.error.HTTPError as exc: raise RuntimeError(f'Local conversation endpoint returned HTTP {exc.code}.') from None
            except (urllib.error.URLError,TimeoutError,OSError): raise RuntimeError('Local Ollama conversation endpoint is unavailable.') from None
        finally: self._request_lock.release()
        if len(raw)>self.MAX_OUTPUT_CHARS*4: raise ValueError('Local conversation response exceeded the response limit.')
        try:
            data=json.loads(raw.decode('utf-8')); choices=data.get('choices'); response=choices[0].get('message',{}).get('content') if isinstance(choices,list) and choices else None
        except (UnicodeDecodeError,json.JSONDecodeError,AttributeError,TypeError,IndexError): raise ValueError('Local conversation endpoint returned an invalid response.') from None
        if not isinstance(response,str) or not response.strip(): raise ValueError('Local conversation endpoint returned an empty response.')
        response=response.strip()
        if len(response)>self.MAX_OUTPUT_CHARS: raise ValueError('Local conversation output exceeded the response limit.')
        return response
