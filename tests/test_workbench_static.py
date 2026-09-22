import re
import shutil
import subprocess
import unittest
import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.service.sync_service import SyncService


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "ui"


class WorkbenchStaticTests(unittest.TestCase):
    def test_vendored_diff2html_assets_match_the_pinned_distribution(self):
        expected = {
            "diff2html.min.js": "a2110a09cee157bd5466da77be02107ac81a0baa2bc1f3fe81aac8183314598e",
            "diff2html.min.css": "d3ecc0e9b2b1e5c8466c19de29bed052fd0863475d25829ecc858446efded372",
        }
        vendor = UI / "vendor" / "diff2html"
        for name, digest in expected.items():
            with self.subTest(asset=name):
                self.assertEqual(hashlib.sha256((vendor / name).read_bytes()).hexdigest(), digest)

    def test_single_file_shell_contains_confirmed_controls_only(self):
        html = (UI / "index.html").read_text(encoding="utf-8")
        required_ids = {
            "fileInput", "editor", "preview", "catalogList", "focusReadButton",
            "focusReadOutput", "focusEditor", "focusApplyButton", "collectionInput", "remoteInput",
            "remoteListButton", "remoteOpenButton", "pullPreviewButton",
            "pullConfirmButton", "pushPreviewButton", "pushConfirmButton", "uploadButton", "providerSaveButton",
            "editorModeTitle", "editorModeHint", "syncOutput", "dirtyBadge", "statusMessage",
            "diffStats", "diffFiles", "diffAdded", "diffDeleted", "diffViewer",
            "providerTokenStatus", "collectionExamples",
        }

        for element_id in required_ids:
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', html)
        self.assertIn('data-workbench="single-file"', html)
        self.assertIn('<article id="preview"', html)
        self.assertIn('data-editor-mode="difference"', html)
        self.assertIn('data-editor-mode="source"', html)
        self.assertIn('data-editor-mode="render"', html)
        self.assertIn('/static/vendor/diff2html/diff2html.min.css', html)
        self.assertIn('/static/vendor/diff2html/diff2html.min.js', html)
        self.assertIsNone(re.search(r"\breview\b", html, re.IGNORECASE))
        self.assertNotIn("tablist", html)

    def test_frontend_calls_catalog_focus_and_sync_contracts(self):
        script = (UI / "app.js").read_text(encoding="utf-8")
        for endpoint in [
            "/api/v1/document/catalog",
            "/api/v1/document/focus/read",
            "/api/v1/document/focus/apply",
            "/api/v1/document/render",
            "/api/v1/sync/list",
            "/api/v1/sync/open",
            "/api/v1/sync/pull/preview",
            "/api/v1/sync/pull/confirm",
            "/api/v1/sync/push/preview",
            "/api/v1/sync/push/confirm",
            "/api/v1/sync/upload",
            "/api/v1/providers",
        ]:
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, script)
        self.assertIsNone(re.search(r"\breview\b", script, re.IGNORECASE))
        self.assertIn('window.addEventListener("beforeunload"', script)
        self.assertIn("confirmDiscard()", script)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("sessionStorage", script)
        self.assertIn("renderProviderTokenStatus", script)
        self.assertIn("setFocusMode", script)
        self.assertIn("refreshRenderedPreview", script)
        self.assertIn("setEditorMode", script)
        self.assertIn("window.Diff2Html.parse", script)
        self.assertIn("window.Diff2Html.html", script)
        self.assertNotIn("appendInlineMarkdown", script)
        self.assertNotIn("isMarkdownBlockStart", script)

    def test_javascript_has_valid_syntax(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        result = subprocess.run(
            [node, "--check", str(UI / "app.js")],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_static_assets_are_served_by_the_application(self):
        client = TestClient(create_app(sync_service=SyncService()))

        html = client.get("/")
        script = client.get("/static/app.js")
        styles = client.get("/static/styles.css")
        diff_script = client.get("/static/vendor/diff2html/diff2html.min.js")
        diff_styles = client.get("/static/vendor/diff2html/diff2html.min.css")

        self.assertEqual(html.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertEqual(styles.status_code, 200)
        self.assertEqual(diff_script.status_code, 200)
        self.assertEqual(diff_styles.status_code, 200)
        self.assertIn("single-file", html.text)
        self.assertIn("refreshCatalog", script.text)
        self.assertIn("@media (max-width: 760px)", styles.text)
        self.assertIn('data-editor-mode="difference"', html.text)
        self.assertNotIn("mobile-pane-switch", html.text)
        self.assertIn("Diff2Html", diff_script.text)
        self.assertIn(".d2h-file-wrapper", diff_styles.text)


if __name__ == "__main__":
    unittest.main()
