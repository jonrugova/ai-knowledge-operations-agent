from approval_store import (
    CANONICAL_RUSH_APPROVAL_TYPE,
    LEGACY_RUSH_APPROVAL_TYPE,
    RUSH_REQUESTED_ACTION,
    decide_approval,
    get_approval_request,
)
from protected_actions import execute_approved_rush


APPROVAL_TYPE_ACTIONS = {
    CANONICAL_RUSH_APPROVAL_TYPE: RUSH_REQUESTED_ACTION,
    LEGACY_RUSH_APPROVAL_TYPE: RUSH_REQUESTED_ACTION,
}
SUPPORTED_ACTIONS = {RUSH_REQUESTED_ACTION}


def resolve_requested_action(approval):
    approval_type = approval.get("approval_type")
    expected_action = APPROVAL_TYPE_ACTIONS.get(approval_type)
    requested_action = approval.get("requested_action", expected_action)

    if expected_action is None or requested_action not in SUPPORTED_ACTIONS:
        raise ValueError("Approval request has no supported requested action.")
    if requested_action != expected_action:
        raise ValueError(
            "Approval request action does not match its approval type."
        )
    return requested_action


def resume_approved_workflow(approval_id: str):
    approval = get_approval_request(approval_id)
    if approval.get("status") != "approved":
        raise ValueError(
            f"Approval request {approval_id} is {approval.get('status')}; "
            "workflow resume requires approved status."
        )

    requested_action = resolve_requested_action(approval)

    if requested_action == RUSH_REQUESTED_ACTION:
        return execute_approved_rush(approval_id)
    raise ValueError("Approval request has no supported requested action.")


def decide_and_resume_approval(
    approval_id: str,
    decision: str,
    decided_by: str,
    decision_note: str,
):
    approval = get_approval_request(approval_id)
    if (
        approval.get("requested_by")
        and approval.get("requested_by") == decided_by
    ):
        raise PermissionError(
            "The requester cannot decide their own approval request."
        )

    if decision == "approved":
        resolve_requested_action(approval)

    approval = decide_approval(
        approval_id=approval_id,
        decision=decision,
        decided_by=decided_by,
        decision_note=decision_note,
    )
    result = {
        "approval": approval,
        "execution": None,
        "execution_status": "not_executed",
    }
    if decision == "approved":
        try:
            result["execution"] = resume_approved_workflow(approval_id)
        except Exception:
            result["execution_status"] = "failed"
        else:
            result["execution_status"] = "executed"

    return result