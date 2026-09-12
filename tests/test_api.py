import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

import approval_store
import approval_workflow
import api
import protected_actions
from api import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = TemporaryDirectory()
        self.original_approvals_path = approval_store.APPROVALS_PATH
        self.original_executions_path = protected_actions.EXECUTIONS_PATH
        approval_store.APPROVALS_PATH = (
            Path(self.temp_directory.name) / "approvals.json"
        )
        protected_actions.EXECUTIONS_PATH = (
            Path(self.temp_directory.name) / "executions.json"
        )
        self.original_admin_password = app.state.admin_password
        self.original_employee_password = app.state.employee_password
        app.state.admin_password = "offline-test-password"
        app.state.employee_password = "offline-employee-password"
        self.client = TestClient(app)

    def tearDown(self):
        app.state.admin_password = self.original_admin_password
        app.state.employee_password = self.original_employee_password
        approval_store.APPROVALS_PATH = self.original_approvals_path
        protected_actions.EXECUTIONS_PATH = self.original_executions_path
        self.temp_directory.cleanup()

    def login(self):
        response = self.client.post(
            "/auth/login",
            json={
                "username": "manager",
                "password": "offline-test-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response

    def create_pending_approval(self, requested_by="employee"):
        return approval_store.create_approval_request(
            approval_type="rush production request",
            reason="Customer requested faster delivery.",
            user_request="Please rush order 123.",
            requested_by=requested_by,
        )

    def login_as_employee(self):
        response = self.client.post(
            "/auth/login",
            json={
                "username": "employee",
                "password": "offline-employee-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_health_returns_200(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)

    def test_health_returns_ok_status(self):
        response = self.client.get("/health")

        self.assertEqual(response.json(), {"status": "ok"})

    def test_cors_allows_development_frontend(self):
        response = self.client.options(
            "/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )
        self.assertEqual(
            response.headers["access-control-allow-credentials"],
            "true",
        )

    def test_cors_does_not_allow_unknown_origin(self):
        response = self.client.options(
            "/chat",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertNotIn(
            "access-control-allow-origin",
            response.headers,
        )

    def test_empty_chat_message_is_rejected(self):
        self.login()
        response = self.client.post("/chat", json={"message": ""})

        self.assertEqual(response.status_code, 422)

    def test_whitespace_only_chat_message_is_rejected(self):
        self.login()
        response = self.client.post("/chat", json={"message": "   \n\t"})

        self.assertEqual(response.status_code, 422)

    @patch("api.answer_question")
    def test_chat_returns_answer_and_tool_names(self, mock_answer):
        self.login()
        mock_answer.return_value = (
            "Test answer",
            [{"name": "search_company_knowledge"}],
        )

        response = self.client.post(
            "/chat",
            json={"message": "Test question"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "answer": "Test answer",
                "tools_used": ["search_company_knowledge"],
            },
        )
        mock_answer.assert_called_once_with(
            "Test question",
            requester_id="manager",
        )

    @patch("api.answer_question")
    def test_chat_exception_returns_generic_error(self, mock_answer):
        self.login()
        raw_error = "sensitive internal failure"
        mock_answer.side_effect = RuntimeError(raw_error)

        response = self.client.post(
            "/chat",
            json={"message": "Test question"},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "Internal server error"},
        )
        self.assertNotIn(raw_error, response.text)

    def test_get_approvals_returns_filtered_records(self):
        self.login()
        approval = self.create_pending_approval()
        records = approval_store.list_approval_requests()
        records[0]["internal_value"] = "must not be exposed"
        approval_store._save_approvals(records)

        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(
            response.json()[0]["approval_id"],
            approval["approval_id"],
        )
        self.assertIsNone(response.json()[0]["execution"])
        self.assertEqual(
            response.json()[0]["execution_status"],
            "pending",
        )
        self.assertNotIn("internal_value", response.json()[0])

    def test_get_approvals_returns_empty_list(self):
        self.login()
        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_approve_pending_request_succeeds(self):
        self.login()
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decision_note": "Request verified.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["approval"]["status"],
            "approved",
        )
        self.assertEqual(
            response.json()["approval"]["decided_by"],
            "manager",
        )
        self.assertEqual(
            response.json()["execution"]["status"],
            "executed",
        )
        self.assertEqual(
            response.json()["execution_status"],
            "executed",
        )
        self.assertEqual(
            protected_actions.get_execution_for_approval(
                approval["approval_id"]
            )["approval_id"],
            approval["approval_id"],
        )

    def test_reject_pending_request_succeeds(self):
        self.login()
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "rejected",
                "decision_note": "Insufficient justification.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["approval"]["status"],
            "rejected",
        )
        self.assertIsNone(response.json()["execution"])
        self.assertEqual(
            response.json()["execution_status"],
            "not_executed",
        )
        self.assertIsNone(
            protected_actions.get_execution_for_approval(
                approval["approval_id"]
            )
        )

    def test_get_approvals_reports_execution_information(self):
        self.login()
        approval = self.create_pending_approval()
        decision = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decision_note": "Request verified.",
            },
        )
        self.assertEqual(decision.status_code, 200)

        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 200)
        execution = response.json()[0]["execution"]
        self.assertEqual(execution["status"], "executed")
        self.assertEqual(
            execution["action_type"],
            "rush production execution",
        )
        self.assertIn("execution_id", execution)
        self.assertIn("executed_at", execution)
        self.assertNotIn("approval_id", execution)
        self.assertEqual(
            response.json()[0]["execution_status"],
            "executed",
        )

    @patch(
        "approval_workflow.execute_approved_rush",
        side_effect=RuntimeError("sensitive execution failure"),
    )
    def test_saved_approval_reports_execution_failure(self, _mock_execute):
        self.login()
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decision_note": "Request verified.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["approval"]["status"],
            "approved",
        )
        self.assertIsNone(response.json()["execution"])
        self.assertEqual(
            response.json()["execution_status"],
            "failed",
        )
        self.assertNotIn("sensitive execution failure", response.text)

    def test_get_approvals_marks_approved_without_execution_for_retry(self):
        self.login()
        approval = self.create_pending_approval()
        approval_store.decide_approval(
            approval["approval_id"],
            "approved",
            "manager",
            "Previously approved.",
        )

        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["status"], "approved")
        self.assertIsNone(response.json()[0]["execution"])
        self.assertEqual(
            response.json()[0]["execution_status"],
            "retry_required",
        )

    def test_invalid_decision_is_rejected(self):
        self.login()
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "maybe",
                "decision_note": "Review complete.",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_unexpected_reviewer_field_is_rejected(self):
        self.login()
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decided_by": "spoofed-reviewer",
                "decision_note": "Review complete.",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_blank_decision_note_is_rejected(self):
        self.login()
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decision_note": "\n\t",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_unknown_approval_id_returns_404(self):
        self.login()
        response = self.client.post(
            "/approvals/unknown-id/decision",
            json={
                "decision": "approved",
                "decision_note": "Review complete.",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"detail": "Approval request not found"},
        )

    def test_deciding_already_decided_request_returns_409(self):
        self.login()
        approval = self.create_pending_approval()
        approval_store.decide_approval(
            approval["approval_id"],
            "approved",
            "manager",
            "Initial decision.",
        )

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "rejected",
                "decision_note": "Attempted second decision.",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"detail": "Approval request has already been decided"},
        )

    def test_unauthenticated_chat_returns_401(self):
        response = self.client.post(
            "/chat",
            json={"message": "Do not answer this."},
        )

        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_approvals_returns_401(self):
        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_approval_decision_returns_401(self):
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decision_note": "Must not be applied.",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            approval_store.get_approval_request(approval["approval_id"])[
                "status"
            ],
            "pending",
        )

    def test_wrong_password_returns_401(self):
        response = self.client.post(
            "/auth/login",
            json={
                "username": "manager",
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Invalid credentials"})

    def test_correct_login_succeeds(self):
        response = self.login()

        self.assertEqual(
            response.json(),
            {
                "authenticated": True,
                "username": "manager",
                "role": "approver",
            },
        )

    def test_authenticated_auth_me_reports_true(self):
        self.login()

        response = self.client.get("/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "authenticated": True,
                "username": "manager",
                "role": "approver",
            },
        )

    def test_employee_login_succeeds(self):
        response = self.login_as_employee()

        self.assertEqual(
            response.json(),
            {
                "authenticated": True,
                "username": "employee",
                "role": "employee",
            },
        )

    def test_employee_cannot_view_approvals(self):
        self.login_as_employee()

        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 403)

    def test_employee_cannot_decide_approvals(self):
        self.login_as_employee()
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decision_note": "Must be blocked.",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            approval_store.get_approval_request(approval["approval_id"])[
                "status"
            ],
            "pending",
        )

    def test_manager_can_view_approvals(self):
        self.login()
        self.create_pending_approval()

        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 200)

    def test_self_decision_is_forbidden_and_stays_pending(self):
        self.login()
        approval = self.create_pending_approval(requested_by="manager")

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decision_note": "Self approval must be blocked.",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            approval_store.get_approval_request(approval["approval_id"])[
                "status"
            ],
            "pending",
        )

    def test_decision_body_rejects_spoofed_reviewer(self):
        self.login()
        approval = self.create_pending_approval()

        response = self.client.post(
            f"/approvals/{approval['approval_id']}/decision",
            json={
                "decision": "approved",
                "decided_by": "spoofed",
                "decision_note": "Unexpected field.",
            },
        )

        self.assertEqual(response.status_code, 422)

    @patch("api.answer_question")
    def test_chat_passes_authenticated_username_to_agent(self, mock_answer):
        self.login_as_employee()
        mock_answer.return_value = ("Offline answer", [])

        response = self.client.post(
            "/chat",
            json={"message": "Employee question"},
        )

        self.assertEqual(response.status_code, 200)
        mock_answer.assert_called_once_with(
            "Employee question",
            requester_id="employee",
        )

    @patch("api.answer_question")
    def test_authenticated_chat_succeeds(self, mock_answer):
        self.login()
        mock_answer.return_value = ("Offline answer", [])

        response = self.client.post(
            "/chat",
            json={"message": "Offline question"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"answer": "Offline answer", "tools_used": []},
        )

    def test_authenticated_approvals_succeeds(self):
        self.login()
        self.create_pending_approval()

        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_logout_clears_authentication(self):
        self.login()

        response = self.client.post("/auth/logout")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"authenticated": False})
        self.assertEqual(
            self.client.get("/auth/me").json(),
            {"authenticated": False},
        )

    def test_protected_endpoint_fails_after_logout(self):
        self.login()
        self.client.post("/auth/logout")

        response = self.client.get("/approvals")

        self.assertEqual(response.status_code, 401)

    def test_login_response_does_not_contain_admin_password(self):
        response = self.login()

        self.assertNotIn("offline-test-password", response.text)

    def test_session_cookie_is_httponly(self):
        response = self.login()

        cookie = response.headers["set-cookie"].lower()
        self.assertIn("knowledge_agent_session=", cookie)
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)


if __name__ == "__main__":
    unittest.main()