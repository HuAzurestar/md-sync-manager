import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.controller import doc_guard
from src.core import doc_standard
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
                        "type: pirc.requirement\n" + key_source + "---\n\n"
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
            self.assertEqual(
                created_requirement.returncode, 0, created_requirement.stderr
            )
            created_solution = run_guard(
                "init", "solution", solution, "--requirement", requirement
            )
            self.assertEqual(created_solution.returncode, 0, created_solution.stderr)

            requirement_document = parse_file(requirement)
            solution_document = parse_file(solution)
            self.assertEqual(requirement_document.document_type, "pirc.requirement")
            self.assertEqual(solution_document.document_type, "pirc.solution")
            self.assertEqual(
                sum(
                    line.startswith("## ")
                    for line in requirement_document.body.splitlines()
                ),
                4,
            )
            self.assertEqual(
                sum(
                    line.startswith("## ")
                    for line in solution_document.body.splitlines()
                ),
                4,
            )
            self.assertIn(
                f"| 需求文档 | `{requirement.name}` |", solution_document.body
            )
            self.assertIn("| Issue | `PIRC-99` |", solution_document.body)

            checked = run_guard("check", requirement)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("PASS", checked.stdout)


class FullStandardContractTests(unittest.TestCase):
    def _generated_pair(self, root: Path) -> tuple[Path, Path]:
        requirement = root / "PIRC-99 Example 需求分析.md"
        solution = root / "PIRC-99 Example 方案设计.md"
        self.assertEqual(run_guard("init", "requirement", requirement).returncode, 0)
        self.assertEqual(
            run_guard(
                "init", "solution", solution, "--requirement", requirement
            ).returncode,
            0,
        )
        return requirement, solution

    def test_check_rejects_relation_only_document_and_wrong_heading_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            relation_only = requirement.read_text(encoding="utf-8").split(
                "## 背景与目标"
            )[0]
            requirement.write_text(
                relation_only + "## 任意新章节\n\n#### AC-001 错层记录\n",
                encoding="utf-8",
            )

            checked = run_guard(
                "check", "--requirement", requirement, "--solution", solution
            )

            self.assertEqual(checked.returncode, 1)
            self.assertIn("structure.required_section", checked.stdout)
            self.assertIn("structure.unknown_section", checked.stdout)
            self.assertRegex(checked.stdout, rf"{requirement.name}:\d+")

    def test_check_json_reports_closed_trace_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))

            checked = run_guard(
                "check",
                "--requirement",
                requirement,
                "--solution",
                solution,
                "--format",
                "json",
            )

            self.assertEqual(checked.returncode, 0, checked.stderr)
            report = json.loads(checked.stdout)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["format_version"], "pirc-doc-guard-v1")
            self.assertEqual(
                report["coverage"]["ac"],
                {
                    "covered": 1,
                    "total": 1,
                    "percent": 100.0,
                },
            )
            self.assertEqual(report["coverage"]["solution"]["covered"], 1)
            self.assertEqual(report["coverage"]["test"]["covered"], 1)
            self.assertRegex(report["documents"][0]["sha256"], r"^[0-9a-f]{64}$")

    def test_status_reference_and_duplicate_id_fail_with_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            source = requirement.read_text(encoding="utf-8")
            source = source.replace("`[P0]`", "`[WIP]` `[P0]`")
            source += (
                "\n#### AC-001 Duplicate\n"
                "- 需求：REQ-999。\n"
                "- Given：x\n- When：x\n- Then：x\n"
            )
            requirement.write_text(source, encoding="utf-8")

            checked = run_guard(
                "check", "--requirement", requirement, "--solution", solution
            )

            self.assertEqual(checked.returncode, 1)
            self.assertIn("status.invalid", checked.stdout)
            self.assertIn("record.duplicate_id", checked.stdout)
            self.assertIn("reference.unknown", checked.stdout)

    def test_conditional_module_and_extension_require_fixed_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            source = requirement.read_text(encoding="utf-8")
            source += (
                "\n## 生产约束\n\n### 非功能性需求\n\n"
                "#### NFR-001 Incomplete\n- 需求：REQ-001\n"
                "\n#### EXT-001 Invalid extension\n"
                "- 父节：依赖、风险与补充\n"
                "- 用途：example\n- 结构类型：任意对象\n- 关联：REQ-001\n"
            )
            requirement.write_text(source, encoding="utf-8")

            checked = run_guard(
                "check", "--requirement", requirement, "--solution", solution
            )

            self.assertEqual(checked.returncode, 1)
            self.assertIn("record.missing_field", checked.stdout)
            self.assertIn("extension.parent_mismatch", checked.stdout)
            self.assertIn("extension.structure_invalid", checked.stdout)

    def test_all_conditional_modules_cover_valid_and_invalid_boundaries(self):
        requirement_records = {
            "NFR-001": [
                "需求：REQ-001",
                "指标：P99",
                "适用范围：检查",
                "基线：1 秒",
                "目标或上限：2 秒",
                "测量与验收：AC-001",
            ],
            "SEC-001": [
                "需求：REQ-001",
                "数据/资产：文档",
                "触发因素：本地读取",
                "约束：不联网",
                "失败表现：阻断",
                "验收：AC-001",
            ],
            "STATE-001": [
                "需求：REQ-001",
                "实体：审查",
                "当前状态：待审",
                "事件：通过",
                "下一状态：完成",
                "非法跃迁结果：阻断",
                "验收：AC-001",
            ],
        }
        solution_records = {
            "MIG-001": [
                "需求/方案：REQ-001、SOL-001",
                "对象：格式",
                "现状：旧格式",
                "目标：新格式",
                "兼容：只读",
                "迁移/废弃：无需迁移",
                "回滚：删除新增文件",
                "测试：TEST-001",
            ],
            "OBS-001": [
                "需求/方案：REQ-001、SOL-001",
                "阶段或信号：检查",
                "机制或指标：退出码",
                "门槛：零错误",
                "失败动作：阻断",
                "测试：TEST-001",
            ],
            "RES-001": [
                "需求/方案：REQ-001、SOL-001",
                "故障：读取失败",
                "超时/重试：不重试",
                "限流/熔断：不适用",
                "降级：阻断",
                "恢复：修复输入",
                "测试：TEST-001",
            ],
            "CAP-001": [
                "需求/方案：REQ-001、SOL-001",
                "资源：单文件",
                "基线：1 文件",
                "预计：2 文件",
                "上限：2 文件",
                "测量：计数",
                "超限动作：阻断",
                "测试：TEST-001",
            ],
        }
        life_fields = [
            "方案：SOL-001",
            "状态：当前",
            "替代文档：无",
            "As-Built 偏差：无",
            "影响：无",
            "责任：作者",
            "回填时间：完成时",
            "测试：TEST-001",
        ]
        omitted_fields = {
            "NFR-001": "测量与验收：AC-001",
            "SEC-001": "验收：AC-001",
            "STATE-001": "验收：AC-001",
            "MIG-001": "回滚：删除新增文件",
            "OBS-001": "门槛：零错误",
            "RES-001": "恢复：修复输入",
            "CAP-001": "超限动作：阻断",
            "LIFE-001": "回填时间：完成时",
        }

        def record_block(record_id, fields, mode, illegal_target):
            selected = [
                item
                for item in fields
                if mode != "missing" or item != omitted_fields[record_id]
            ]
            if mode == "illegal":
                selected.append(f"非法关联：{illegal_target}")
            return (
                f"### {record_id} 记录组\n\n#### {record_id} 条件记录\n"
                + "\n".join(f"- {item}" for item in selected)
                + "\n\n"
            )

        for mode in ("valid", "missing", "wrong_parent", "illegal"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                requirement, solution = self._generated_pair(Path(directory))
                req_blocks = "".join(
                    record_block(record_id, fields, mode, "SOL-001")
                    for record_id, fields in requirement_records.items()
                )
                production_blocks = "".join(
                    record_block(record_id, fields, mode, "AC-001")
                    for record_id, fields in solution_records.items()
                ).replace("REQ-001", f"`{requirement.name}#REQ-001`")
                life_block = record_block("LIFE-001", life_fields, mode, "REQ-001")
                requirement_parent = (
                    "依赖、风险与补充" if mode == "wrong_parent" else "生产约束"
                )
                production_parent = (
                    "生命周期与补充" if mode == "wrong_parent" else "生产保障"
                )
                life_parent = "生产保障" if mode == "wrong_parent" else "生命周期与补充"
                requirement.write_text(
                    requirement.read_text(encoding="utf-8")
                    + f"\n## {requirement_parent}\n\n{req_blocks}",
                    encoding="utf-8",
                )
                solution.write_text(
                    solution.read_text(encoding="utf-8")
                    + f"\n## {production_parent}\n\n{production_blocks}"
                    + f"\n## {life_parent}\n\n{life_block}",
                    encoding="utf-8",
                )

                checked = run_guard("check", requirement)

                if mode == "valid":
                    self.assertEqual(
                        checked.returncode, 0, checked.stdout + checked.stderr
                    )
                else:
                    self.assertEqual(
                        checked.returncode, 1, checked.stdout + checked.stderr
                    )
                    expected = {
                        "missing": "record.missing_field",
                        "wrong_parent": "record.parent_invalid",
                        "illegal": "reference.direction",
                    }[mode]
                    self.assertGreaterEqual(checked.stdout.count(expected), 8)

    def test_catalog_extract_and_context_are_stable_and_scoped(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))

            catalogued = run_guard("catalog", requirement, "--format", "json")
            self.assertEqual(catalogued.returncode, 0, catalogued.stderr)
            catalog = json.loads(catalogued.stdout)
            self.assertIn("scope", {entry["key"] for entry in catalog["entries"]})
            self.assertTrue(all("byte_count" in item for item in catalog["entries"]))

            extracted = run_guard(
                "extract",
                requirement,
                "--id",
                "REQ-001",
                "--profile",
                "full",
                "--format",
                "json",
            )
            self.assertEqual(extracted.returncode, 0, extracted.stderr)
            extraction = json.loads(extracted.stdout)
            self.assertEqual(extraction["record_id"], "REQ-001")
            self.assertIn("REQ-001", extraction["markdown"])
            self.assertNotIn("NG-001", extraction["markdown"])

            contextualized = run_guard(
                "context",
                "--requirement",
                requirement,
                "--solution",
                solution,
                "--requirement-id",
                "REQ-001",
                "--format",
                "json",
            )
            self.assertEqual(contextualized.returncode, 0, contextualized.stderr)
            context = json.loads(contextualized.stdout)
            self.assertEqual(context["requirement_id"], "REQ-001")
            self.assertEqual(
                set(context["record_ids"]), {"REQ-001", "AC-001", "SOL-001", "TEST-001"}
            )

    def test_review_enforces_layers_hashes_and_finding_dispositions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirement, solution = self._generated_pair(root)
            initial = run_guard("review", requirement, "--format", "json")
            self.assertEqual(initial.returncode, 0, initial.stderr)
            pending = json.loads(initial.stdout)
            self.assertEqual(pending["overall_status"], "PENDING_AGENT")

            hashes = pending["source_sha256"]
            agent_file = root / "agent.json"
            agent_file.write_text(
                json.dumps(
                    {
                        "layer": "AGENT",
                        "owner": "agent-reviewer",
                        "status": "CLEAR",
                        "source_sha256": hashes,
                        "findings": [],
                    }
                ),
                encoding="utf-8",
            )
            agent = run_guard(
                "review",
                requirement,
                "--agent-result",
                agent_file,
                "--format",
                "json",
            )
            self.assertEqual(agent.returncode, 0, agent.stderr)
            self.assertEqual(
                json.loads(agent.stdout)["overall_status"], "PENDING_HUMAN"
            )

            human_file = root / "human.json"
            human_file.write_text(
                json.dumps(
                    {
                        "layer": "HUMAN",
                        "owner": "human-approver",
                        "status": "APPROVED",
                        "source_sha256": hashes,
                        "findings": [],
                    }
                ),
                encoding="utf-8",
            )
            approved = run_guard(
                "review",
                requirement,
                "--agent-result",
                agent_file,
                "--human-result",
                human_file,
                "--format",
                "json",
            )
            self.assertEqual(approved.returncode, 0, approved.stderr)
            self.assertEqual(json.loads(approved.stdout)["overall_status"], "APPROVED")

            stale = json.loads(agent_file.read_text(encoding="utf-8"))
            stale["source_sha256"][str(requirement.resolve())] = "0" * 64
            agent_file.write_text(json.dumps(stale), encoding="utf-8")
            rejected = run_guard("review", requirement, "--agent-result", agent_file)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("source_sha256", rejected.stderr)

    def test_atomic_create_cleans_temporary_file_when_replace_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "PIRC-99 Atomic 需求分析.md"
            content = doc_guard._render_template(
                "requirement-analysis.md",
                {
                    "TITLE": target.stem,
                    "ISSUE_ID": "PIRC-99",
                    "REQUIREMENT_PATH": target.name,
                    "SOLUTION_PATH": "PIRC-99 Atomic 方案设计.md",
                },
            )
            with mock.patch(
                "src.controller.doc_guard.os.link", side_effect=OSError("boom")
            ):
                with self.assertRaisesRegex(OSError, "boom"):
                    doc_guard._create(target, content)

            self.assertFalse(target.exists())
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_body_hash_ignores_yaml_and_declared_sha_slots_only(self):
        first = (
            "---\ntitle: A\ntype: pirc.requirement\n---\n\n"
            "# Body\n- SHA-256：`" + "a" * 64 + "`\n"
            "- Evidence computed with SHA-256: " + "b" * 64 + "\n"
        )
        second = first.replace("title: A", "title: B").replace("a" * 64, "c" * 64)
        changed_evidence = second.replace("b" * 64, "d" * 64)

        self.assertEqual(
            doc_standard.source_sha256(first), doc_standard.source_sha256(second)
        )
        self.assertNotEqual(
            doc_standard.source_sha256(second),
            doc_standard.source_sha256(changed_evidence),
        )

    def test_duplicate_yaml_key_points_to_the_second_key(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "PIRC-99 Duplicate 需求分析.md"
            document.write_text(
                "---\ntitle: X\ntype: pirc.requirement\n"
                "remote: youtrack/issues/PIRC/1\n"
                "remote: youtrack/issues/PIRC/2\n---\n\n# X\n",
                encoding="utf-8",
            )
            checked = run_guard("check", document)
            self.assertEqual(checked.returncode, 1)
            self.assertIn(f"{document.name}:5", checked.stdout)

    def test_solution_cannot_reference_blocked_or_out_of_scope_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            source = requirement.read_text(encoding="utf-8").replace(
                "### 非目标",
                "2. `REQ-002` `[BLK]` 外部索引。\n"
                "   - 占用：PIRC-88 / owner。\n"
                "   - 阻塞原因：格式未冻结。\n"
                "   - 释放条件：PIRC-88 发布。\n\n"
                "### 非目标",
            )
            requirement.write_text(source, encoding="utf-8")
            solution.write_text(
                solution.read_text(encoding="utf-8").replace(
                    "#REQ-001`。", "#REQ-001`、`REQ-002`。"
                ),
                encoding="utf-8",
            )

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 1)
            self.assertIn("scope.non_current_reference", checked.stdout)
            self.assertRegex(checked.stdout, rf"{solution.name}:\d+")

    def test_malformed_id_and_mixed_record_shape_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            source = solution.read_text(encoding="utf-8")
            source = source.replace(
                "## 实施与验收",
                "#### SOL-002 额外方案\n"
                "- 需求：REQ-001。\n- 输入：x。\n- 输出：x。\n"
                "- 过程：x。\n- 失败：x。\n- 测试：TEST-001。\n"
                "- 非法额外字段：x。\n\n"
                "#### SOL-01 非法编号\n- 需求：REQ-001。\n\n"
                "## 实施与验收",
            )
            solution.write_text(source, encoding="utf-8")

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 1)
            self.assertIn("record.shape_mismatch", checked.stdout, checked.stderr)
            self.assertIn("record.id_invalid", checked.stdout)

    def test_ordinary_catalog_has_hierarchical_keys_and_fence_aware_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "notes.md"
            document.write_text(
                "---\ntitle: Notes\n---\n\n# Notes\n\n"
                "## Alpha\nvisible\n![x](image.png)\n"
                "```md\n## Hidden\n![hidden](secret.png)\n- hidden\n```\n"
                "### Child\n- visible item\n\n### Child\nsecond\n",
                encoding="utf-8",
            )

            catalogued = run_guard("catalog", document, "--format", "json")

            self.assertEqual(catalogued.returncode, 0, catalogued.stderr)
            report = json.loads(catalogued.stdout)
            entries = {entry["key"]: entry for entry in report["entries"]}
            self.assertEqual(set(entries), {"alpha", "alpha/child", "alpha/child~2"})
            self.assertEqual(entries["alpha"]["image_count"], 1)
            self.assertEqual(entries["alpha"]["code_block_count"], 1)
            self.assertEqual(entries["alpha/child"]["list_count"], 1)
            self.assertNotIn("secret.png", str(entries))

    def test_extract_profiles_and_extension_catalog_have_fixed_projections(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, _ = self._generated_pair(Path(directory))
            requirement.write_text(
                requirement.read_text(encoding="utf-8")
                + "\n## 依赖、风险与补充\n\n### 项目扩展\n\n"
                "#### EXT-001 术语表\n"
                "- 父节：依赖、风险与补充\n- 用途：统一术语。\n"
                "- 触发条件：存在术语。\n- 结构类型：表格\n- 关联：REQ-001\n",
                encoding="utf-8",
            )

            catalog = json.loads(
                run_guard("catalog", requirement, "--format", "json").stdout
            )
            extension = next(
                item for item in catalog["entries"] if item["key"] == "EXT-001"
            )
            self.assertEqual(extension["type"], "extension")

            focus = json.loads(
                run_guard(
                    "extract",
                    requirement,
                    "--id",
                    "EXT-001",
                    "--profile",
                    "focus",
                    "--format",
                    "json",
                ).stdout
            )
            audit = json.loads(
                run_guard(
                    "extract",
                    requirement,
                    "--id",
                    "EXT-001",
                    "--profile",
                    "audit",
                    "--format",
                    "json",
                ).stdout
            )
            full = json.loads(
                run_guard(
                    "extract",
                    requirement,
                    "--id",
                    "EXT-001",
                    "--profile",
                    "full",
                    "--format",
                    "json",
                ).stdout
            )
            common = {
                "source_path",
                "source_sha256",
                "selector",
                "section_key",
                "record_id",
                "profile",
                "range",
            }
            self.assertTrue(common <= focus.keys())
            self.assertNotIn("diagnostics", focus)
            self.assertIn("related_records", audit)
            self.assertIn("diagnostics", audit)
            self.assertIn("fields", full)
            self.assertIn("raw_markdown", full)
            self.assertNotEqual(set(focus), set(audit))
            self.assertNotEqual(set(audit), set(full))

    def test_review_validates_complete_findings_and_builds_change_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirement, _ = self._generated_pair(root)
            pending = json.loads(
                run_guard("review", requirement, "--format", "json").stdout
            )
            hashes = pending["source_sha256"]
            malformed = root / "malformed.json"
            malformed.write_text(
                json.dumps(
                    {
                        "layer": "AGENT",
                        "owner": "agent-reviewer",
                        "status": [],
                        "source_sha256": hashes,
                        "findings": [],
                    }
                ),
                encoding="utf-8",
            )
            malformed_result = run_guard(
                "review", requirement, "--agent-result", malformed
            )
            self.assertEqual(malformed_result.returncode, 2)
            self.assertNotIn("Traceback", malformed_result.stderr)

            incomplete = root / "incomplete.json"
            incomplete.write_text(
                json.dumps(
                    {
                        "layer": "AGENT",
                        "owner": "agent-reviewer",
                        "status": "WARNING",
                        "source_sha256": hashes,
                        "findings": [{"target": "REQ-001", "disposition": "ACCEPTED"}],
                    }
                ),
                encoding="utf-8",
            )
            rejected = run_guard("review", requirement, "--agent-result", incomplete)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("finding", rejected.stderr)

            accepted = root / "accepted.json"
            accepted.write_text(
                json.dumps(
                    {
                        "layer": "AGENT",
                        "owner": "agent-reviewer",
                        "status": "WARNING",
                        "source_sha256": hashes,
                        "findings": [
                            {
                                "layer": "AGENT",
                                "owner": "reviewer",
                                "severity": "MEDIUM",
                                "target": "REQ-001",
                                "source_sha256": hashes,
                                "reason": "Ambiguous boundary",
                                "evidence": "REQ-001 result",
                                "suggestion": "Clarify the boundary",
                                "disposition": "ACCEPTED",
                                "acceptance_check": "REQ-001 names the boundary",
                                "assignee": "author",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            reviewed = run_guard(
                "review", requirement, "--agent-result", accepted, "--format", "json"
            )
            self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
            report = json.loads(reviewed.stdout)
            self.assertIn("review_package", report)
            self.assertEqual(report["overall_status"], "PENDING_HUMAN")
            self.assertEqual(
                report["change_items"],
                [
                    {
                        "finding": 1,
                        "target": "REQ-001",
                        "reason": "Ambiguous boundary",
                        "expected_change": "Clarify the boundary",
                        "acceptance_check": "REQ-001 names the boundary",
                        "owner": "author",
                    }
                ],
            )

    def test_cross_document_reference_paths_and_directions_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            source = solution.read_text(encoding="utf-8")
            source = source.replace(
                f"`{requirement.name}#REQ-001`。",
                "`wrong.md#REQ-001`、AC-001。",
            )
            solution.write_text(source, encoding="utf-8")

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 1)
            self.assertIn("reference.path_mismatch", checked.stdout)
            self.assertIn("reference.direction", checked.stdout)

    def test_each_path_is_checked_when_the_same_target_is_referenced_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            source = solution.read_text(encoding="utf-8")
            valid_reference = f"`{requirement.name}#REQ-001`"
            record_start = source.index("#### SOL-001")
            record_source = source[record_start:]
            self.assertIn(valid_reference, record_source)
            record_source = record_source.replace(
                valid_reference,
                f"`wrong.md#REQ-001`\u3001{valid_reference}",
                1,
            )
            source = source[:record_start] + record_source
            solution.write_text(source, encoding="utf-8")

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 1)
            self.assertIn("reference.path_mismatch", checked.stdout)
            self.assertIn("wrong.md", checked.stdout)

    def test_audit_extraction_includes_cross_document_direct_context(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, _ = self._generated_pair(Path(directory))

            extracted = run_guard(
                "extract",
                requirement,
                "--id",
                "REQ-001",
                "--profile",
                "audit",
                "--format",
                "json",
            )

            self.assertEqual(extracted.returncode, 0, extracted.stderr)
            report = json.loads(extracted.stdout)
            related = {item["id"] for item in report["related_records"]}
            self.assertEqual(related, {"AC-001", "SOL-001", "TEST-001"})
            self.assertEqual(report["coverage"]["test"]["percent"], 100.0)

            markdown = run_guard(
                "extract", requirement, "--id", "REQ-001", "--profile", "focus"
            )
            self.assertEqual(markdown.returncode, 0, markdown.stderr)
            self.assertIn("source_sha256:", markdown.stdout)
            self.assertIn("selector:", markdown.stdout)
            self.assertIn("REQ-001", markdown.stdout)

    def test_zero_current_requirements_reports_not_applicable(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            requirement.write_text(
                requirement.read_text(encoding="utf-8").replace("`[P0]`", "`[P1]`"),
                encoding="utf-8",
            )

            checked = run_guard(
                "check",
                "--requirement",
                requirement,
                "--solution",
                solution,
                "--format",
                "json",
            )

            self.assertEqual(checked.returncode, 1)
            report = json.loads(checked.stdout)
            self.assertEqual(
                report["coverage"]["ac"],
                {
                    "covered": 0,
                    "total": 0,
                    "not_applicable": True,
                },
            )
            self.assertTrue(
                any(
                    item["code"] == "scope.non_current_reference"
                    for item in report["diagnostics"]
                )
            )

    def test_atomic_create_cleans_temporary_file_when_validation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "PIRC-99 Invalid 需求分析.md"
            with mock.patch(
                "src.controller.doc_guard.parse_file", side_effect=ValueError("invalid")
            ):
                with self.assertRaisesRegex(ValueError, "invalid"):
                    doc_guard._create(target, "---\ntitle: X\n---\n\n# X\n")

            self.assertFalse(target.exists())
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_atomic_create_closes_descriptor_when_fdopen_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "PIRC-99 Descriptor.md"
            content = doc_guard._render_template(
                "requirement-analysis.md",
                {
                    "TITLE": target.stem,
                    "ISSUE_ID": "PIRC-99",
                    "REQUIREMENT_PATH": target.name,
                    "SOLUTION_PATH": "PIRC-99 Solution.md",
                },
            )
            real_mkstemp = doc_guard.tempfile.mkstemp
            created = []

            def record_mkstemp(*args, **kwargs):
                result = real_mkstemp(*args, **kwargs)
                created.append(result)
                return result

            try:
                with (
                    mock.patch.object(
                        doc_guard.tempfile, "mkstemp", side_effect=record_mkstemp
                    ),
                    mock.patch.object(
                        doc_guard.os, "fdopen", side_effect=OSError("fdopen failed")
                    ),
                ):
                    with self.assertRaisesRegex(OSError, "^fdopen failed$"):
                        doc_guard._create(target, content)

                descriptor, temporary_name = created[0]
                with self.assertRaises(OSError):
                    os.fstat(descriptor)
                self.assertFalse(target.exists())
                self.assertFalse(Path(temporary_name).exists())
            finally:
                if created:
                    descriptor, temporary_name = created[0]
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
                    Path(temporary_name).unlink(missing_ok=True)

    def test_atomic_create_closes_stream_when_fsync_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "PIRC-99 Fsync.md"
            content = doc_guard._render_template(
                "requirement-analysis.md",
                {
                    "TITLE": target.stem,
                    "ISSUE_ID": "PIRC-99",
                    "REQUIREMENT_PATH": target.name,
                    "SOLUTION_PATH": "PIRC-99 Solution.md",
                },
            )
            descriptors = []

            def fail_fsync(descriptor):
                descriptors.append(descriptor)
                raise OSError("fsync failed")

            with mock.patch.object(doc_guard.os, "fsync", side_effect=fail_fsync):
                with self.assertRaisesRegex(OSError, "^fsync failed$"):
                    doc_guard._create(target, content)

            with self.assertRaises(OSError):
                os.fstat(descriptors[0])
            self.assertFalse(target.exists())
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_relation_children_and_headings_below_h4_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, _ = self._generated_pair(Path(directory))
            source = requirement.read_text(encoding="utf-8")
            source = source.replace(
                "## 背景与目标",
                "### 关系表下非法分组\n\n## 背景与目标",
            ).replace(
                "#### KR-001 补充关键结果",
                "#### KR-001 补充关键结果\n\n##### 非法更深分节",
            )
            requirement.write_text(source, encoding="utf-8")

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 1)
            self.assertIn("structure.relation_children", checked.stdout)
            self.assertIn("structure.heading_too_deep", checked.stdout)

    def test_required_reference_edges_and_backlinks_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            requirement.write_text(
                requirement.read_text(encoding="utf-8").replace(
                    "- 验收：AC-001。", "- 验收：待补充。"
                ),
                encoding="utf-8",
            )
            solution.write_text(
                solution.read_text(encoding="utf-8").replace(
                    "- 测试：TEST-001。", "- 测试：待补充。"
                ),
                encoding="utf-8",
            )

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 1)
            self.assertIn("reference.required", checked.stdout)
            self.assertIn("reference.backlink_missing", checked.stdout)
            self.assertIn("coverage.ac_missing", checked.stdout)

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
            self.assertEqual(
                run_guard("init", "requirement", requirement).returncode, 0
            )
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
            self.assertEqual(
                run_guard("init", "requirement", requirement).returncode, 0
            )
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
                root / "workspace-b" / "MPA" / "project" / "PIRC-99 Example 方案设计.md"
            )
            self.assertEqual(
                run_guard("init", "requirement", requirement).returncode, 0
            )
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
            self.assertEqual(
                run_guard("init", "requirement", requirement).returncode, 0
            )
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

    def test_record_fields_ignore_fenced_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            source = solution.read_text(encoding="utf-8")
            boundary = source.index("\n## ", source.index("#### SOL-001"))
            source = (
                source[:boundary]
                + "\n```text\n- 需求：REQ-999\n- 测试：TEST-999\n```\n"
                + source[boundary:]
            )
            solution.write_text(source, encoding="utf-8")

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("PASS", checked.stdout)
            self.assertNotIn("REQ-999", checked.stdout)
            self.assertNotIn("TEST-999", checked.stdout)

    def test_wrong_record_shapes_are_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            requirement, solution = self._generated_pair(Path(directory))
            requirement.write_text(
                requirement.read_text(encoding="utf-8").replace(
                    "\n## 验收",
                    "\n#### REQ-999 H4 不是需求记录形状\n- 结果：x\n\n## 验收",
                ),
                encoding="utf-8",
            )
            solution.write_text(
                solution.read_text(encoding="utf-8").replace(
                    "\n## 实施与验收",
                    "\n1. `SOL-999` 有序列表不是方案记录形状。\n\n## 实施与验收",
                ),
                encoding="utf-8",
            )

            checked = run_guard("check", requirement)

            self.assertEqual(checked.returncode, 1)
            self.assertGreaterEqual(checked.stdout.count("record.shape_invalid"), 2)

    def test_adjacent_fenced_blocks_are_counted_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "ordinary.md"
            document.write_text(
                "---\ntitle: X\n---\n\n# X\n## A\n"
                "```text\none\n```\n```text\ntwo\n```\n",
                encoding="utf-8",
            )

            catalogued = run_guard("catalog", document, "--format", "json")

            self.assertEqual(catalogued.returncode, 0, catalogued.stderr)
            report = json.loads(catalogued.stdout)
            section = next(item for item in report["entries"] if item["key"] == "a")
            self.assertEqual(section["code_block_count"], 2)

    def test_atomic_publish_does_not_overwrite_a_racing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "PIRC-99 Race 需求分析.md"
            content = doc_guard._render_template(
                "requirement-analysis.md",
                {
                    "TITLE": target.stem,
                    "ISSUE_ID": "PIRC-99",
                    "REQUIREMENT_PATH": target.name,
                    "SOLUTION_PATH": "PIRC-99 Race 方案设计.md",
                },
            )
            real_link = doc_guard.os.link

            def racing_link(source, destination):
                Path(destination).write_text("competitor", encoding="utf-8")
                return real_link(source, destination)

            with mock.patch(
                "src.controller.doc_guard.os.link", side_effect=racing_link
            ):
                with self.assertRaises(FileExistsError):
                    doc_guard._create(target, content)

            self.assertEqual(target.read_text(encoding="utf-8"), "competitor")
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_atomic_publish_commits_before_temporary_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "PIRC-99 Cleanup.md"
            content = doc_guard._render_template(
                "requirement-analysis.md",
                {
                    "TITLE": target.stem,
                    "ISSUE_ID": "PIRC-99",
                    "REQUIREMENT_PATH": target.name,
                    "SOLUTION_PATH": "PIRC-99 Solution.md",
                },
            )
            real_unlink = Path.unlink
            failed_once = False
            samefile_calls = []

            def fail_first_temporary_unlink(path, *args, **kwargs):
                nonlocal failed_once
                if path.suffix == ".tmp" and not failed_once:
                    failed_once = True
                    raise OSError("cleanup failed")
                return real_unlink(path, *args, **kwargs)

            real_samefile = Path.samefile

            def record_samefile(path, other):
                samefile_calls.append((path, other))
                return real_samefile(path, other)

            with (
                mock.patch.object(Path, "unlink", fail_first_temporary_unlink),
                mock.patch.object(Path, "samefile", record_samefile),
            ):
                doc_guard._create(target, content)

            self.assertEqual(target.read_text(encoding="utf-8"), content)
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])
            self.assertEqual(samefile_calls, [])

    def test_atomic_cleanup_preserves_a_replaced_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "PIRC-99 Replaced.md"
            content = doc_guard._render_template(
                "requirement-analysis.md",
                {
                    "TITLE": target.stem,
                    "ISSUE_ID": "PIRC-99",
                    "REQUIREMENT_PATH": target.name,
                    "SOLUTION_PATH": "PIRC-99 Solution.md",
                },
            )
            real_unlink = Path.unlink
            replaced = False

            def replace_target_before_cleanup_failure(path, *args, **kwargs):
                nonlocal replaced
                if path.suffix == ".tmp" and not replaced:
                    replaced = True
                    real_unlink(target)
                    target.write_text("competitor", encoding="utf-8")
                    raise OSError("cleanup failed after target replacement")
                return real_unlink(path, *args, **kwargs)

            with mock.patch.object(
                Path, "unlink", replace_target_before_cleanup_failure
            ):
                doc_guard._create(target, content)

            self.assertEqual(target.read_text(encoding="utf-8"), "competitor")
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_solution_init_rejects_local_dangling_requirement_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirement = root / "PIRC-99 Broken 需求分析.md"
            solution = root / "PIRC-99 Broken 方案设计.md"
            self.assertEqual(
                run_guard("init", "requirement", requirement).returncode, 0
            )
            requirement.write_text(
                requirement.read_text(encoding="utf-8").replace(
                    "- 需求：REQ-001。", "- 需求：REQ-999。"
                ),
                encoding="utf-8",
            )

            created = run_guard(
                "init", "solution", solution, "--requirement", requirement
            )

            self.assertEqual(created.returncode, 2)
            self.assertIn("requirement must pass", created.stderr)
            self.assertFalse(solution.exists())


if __name__ == "__main__":
    unittest.main()
