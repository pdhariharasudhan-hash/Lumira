from .recovery_models import RecoveryPolicy, RecoveryState


class RecoveryController:

    def __init__(self, policy=None):
        self.policy = policy or RecoveryPolicy()

    def can_retry(self, state: RecoveryState) -> bool:
        return (
            not state.aborted
            and not state.recovered
            and state.retry_count < self.policy.max_retries
        )

    def retry(self, state: RecoveryState) -> bool:
        if state.aborted or state.recovered:
            return False

        if not self.can_retry(state):
            state.aborted = True

            if state.failures:
                state.failures[-1].aborted = True

            return False

        state.retry_count += 1
        return True

    def can_recover(self, state: RecoveryState) -> bool:
        return self.policy.allow_recovery and not state.aborted

    def recover(self, state: RecoveryState) -> bool:
        if state.recovered:
            return True

        if not self.can_recover(state):
            state.aborted = True

            if state.failures:
                state.failures[-1].aborted = True

            return False

        state.recovered = True

        if state.failures:
            state.failures[-1].recovered = True

        return True

    def abort(self, state: RecoveryState) -> None:
        state.aborted = True

        if state.failures:
            state.failures[-1].aborted = True

    def reset_retry(self, state: RecoveryState) -> None:
        """
        Reset transient recovery state before continuing
        with the next pipeline stage.

        Failure history is preserved.
        The recovered flag belongs to the previously
        recovered stage and must not block future stages.
        """
        state.retry_count = 0
        state.recovered = False
