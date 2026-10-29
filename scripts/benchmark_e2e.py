#!/usr/bin/env python3
"""Massa sintética, pipeline CSV -> motor -> artefatos -> SQL -> consulta paginada.

Cada tamanho usa processo novo para obter pico RSS independente. Geração da massa
fica fora do tempo total. A instrumentação de função mede o verificador existente
sem alterar seu código e acrescenta overhead a toda a etapa de cálculo.
"""

import argparse
import csv
import hashlib
import json
import platform
import random
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def generate(directory: Path, count: int, seed: int):
    from otm_guard.ingest import SCHEMAS

    rng = random.Random(seed)
    with (
        (directory / "pedidos_oms.csv").open("w", newline="") as oms,
        (directory / "saidas_otm.csv").open("w", newline="") as otm,
    ):
        ow, sw = csv.writer(oms), csv.writer(otm)
        ow.writerow(SCHEMAS["pedidos_oms.csv"])
        sw.writerow(SCHEMAS["saidas_otm.csv"])
        row, group = 0, 0
        while row < count:
            skus = ("A", "B") if group % 3 == 0 and count - row >= 2 else ("X",)
            demand = rng.randint(1, 90)
            for sku in skus:
                q = demand * (2 if sku == "B" else 1)
                pid = f"P{row:07d}"
                ow.writerow([pid, f"O{group:07d}", f"C{group % 5}", "F1", sku, q])
                sw.writerow([pid, sku, rng.randint(0, q), "SUCESSO"])
                row += 1
            group += 1

    def write(name, rows):
        with (directory / name).open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(SCHEMAS[name])
            writer.writerows(rows)

    write(
        "foto_estoque_cd_05h.csv",
        [(f"C{cd}", sku, count * 100) for cd in range(5) for sku in ("A", "B", "X")],
    )
    write(
        "regras_embalagem.csv",
        [("A", "Sintética", 1, "SIM"), ("B", "Sintética", 6, "NÃO"), ("X", "Sintética", 12, "NÃO")],
    )
    write(
        "de_para_combos.csv",
        [
            ("SYNTHETIC", "Combo sintético", sku, p, "Ajustar para maior combo completo")
            for sku, p in [("A", 1), ("B", 2)]
        ],
    )


def child(count: int, seed: int) -> dict:
    from otm_guard import engine
    from otm_guard.ingest import load_dataset
    from otm_guard.report import source_hashes
    from platform_api.config import Settings
    from platform_api.publish import enriched_rows, publish, stock_rows
    from platform_api.repository import Repository, make_engine
    from platform_api.storage import LocalStorage, digest

    times = {}
    verified = 0.0
    entered = 0.0
    target = engine.verify_result.__code__

    def profile_call(frame, event, arg):
        nonlocal verified, entered
        if frame.f_code is target:
            if event == "call":
                entered = time.perf_counter()
            elif event == "return":
                verified += time.perf_counter() - entered

    with tempfile.TemporaryDirectory(prefix="otm-benchmark-") as folder:
        root = Path(folder)
        inputs = root / "inputs"
        inputs.mkdir()
        generate(inputs, count, seed)
        repo = Repository(make_engine(Settings(environment="test", data_dir=root / "db", seed_demo=False)))
        now = time.time()
        rid = "benchmark-run"
        repo.create(
            {
                "id": rid,
                "owner": "benchmark",
                "label": "Sintético",
                "policy": "strict",
                "state": "QUEUED",
                "kind": "PROPOSAL",
                "visibility": "private",
                "fingerprint": "synthetic",
                "idempotency_key": "benchmark",
                "created_at": now,
                "updated_at": now,
                "attempt": 0,
            }
        )
        repo.claim(rid, 1800)
        store = LocalStorage(root / "objects")
        started = time.perf_counter()
        t = started
        data = load_dataset(inputs)
        times["ingestion"] = time.perf_counter() - t
        previous = sys.getprofile()
        t = time.perf_counter()
        sys.setprofile(profile_call)
        try:
            result = engine.reconcile(data)
        finally:
            sys.setprofile(previous)
        calculation = time.perf_counter() - t
        times["reconcile_excluding_verifier"] = max(0, calculation - verified)
        times["verification"] = verified
        t = time.perf_counter()
        output = root / "output"
        engine_id = publish(data, result, output)
        files = []
        for p in sorted(output.iterdir()):
            key = f"bench/{p.name}"
            store.put(key, p)
            files.append({"name": p.name, "key": key, "sha256": digest(p), "size": p.stat().st_size})
        times["publication_and_object_copy"] = time.perf_counter() - t
        summary = {
            "engine_run_id": engine_id,
            "metrics": result.metrics,
            "checks": result.checks,
            "inputs_sha256": data.input_hashes,
        }
        t = time.perf_counter()
        repo.complete(
            rid, enriched_rows(data, result, False), stock_rows(data, result), summary, {}, files, 1
        )
        times["sql_persistence"] = time.perf_counter() - t
        t = time.perf_counter()
        page = repo.page("decisions", rid, 20, 0)
        times["first_page_query"] = time.perf_counter() - t
        times["total"] = time.perf_counter() - started
        assert len(page["items"]) == min(20, count) and page["total"] == count and all(result.checks.values())
        for f in files:
            assert digest(store.path(f["key"])) == f["sha256"]
        db_bytes = (root / "db/platform.db").stat().st_size
        repo.engine.dispose()
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {
            "pois": count,
            "seed": seed,
            "synthetic": True,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "timings_seconds": {k: round(v, 6) for k, v in times.items()},
            "peak_process_rss_mib": round(rss / (1024**2 if sys.platform == "darwin" else 1024), 3),
            "artifact_bytes": sum(f["size"] for f in files),
            "sqlite_bytes": db_bytes,
            "pois_per_second": round(count / times["total"], 2),
            "checks": result.checks,
            "metrics": result.metrics,
            "source_sha256": source_hashes(),
            "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scope": "CSV, motor instrumentado, publicação streaming, cópia local imutável, SQL SQLite e primeira página; geração e verificação extra de hashes fora do total",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", default="10000,100000,500000,1000000")
    parser.add_argument("--seed", type=int, default=20261029)
    parser.add_argument("--child", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.child:
        print(json.dumps(child(args.child, args.seed), ensure_ascii=False))
        return
    sizes = [int(s) for s in args.sizes.split(",")]
    if any(n < 1 or n > 1_000_000 for n in sizes):
        parser.error("Tamanhos devem estar entre 1 e 1000000")
    rows = []
    for n in sizes:
        process = subprocess.run(
            [sys.executable, __file__, "--child", str(n), "--seed", str(args.seed)],
            capture_output=True,
            text=True,
        )
        if process.returncode:
            raise SystemExit(process.stderr)
        row = json.loads(process.stdout)
        rows.append(row)
        print(
            f"Concluído: {n} POIs, {row['timings_seconds']['total']} s, {row['peak_process_rss_mib']} MiB RSS",
            flush=True,
        )
        if args.output:
            args.output.write_text(
                json.dumps(
                    {"results": rows, "complete": len(rows) == len(sizes)}, ensure_ascii=False, indent=2
                )
                + "\n"
            )
    print(json.dumps({"results": rows, "complete": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
