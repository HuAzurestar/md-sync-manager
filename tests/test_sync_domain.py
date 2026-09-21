import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from src.core.config import ConfigStore
from src.core.document import parse_file, parse_text, render_document
from src.core.remote import RemoteAccessPolicy, RemoteContent, RemoteItem
from src.providers.base import RemoteProvider
from src.service.sync_service import PartialSyncError, SyncService


class FakeProvider(RemoteProvider):
    source = "github"
    resource_type = "issues"
    supports_parent = True

    def __init__(self, fail_parent=False):
        self.fail_parent = fail_parent

    def list(self, collection):
        self.validate(collection, require="collection")
        return [RemoteItem("1", "One")]

    def pull(self, remote):
        return RemoteContent("Title", "Body\n")

    def push(self, remote, content):
        return None

    def upload(self, collection, content, *, parent=None, base=None, head=None):
        return collection.with_id("42")

    def set_parent(self, remote, parent):
        if self.fail_parent:
            raise RuntimeError("parent link failed")


def write_document(path: Path, *, parent: str | None = None) -> None:
    document = parse_text("---\ntitle: Local\n---\n\nBody\n", path)
    if parent:
        document.metadata["parent"] = parent
    path.write_text(render_document(document), encoding="utf-8")


class SyncDomainTests(unittest.TestCase):
    def test_access_policy_is_case_insensitive_and_applies_to_objects(self):
        policy = RemoteAccessPolicy(("github/issues/Owner/Repo",))
        service = SyncService((FakeProvider(),), policy)

        self.assertEqual(service.list("github/issues/owner/repo")[0].title, "One")
        with self.assertRaisesRegex(ValueError, "outside"):
            service.list("github/issues/owner/other")

    def test_partial_upload_preserves_binding_and_reports_created_remote(self):
        service = SyncService((FakeProvider(fail_parent=True),))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            write_document(path, parent="github/issues/o/r/1")

            with self.assertRaises(PartialSyncError) as raised:
                service.upload(path, "github/issues/o/r")

            self.assertEqual(str(parse_file(path).remote), "github/issues/o/r/42")
            self.assertEqual(
                raised.exception.as_result(),
                {
                    "status": "PARTIAL",
                    "operation": "upload",
                    "remote": "github/issues/o/r/42",
                    "message": "parent link failed",
                },
            )


class ConfigStoreTests(unittest.TestCase):
    def test_public_config_never_returns_tokens_and_honors_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sync.yaml"
            path.write_text(
                yaml.safe_dump(
                    {
                        "providers": {
                            "github": {
                                "enabled": True,
                                "api_url": "https://example.invalid",
                                "token": "stored-secret",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"GITHUB_TOKEN": "environment-secret"}):
                store = ConfigStore(path)
                public = store.public()
                effective = store.load()

            self.assertEqual(
                effective["providers"]["github"]["token"], "environment-secret"
            )
            self.assertNotIn("token", public["providers"]["github"])
            self.assertTrue(public["providers"]["github"]["token_configured"])
            self.assertEqual(
                public["providers"]["github"]["token_source"], "environment"
            )
            self.assertNotIn("stored-secret", repr(public))
            self.assertNotIn("environment-secret", repr(public))

    def test_update_is_persistent_and_rejects_unknown_provider_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sync.yaml"
            store = ConfigStore(path)
            public = store.update(
                {
                    "gitee": {
                        "enabled": True,
                        "url": "https://gitee.example/api/",
                        "token": "secret",
                    }
                }
            )

            self.assertTrue(path.exists())
            self.assertTrue(public["providers"]["gitee"]["token_configured"])
            self.assertNotIn("secret", repr(public))
            with self.assertRaisesRegex(ValueError, "unsupported provider setting"):
                store.update({"gitee": {"review": True}})


if __name__ == "__main__":
    unittest.main()
