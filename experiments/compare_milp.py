#!/usr/bin/env python3
"""Experimento MILP isolado: objetivos diferentes podem mudar a distribuição.

Quatro pedidos do mesmo combo 1:1 demandam 6,2,2,2 kits. Há seis kits em estoque.
Nenhum dado real do case é substituído. Este módulo não integra o caminho da API.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def compare() -> dict:
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp

    from otm_guard.engine import reconcile
    from otm_guard.models import MAX_RULE, Combo, Dataset, Order, Packaging, Suggestion

    demand = np.array([6, 2, 2, 2])
    orders, suggestions = {}, {}
    for order, quantity in enumerate(demand):
        for sku in ("A", "B"):
            pid = f"P{order}-{sku}"
            orders[pid] = Order(pid, f"PED{order}", "CD", "F", sku, int(quantity))
            suggestions[pid] = Suggestion(pid, sku, int(quantity), "SUCESSO")
    data = Dataset(
        orders,
        suggestions,
        {("CD", "A"): 6, ("CD", "B"): 6},
        {s: Packaging(s, "Sintética", 1, True) for s in ("A", "B")},
        {"C": Combo("C", "Sintético", MAX_RULE, {"A": 1, "B": 1})},
        {"A": "C", "B": "C"},
    )
    baseline = reconcile(data)
    kits = [next(r.qtd_final for r in baseline.decisions if r.poi_id == f"P{i}-A") for i in range(4)]
    rows = [{"objective": "deterministic_lexical", "kits_by_order": kits}]
    # n[4] inteiros de kits, z[4] binários de pedido completo, t contínuo de equidade.
    matrix, lower, upper = [], [], []
    matrix.append([1, 1, 1, 1, 0, 0, 0, 0, 0])
    lower.append(-np.inf)
    upper.append(6)
    for i in range(4):
        row = [0.0] * 9
        row[i] = 1
        row[4 + i] = -float(demand[i])
        matrix.append(row)
        lower.append(0)
        upper.append(np.inf)
        row = [0.0] * 9
        row[i] = 1
        row[8] = -float(demand[i])
        matrix.append(row)
        lower.append(0)
        upper.append(np.inf)
    # Peso diminuto desempata por unidades sem mudar a prioridade discreta.
    for objective in ("max_units", "max_complete_orders", "commercial_priority", "max_min_fraction"):
        c = np.zeros(9)
        if objective == "max_units":
            c[:4] = -2
        elif objective == "max_complete_orders":
            c[4:8] = -1
            c[:4] = -0.001
        elif objective == "commercial_priority":
            c[:4] = -np.array([1, 4, 3, 2]) * 2
        else:
            c[8] = -1
            c[:4] = -0.00001
        solved = milp(
            c,
            integrality=[1] * 8 + [0],
            bounds=Bounds([0] * 9, [*demand, *([1] * 5)]),
            constraints=LinearConstraint(np.array(matrix), lower, upper),
            options={"time_limit": 5},
        )
        if not solved.success:
            raise RuntimeError(f"Solver não demonstrou ótimo: {solved.message}")
        rows.append({"objective": objective, "kits_by_order": [int(round(n)) for n in solved.x[:4]]})
    for row in rows:
        quantities = row["kits_by_order"]
        assert all(0 <= q <= int(d) for q, d in zip(quantities, demand, strict=True)) and sum(quantities) <= 6
        row.update(
            units=sum(quantities) * 2,
            complete_orders=int(sum(q == d for q, d in zip(quantities, demand, strict=True))),
            minimum_served_fraction=round(
                min(q / int(d) for q, d in zip(quantities, demand, strict=True)), 4
            ),
        )
    return {
        "synthetic": True,
        "demands_in_kits": demand.tolist(),
        "available_kits": 6,
        "priority_weights": [1, 4, 3, 2],
        "results": rows,
        "notice": "MILP experimental. Maximizar unidades, pedidos completos ou equidade são objetivos distintos; não substitui o motor nem homologa prioridades.",
    }


if __name__ == "__main__":
    print(json.dumps(compare(), ensure_ascii=False, indent=2))
