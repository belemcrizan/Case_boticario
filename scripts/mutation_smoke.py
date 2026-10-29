#!/usr/bin/env python3
"""Três mutações representativas no motor em cópias temporárias isoladas."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    mutations = {
        "stock_credit_instead_of_debit": ("available[key] -= final", "available[key] += final"),
        "skip_packaging_rounding": ("final = limited // step * step", "final = limited"),
        "skip_strict_policy": ("if not proportional or kits != max_cap_kits:", "if False:"),
    }
    source = (ROOT / "otm_guard/engine.py").read_text()
    results = []
    for name, (before, after) in mutations.items():
        assert before in source
        with tempfile.TemporaryDirectory(prefix="otm-mutant-") as folder:
            target = Path(folder)
            for directory in ("otm_guard", "tests", "data"):
                shutil.copytree(
                    ROOT / directory, target / directory, ignore=shutil.ignore_patterns("__pycache__")
                )
            (target / "otm_guard/engine.py").write_text(source.replace(before, after, 1))
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "tests.test_engine", "-q"],
                cwd=target,
                capture_output=True,
                text=True,
            )
            results.append({"mutation": name, "killed": result.returncode != 0})
    report = {"sample_only": True, "mutations": results, "all_killed": all(r["killed"] for r in results)}
    print(json.dumps(report, indent=2))
    if not report["all_killed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
