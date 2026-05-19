from pydantic import ValidationError

from app.domain.models.plan import ExecutionResult, Step
from app.domain.models.session import SessionStatus


def test_execution_result_ignores_extra_status_field():
    result = ExecutionResult.model_validate(
        {
            "success": True,
            "result": "done",
            "attachments": ["/home/ubuntu/result.md"],
            "status": "pending_input",
        }
    )

    assert result.success is True
    assert result.result == "done"
    assert result.attachments == ["/home/ubuntu/result.md"]


def test_step_still_rejects_invalid_execution_status():
    try:
        Step.model_validate({"status": "pending_input"})
    except ValidationError:
        return

    raise AssertionError("Step should reject invalid execution statuses")


def test_session_status_has_failed_state():
    assert SessionStatus.FAILED.value == "failed"
