import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from src.controller.main import build_parser, format_table
from src.controller.sync_controller import SyncController
from src.core.document import parse_file, parse_text, render_document
from src.core.remote import RemoteContent, RemoteItem, RemotePath
from src.providers.base import RemoteProvider
from src.providers.gitee import GiteeIssueProvider, GiteePullProvider
from src.providers.github import GitHubIssueProvider, GitHubPullProvider
from src.providers.youtrack import YouTrackArticleProvider, YouTrackIssueProvider


class FakeProvider(RemoteProvider):
    source = "github"
    resource_type = "issues"
    supports_parent = True

    def __init__(self, *, fail_parent=False):
        self.calls = []
        self.fail_parent = fail_parent

    def list(self, collection):
        self.validate(collection, require="collection")
        self.calls.append(("list", collection))
        return [RemoteItem("2", "Second"), RemoteItem("10", "Tenth")]

    def pull(self, remote):
        self.validate(remote, require="object")
        self.calls.append(("pull", remote))
        return RemoteContent("Remote title", "Remote body\n")

    def push(self, remote, content):
        self.validate(remote, require="object")
        self.calls.append(("push", remote, content))

    def upload(self, collection, content, *, parent=None, base=None, head=None):
        self.validate(collection, require="collection")
        self.calls.append(("upload", collection, content, parent, base, head))
        return collection.with_id("42")

    def set_parent(self, remote, parent):
        self.calls.append(("set_parent", remote, parent))
        if self.fail_parent:
            raise RuntimeError("parent failed")


class PullOnlyProvider(FakeProvider):
    source = "github"
    resource_type = "pulls"
    supports_parent = False


def controller_with(provider):
    controller = SyncController({})
    controller.register(provider)
    return controller


def write_document(
    path,
    *,
    title="Local title",
    body="Local body\n",
    remote=None,
    parent=None,
    document_type=None,
):
    metadata = {"title": title}
    if document_type:
        metadata["type"] = document_type
    if parent:
        metadata["parent"] = parent
    document = parse_text("---\ntitle: placeholder\n---\n\n" + body, path)
    document.metadata = metadata
    document.remote = RemotePath.parse(remote, require="object") if remote else None
    document.body = body
    path.write_text(render_document(document), encoding="utf-8")


class RemotePathTests(unittest.TestCase):
    def test_supported_collection_and_object_paths(self):
        values = [
            ("github/issues/o/r", True),
            ("github/pulls/o/r/7", False),
            ("gitee/issues/o/r/8", False),
            ("gitee/pulls/o/r", True),
            ("youtrack/issues/DEMO/1", False),
            ("youtrack/articles/demo/22", False),
        ]
        for value, is_collection in values:
            with self.subTest(value=value):
                self.assertEqual(RemotePath.parse(value).is_collection, is_collection)
                self.assertEqual(str(RemotePath.parse(value)), value)

    def test_invalid_or_wrong_kind_paths_are_rejected(self):
        invalid = [
            "github/issue/o/r",
            "github/issues/o",
            "github/issues/o/r/1/extra",
            "unknown/issues/o/r",
            "youtrack/issues/DEMO/DEMO-1",
            "youtrack/articles/DEMO/DEMO-A-1",
        ]
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RemotePath.parse(value)
        with self.assertRaises(ValueError):
            RemotePath.parse("github/issues/o/r/1", require="collection")
        with self.assertRaises(ValueError):
            RemotePath.parse("github/issues/o/r", require="object")

    def test_collection_rejects_an_empty_created_id(self):
        collection = RemotePath.parse("github/issues/o/r", require="collection")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            collection.with_id("")

    def test_youtrack_collection_rejects_a_readable_id(self):
        collection = RemotePath.parse("youtrack/issues/DEMO", require="collection")
        with self.assertRaisesRegex(ValueError, "numeric"):
            collection.with_id("DEMO-1")


class DocumentTests(unittest.TestCase):
    def test_minimal_scalar_remote_round_trip(self):
        source = "---\ntitle: Example\nparent: github/issues/o/r/1\nremote: github/issues/o/r/2\n---\n\nBody\n"
        document = parse_text(source)
        self.assertEqual(str(document.remote), "github/issues/o/r/2")
        self.assertEqual(document.parent, "github/issues/o/r/1")
        reparsed = parse_text(render_document(document))
        self.assertEqual(str(reparsed.remote), "github/issues/o/r/2")
        self.assertEqual(reparsed.body, "Body\n")

    def test_mapping_remote_and_extra_metadata_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "remote must"):
            parse_text("---\ntitle: X\nremote:\n  github_issue: 1\n---\n\nBody")
        with self.assertRaisesRegex(ValueError, "unsupported metadata"):
            parse_text("---\ntitle: X\nstatus: open\n---\n\nBody")

    def test_parent_must_be_an_object_path(self):
        with self.assertRaisesRegex(ValueError, "expected an object"):
            parse_text("---\ntitle: X\nparent: youtrack/issues/DEMO\n---\n\nBody")


class ControllerTests(unittest.TestCase):
    def test_list_and_table(self):
        provider = FakeProvider()
        items = controller_with(provider).list("github/issues/o/r")
        self.assertEqual(
            format_table(items), "ID  TITLE\n--  -----\n2   Second\n10  Tenth"
        )
        self.assertEqual(provider.calls[0][0], "list")

    def test_pull_creates_single_bound_document(self):
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            controller_with(provider).pull(path, "github/issues/o/r/3")
            document = parse_file(path)
            self.assertEqual(document.title, "Remote title")
            self.assertEqual(document.body, "Remote body\n")
            self.assertEqual(str(document.remote), "github/issues/o/r/3")

    def test_pull_preserves_standard_document_type(self):
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            write_document(
                path,
                remote="github/issues/o/r/3",
                document_type="pirc.requirement",
            )

            controller_with(provider).pull(path)

            self.assertEqual(parse_file(path).document_type, "pirc.requirement")

    def test_push_only_updates_and_requires_remote(self):
        provider = FakeProvider()
        controller = controller_with(provider)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            write_document(path)
            with self.assertRaisesRegex(ValueError, "use upload"):
                controller.push(path)
            self.assertEqual(provider.calls, [])

            write_document(path, remote="github/issues/o/r/9")
            controller.push(path)
            self.assertEqual([call[0] for call in provider.calls], ["push"])

    def test_upload_only_creates_and_writes_remote(self):
        provider = FakeProvider()
        controller = controller_with(provider)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            write_document(path)
            controller.upload(path, "github/issues/o/r")
            self.assertEqual([call[0] for call in provider.calls], ["upload"])
            self.assertEqual(str(parse_file(path).remote), "github/issues/o/r/42")

            with self.assertRaisesRegex(ValueError, "use push"):
                controller.upload(path, "github/issues/o/r")
            self.assertEqual([call[0] for call in provider.calls], ["upload"])

    def test_upload_parent_is_creation_only_and_must_match_scope(self):
        provider = FakeProvider()
        controller = controller_with(provider)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            write_document(path, parent="github/issues/o/r/5")
            controller.upload(path, "github/issues/o/r", parent="github/issues/o/r/6")
            self.assertEqual(
                [call[0] for call in provider.calls], ["upload", "set_parent"]
            )
            self.assertEqual(parse_file(path).parent, "github/issues/o/r/6")

            other = Path(directory) / "other.md"
            write_document(other, parent="github/issues/o/other/5")
            with self.assertRaisesRegex(ValueError, "same project or repository"):
                controller.upload(other, "github/issues/o/r")

    def test_created_id_is_saved_before_parent_link_failure(self):
        provider = FakeProvider(fail_parent=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            write_document(path, parent="github/issues/o/r/5")
            with self.assertRaisesRegex(RuntimeError, "parent failed"):
                controller_with(provider).upload(path, "github/issues/o/r")
            self.assertEqual(str(parse_file(path).remote), "github/issues/o/r/42")

    def test_write_failure_reports_the_created_remote(self):
        provider = FakeProvider()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            write_document(path)
            with patch.object(Path, "write_text", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(
                    RuntimeError, "created github/issues/o/r/42"
                ):
                    controller_with(provider).upload(path, "github/issues/o/r")

    def test_pull_request_parent_is_rejected_before_upload(self):
        provider = PullOnlyProvider()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            write_document(path, parent="github/pulls/o/r/5")
            with self.assertRaisesRegex(ValueError, "does not support parent"):
                controller_with(provider).upload(
                    path, "github/pulls/o/r", base="main", head="feature"
                )
            self.assertEqual(provider.calls, [])


class ProviderContractTests(unittest.TestCase):
    def test_all_six_types_implement_one_contract(self):
        dummy = object()
        providers = [
            GitHubIssueProvider(dummy),
            GitHubPullProvider(dummy),
            GiteeIssueProvider(dummy),
            GiteePullProvider(dummy),
            YouTrackIssueProvider(dummy),
            YouTrackArticleProvider(dummy),
        ]
        self.assertTrue(
            all(isinstance(provider, RemoteProvider) for provider in providers)
        )
        self.assertEqual(len({provider.route for provider in providers}), 6)

    def test_cli_has_only_the_four_public_operations(self):
        parser = build_parser()
        for command in ["list", "pull", "push", "upload"]:
            with self.subTest(command=command):
                arguments = [command]
                if command == "list":
                    arguments += ["github/issues/o/r"]
                elif command == "pull":
                    arguments += ["doc.md"]
                elif command == "push":
                    arguments += ["doc.md"]
                else:
                    arguments += ["doc.md", "--target", "github/issues/o/r"]
                self.assertEqual(parser.parse_args(arguments).command, command)
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["sync-to-remote", "doc.md"])

    def test_youtrack_lists_through_project_resources(self):
        class Client:
            def __init__(self):
                self.paths = []

            def get(self, path):
                self.paths.append(path)
                return []

        client = Client()
        YouTrackIssueProvider(client).list(RemotePath.parse("youtrack/issues/DEMO"))
        YouTrackArticleProvider(client).list(RemotePath.parse("youtrack/articles/DEMO"))
        self.assertTrue(client.paths[0].startswith("/api/admin/projects/DEMO/issues?"))
        self.assertTrue(
            client.paths[1].startswith("/api/admin/projects/DEMO/articles?")
        )

    def test_youtrack_translates_numeric_paths_to_readable_api_ids(self):
        class Client:
            def __init__(self):
                self.paths = []

            def get(self, path):
                self.paths.append(path)
                if "/issues?" in path:
                    return [{"idReadable": "DEMO-39", "summary": "Issue"}]
                if "/articles?" in path:
                    return [{"idReadable": "DEMO-A-22", "summary": "Article"}]
                if path.startswith("/api/issues/"):
                    return {"summary": "Issue", "description": "Issue body"}
                return {"summary": "Article", "content": "Article body"}

            def post(self, path, payload):
                self.paths.append(path)
                if path.startswith("/api/issues?"):
                    return {"idReadable": "DEMO-40"}
                return {"idReadable": "DEMO-A-23"}

        client = Client()
        issue_provider = YouTrackIssueProvider(client)
        article_provider = YouTrackArticleProvider(client)
        issue_collection = RemotePath.parse("youtrack/issues/demo")
        article_collection = RemotePath.parse("youtrack/articles/demo")

        self.assertEqual(issue_provider.list(issue_collection)[0].object_id, "39")
        self.assertEqual(article_provider.list(article_collection)[0].object_id, "22")
        issue_provider.pull(RemotePath.parse("youtrack/issues/demo/39"))
        article_provider.pull(RemotePath.parse("youtrack/articles/demo/22"))
        self.assertEqual(
            str(issue_provider.upload(issue_collection, RemoteContent("T", "B"))),
            "youtrack/issues/demo/40",
        )
        self.assertEqual(
            str(article_provider.upload(article_collection, RemoteContent("T", "B"))),
            "youtrack/articles/demo/23",
        )
        self.assertTrue(
            any(path.startswith("/api/issues/demo-39?") for path in client.paths)
        )
        self.assertTrue(
            any(path.startswith("/api/articles/demo-A-22?") for path in client.paths)
        )

    def test_parent_project_scope_is_case_insensitive(self):
        provider = YouTrackIssueProvider(object())
        provider.validate_parent(
            RemotePath.parse("youtrack/issues/demo"),
            RemotePath.parse("youtrack/issues/DEMO/1"),
        )


if __name__ == "__main__":
    unittest.main()
