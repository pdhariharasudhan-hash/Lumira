from datetime import UTC, datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from app.services.work_items.work_item_service import WorkItemService
from app.services.work_items.workflow_insights_service import WorkflowInsightsService

router = APIRouter(prefix="/workflows", tags=["workflows"])
_service = WorkflowInsightsService()

def _svc():
    return _service() if callable(_service) else _service

@router.get("/insights")
def workflow_insights(project_id: str | None = Query(default=None, max_length=128), goal_id: str | None = Query(default=None, max_length=128)):
    return _svc().summary(project_id, goal_id)

def _workflows(**filters):
    return _svc().workflow_service.list_workflows(limit=200, **filters) if getattr(_svc(), "workflow_service", None) else WorkItemService().list_workflows(limit=200, **filters)

def workflow_summary(category=None, project_id=None):
    items=_workflows(category=category, project_id=project_id)
    wf_counts={}; task_counts={}
    for wf in items:
        wf_counts[wf.get("status","unknown")]=wf_counts.get(wf.get("status","unknown"),0)+1
        for task in wf.get("tasks",[]): task_counts[task.get("status","unknown")]=task_counts.get(task.get("status","unknown"),0)+1
    return {"success":True,"scanned_workflows":len(items),"workflow_status_counts":wf_counts,"task_status_counts":task_counts}

def workflow_attention(limit=20):
    rank={"failed":0,"blocked":1}
    items=[wf for wf in _workflows() if wf.get("status") in rank]
    items.sort(key=lambda wf:(rank[wf.get("status")], wf.get("updated_at","")), reverse=False)
    return {"success":True,"items":items[:max(1,min(int(limit),100))]}

def search_workflows(q=None, status=None, limit=50):
    needle=(q or "").lower()
    items=_workflows(status=status) if status else _workflows()
    if needle: items=[wf for wf in items if needle in str(wf.get("title","")).lower() or any(needle in str(t.get("title","")).lower() for t in wf.get("tasks",[]))]
    return {"success":True,"total":len(items),"workflows":items[:max(1,min(int(limit),200))]}

def export_workflows(limit=100):
    limit=max(1,min(int(limit),200)); items=_workflows()
    return {"schema_version":1,"count":min(len(items),limit),"truncated":len(items)>limit,"workflows":items[:limit]}

def workflow_dependency_graph(workflow_id):
    wf=_get(workflow_id); tasks=wf.get("tasks",[])
    return {"workflow_id":workflow_id,"node_count":len(tasks),"nodes":[t.get("task_id") for t in tasks],"edges":[{"from":d,"to":t.get("task_id")} for t in tasks for d in t.get("dependencies",[])]}

def _get(workflow_id):
    svc=_svc(); base=getattr(svc,"workflow_service",None) or svc
    wf=base.get_workflow(workflow_id)
    if not wf: raise HTTPException(404,"workflow not found")
    return wf

def _update(workflow_id,task_id,status,blocker=None,result=None):
    svc=_svc(); base=getattr(svc,"workflow_service",None) or svc
    try:return base.update_task(workflow_id,task_id,status,blocker=blocker,result=result)
    except (KeyError,ValueError) as exc: raise HTTPException(409,str(exc))

def _task(wf,task_id):
    task=next((t for t in wf.get("tasks",[]) if t.get("task_id")==task_id),None)
    if not task: raise HTTPException(404,"task not found")
    return task

def retry_failed_task(workflow_id,task_id):
    wf=_get(workflow_id); task=_task(wf,task_id)
    if task.get("status")!="failed": raise HTTPException(409,"task is not failed")
    return {"success":True,"retried_task_id":task_id,"workflow":_update(workflow_id,task_id,"pending")}

def unblock_task(workflow_id,task_id):
    wf=_get(workflow_id); task=_task(wf,task_id)
    done={t.get("task_id") for t in wf.get("tasks",[]) if t.get("status")=="completed"}
    if any(d not in done for d in task.get("dependencies",[])): raise HTTPException(409,"dependencies incomplete")
    return {"success":True,"workflow":_update(workflow_id,task_id,"pending")}

def start_ready_task(workflow_id,task_id):
    wf=_get(workflow_id); task=_task(wf,task_id); done={t.get("task_id") for t in wf.get("tasks",[]) if t.get("status")=="completed"}
    if any(d not in done for d in task.get("dependencies",[])): raise HTTPException(409,"dependencies incomplete")
    return {"success":True,"workflow":_update(workflow_id,task_id,"in_progress")}

def workflow_timeline(days=7):
    cutoff=datetime.now(UTC)-timedelta(days=max(1,min(int(days),365))); events=[]
    for wf in _workflows():
        for task in wf.get("tasks",[]):
            for event in task.get("history",[]):
                try: at=datetime.fromisoformat(str(event.get("at","")).replace("Z","+00:00"))
                except ValueError: continue
                if at>=cutoff: events.append({**event,"workflow_id":wf.get("workflow_id"),"task_id":task.get("task_id")})
    return {"success":True,"events":events}
