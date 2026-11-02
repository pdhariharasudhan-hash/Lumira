class TaskRecoveryPackageService:
    def __init__(self, evidence_service, analysis_service):
        self.evidence_service = evidence_service
        self.analysis_service = analysis_service

    def build(self, workflow_id, task_id):
        evidence = self.evidence_service.evidence(workflow_id, task_id)
        analysis = self.analysis_service.analyze(evidence)
        return {"success": True, "evidence": evidence, "analysis": analysis}
