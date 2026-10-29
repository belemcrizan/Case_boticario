import contextlib
import hashlib
import io
import json
from dataclasses import replace
from unittest.mock import patch

from otm_guard.cli import main
from otm_guard.engine import reconcile
from otm_guard.ingest import load_dataset
from otm_guard.models import ContractError, Issue
from otm_guard.report import _safe_cell, write_bundle

from .helpers import FilesCase


class CliReportTests(FilesCase):
    def invoke(self, *extra, output="result"):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main(["--input-dir", str(self.inputs), "--output-dir", str(self.root / output), *extra])

    def test_cli_and_all_seven_files(self):
        self.assertEqual(self.invoke(), 0)
        folder = self.root / "result"
        self.assertEqual({p.name for p in folder.iterdir()}, {
            "proposta_conciliada.csv", "fila_revisao.csv", "balanco_estoque.csv",
            "resumo.json", "manifest.json", "qualidade_dados.json", "relatorio.html",
        })
        summary = json.loads((folder / "resumo.json").read_text())
        self.assertTrue(summary["requires_review"])
        self.assertIsNone(summary["stock_snapshot_timestamp"])

    def test_fail_on_review_keeps_evidence_and_returns_three(self):
        self.assertEqual(self.invoke("--fail-on-review"), 3)
        self.assertTrue((self.root / "result/manifest.json").exists())

    def test_no_overwrite_and_failure_has_no_partial_output(self):
        self.assertEqual(self.invoke(), 0)
        before = (self.root / "result/manifest.json").read_bytes()
        self.assertEqual(self.invoke(), 2)
        self.assertEqual((self.root / "result/manifest.json").read_bytes(), before)
        (self.inputs / "saidas_otm.csv").unlink()
        self.assertEqual(self.invoke(output="invalid"), 2)
        self.assertFalse((self.root / "invalid").exists())

    def test_identical_runs_have_identical_artifact_bytes(self):
        self.assertEqual(self.invoke(output="first"), 0)
        self.assertEqual(self.invoke(output="second"), 0)
        for path in (self.root / "first").iterdir():
            with self.subTest(file=path.name):
                self.assertEqual(path.read_bytes(), (self.root / "second" / path.name).read_bytes())

    def test_manifest_checksums_cover_actual_artifacts(self):
        self.assertEqual(self.invoke(), 0)
        folder = self.root / "result"
        manifest = json.loads((folder / "manifest.json").read_text())
        for name, expected in manifest["artifacts_sha256"].items():
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(len(manifest["artifacts_sha256"]), 6)

    def test_policy_is_part_of_run_identity(self):
        self.invoke(output="strict")
        self.invoke("--incomplete-policy", "complete-kits", output="kits")
        a = json.loads((self.root / "strict/resumo.json").read_text())
        b = json.loads((self.root / "kits/resumo.json").read_text())
        self.assertNotEqual(a["run_id"], b["run_id"])
        self.assertEqual(b["metrics"]["unidades_finais"], 269)

    def test_html_escapes_free_text_without_second_template_pass(self):
        data = load_dataset(self.inputs)
        data.issues.append(Issue("INFO", "TESTE", "fonte", 1, "VERSION-ROWS", '<script>alert("x")</script>'))
        result = reconcile(data)
        write_bundle(data, result, self.root / "html")
        content = (self.root / "html/relatorio.html").read_text()
        self.assertNotIn('<script>alert("x")</script>', content)
        self.assertIn("&lt;script&gt;", content)
        self.assertIn("VERSION-ROWS", content)

    def test_formula_cells_are_neutralized(self):
        for text in ("=1+1", "+1", "-1", "@SUM(A1)", "  =1"):
            self.assertEqual(_safe_cell(text), "'" + text)
        self.assertEqual(_safe_cell(12), 12)
        self.assertEqual(_safe_cell("SKU-X1"), "SKU-X1")

    def test_write_failure_removes_staging_and_lock(self):
        data = load_dataset(self.inputs)
        result = reconcile(data)
        with patch("otm_guard.report._csv", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                write_bundle(data, result, self.root / "broken")
        self.assertFalse((self.root / "broken").exists())
        self.assertEqual(list(self.root.glob(".broken*")), [])

    def test_existing_lock_rejects_concurrent_writer(self):
        (self.root / ".result.lock").write_text("")
        data = load_dataset(self.inputs)
        with self.assertRaises(ContractError):
            write_bundle(data, reconcile(data), self.root / "result")
        self.assertTrue((self.root / ".result.lock").exists())

    def test_invariant_error_is_nonzero_without_output(self):
        from otm_guard.models import InvariantError
        with patch("otm_guard.cli.reconcile", side_effect=InvariantError("synthetic")):
            self.assertEqual(self.invoke(), 1)
        self.assertFalse((self.root / "result").exists())
