#!/usr/bin/env python3
"""Recalcula e compara os exemplos versionados, inclusive hashes e relatório."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from otm_guard.engine import reconcile
from otm_guard.ingest import load_dataset
from otm_guard.models import Policy
from otm_guard.report import write_bundle


def main() -> None:
    data = load_dataset(ROOT / "data/input")
    with tempfile.TemporaryDirectory() as folder:
        for mode in ("strict", "complete-kits"):
            actual = Path(folder) / mode
            expected = ROOT / "examples" / mode
            write_bundle(data, reconcile(data, Policy(mode)), actual)
            if {p.name for p in actual.iterdir()} != {p.name for p in expected.iterdir()}:
                raise SystemExit(f"Conjunto de arquivos diverge: {mode}")
            for path in actual.iterdir():
                if path.read_bytes() != (expected / path.name).read_bytes():
                    raise SystemExit(f"Exemplo desatualizado: {mode}/{path.name}")
    print("Exemplos strict e complete-kits reproduzidos integralmente.")


if __name__ == "__main__":
    main()
