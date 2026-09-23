import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
BROWSER_CANDIDATES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
)


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class WorkbenchBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise unittest.SkipTest("playwright is not installed") from exc

        executable = next((path for path in BROWSER_CANDIDATES if path.exists()), None)
        if executable is None:
            raise unittest.SkipTest("Edge or Chrome is not installed")

        cls._temporary = tempfile.TemporaryDirectory()
        cls._port = _free_port()
        environment = os.environ.copy()
        environment.update(
            {
                "SMMD_HOST": "127.0.0.1",
                "SMMD_PORT": str(cls._port),
                "SMMD_CONFIG": str(Path(cls._temporary.name) / "sync.yaml"),
            }
        )
        environment.pop("YOUTRACK_TOKEN", None)
        cls._server = subprocess.Popen(
            [sys.executable, "-m", "src.controller.server"],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 15
        health_url = f"http://127.0.0.1:{cls._port}/api/v1/health"
        while time.monotonic() < deadline:
            if cls._server.poll() is not None:
                raise RuntimeError("workbench server stopped during browser setup")
            try:
                with urlopen(health_url, timeout=0.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("workbench server did not become ready")

        cls._playwright = sync_playwright().start()
        cls._browser = cls._playwright.chromium.launch(
            executable_path=str(executable), headless=True
        )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "_browser"):
            cls._browser.close()
        if hasattr(cls, "_playwright"):
            cls._playwright.stop()
        if hasattr(cls, "_server"):
            cls._server.terminate()
            try:
                cls._server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls._server.kill()
                cls._server.wait(timeout=5)
        if hasattr(cls, "_temporary"):
            cls._temporary.cleanup()

    def setUp(self):
        self.page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self.page.goto(f"http://127.0.0.1:{self._port}")
        self.page.locator("#catalogList .catalog-item").first.wait_for()

    def tearDown(self):
        self.page.close(run_before_unload=False)

    def test_dirty_document_requires_confirmation_before_local_replacement(self):
        editor = self.page.locator("#editor")
        editor.fill("# Draft\nchanged\n")
        self.assertEqual(self.page.locator("#dirtyBadge").get_attribute("data-state"), "dirty")

        replacement = {
            "name": "replacement.md",
            "mimeType": "text/markdown",
            "buffer": b"# Replacement\n",
        }
        self.page.once("dialog", lambda dialog: dialog.dismiss())
        self.page.locator("#fileInput").set_input_files(replacement)
        self.assertEqual(editor.input_value(), "# Draft\nchanged\n")
        self.assertEqual(self.page.locator("#currentName").inner_text(), "untitled.md")

        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator("#fileInput").set_input_files(replacement)
        self.page.locator("#currentName").filter(has_text="replacement.md").wait_for()
        self.assertEqual(editor.input_value(), "# Replacement\n")
        self.assertEqual(self.page.locator("#dirtyBadge").get_attribute("data-state"), "clean")

    def test_download_matches_editor_bytes(self):
        content = "# Download check\n\n中文与 symbols: <>&\n"
        self.page.locator("#editor").fill(content)
        self.page.locator('[data-panel="syncPanel"]').click()

        with self.page.expect_download() as download_info:
            self.page.locator("#downloadButton").click()
        download = download_info.value

        self.assertEqual(download.suggested_filename, "untitled.md")
        self.assertEqual(Path(download.path()).read_bytes(), content.encode("utf-8"))
        self.assertEqual(self.page.locator("#dirtyBadge").get_attribute("data-state"), "dirty")
        self.assertEqual(self.page.locator("#statusMessage").inner_text(), "Copy download started")

    def test_remote_sync_does_not_claim_local_file_was_saved(self):
        original = "---\ntitle: Demo\nremote: github/issues/o/r/9\n---\n\n# Old\n"
        self.page.locator("#fileInput").set_input_files(
            {"name": "demo.md", "mimeType": "text/markdown", "buffer": original.encode()}
        )
        self.assertEqual(self.page.locator("#dirtyBadge").inner_text(), "Local file unchanged")
        self.page.locator("#editor").fill(original + "local edit\n")

        def fulfill(route):
            if route.request.url.endswith("/sync/push/preview"):
                data = {
                    "preview_id": "push-preview",
                    "direction": "push",
                    "diff": "--- a/demo.md\n+++ b/demo.md\n@@ -1 +1 @@\n-old\n+new\n",
                }
            elif route.request.url.endswith("/sync/push/confirm"):
                data = {"result": {"status": "SUCCESS"}}
            elif route.request.url.endswith("/sync/pull/preview"):
                data = {
                    "preview_id": "pull-preview",
                    "direction": "pull",
                    "diff": "--- a/demo.md\n+++ b/demo.md\n@@ -1 +1 @@\n-old\n+new\n",
                }
            else:
                data = {"content": original + "remote edit\n"}
            route.fulfill(json={"status": "success", "data": data, "error": None})

        self.page.route("**/api/v1/sync/push/**", fulfill)
        self.page.route("**/api/v1/sync/pull/**", fulfill)
        self.page.locator('[data-panel="syncPanel"]').click()
        self.page.locator("#pushPreviewButton").click()
        self.page.locator("#pushConfirmButton").click()
        self.page.wait_for_function(
            "document.querySelector('#statusMessage').textContent === 'Push complete'"
        )
        self.assertEqual(self.page.locator("#dirtyBadge").get_attribute("data-state"), "dirty")
        self.assertTrue(self.page.evaluate("hasUnsavedChanges()"))

        self.page.locator("#pullPreviewButton").click()
        self.page.locator("#pullConfirmButton").click()
        self.page.wait_for_function(
            "document.querySelector('#statusMessage').textContent === 'Pull applied'"
        )
        self.assertEqual(self.page.locator("#dirtyBadge").get_attribute("data-state"), "dirty")
        self.page.once("dialog", lambda dialog: dialog.dismiss())
        self.page.locator("#fileInput").set_input_files(
            {"name": "other.md", "mimeType": "text/markdown", "buffer": b"# Other\n"}
        )
        self.assertEqual(self.page.locator("#currentName").inner_text(), "demo.md")

    def test_upload_binding_remains_unsaved_in_original_local_file(self):
        self.page.locator("#fileInput").set_input_files(
            {"name": "new.md", "mimeType": "text/markdown", "buffer": b"# New\n"}
        )
        bound = "---\ntitle: New\nremote: github/issues/o/r/42\n---\n\n# New\n"
        self.page.route(
            "**/api/v1/sync/upload",
            lambda route: route.fulfill(
                json={
                    "status": "success",
                    "data": {"content": bound, "result": {"status": "SUCCESS"}},
                    "error": None,
                }
            ),
        )
        self.page.locator('[data-panel="syncPanel"]').click()
        self.page.locator("#uploadButton").click()
        self.page.wait_for_function(
            "document.querySelector('#statusMessage').textContent === 'Upload complete'"
        )
        self.assertEqual(self.page.locator("#dirtyBadge").get_attribute("data-state"), "dirty")
        self.assertTrue(self.page.evaluate("hasUnsavedChanges()"))

    def test_open_file_keyboard_access_and_chinese_accessible_copy(self):
        self.page.locator("body").click(position={"x": 1, "y": 1})
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "openFileButton")

        with self.page.expect_file_chooser() as chooser_info:
            self.page.keyboard.press("Enter")
        chooser_info.value.set_files(
            {
                "name": "keyboard.md",
                "mimeType": "text/markdown",
                "buffer": b"# Keyboard\n",
            }
        )
        self.page.locator("#currentName").filter(has_text="keyboard.md").wait_for()

        self.page.locator("#languageSelect").select_option("zh")
        self.assertEqual(self.page.locator("html").get_attribute("lang"), "zh")
        self.assertEqual(self.page.locator(".mode-nav").get_attribute("aria-label"), "工作台模式")
        self.assertEqual(self.page.locator("#editor").get_attribute("aria-label"), "Markdown 源码编辑器")
        self.assertEqual(self.page.locator("#statusMessage").inner_text(), "目录：1 个标题")

    def test_responsive_layout_and_narrow_diff_remain_readable(self):
        for width in (390, 768, 820, 1024, 1101, 1440):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 900})
                page_width = self.page.evaluate("document.documentElement.scrollWidth")
                self.assertLessEqual(page_width, width)

        long_line = "old line with a somewhat long sentence for narrow screens"
        diff = (
            "--- a/doc.md\n+++ b/doc.md\n@@ -1,2 +1,2 @@\n"
            f"-{long_line}\n+new line with a somewhat long sentence for narrow screens\n"
        )
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.evaluate("([value]) => renderSyncOutput(value, 'diff', true, 'pull')", [diff])
        changed_line = self.page.locator(".d2h-code-line-ctn").first
        box = changed_line.bounding_box()
        self.assertIsNotNone(box)
        self.assertGreater(box["width"], 40)
        self.assertLess(box["height"], 180)

    def test_focus_apply_failure_feedback_and_narrow_pane_switch(self):
        self.page.locator("#editor").fill(
            "# Root\nintro\n## One\nold\n## Two\nlast\n"
        )
        self.page.locator("#catalogButton").click()
        choices = self.page.locator(".catalog-select")
        choices.nth(1).check()
        choices.nth(2).check()
        self.page.locator("#focusReadButton").click()
        self.page.wait_for_function(
            "document.querySelector('#focusReadOutput').textContent.includes('## Two')"
        )
        multi_source = self.page.locator("#focusReadOutput").inner_text()
        self.assertLess(multi_source.index("## One"), multi_source.index("## Two"))
        self.assertTrue(self.page.locator("#focusEditor").is_disabled())

        choices.nth(2).uncheck()
        self.page.locator("#focusReadButton").click()
        self.assertFalse(self.page.locator("#focusEditor").is_disabled())
        self.page.locator("#focusEditor").fill("## One\nnew\n")
        self.page.locator("#focusApplyButton").click()
        self.page.wait_for_function(
            "document.querySelector('#editor').value.includes('## One\\nnew\\n')"
        )
        self.assertIn("## One\nnew\n", self.page.locator("#editor").input_value())

        self.page.locator("#editor").fill("# Rendered\n\n**bold** text\n\n- item\n")
        self.page.locator('[data-editor-mode="render"]').click()
        self.page.locator("#preview h1").wait_for()
        self.assertEqual(self.page.locator("#preview h1").inner_text(), "Rendered")
        self.assertEqual(self.page.locator("#preview strong").inner_text(), "bold")
        self.assertEqual(self.page.locator("#preview li").inner_text(), "item")
        self.assertNotIn("# Rendered", self.page.locator("#preview").inner_text())
        self.assertTrue(self.page.locator("#editor").is_hidden())
        self.page.locator('[data-editor-mode="source"]').click()
        self.assertTrue(self.page.locator("#editor").is_visible())
        self.assertTrue(self.page.locator("#preview").is_hidden())

        focus_button = self.page.locator("#focusModeButton")
        focus_button.click()
        self.assertTrue(self.page.locator("body").evaluate("node => node.classList.contains('focus-mode')"))
        self.assertEqual(focus_button.get_attribute("aria-pressed"), "true")
        self.assertEqual(focus_button.inner_text(), "Exit immersive")
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "editor")
        self.page.keyboard.press("Escape")
        self.assertFalse(self.page.locator("body").evaluate("node => node.classList.contains('focus-mode')"))
        self.assertEqual(focus_button.inner_text(), "Immersive editing")

        self.page.set_viewport_size({"width": 600, "height": 800})
        self.assertTrue(self.page.locator("#editor").is_visible())
        self.assertTrue(self.page.locator(".editor-mode-switch").is_visible())

        self.page.locator('[data-panel="syncPanel"]').click()
        self.page.locator("#remoteInput").fill("not-a-supported-remote")
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator("#remoteOpenButton").click()
        status = self.page.locator("#statusMessage")
        self.page.wait_for_function(
            "document.querySelector('#statusMessage').dataset.error === 'true'"
        )
        self.assertTrue(status.inner_text().strip())

    def test_provider_token_state_is_clear_and_secret_is_not_echoed(self):
        self.page.locator('[data-panel="syncPanel"]').click()
        self.page.locator("details summary").click()
        self.page.locator("#providerSelect").select_option("youtrack")
        self.page.wait_for_function(
            "document.querySelector('#providerTokenStatus').textContent.length > 0"
        )
        self.assertIn(
            self.page.locator("#providerTokenStatus").get_attribute("data-state"),
            {"configured", "missing"},
        )

        self.page.locator("#providerToken").fill("browser-only-secret")
        self.page.locator("#providerSaveButton").click()
        self.assertEqual(self.page.locator("#providerToken").input_value(), "")
        self.page.wait_for_function(
            "document.querySelector('#statusMessage').textContent.includes('configuration saved')"
        )
        response_text = self.page.evaluate(
            "fetch('/api/v1/providers').then(response => response.text())"
        )
        self.assertNotIn("browser-only-secret", response_text)
        clear_token = self.page.locator("#providerClearToken")
        self.assertFalse(clear_token.is_disabled())
        clear_token.check()
        self.assertTrue(self.page.locator("#providerToken").is_disabled())
        self.page.locator("#providerSaveButton").click()
        self.page.wait_for_function(
            "document.querySelector('#providerTokenStatus').dataset.state === 'missing'"
        )
        self.assertTrue(clear_token.is_disabled())

    def test_editor_is_locked_while_push_confirmation_is_in_flight(self):
        self.page.locator('[data-panel="syncPanel"]').click()
        self.page.evaluate(
            """() => {
              const originalFetch = window.fetch;
              window.fetch = (input, options) => {
                if (String(input).endsWith('/api/v1/sync/push/confirm')) {
                  return new Promise((resolve) => {
                    window.__resolvePush = () => resolve(new Response(JSON.stringify({
                      status: 'success', data: {result: {status: 'success'}}, error: null
                    }), {status: 200, headers: {'Content-Type': 'application/json'}}));
                  });
                }
                return originalFetch(input, options);
              };
              state.pushPreviewId = 'pending-preview';
              document.querySelector('#pushConfirmButton').disabled = false;
            }"""
        )

        self.page.locator("#pushConfirmButton").click()
        self.page.wait_for_function("Boolean(window.__resolvePush)")

        self.assertEqual(self.page.locator("#dropZone").get_attribute("aria-busy"), "true")
        self.assertFalse(self.page.locator("#editor").is_editable())
        self.assertTrue(self.page.locator("#openFileButton").is_disabled())

        self.page.evaluate("window.__resolvePush()")
        self.page.wait_for_function(
            "document.querySelector('#dropZone').getAttribute('aria-busy') === 'false'"
        )
        self.assertTrue(self.page.locator("#editor").is_editable())
        self.assertFalse(self.page.locator("#openFileButton").is_disabled())

    def test_upload_sends_branch_fields_only_for_github_or_gitee_pulls(self):
        payloads = []

        def fulfill_upload(route):
            payloads.append(route.request.post_data_json)
            route.fulfill(
                json={
                    "status": "success",
                    "data": {
                        "name": "untitled.md",
                        "content": "# Uploaded\n",
                        "result": {"status": "success"},
                    },
                    "error": None,
                }
            )

        self.page.route("**/api/v1/sync/upload", fulfill_upload)
        self.page.locator('[data-panel="syncPanel"]').click()
        collection = self.page.locator("#collectionInput")

        collection.fill("github/pulls/owner/repo")
        self.assertTrue(self.page.locator("#pullRequestFields").is_visible())
        self.page.locator("#baseInput").fill("main")
        self.page.locator("#headInput").fill("feature/topic")
        self.page.locator("#uploadButton").click()
        self.page.wait_for_function("document.querySelector('#editor').value === '# Uploaded\\n'")

        collection.fill("github/issues/owner/repo")
        self.assertTrue(self.page.locator("#pullRequestFields").is_hidden())
        self.page.locator("#uploadButton").click()
        self.page.wait_for_function("document.querySelector('#dropZone').getAttribute('aria-busy') === 'false'")

        self.assertEqual(payloads[0]["base"], "main")
        self.assertEqual(payloads[0]["head"], "feature/topic")
        self.assertNotIn("base", payloads[1])
        self.assertNotIn("head", payloads[1])

    def test_only_the_latest_transfer_preview_can_be_confirmed(self):
        def fulfill_preview(route):
            path = route.request.url.split("?", 1)[0]
            if path.endswith("/sync/pull/preview"):
                data = {
                    "preview_id": "pull-preview",
                    "direction": "pull",
                    "diff": "--- a/doc.md\n+++ b/doc.md\n@@ -1 +1 @@\n-local\n+pull change\n",
                }
            elif path.endswith("/sync/push/preview"):
                data = {
                    "preview_id": "push-preview",
                    "direction": "push",
                    "diff": "--- a/doc.md\n+++ b/doc.md\n@@ -1 +1 @@\n-remote\n+push change\n",
                }
            else:
                route.continue_()
                return
            route.fulfill(json={"status": "success", "data": data, "error": None})

        self.page.route("**/api/v1/sync/**/preview", fulfill_preview)
        self.page.locator('[data-panel="syncPanel"]').click()

        self.page.locator("#pullPreviewButton").click()
        self.page.wait_for_function("!document.querySelector('#pullConfirmButton').disabled")
        self.assertTrue(self.page.locator("#pushConfirmButton").is_disabled())

        self.page.locator("#pushPreviewButton").click()
        self.page.wait_for_function("!document.querySelector('#pushConfirmButton').disabled")
        self.assertTrue(self.page.locator("#pullConfirmButton").is_disabled())
        self.assertIn("push change", self.page.locator("#syncOutput").inner_text())
        self.assertIn("Push", self.page.locator("#diffFiles").inner_text())

        self.page.locator("#pullPreviewButton").click()
        self.page.wait_for_function("!document.querySelector('#pullConfirmButton').disabled")
        self.assertTrue(self.page.locator("#pushConfirmButton").is_disabled())
        self.assertIn("pull change", self.page.locator("#syncOutput").inner_text())
        self.assertIn("Pull", self.page.locator("#diffFiles").inner_text())

    def test_changing_pull_target_invalidates_confirmation(self):
        self.page.route(
            "**/api/v1/sync/pull/preview",
            lambda route: route.fulfill(
                json={
                    "status": "success",
                    "data": {
                        "preview_id": "old-target",
                        "direction": "pull",
                        "diff": "--- a/doc.md\n+++ b/doc.md\n@@ -1 +1 @@\n-old\n+new\n",
                    },
                    "error": None,
                }
            ),
        )
        self.page.locator('[data-panel="syncPanel"]').click()
        self.page.locator("#remoteInput").fill("github/issues/o/r/1")
        self.page.locator("#pullPreviewButton").click()
        self.page.wait_for_function("!document.querySelector('#pullConfirmButton').disabled")
        self.page.locator("#remoteInput").fill("github/issues/o/r/2")
        self.assertTrue(self.page.locator("#pullConfirmButton").is_disabled())
        self.assertIn("preview again", self.page.locator("#statusMessage").inner_text())

    def test_remote_list_open_pull_push_and_upload_controls(self):
        def fulfill(route):
            path = route.request.url.split("?", 1)[0]
            data = None
            if path.endswith("/sync/list"):
                data = {"items": [{"id": "7", "title": "Remote note"}]}
            elif path.endswith("/sync/open"):
                data = {"name": "remote.md", "content": "# Remote\noriginal\n"}
            elif path.endswith("/sync/pull/preview"):
                data = {
                    "preview_id": "browser-preview",
                    "direction": "pull",
                    "diff": "--- a/remote.md\n+++ b/remote.md\n@@ -1,2 +1,2 @@\n # Remote\n-local edit\n+remote update\n",
                }
            elif path.endswith("/sync/pull/confirm"):
                data = {"content": "# Remote\npulled\n"}
            elif path.endswith("/sync/push/preview"):
                data = {
                    "preview_id": "push-preview",
                    "direction": "push",
                    "diff": "--- a/remote.md\n+++ b/remote.md\n@@ -1,2 +1,3 @@\n # Remote\n-remote\n+<script>window.diffXss = true</script>\n+push me\n",
                }
            elif path.endswith("/sync/push/confirm"):
                data = {"result": {"status": "success", "remote": "7"}}
            elif path.endswith("/sync/upload"):
                data = {
                    "name": "remote.md",
                    "content": "# Remote\nuploaded\n",
                    "result": {"status": "success", "remote": "8"},
                }
            else:
                route.continue_()
                return
            route.fulfill(json={"status": "success", "data": data, "error": None})

        self.page.route("**/api/v1/sync/**", fulfill)
        self.page.locator('[data-panel="syncPanel"]').click()
        self.page.locator("#remoteListButton").click()
        self.page.locator('#remoteObjectSelect option[value="7"]').wait_for(state="attached")
        self.page.locator("#remoteObjectSelect").select_option("7")
        self.page.locator("#remoteOpenButton").click()
        self.page.wait_for_function(
            "document.querySelector('#currentName').textContent === 'remote.md'"
        )
        self.assertEqual(self.page.locator("#editor").input_value(), "# Remote\noriginal\n")

        self.page.locator("#editor").fill("# Remote\nlocal edit\n")
        self.page.locator("#pullPreviewButton").click()
        self.page.locator("#pullConfirmButton").wait_for(state="visible")
        self.page.wait_for_function(
            "!document.querySelector('#pullConfirmButton').disabled"
        )
        self.assertIn("remote update", self.page.locator("#syncOutput").inner_text())
        self.assertEqual(self.page.locator("#diffAdded").inner_text(), "+1")
        self.assertEqual(self.page.locator("#diffDeleted").inner_text(), "−1")
        self.assertEqual(
            self.page.locator("#diffFiles").inner_text(),
            "Pull · remote → source · 1 file changed",
        )
        self.assertTrue(self.page.locator("#diffViewer .d2h-del").count() > 0)
        self.assertTrue(self.page.locator("#diffViewer .d2h-ins").count() > 0)
        self.assertEqual(
            self.page.locator(".editor-column").get_attribute("data-editor-mode"),
            "difference",
        )
        self.assertTrue(self.page.locator("#editor").is_hidden())
        self.page.locator("#pullConfirmButton").click()
        self.page.wait_for_function(
            "document.querySelector('#editor').value.includes('pulled')"
        )
        self.assertIn("remote update", self.page.locator("#syncOutput").inner_text())
        self.assertEqual(
            self.page.locator(".editor-column").get_attribute("data-editor-mode"),
            "difference",
        )
        self.assertEqual(
            self.page.locator("#diffFiles").inner_text(),
            "Pull · remote → source · 1 file changed",
        )

        self.page.locator('[data-editor-mode="source"]').click()
        self.page.locator("#editor").fill("# Remote\npush me\n")
        self.page.locator("#pushPreviewButton").click()
        self.page.wait_for_function(
            "!document.querySelector('#pushConfirmButton').disabled"
        )
        self.assertIn("push me", self.page.locator("#syncOutput").inner_text())
        self.assertEqual(self.page.locator("#diffViewer script").count(), 0)
        self.assertIsNone(self.page.evaluate("window.diffXss"))
        self.assertEqual(
            self.page.locator(".editor-column").get_attribute("data-editor-mode"),
            "difference",
        )
        self.page.locator("#pushConfirmButton").click()
        self.page.wait_for_function(
            "document.querySelector('#statusMessage').textContent === 'Push complete'"
        )
        self.assertIn("push me", self.page.locator("#syncOutput").inner_text())
        self.assertEqual(
            self.page.locator("#diffFiles").inner_text(),
            "Push · source → remote · 1 file changed",
        )
        self.page.locator("#uploadButton").click()
        self.page.wait_for_function(
            "document.querySelector('#statusMessage').textContent === 'Upload complete'"
        )
        self.assertEqual(self.page.locator("#editor").input_value(), "# Remote\nuploaded\n")


if __name__ == "__main__":
    unittest.main()
