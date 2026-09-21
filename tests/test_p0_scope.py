import re
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.core.capabilities import P0_CAPABILITIES


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"


class P0ScopeTests(unittest.TestCase):
    def test_source_tree_has_no_removed_or_deferred_product_surface(self):
        forbidden = re.compile(
            r"\b(review|audit|pair[-_ ]check|sqlite|sqlalchemy|migration)\b",
            re.IGNORECASE,
        )
        deferred_template = re.compile(r"\b(document[._ -]?template|template generation)\b", re.IGNORECASE)
        violations = []
        for path in SOURCE_ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".js", ".html", ".css", ".yaml"}:
                continue
            source = path.read_text(encoding="utf-8")
            match = forbidden.search(source) or deferred_template.search(source)
            if match:
                violations.append(f"{path.relative_to(ROOT)}: {match.group(0)}")

        self.assertEqual(violations, [])
        self.assertFalse(any("review" in path.name.casefold() for path in SOURCE_ROOT.rglob("*")))

    def test_dependencies_and_routes_have_no_database_or_review_layer(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"sqlalchemy|sqlite|alembic", requirements, re.IGNORECASE))

        application = create_app()
        paths = {route.path for route in application.routes if hasattr(route, "path")}
        self.assertFalse(any("review" in path.casefold() for path in paths))
        self.assertEqual(
            P0_CAPABILITIES,
            (
                "sync.providers", "sync.list", "sync.open", "sync.pull",
                "sync.push", "sync.upload", "document.catalog",
                "document.focus.read", "document.focus.apply",
                "workbench.single-file",
            ),
        )


if __name__ == "__main__":
    unittest.main()
