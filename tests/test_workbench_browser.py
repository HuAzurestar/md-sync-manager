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
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
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

    def test_focus_apply_failure_feedback_and_narrow_pane_switch(self):
        self.page.locator("#editor").fill(
            "# Root\nintro\n## One\nold\n## Two\nlast\n"
        )
        self.page.locator("#catalogButton").click()
        choices = self.page.locator(".catalog-select")
        choices.nth(1).check()
        self.page.locator("#focusReadButton").click()
        self.page.locator("#focusEditor").fill("## One\nnew\n")
        self.page.locator("#focusApplyButton").click()
        self.page.wait_for_function(
            "document.querySelector('#editor').value.includes('## One\\nnew\\n')"
        )
        self.assertIn("## One\nnew\n", self.page.locator("#editor").input_value())

        self.page.set_viewport_size({"width": 600, "height": 800})
        self.assertTrue(self.page.locator(".preview-pane").is_hidden())
        self.page.locator("#showPreviewButton").click()
        self.assertTrue(self.page.locator(".editor-pane").is_hidden())
        self.assertTrue(self.page.locator(".preview-pane").is_visible())
        self.page.locator("#showEditorButton").click()
        self.assertTrue(self.page.locator(".editor-pane").is_visible())

        self.page.locator('[data-panel="syncPanel"]').click()
        self.page.locator("#remoteInput").fill("not-a-supported-remote")
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.locator("#remoteOpenButton").click()
        status = self.page.locator("#statusMessage")
        self.page.wait_for_function(
            "document.querySelector('#statusMessage').dataset.error === 'true'"
        )
        self.assertTrue(status.inner_text().strip())


if __name__ == "__main__":
    unittest.main()
