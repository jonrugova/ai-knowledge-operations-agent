import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


APPROVALS_PATH = Path("data/approvals.json")
CANONICAL_RUSH_APPROVAL_TYPE = "rush production request"
LEGACY_RUSH_APPROVAL_TYPE = "rush_order"
RUSH_REQUESTED_ACTION = "execute_approved_rush"


def _load_approvals():
    if not APPROVALS_PATH.exists():
        return []

    approvals = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    if not isinstance(approvals, list):
        raise ValueError("data/approvals.json must contain a JSON list.")
    return approvals


def _save_approvals(approvals):
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(
        json.dumps(approvals, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def list_approval_requests():
    return _load_approvals()


def create_approval_request(
    approval_type: str,
    reason: str,
    user_request: str,
    requested_by: str,
):
    if not isinstance(requested_by, str) or not requested_by.strip():
        raise ValueError("requested_by must be a nonblank string.")

    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    approvals = _load_approvals()
    if approval_type == LEGACY_RUSH_APPROVAL_TYPE:
        approval_type = CANONICAL_RUSH_APPROVAL_TYPE

    approval = {
        "approval_id": str(uuid4()),
        "approval_type": approval_type,
        "reason": reason,
        "user_request": user_request,
        "requested_by": requested_by.strip(),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if approval_type == CANONICAL_RUSH_APPROVAL_TYPE:
        approval["requested_action"] = RUSH_REQUESTED_ACTION
    approvals.append(approval)

    # The approval record is persisted outside the model.
    _save_approvals(approvals)
    return approval


def get_approval_request(approval_id: str):
    approvals = _load_approvals()
    for approval in approvals:
        if approval.get("approval_id") == approval_id:
            return approval
    raise ValueError(f"Approval request not found: {approval_id}")


def decide_approval(
    approval_id: str,
    decision: str,
    decided_by: str,
    decision_note: str,
):
    if decision not in {"approved", "rejected"}:
        raise ValueError('decision must be exactly "approved" or "rejected".')

    approvals = _load_approvals()
    for approval in approvals:
        if approval.get("approval_id") != approval_id:
            continue

        # Only pending requests may transition to approved or rejected.
        if approval.get("status") != "pending":
            raise ValueError(
                f"Approval request {approval_id} is already "
                f"{approval.get('status')}."
            )
        if (
            approval.get("requested_by")
            and approval.get("requested_by") == decided_by
        ):
            raise PermissionError(
                "The requester cannot decide their own approval request."
            )

        approval["status"] = decision
        approval["decided_at"] = datetime.now(timezone.utc).isoformat()
        approval["decided_by"] = decided_by
        approval["decision_note"] = decision_note
        _save_approvals(approvals)
        return approval

    raise ValueError(f"Approval request not found: {approval_id}")