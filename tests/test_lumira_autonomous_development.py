import pytest

from app.services.autonomous_development.worker.development_worker import (
    DevelopmentWorker,
)


def test_lumira_autonomous_development_worker_starts_bounded_iteration(tmp_path):
    worker = DevelopmentWorker(tmp_path)

    iteration = worker.begin_iteration(1)

    assert iteration.status == "in_progress"
    assert worker.result(1)["iteration"] == 1
    assert worker.can_continue(1) is True


def test_lumira_autonomous_development_rejects_iteration_above_limit(
    tmp_path,
):
    worker = DevelopmentWorker(tmp_path)

    with pytest.raises(ValueError, match="iteration limit exceeded"):
        worker.begin_iteration(worker.MAX_ITERATIONS + 1)
