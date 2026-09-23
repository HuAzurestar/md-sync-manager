import unittest

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.controller.server import DEFAULT_HOST, DEFAULT_PORT
from src.core.capabilities import P0_CAPABILITIES
from src.service.sync_service import SyncService


OUT_OF_SCOPE_CAPABILITIES = {
    "review", "review-view", "review-record", "document.audit",
    "document.full", "document.template", "document.pair-check",
}


class AppShellTests(unittest.TestCase):
    def test_health_exposes_only_the_confirmed_p0_allowlist(self):
        response = TestClient(create_app()).get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["data"]["state"], "ready")
        self.assertEqual(payload["data"]["capabilities"], list(P0_CAPABILITIES))
        self.assertFalse(set(payload["data"]["capabilities"]) & OUT_OF_SCOPE_CAPABILITIES)

    def test_route_snapshot_has_no_review_or_deferred_product_surface(self):
        application = create_app()
        paths = {route.path for route in application.routes if hasattr(route, "path")}

        self.assertTrue(
            {"/", "/api/v1/health", "/api/v1/openapi.json"}.issubset(paths)
        )
        self.assertFalse(any("review" in path for path in paths))

    def test_unhandled_failure_uses_readable_response_envelope(self):
        application = create_app()

        @application.get("/explode")
        async def explode():
            raise RuntimeError("provider unavailable: private-token")

        response = TestClient(application, raise_server_exceptions=False).get("/explode")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "data": None,
                "error": {"message": "Operation failed; check provider settings or retry."},
            },
        )
        self.assertNotIn("private-token", response.text)

    def test_validation_errors_do_not_echo_submitted_content_or_token(self):
        client = TestClient(create_app(), raise_server_exceptions=False)
        content = client.post(
            "/api/v1/document/inspect",
            json={"content": "private-markdown-body"},
        )
        token = client.put(
            "/api/v1/providers",
            json={"providers": "private-provider-token"},
        )

        self.assertEqual(content.status_code, 500)
        self.assertEqual(token.status_code, 500)
        self.assertNotIn("private-markdown-body", content.text)
        self.assertNotIn("private-provider-token", token.text)
        self.assertIn("required fields", content.json()["error"]["message"])

    def test_missing_provider_has_actionable_safe_error(self):
        response = TestClient(
            create_app(sync_service=SyncService()), raise_server_exceptions=False
        ).post(
            "/api/v1/sync/list", json={"target": "youtrack/issues/DEMO"}
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["error"]["message"],
            "Set up YouTrack in Provider configuration.",
        )

    def test_inspect_preserves_inline_dashes_in_front_matter(self):
        response = TestClient(create_app()).post(
            "/api/v1/document/inspect",
            json={
                "name": "bound.md",
                "content": (
                    "---\ntitle: A---B\nremote: github/issues/o/r/2\n"
                    "---\n\nBody\n"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["title"], "A---B")
        self.assertEqual(response.json()["data"]["remote"], "github/issues/o/r/2")

    def test_workbench_shell_and_server_defaults_are_local_only(self):
        response = TestClient(create_app()).get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-workbench="single-file"', response.text)
        self.assertNotIn('id="review', response.text.casefold())
        self.assertEqual(DEFAULT_HOST, "127.0.0.1")
        self.assertEqual(DEFAULT_PORT, 8000)


if __name__ == "__main__":
    unittest.main()
