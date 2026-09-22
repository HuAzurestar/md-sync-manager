import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.config import ConfigStore
from src.core.remote import RemoteContent, RemoteItem
from src.providers.base import RemoteProvider
from src.service.sync_service import SyncService


class FakeProvider(RemoteProvider):
    source = "github"
    resource_type = "issues"
    supports_parent = True

    def __init__(self, *, fail_parent=False):
        self.calls = []
        self.fail_parent = fail_parent

    def list(self, collection):
        self.calls.append(("list", str(collection)))
        return [RemoteItem("7", "Seven")]

    def pull(self, remote):
        self.calls.append(("pull", str(remote)))
        return RemoteContent("Remote title", "# Remote\nRemote body\n")

    def push(self, remote, content):
        self.calls.append(("push", str(remote), content.body))

    def upload(self, collection, content, *, parent=None, base=None, head=None):
        self.calls.append(("upload", str(collection), content.body))
        return collection.with_id("42")

    def set_parent(self, remote, parent):
        self.calls.append(("set_parent", str(remote), str(parent)))
        if self.fail_parent:
            raise RuntimeError("parent link failed")


def bound_content(body="# Local\nLocal body\n"):
    return (
        "---\n"
        "title: Local title\n"
        "remote: github/issues/o/r/9\n"
        "---\n\n"
        + body
    )


class SyncApiTests(unittest.TestCase):
    def make_client(self, directory, *, fail_parent=False):
        provider = FakeProvider(fail_parent=fail_parent)
        service = SyncService((provider,))
        application = create_app(
            config_store=ConfigStore(Path(directory) / "config.yaml"),
            sync_service=service,
        )
        return TestClient(application, raise_server_exceptions=False), provider

    def test_list_and_open_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            client, _provider = self.make_client(directory)

            listed = client.post(
                "/api/v1/sync/list", json={"target": "github/issues/o/r"}
            )
            opened = client.post(
                "/api/v1/sync/open", json={"remote": "github/issues/o/r/7"}
            )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["data"]["items"], [{"id": "7", "title": "Seven"}])
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.json()["data"]["document"]["remote"], "github/issues/o/r/7")
        self.assertNotIn("sha", repr(opened.json()).casefold())

    def test_pull_requires_preview_and_exact_original_content(self):
        original = bound_content()
        with tempfile.TemporaryDirectory() as directory:
            client, _provider = self.make_client(directory)
            preview = client.post(
                "/api/v1/sync/pull/preview",
                json={"name": "doc.md", "content": original},
            ).json()["data"]

            rejected = client.post(
                "/api/v1/sync/pull/confirm",
                json={
                    "name": "doc.md",
                    "content": original + "changed",
                    "preview_id": preview["preview_id"],
                },
            )
            confirmed = client.post(
                "/api/v1/sync/pull/confirm",
                json={
                    "name": "doc.md",
                    "content": original,
                    "preview_id": preview["preview_id"],
                },
            )

        self.assertTrue(preview["changed"])
        self.assertIn("--- a/doc.md", preview["diff"])
        self.assertIn("+++ b/doc.md", preview["diff"])
        self.assertEqual(rejected.status_code, 500)
        self.assertIn("no longer matches", rejected.json()["error"]["message"])
        self.assertEqual(confirmed.status_code, 200)
        self.assertIn("Remote body", confirmed.json()["data"]["content"])

    def test_push_upload_and_partial_upload_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            client, provider = self.make_client(directory)
            pushed = client.post(
                "/api/v1/sync/push",
                json={"name": "doc.md", "content": bound_content()},
            )
            uploaded = client.post(
                "/api/v1/sync/upload",
                json={
                    "name": "new.md",
                    "content": "# New\nBody\n",
                    "target": "github/issues/o/r",
                },
            )

            partial_client, _partial_provider = self.make_client(
                directory, fail_parent=True
            )
            partial = partial_client.post(
                "/api/v1/sync/upload",
                json={
                    "name": "partial.md",
                    "content": "# Partial\nBody\n",
                    "target": "github/issues/o/r",
                    "parent": "github/issues/o/r/1",
                },
            )

        self.assertEqual(pushed.json()["data"]["result"]["direction"], "push")
        self.assertEqual(uploaded.json()["data"]["result"]["status"], "SUCCESS")
        self.assertEqual(uploaded.json()["data"]["document"]["remote"], "github/issues/o/r/42")
        self.assertEqual(partial.status_code, 200)
        self.assertEqual(partial.json()["data"]["result"]["status"], "PARTIAL")
        self.assertEqual(partial.json()["data"]["document"]["remote"], "github/issues/o/r/42")
        self.assertEqual([call[0] for call in provider.calls], ["push", "upload"])

    def test_push_preview_requires_unchanged_local_and_remote_content(self):
        original = bound_content("# Local\nPush this body\n")
        with tempfile.TemporaryDirectory() as directory:
            client, provider = self.make_client(directory)
            preview = client.post(
                "/api/v1/sync/push/preview",
                json={"name": "doc.md", "content": original},
            ).json()["data"]
            changed_local = client.post(
                "/api/v1/sync/push/confirm",
                json={
                    "name": "doc.md",
                    "content": original + "changed",
                    "preview_id": preview["preview_id"],
                },
            )
            confirmed = client.post(
                "/api/v1/sync/push/confirm",
                json={
                    "name": "doc.md",
                    "content": original,
                    "preview_id": preview["preview_id"],
                },
            )

        self.assertTrue(preview["changed"])
        self.assertIn("--- a/doc.md", preview["diff"])
        self.assertIn("+++ b/doc.md", preview["diff"])
        self.assertEqual(changed_local.status_code, 500)
        self.assertIn("no longer matches", changed_local.json()["error"]["message"])
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["data"]["result"]["direction"], "push")
        self.assertEqual([call[0] for call in provider.calls], ["pull", "pull", "push"])

    def test_push_confirm_rejects_remote_change_after_preview(self):
        original = bound_content("# Local\nPush this body\n")
        with tempfile.TemporaryDirectory() as directory:
            client, provider = self.make_client(directory)
            preview = client.post(
                "/api/v1/sync/push/preview",
                json={"name": "doc.md", "content": original},
            ).json()["data"]

            def changed_pull(remote):
                provider.calls.append(("pull", str(remote)))
                return RemoteContent("Changed remotely", "# Remote\nNew remote body\n")

            provider.pull = changed_pull
            rejected = client.post(
                "/api/v1/sync/push/confirm",
                json={
                    "name": "doc.md",
                    "content": original,
                    "preview_id": preview["preview_id"],
                },
            )

        self.assertEqual(rejected.status_code, 500)
        self.assertIn("remote document no longer matches", rejected.json()["error"]["message"])
        self.assertNotIn("push", [call[0] for call in provider.calls])

    def test_provider_config_is_public_and_persistent_without_token_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            client, _provider = self.make_client(directory)
            response = client.put(
                "/api/v1/providers",
                json={
                    "providers": {
                        "github": {
                            "enabled": True,
                            "url": "https://github.example/api",
                            "token": "top-secret",
                        }
                    }
                },
            )
            loaded = client.get("/api/v1/providers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(loaded.status_code, 200)
        self.assertTrue(response.json()["data"]["providers"]["github"]["token_configured"])
        self.assertNotIn("top-secret", repr(response.json()))
        self.assertNotIn("top-secret", repr(loaded.json()))

    def test_invalid_requests_use_http_500_and_no_review_route_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            client, _provider = self.make_client(directory)
            malformed = client.post("/api/v1/sync/list", json={})
            missing_route = client.post("/api/v1/review", json={})

        self.assertEqual(malformed.status_code, 500)
        self.assertEqual(malformed.json()["status"], "error")
        self.assertEqual(missing_route.status_code, 404)


if __name__ == "__main__":
    unittest.main()
