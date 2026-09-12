import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from api import AppSettings, create_app, load_settings


class ProductionConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = TemporaryDirectory()
        self.dist_path = Path(self.temp_directory.name)
        (self.dist_path / "index.html").write_text(
            "<!doctype html><title>AI Knowledge Agent</title>",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def make_app(self, app_env="development", frontend_origin=None):
        return create_app(
            AppSettings(
                app_env=app_env,
                session_secret="offline-session-secret",
                admin_password="offline-admin-password",
                employee_password="offline-employee-password",
                frontend_origin=frontend_origin,
            ),
            frontend_dist=self.dist_path,
        )

    def login(self, client):
        return client.post(
            "/auth/login",
            json={
                "username": "manager",
                "password": "offline-admin-password",
            },
        )

    def test_development_session_cookie_is_not_secure(self):
        response = self.login(TestClient(self.make_app()))

        cookie = response.headers["set-cookie"].lower()
        self.assertNotIn("secure", cookie)
        self.assertIn("httponly", cookie)

    def test_production_session_cookie_is_secure(self):
        response = self.login(
            TestClient(
                self.make_app(
                    app_env="production",
                    frontend_origin="https://app.example.com",
                ),
                base_url="https://testserver",
            )
        )

        cookie = response.headers["set-cookie"].lower()
        self.assertIn("secure", cookie)
        self.assertIn("httponly", cookie)

    def test_development_cors_allows_localhost(self):
        client = TestClient(self.make_app())

        response = client.options(
            "/chat",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )

    def test_unknown_origin_is_rejected(self):
        client = TestClient(self.make_app())

        response = client.options(
            "/chat",
            headers={
                "Origin": "https://unknown.example",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_production_uses_configured_frontend_origin(self):
        client = TestClient(
            self.make_app(
                app_env="production",
                frontend_origin="https://app.example.com",
            )
        )

        allowed = client.options(
            "/chat",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        rejected = client.options(
            "/chat",
            headers={
                "Origin": "https://other.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(
            allowed.headers["access-control-allow-origin"],
            "https://app.example.com",
        )
        self.assertNotIn(
            "access-control-allow-origin",
            rejected.headers,
        )

    def test_security_headers_are_present(self):
        response = TestClient(self.make_app()).get("/health")

        self.assertEqual(
            response.headers["x-content-type-options"],
            "nosniff",
        )
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(
            response.headers["referrer-policy"],
            "strict-origin-when-cross-origin",
        )

    def test_health_remains_public(self):
        response = TestClient(self.make_app()).get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_missing_production_secrets_fail_safely(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "Missing required environment variables",
        ) as raised:
            load_settings({"APP_ENV": "production"})

        self.assertNotIn("offline-session-secret", str(raised.exception))
        self.assertNotIn("offline-admin-password", str(raised.exception))

    def test_api_routes_are_not_swallowed_by_react_fallback(self):
        client = TestClient(self.make_app())

        self.assertEqual(client.get("/auth/not-a-route").status_code, 404)
        self.assertEqual(client.get("/approvals/not-a-route").status_code, 404)
        self.assertEqual(client.get("/dashboard").status_code, 200)
        self.assertIn(
            "AI Knowledge Agent",
            client.get("/dashboard").text,
        )


if __name__ == "__main__":
    unittest.main()