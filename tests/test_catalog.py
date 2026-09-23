import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.core.catalog import catalog_file, catalog_text, format_catalog


CATALOG_BASIC = """---
title: Catalog Fixture
---
# Root
root body
## Alpha
alpha body
```text
# fenced fake
```
### Child
child body
## Omega
omega body
"""


class CatalogTests(unittest.TestCase):
    def test_catalog_preserves_source_order_lines_and_heading_source(self):
        catalog = catalog_text(CATALOG_BASIC, path="catalog-basic.md")

        self.assertEqual(
            [entry.heading for entry in catalog.entries],
            ["# Root", "## Alpha", "### Child", "## Omega"],
        )
        self.assertEqual([entry.level for entry in catalog.entries], [1, 2, 3, 2])
        self.assertEqual([entry.line for entry in catalog.entries], [4, 6, 11, 13])
        self.assertEqual(catalog.entries[1].text, "Alpha")
        self.assertEqual(catalog.character_count, len(CATALOG_BASIC))

    def test_tilde_fences_closing_hashes_and_duplicates(self):
        source = """# Root #
~~~markdown
## fake
~~~~
 ## Same ###
 ## Same ###
"""
        catalog = catalog_text(source)

        self.assertEqual(
            [entry.heading for entry in catalog.entries],
            ["# Root #", " ## Same ###", " ## Same ###"],
        )
        self.assertEqual([entry.text for entry in catalog.entries], ["Root", "Same", "Same"])

    def test_front_matter_is_not_cataloged(self):
        source = """---
# YAML comment
title: Example
literal: |
  # YAML scalar
...
# Document
"""

        catalog = catalog_text(source)

        self.assertEqual([entry.heading for entry in catalog.entries], ["# Document"])
        self.assertEqual(catalog.entries[0].line, 7)

    def test_fence_with_trailing_text_does_not_close(self):
        source = """# Root
```text
# hidden
``` trailing text
## still hidden
```
## Visible
"""

        catalog = catalog_text(source)

        self.assertEqual(
            [entry.heading for entry in catalog.entries], ["# Root", "## Visible"]
        )

    def test_format_numbers_are_display_only(self):
        catalog = catalog_text("# Root\n## Child\n")

        self.assertEqual(format_catalog(catalog), "1. # Root\n2. ## Child")
        self.assertEqual(catalog.entries[1].heading, "## Child")

    def test_plain_markdown_file_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plain.md"
            path.write_text("# Plain\nBody\n", encoding="utf-8")

            catalog = catalog_file(path)
            result = subprocess.run(
                [sys.executable, "-m", "src.controller.main", "catalog", str(path)],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(catalog.entries[0].heading, "# Plain")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1. # Plain")

    def test_invalid_paths_fail_with_readable_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FileNotFoundError, "not found"):
                catalog_file(root / "missing.md")
            with self.assertRaisesRegex(ValueError, "not a file"):
                catalog_file(root)
            (root / "plain.txt").write_text("plain", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "only .md"):
                catalog_file(root / "plain.txt")


if __name__ == "__main__":
    unittest.main()
