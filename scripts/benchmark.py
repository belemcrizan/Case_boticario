#!/usr/bin/env python3
"""Benchmark sintético do motor + verificador. Não mede CSV, disco ou HTML."""

import argparse
import json
import platform
import random
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from otm_guard.engine import reconcile
from otm_guard.models import MAX_RULE, Combo, Dataset, Order, Packaging, Suggestion
from otm_guard.report import source_hashes


def generate(groups: int, seed: int) -> Dataset:
    rng = random.Random(seed)
    orders, suggestions = {}, {}
    stock = {(f"CD{i}", sku): groups * 30 for i in range(5) for sku in ("A", "B", "X")}
    for group in range(groups):
        cd = f"CD{group % 5}"
        demand = rng.randint(1, 50)
        for component, sku in enumerate(("A", "B") if group % 3 == 0 else ("X",)):
            pid = f"POI-{group:09d}-{component}"
            quantity = demand * (2 if sku == "B" else 1)
            orders[pid] = Order(pid, f"PED-{group:09d}", cd, f"F{group:09d}", sku, quantity)
            suggestions[pid] = Suggestion(pid, sku, rng.randint(0, quantity), "SUCESSO")
    return Dataset(
        orders, suggestions, stock,
        {"A": Packaging("A", "M", 1, True), "B": Packaging("B", "M", 6, False),
         "X": Packaging("X", "M", 12, False)},
        {"C": Combo("C", "Sintético 1:2", MAX_RULE, {"A": 1, "B": 2})}, {"A": "C", "B": "C"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--groups", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20261029)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.groups <= 1_000_000:
        parser.error("--groups deve estar entre 1 e 1000000")
    data = generate(args.groups, args.seed)
    tracemalloc.start()
    started = time.perf_counter()
    result = reconcile(data)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report = {
        "scope": "motor + verificação; exclui geração, leitura CSV e relatórios",
        "synthetic": True, "groups": args.groups, "seed": args.seed,
        "python": platform.python_version(), "platform": platform.platform(),
        "elapsed_seconds_with_tracemalloc": round(elapsed, 6),
        "peak_additional_traced_mib": round(peak / 1024**2, 3),
        "memory_scope": "alocações Python durante reconcile; exclui Dataset e RSS total",
        "source_sha256": source_hashes(), "metrics": result.metrics, "checks": result.checks,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
