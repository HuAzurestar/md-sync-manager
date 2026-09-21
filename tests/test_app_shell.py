import unittest

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.controller.server import DEFAULT_HOST, DEFAULT_PORT
from src.core.capabilities import DEFERRED_CAPABILITIES, P0_CAPABILITIES


class AppShellTests(unittest.TestCase):
    def test_health_exposes_only_the_confirmed_p0_allowlist(self):
        response = TestClient(create_app()).get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertIsNone(payload["error"])
        self.assertEqual(payload["data"]["state"], "ready")
        self.assertEqual(payload["data"]["capabilities"], list(P0_CAPABILITIES))
        self.assertFalse(set(payload["data"]["capabilities"]) & DEFERRED_CAPABILITIES)

    def test_route_snapshot_has_no_review_or_deferred_product_surface(self):
        application = create_app()
        paths = {route.path for route in application.routes}

        self.assertEqual(
            paths,
            {"/", "/api/v1/health", "/api/v1/openapi.json"},
        )
        self.assertFalse(any("review" in path for path in paths))

    def test_unhandled_failure_uses_readable_response_envelope(self):
        application = create_app()

        @application.get("/explode")
        async def explode():
            raise RuntimeError("provider unavailable")

        response = TestClient(application, raise_server_exceptions=False).get("/explode")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "status": "error",
                "data": None,
                "error": {"message": "provider unavailable"},
            },
        )

    def test_workbench_shell_and_server_defaults_are_local_only(self):
        response = TestClient(create_app()).get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-workbench="single-file"', response.text)
        self.assertNotIn("review", response.text.casefold())
        self.assertEqual(DEFAULT_HOST, "127.0.0.1")
        self.assertEqual(DEFAULT_PORT, 8000)


if __name__ == "__main__":
    unittest.main()
