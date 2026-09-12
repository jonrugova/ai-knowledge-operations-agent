import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from approval_store import (
    CANONICAL_RUSH_APPROVAL_TYPE,
    LEGACY_RUSH_APPROVAL_TYPE,
    get_approval_request,
)


EXECUTIONS_PATH = Path("data/executions.json")


def _load_executions():
    if not EXECUTIONS_PATH.exists():
        return []

    executions = json.loads(EXECUTIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(executions, list):
        raise ValueError("data/executions.json must contain a JSON list.")
    return executions


def _save_executions(executions):
    EXECUTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXECUTIONS_PATH.write_text(
        json.dumps(executions, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_execution_for_approval(approval_id: str):
    for execution in _load_executions():
        if execution.get("approval_id") == approval_id:
            return execution
    return None


def execute_approved_rush(approval_id: str):
    # Persisted approval status is the authority for this gate.
    approval = get_approval_request(approval_id)

    if approval.get("approval_type") not in {
        CANONICAL_RUSH_APPROVAL_TYPE,
        LEGACY_RUSH_APPROVAL_TYPE,
    }:
        raise ValueError(
            f"Approval request {approval_id} is not for rush production."
        )

    if approval.get("status") != "approved":
        raise ValueError(
            f"Approval request {approval_id} is "
            f"{approval.get('status')}; execution requires approved status."
        )

    executions = _load_executions()
    if any(
        execution.get("approval_id") == approval_id
        for execution in executions
    ):
        # Duplicate execution is prevented even when approval remains approved.
        raise ValueError(
            f"Approval request {approval_id} has already been executed."
        )

    # Approval and execution are separate persisted states.
    execution = {
        "execution_id": str(uuid4()),
        "approval_id": approval_id,
        "action_type": "rush production execution",
        "status": "executed",
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
    executions.append(execution)
    _save_executions(executions)
    return execution