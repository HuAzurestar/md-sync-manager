import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.focus import (
    FocusConflictError,
    FocusSelectionError,
    focus_apply_file,
    focus_apply_text,
    focus_read_text,
)
from src.service.sync_service import SyncService


SOURCE = """---
title: Focus Fixture
---
# Root
root
## Alpha
alpha
### Child
child
## alpha
lower
## Tail
tail
"""


class FocusTests(unittest.TestCase):
    def test_read_uses_same_or_higher_boundary_and_source_order(self):
        sections = focus_read_text(SOURCE, ["## alpha", "## Alpha"])

        self.assertEqual([section.selector for section in sections], ["## Alpha", "## alpha"])
        self.assertEqual(sections[0].start_line, 6)
        self.assertEqual(sections[0].end_line, 9)
        self.assertEqual(sections[0].source, "## Alpha\nalpha\n### Child\nchild\n")
        self.assertEqual(sections[1].source, "## alpha\nlower\n")

    def test_terminal_section_reaches_end_of_file(self):
        section = focus_read_text(SOURCE, ["## Tail"])[0]

        self.assertEqual(section.end_line, 13)
        self.assertEqual(section.source, "## Tail\ntail\n")

    def test_duplicate_missing_wrong_case_and_fuzzy_selectors_fail(self):
        duplicate = "# Root\n## Same\none\n## Same\ntwo\n"
        with self.assertRaisesRegex(FocusSelectionError, "ambiguous"):
            focus_read_text(duplicate, ["## Same"])
        for selector in ["## ALPHA", "Alpha", "## Alp"]:
            with self.subTest(selector=selector):
                with self.assertRaisesRegex(FocusSelectionError, "not found"):
                    focus_read_text(SOURCE, [selector])

    def test_apply_compares_retained_source_and_preserves_non_target_bytes(self):
        expected = "## Alpha\nalpha\n### Child\nchild\n"
        replacement = "## Alpha\nnew alpha\n"
        updated, previous = focus_apply_text(
            SOURCE,
            selector="## Alpha",
            expected_source=expected,
            replacement=replacement,
        )

        self.assertEqual(previous.source, expected)
        self.assertTrue(updated.startswith(SOURCE[: SOURCE.index(expected)]))
        self.assertTrue(updated.endswith(SOURCE[SOURCE.index("## alpha") :]))
        self.assertIn(replacement, updated)
        with self.assertRaisesRegex(ValueError, "retain"):
            focus_apply_text(
                SOURCE,
                selector="## Alpha",
                expected_source=expected,
                replacement="## Changed\nnew\n",
            )

    def test_conflict_performs_zero_file_writes_and_success_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "focus.md"
            path.write_text(SOURCE, encoding="utf-8", newline="")
            before = path.read_bytes()

            with self.assertRaises(FocusConflictError):
                focus_apply_file(
                    path,
                    selector="## Tail",
                    expected_source="## Tail\nstale\n",
                    replacement="## Tail\nnew\n",
                )
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

            focus_apply_file(
                path,
                selector="## Tail",
                expected_source="## Tail\ntail\n",
                replacement="## Tail\nnew tail\n",
            )
            self.assertIn("## Tail\nnew tail\n", path.read_text(encoding="utf-8"))
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_focus_api_returns_ranges_and_updated_content_without_sha(self):
        client = TestClient(create_app(sync_service=SyncService()), raise_server_exceptions=False)

        read = client.post(
            "/api/v1/document/focus/read",
            json={"name": "focus.md", "content": SOURCE, "selectors": ["## Alpha"]},
        )
        source = read.json()["data"]["sections"][0]["source"]
        applied = client.post(
            "/api/v1/document/focus/apply",
            json={
                "name": "focus.md",
                "content": SOURCE,
                "selector": "## Alpha",
                "expected_source": source,
                "replacement": "## Alpha\nchanged\n",
            },
        )
        catalog = client.post(
            "/api/v1/document/catalog",
            json={"name": "focus.md", "content": SOURCE},
        )

        self.assertEqual(read.status_code, 200)
        self.assertEqual(applied.status_code, 200)
        self.assertIn("changed", applied.json()["data"]["content"])
        self.assertEqual(catalog.json()["data"]["entries"][0]["heading"], "# Root")
        self.assertNotIn("sha", repr(applied.json()).casefold())

    def test_focus_cli_read_and_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "focus.md"
            expected = root / "expected.txt"
            replacement = root / "replacement.txt"
            document.write_text(SOURCE, encoding="utf-8", newline="")
            expected.write_text("## Tail\ntail\n", encoding="utf-8", newline="")
            replacement.write_text("## Tail\nnew\n", encoding="utf-8", newline="")

            read = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.controller.main",
                    "focus-read",
                    str(document),
                    "--selector",
                    "## Tail",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            apply = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.controller.main",
                    "focus-apply",
                    str(document),
                    "--selector",
                    "## Tail",
                    "--expected-file",
                    str(expected),
                    "--replacement-file",
                    str(replacement),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertEqual(json.loads(read.stdout)["sections"][0]["selector"], "## Tail")
        self.assertEqual(apply.returncode, 0, apply.stderr)
        self.assertEqual(json.loads(apply.stdout)["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
