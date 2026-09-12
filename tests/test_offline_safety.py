import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import approval_store
import approval_workflow
import protected_actions
from delivery_tool import add_business_days, calculate_delivery_timeline


class DeliveryTimelineTests(unittest.TestCase):
    def test_valid_timeline(self):
        timeline = calculate_delivery_timeline("2026-09-15")

        self.assertEqual(timeline["production_ready_date"], "2026-10-06")
        self.assertEqual(timeline["earliest_delivery_date"], "2026-10-09")
        self.assertEqual(timeline["latest_delivery_date"], "2026-10-13")

    def test_business_days_skip_weekend(self):
        friday = date(2026, 9, 18)

        self.assertEqual(add_business_days(friday, 1), date(2026, 9, 21))
        self.assertEqual(add_business_days(friday, 3), date(2026, 9, 23))

    def test_invalid_date(self):
        with self.assertRaises(ValueError):
            calculate_delivery_timeline("2026-02-30")

    def test_invalid_date_format(self):
        with self.assertRaises(ValueError):
            calculate_delivery_timeline("09/15/2026")


class ApprovalSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_path = Path(self.temporary_directory.name)

        self.original_approvals_path = approval_store.APPROVALS_PATH
        self.original_executions_path = protected_actions.EXECUTIONS_PATH

        approval_store.APPROVALS_PATH = temporary_path / "approvals.json"
        protected_actions.EXECUTIONS_PATH = temporary_path / "executions.json"

    def tearDown(self):
        approval_store.APPROVALS_PATH = self.original_approvals_path
        protected_actions.EXECUTIONS_PATH = self.original_executions_path
        self.temporary_directory.cleanup()

    def create_approval(self, approval_type="rush production request"):
        return approval_store.create_approval_request(
            approval_type=approval_type,
            reason="Offline safety test.",
            user_request="Please rush this order.",
            requested_by="employee",
        )

    def make_approval_legacy(self, approval_id, include_action=False):
        approvals = approval_store.list_approval_requests()
        for approval in approvals:
            if approval["approval_id"] == approval_id:
                approval["approval_type"] = "rush_order"
                if not include_action:
                    approval.pop("requested_action", None)
        approval_store._save_approvals(approvals)

    def decide(self, approval_id, decision):
        return approval_store.decide_approval(
            approval_id=approval_id,
            decision=decision,
            decided_by="Offline test reviewer",
            decision_note=f"Request {decision} for offline testing.",
        )

    def test_new_approval_starts_pending(self):
        approval = self.create_approval()

        self.assertEqual(approval["status"], "pending")
        persisted = approval_store.get_approval_request(
            approval["approval_id"]
        )
        self.assertEqual(persisted["status"], "pending")
        self.assertEqual(
            persisted["requested_action"],
            "execute_approved_rush",
        )

    def test_approval_requires_requester_identity(self):
        with self.assertRaisesRegex(
            ValueError,
            "requested_by must be a nonblank string",
        ):
            approval_store.create_approval_request(
                approval_type="rush production request",
                reason="Missing requester.",
                user_request="This must not be persisted.",
                requested_by=" ",
            )

    def test_legacy_alias_is_normalized_for_new_records(self):
        approval = self.create_approval(approval_type="rush_order")

        self.assertEqual(
            approval["approval_type"],
            approval_store.CANONICAL_RUSH_APPROVAL_TYPE,
        )
        self.assertEqual(
            approval["requested_action"],
            "execute_approved_rush",
        )

    def test_legacy_approval_type_resolves_to_rush_action(self):
        approval = self.create_approval()
        self.make_approval_legacy(approval["approval_id"])
        persisted = approval_store.get_approval_request(
            approval["approval_id"]
        )

        self.assertEqual(
            approval_workflow.resolve_requested_action(persisted),
            "execute_approved_rush",
        )

    def test_pending_approval_cannot_resume(self):
        approval = self.create_approval()

        with self.assertRaisesRegex(ValueError, "requires approved status"):
            approval_workflow.resume_approved_workflow(
                approval["approval_id"]
            )

    def test_pending_approval_cannot_execute(self):
        approval = self.create_approval()

        with self.assertRaisesRegex(ValueError, "is pending"):
            protected_actions.execute_approved_rush(
                approval["approval_id"]
            )
        self.assertFalse(protected_actions.EXECUTIONS_PATH.exists())

    def test_rejected_approval_cannot_execute(self):
        approval = self.create_approval()
        self.decide(approval["approval_id"], "rejected")

        with self.assertRaisesRegex(ValueError, "is rejected"):
            protected_actions.execute_approved_rush(
                approval["approval_id"]
            )
        self.assertFalse(protected_actions.EXECUTIONS_PATH.exists())

    def test_rejected_decision_does_not_resume(self):
        approval = self.create_approval()

        result = approval_workflow.decide_and_resume_approval(
            approval["approval_id"],
            "rejected",
            "Offline test reviewer",
            "Rejected in offline test.",
        )

        self.assertEqual(result["approval"]["status"], "rejected")
        self.assertIsNone(result["execution"])
        self.assertFalse(protected_actions.EXECUTIONS_PATH.exists())

    def test_approved_approval_can_execute(self):
        approval = self.create_approval()
        self.decide(approval["approval_id"], "approved")

        execution = protected_actions.execute_approved_rush(
            approval["approval_id"]
        )

        self.assertEqual(execution["approval_id"], approval["approval_id"])
        self.assertEqual(execution["status"], "executed")
        executions = json.loads(
            protected_actions.EXECUTIONS_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(executions, [execution])

    def test_approved_decision_resumes_and_persists_execution(self):
        approval = self.create_approval()

        result = approval_workflow.decide_and_resume_approval(
            approval["approval_id"],
            "approved",
            "Offline test reviewer",
            "Approved in offline test.",
        )

        self.assertEqual(result["approval"]["status"], "approved")
        self.assertEqual(result["execution"]["status"], "executed")
        self.assertEqual(
            result["execution"]["approval_id"],
            approval["approval_id"],
        )
        self.assertEqual(
            protected_actions.get_execution_for_approval(
                approval["approval_id"]
            ),
            result["execution"],
        )
        self.assertEqual(result["execution_status"], "executed")

    def test_pending_legacy_request_can_be_approved_and_executed(self):
        approval = self.create_approval()
        self.make_approval_legacy(approval["approval_id"])

        result = approval_workflow.decide_and_resume_approval(
            approval["approval_id"],
            "approved",
            "Offline test reviewer",
            "Approved legacy request.",
        )

        self.assertEqual(result["approval"]["status"], "approved")
        self.assertEqual(result["execution_status"], "executed")
        self.assertEqual(result["execution"]["status"], "executed")

    def test_approved_legacy_request_can_be_resumed(self):
        approval = self.create_approval()
        self.make_approval_legacy(approval["approval_id"])
        self.decide(approval["approval_id"], "approved")

        execution = approval_workflow.resume_approved_workflow(
            approval["approval_id"]
        )

        self.assertEqual(execution["status"], "executed")

    def test_approved_approval_cannot_execute_twice(self):
        approval = self.create_approval()
        self.decide(approval["approval_id"], "approved")
        protected_actions.execute_approved_rush(approval["approval_id"])

        with self.assertRaisesRegex(ValueError, "already been executed"):
            protected_actions.execute_approved_rush(
                approval["approval_id"]
            )
        executions = json.loads(
            protected_actions.EXECUTIONS_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(len(executions), 1)

    def test_approved_workflow_cannot_resume_twice(self):
        approval = self.create_approval()
        self.decide(approval["approval_id"], "approved")
        approval_workflow.resume_approved_workflow(approval["approval_id"])

        with self.assertRaisesRegex(ValueError, "already been executed"):
            approval_workflow.resume_approved_workflow(
                approval["approval_id"]
            )

    def test_wrong_approval_type_cannot_execute_as_rush(self):
        approval = self.create_approval(approval_type="refund request")
        self.decide(approval["approval_id"], "approved")

        with self.assertRaisesRegex(ValueError, "not for rush production"):
            protected_actions.execute_approved_rush(
                approval["approval_id"]
            )
        self.assertFalse(protected_actions.EXECUTIONS_PATH.exists())

    def test_wrong_approval_type_cannot_resume_as_rush(self):
        approval = self.create_approval(approval_type="refund request")
        self.decide(approval["approval_id"], "approved")

        with self.assertRaisesRegex(ValueError, "no supported requested action"):
            approval_workflow.resume_approved_workflow(
                approval["approval_id"]
            )
        self.assertFalse(protected_actions.EXECUTIONS_PATH.exists())

    def test_unknown_type_is_rejected_before_approval_mutation(self):
        approval = self.create_approval(approval_type="refund request")

        with self.assertRaisesRegex(ValueError, "no supported requested action"):
            approval_workflow.decide_and_resume_approval(
                approval["approval_id"],
                "approved",
                "Offline test reviewer",
                "Must remain pending.",
            )

        persisted = approval_store.get_approval_request(
            approval["approval_id"]
        )
        self.assertEqual(persisted["status"], "pending")

    def test_unknown_requested_action_is_blocked(self):
        approval = self.create_approval()
        approvals = approval_store.list_approval_requests()
        approvals[0]["requested_action"] = "run_arbitrary_function"
        approval_store._save_approvals(approvals)
        self.decide(approval["approval_id"], "approved")

        with self.assertRaisesRegex(ValueError, "no supported requested action"):
            approval_workflow.resume_approved_workflow(
                approval["approval_id"]
            )
        self.assertFalse(protected_actions.EXECUTIONS_PATH.exists())

    def test_unknown_action_is_rejected_before_approval_mutation(self):
        approval = self.create_approval()
        approvals = approval_store.list_approval_requests()
        approvals[0]["requested_action"] = "run_arbitrary_function"
        approval_store._save_approvals(approvals)

        with self.assertRaisesRegex(ValueError, "no supported requested action"):
            approval_workflow.decide_and_resume_approval(
                approval["approval_id"],
                "approved",
                "Offline test reviewer",
                "Must remain pending.",
            )

        persisted = approval_store.get_approval_request(
            approval["approval_id"]
        )
        self.assertEqual(persisted["status"], "pending")

    def test_older_rush_approval_without_action_can_resume(self):
        approval = self.create_approval()
        approvals = approval_store.list_approval_requests()
        del approvals[0]["requested_action"]
        approval_store._save_approvals(approvals)
        self.decide(approval["approval_id"], "approved")

        execution = approval_workflow.resume_approved_workflow(
            approval["approval_id"]
        )

        self.assertEqual(execution["status"], "executed")

    def test_approval_cannot_be_decided_twice(self):
        approval = self.create_approval()
        self.decide(approval["approval_id"], "approved")

        with self.assertRaisesRegex(ValueError, "is already approved"):
            self.decide(approval["approval_id"], "rejected")
        persisted = approval_store.get_approval_request(
            approval["approval_id"]
        )
        self.assertEqual(persisted["status"], "approved")

    def test_invalid_approval_decision_is_rejected(self):
        approval = self.create_approval()

        with self.assertRaisesRegex(
            ValueError,
            'decision must be exactly "approved" or "rejected"',
        ):
            self.decide(approval["approval_id"], "maybe")
        persisted = approval_store.get_approval_request(
            approval["approval_id"]
        )
        self.assertEqual(persisted["status"], "pending")


if __name__ == "__main__":
    unittest.main()