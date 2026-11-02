class CheckpointIntegrityService:
    """Validate a checkpoint against the run's persisted stage history."""

    def evaluate(self, run):
        point = run.get("safe_resume_point")
        records = {item.get("stage"): item for item in run.get("stage_records", []) if isinstance(item, dict)}
        record = records.get(point)
        unsafe = record is not None and record.get("status") in {"running", "failed"} and point in {
            "save_project", "save_artifact", "generate_image", "capture_audio",
            "transcribe", "summarize", "apply_changes",
        }
        valid = (
            run.get("status") == "failed"
            and run.get("resume_allowed") is True
            and isinstance(point, str)
            and not unsafe
        )
        return {
            "success": True,
            "checkpoint_valid": valid,
            "safe_resume_point": point if valid else None,
            "requires_manual_reconciliation": unsafe,
            "reason": "uncertain_side_effect" if unsafe else (
                None if valid else "run_not_checkpoint_resumable"
            ),
        }
