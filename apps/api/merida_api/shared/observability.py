import logging
from time import monotonic


logger = logging.getLogger("merida.workflow")


def workflow_timer() -> float:
    return monotonic()


def log_workflow_outcome(
    *,
    workflow: str,
    record_id: str,
    outcome_code: str,
    policy_version: str,
    started_at: float,
) -> None:
    duration_ms = max(0, round((monotonic() - started_at) * 1000))
    logger.info(
        "workflow_outcome workflow=%s record_id=%s outcome_code=%s policy_version=%s duration_ms=%s",
        workflow,
        record_id,
        outcome_code,
        policy_version,
        duration_ms,
    )
