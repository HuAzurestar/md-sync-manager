import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.core.document import parse_file, parse_text, render_document


ROOT = Path(__file__).resolve().parents[1]


def run_guard(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "src.controller.doc_guard", *map(str, arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


class StandardMetadataTests(unittest.TestCase):
    def test_standard_type_round_trips_without_changing_remote_binding(self):
        source = (
            "---\n"
            'title: "PIRC-99 requirement"\n'
            'type: "pirc.requirement"\n'
            'parent: "youtrack/articles/PIRC/16"\n'
            'remote: "youtrack/articles/PIRC/17"\n'
            "---\n\n"
            "# PIRC-99 requirement\n"
        )

        document = parse_text(source)
        self.assertEqual(document.document_type, "pirc.requirement")
        rendered = render_document(document)
        reparsed = parse_text(rendered)
        self.assertEqual(reparsed.document_type, "pirc.requirement")
        self.assertEqual(str(reparsed.remote), "youtrack/articles/PIRC/17")

    def test_unknown_type_and_business_metadata_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "type must be one of"):
            parse_text("---\ntitle: X\ntype: pirc.note\n---\n\n# X\n")
        with self.assertRaisesRegex(ValueError, "unsupported metadata fields: status"):
            parse_text("---\ntitle: X\nstatus: TODO\n---\n\n# X\n")

    def test_duplicate_remote_is_rejected(self):
        source = (
            "---\n"
            "title: X\n"
            "remote: youtrack/issues/PIRC/1\n"
            "remote: youtrack/issues/PIRC/2\n"
            "---\n\n"
            "# X\n"
        )
        with self.assertRaisesRegex(ValueError, "duplicate metadata field: remote"):
            parse_text(source)

    def test_cli_rejects_non_string_metadata_key_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = {
                "integer": "1: invalid\n",
                "boolean": "true: invalid\n",
                "null": "null: invalid\n",
                "sequence": "? [a, b]\n: invalid\n",
                "mapping": "? {a: b}\n: invalid\n",
            }
            for name, key_source in cases.items():
                with self.subTest(name=name):
                    document = Path(directory) / f"PIRC-99 Invalid {name}.md"
                    document.write_text(
                        "---\n"
                        "title: X\n"
                        "type: pirc.requirement\n"
                        + key_source
                        + "---\n\n"
                        "# X\n",
                        encoding="utf-8",
                    )

                    checked = run_guard("check", document)

                    self.assertEqual(checked.returncode, 1)
                    self.assertIn("BLOCKED", checked.stdout)
                    self.assertIn("metadata.invalid", checked.stdout)
                    self.assertIn(f"{document.name}:4", checked.stdout)
                    self.assertIn(
                        "metadata field names must be strings", checked.stdout
                    )
                    if name == "integer":
                        self.assertIn(
                            "metadata field names must be strings: 1",
                            checked.stdout,
                        )
                    self.assertNotIn("Traceback", checked.stderr)


class TemplateAndRelationTests(unittest.TestCase):
    def test_generated_pair_has_fixed_skeleton_and_passes_relation_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirement = root / "PIRC-99 Example 需求分析.md"
            solution = root / "PIRC-99 Example 方案设计.md"

            created_requirement = run_guard("init", "requirement", requirement)
            self.assertEqual(created_requirement.returncode, 0, created_requirement.stderr)
            created_solution = run_guard(
                "init", "solution", solution, "--requirement", requirement
            )
            self.assertEqual(created_solution.returncode, 0, created_solution.stderr)

            requirement_document = parse_file(requirement)
            solution_document = parse_file(solution)
            self.assertEqual(requirement_document.document_type, "pirc.requirement")
            self.assertEqual(solution_document.document_type, "pirc.solution")
            self.assertEqual(
                sum(line.startswith("## ") for line in requirement_document.body.splitlines()),
                4,
            )
            self.assertEqual(
                sum(line.startswith("## ") for line in solution_document.body.splitlines()),
                4,
            )
            self.assertIn(f"| 需求文档 | `{requirement.name}` |", solution_document.body)
            self.assertIn("| Issue | `PIRC-99` |", solution_document.body)

            checked = run_guard("check", requirement)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("PASS", checked.stdout)

    def test_single_document_check_reports_missing_relation_with_location(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "PIRC-99 Missing 需求分析.md"
            document.write_text(
                "---\ntitle: Missing\ntype: pirc.requirement\n---\n\n# Missing\n",
                encoding="utf-8",
            )

            checked = run_guard("check", document)

            self.assertEqual(checked.returncode, 1)
            self.assertIn("BLOCKED", checked.stdout)
            self.assertRegex(checked.stdout, rf"{document.name}:\d+")
            self.assertIn("relation.missing", checked.stdout)

    def test_pair_check_rejects_issue_and_path_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirement = root / "PIRC-99 Example 需求分析.md"
            solution = root / "PIRC-99 Example 方案设计.md"
            self.assertEqual(run_guard("init", "requirement", requirement).returncode, 0)
            self.assertEqual(
                run_guard(
                    "init", "solution", solution, "--requirement", requirement
                ).returncode,
                0,
            )
            changed = solution.read_text(encoding="utf-8").replace(
                "| Issue | `PIRC-99` |", "| Issue | `PIRC-100` |"
            )
            changed = changed.replace(
                f"| 需求文档 | `{requirement.name}` |",
                "| 需求文档 | `another.md` |",
            )
            solution.write_text(changed, encoding="utf-8")

            checked = run_guard(
                "check", "--requirement", requirement, "--solution", solution
            )

            self.assertEqual(checked.returncode, 1)
            self.assertIn("relation.issue_mismatch", checked.stdout)
            self.assertIn("relation.path_mismatch", checked.stdout)
            self.assertRegex(checked.stdout, rf"{solution.name}:\d+")

    def test_pair_check_resolves_workspace_relative_relation_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "MPA" / "project"
            project.mkdir(parents=True)
            requirement = project / "PIRC-99 Example 需求分析.md"
            solution = project / "PIRC-99 Example 方案设计.md"
            self.assertEqual(run_guard("init", "requirement", requirement).returncode, 0)
            self.assertEqual(
                run_guard(
                    "init", "solution", solution, "--requirement", requirement
                ).returncode,
                0,
            )
            for document in (requirement, solution):
                content = document.read_text(encoding="utf-8")
                content = content.replace(
                    f"`{requirement.name}`", f"`MPA/project/{requirement.name}`"
                )
                content = content.replace(
                    f"`{solution.name}`", f"`MPA/project/{solution.name}`"
                )
                document.write_text(content, encoding="utf-8")

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("PASS", checked.stdout)

    def test_solution_init_rejects_same_suffix_in_another_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "workspace-a" / "MPA" / "project"
            project.mkdir(parents=True)
            requirement = project / "PIRC-99 Example 需求分析.md"
            expected_solution = project / "PIRC-99 Example 方案设计.md"
            wrong_solution = (
                root
                / "workspace-b"
                / "MPA"
                / "project"
                / "PIRC-99 Example 方案设计.md"
            )
            self.assertEqual(run_guard("init", "requirement", requirement).returncode, 0)
            content = requirement.read_text(encoding="utf-8")
            content = content.replace(
                f"`{requirement.name}`", f"`MPA/project/{requirement.name}`"
            )
            content = content.replace(
                f"`{expected_solution.name}`",
                f"`MPA/project/{expected_solution.name}`",
            )
            requirement.write_text(content, encoding="utf-8")

            created = run_guard(
                "init", "solution", wrong_solution, "--requirement", requirement
            )

            self.assertEqual(created.returncode, 2)
            self.assertIn("does not match the requirement relation", created.stderr)
            self.assertFalse(wrong_solution.exists())

    def test_relation_check_ignores_headings_inside_code_fences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirement = root / "PIRC-99 Example 需求分析.md"
            solution = root / "PIRC-99 Example 方案设计.md"
            self.assertEqual(run_guard("init", "requirement", requirement).returncode, 0)
            self.assertEqual(
                run_guard(
                    "init", "solution", solution, "--requirement", requirement
                ).returncode,
                0,
            )
            requirement.write_text(
                requirement.read_text(encoding="utf-8")
                + "\n```markdown\n## 文档关系\n| Issue | `PIRC-100` | fake | fake |\n```\n",
                encoding="utf-8",
            )

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("PASS", checked.stdout)


if __name__ == "__main__":
    unittest.main()
