import argparse
import json

from approval_store import APPROVALS_PATH
from approval_workflow import decide_and_resume_approval


def list_approvals():
    if not APPROVALS_PATH.exists():
        approvals = []
    else:
        approvals = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    print(json.dumps(approvals, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Review approval requests outside the AI agent."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list")

    for command in ("approve", "reject"):
        decision_parser = subparsers.add_parser(command)
        decision_parser.add_argument("approval_id")
        decision_parser.add_argument("decided_by")
        decision_parser.add_argument("decision_note")

    args = parser.parse_args()

    if args.command == "list":
        list_approvals()
        return

    decision = "approved" if args.command == "approve" else "rejected"

    try:
        # Approval decisions happen here, outside the AI agent.
        result = decide_and_resume_approval(
            approval_id=args.approval_id,
            decision=decision,
            decided_by=args.decided_by,
            decision_note=args.decision_note,
        )
    except (PermissionError, ValueError) as error:
        raise SystemExit(f"Error: {error}") from error

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()