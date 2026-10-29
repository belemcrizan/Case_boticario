import random
import unittest
from dataclasses import replace

from otm_guard.engine import reconcile, verify_result
from otm_guard.ingest import load_dataset
from otm_guard.models import (
    STRICT_RULE, Dataset, InvariantError, Order, Packaging, Policy, Suggestion,
)

from .helpers import FilesCase, combo_dataset


class SuppliedDataTests(FilesCase):
    def test_acceptance_all_twelve_pois(self):
        result = reconcile(load_dataset(self.inputs))
        expected = [0, 0, 10, 3, 6, 0, 108, 30, 30, 12, 0, 0]
        self.assertEqual([r.qtd_final for r in result.decisions], expected)
        self.assertEqual(result.metrics["unidades_otm"], 297)
        self.assertEqual(result.metrics["unidades_finais"], 199)
        self.assertEqual(result.metrics["unidades_demandadas"], 455)
        self.assertEqual(result.metrics["linhas_revisao"], 1)
        self.assertTrue(all(result.checks.values()))
        ghost = result.decisions[10]
        self.assertEqual(ghost.status, "REVISAO")
        self.assertEqual(set(ghost.reasons), {"OTM_AUSENTE", "EMBALAGEM_AUSENTE", "ESTOQUE_AUSENTE"})

    def test_explicit_alternative_policy(self):
        result = reconcile(load_dataset(self.inputs), Policy("complete-kits"))
        self.assertEqual([r.qtd_final for r in result.decisions[:2]], [35, 35])
        self.assertEqual(result.metrics["unidades_finais"], 269)

    def test_idempotent_quantities_without_reallocating_reductions(self):
        data = load_dataset(self.inputs)
        first = reconcile(data)
        data.suggestions = {
            r.poi_id: Suggestion(r.poi_id, r.sku, r.qtd_final, "SUCESSO" if r.qtd_final else "ZERADO")
            for r in first.decisions if r.poi_id in data.suggestions
        }
        second = reconcile(data)
        self.assertEqual([r.qtd_final for r in first.decisions], [r.qtd_final for r in second.decisions])

    def test_sku_mismatch_blocks_whole_combo(self):
        data = load_dataset(self.inputs)
        data.suggestions["POI-1008"] = replace(data.suggestions["POI-1008"], sku="OUTRO")
        rows = {r.poi_id: r for r in reconcile(data).decisions}
        for pid in ("POI-1008", "POI-1009"):
            self.assertEqual(rows[pid].qtd_final, 0)
            self.assertEqual(rows[pid].status, "REVISAO")

    def test_missing_stock_is_not_zero_stock(self):
        data = load_dataset(self.inputs)
        data.stock.pop(("CD_SP", "SKU-X1"))
        row = next(r for r in reconcile(data).decisions if r.poi_id == "POI-1010")
        self.assertEqual(row.status, "REVISAO")
        data.stock[("CD_SP", "SKU-X1")] = 0
        row = next(r for r in reconcile(data).decisions if r.poi_id == "POI-1010")
        self.assertEqual(row.status, "ZERADO")

    def test_unknown_otm_status_is_not_silently_accepted(self):
        data = load_dataset(self.inputs)
        data.suggestions["POI-1010"] = replace(data.suggestions["POI-1010"], status="ERRO")
        row = next(r for r in reconcile(data).decisions if r.poi_id == "POI-1010")
        self.assertEqual(row.qtd_final, 0)
        self.assertIn("STATUS_OTM_NAO_APROVADO", row.reasons)

    def test_demand_is_a_hard_upper_bound(self):
        data = load_dataset(self.inputs)
        data.orders["POI-1010"] = replace(data.orders["POI-1010"], qtd_pedida=7)
        row = next(r for r in reconcile(data).decisions if r.poi_id == "POI-1010")
        self.assertEqual(row.qtd_final, 6)
        self.assertIn("LIMITE_DEMANDA", row.reasons)


class AllocationTests(unittest.TestCase):
    def test_combo_greatest_feasible_kit_count(self):
        self.assertEqual([r.qtd_final for r in reconcile(combo_dataset()).decisions], [3, 6])

    def test_coupled_packaging_requires_lcm(self):
        data = combo_dataset(p=2, q=3, m=6, n=10, cap_a=140, cap_b=210, stock_a=140, stock_b=210)
        result = reconcile(data)
        # n precisa ser múltiplo de MMC(6/MDC(6,2),10/MDC(10,3)) = 30.
        self.assertEqual([r.qtd_final for r in result.decisions], [120, 180])

    def test_fractionation_ignores_master_multiple(self):
        data = combo_dataset(p=1, q=1, m=12, n=12, cap_a=5, cap_b=5)
        data.packaging = {sku: replace(pack, fractionation=True) for sku, pack in data.packaging.items()}
        self.assertEqual([r.qtd_final for r in reconcile(data).decisions], [5, 5])

    def test_strict_mismatch_and_packaging_and_stock_zero_entire_lot(self):
        for data in (
            combo_dataset(rule=STRICT_RULE),
            combo_dataset(p=1, q=1, m=6, cap_a=8, cap_b=8, rule=STRICT_RULE),
            combo_dataset(p=1, q=1, cap_a=8, cap_b=8, stock_b=7, rule=STRICT_RULE),
        ):
            with self.subTest(data=data):
                self.assertEqual([r.qtd_final for r in reconcile(data).decisions], [0, 0])

    def test_strict_balanced_lot_is_preserved(self):
        data = combo_dataset(cap_a=4, cap_b=8, rule=STRICT_RULE)
        self.assertEqual([r.qtd_final for r in reconcile(data).decisions], [4, 8])

    def test_missing_component_is_quarantined(self):
        data = combo_dataset()
        data.orders.pop("P2")
        row = reconcile(data).decisions[0]
        self.assertEqual(row.qtd_final, 0)
        self.assertEqual(row.status, "REVISAO")
        self.assertIn("COMPONENTE_COMBO_AUSENTE", row.reasons)

    def test_invalid_component_blocks_valid_peer(self):
        data = combo_dataset()
        data.suggestions.pop("P2")
        result = reconcile(data)
        self.assertEqual([r.qtd_final for r in result.decisions], [0, 0])
        self.assertEqual(result.remaining_stock, data.stock)

    def test_same_sku_different_orders_share_one_cd_balance(self):
        orders = {f"P{i}": Order(f"P{i}", f"PED{i}", "CD1", "F1", "A", 8) for i in (1, 2)}
        data = Dataset(orders, {pid: Suggestion(pid, "A", 8, "SUCESSO") for pid in orders},
                       {("CD1", "A"): 10}, {"A": Packaging("A", "M", 6, False)}, {}, {})
        result = reconcile(data)
        self.assertEqual([r.qtd_final for r in result.decisions], [6, 0])
        self.assertEqual(result.remaining_stock[("CD1", "A")], 4)

    def test_same_sku_in_different_cds_cannot_borrow_stock(self):
        data = combo_dataset()
        data.orders = {"P1": Order("P1", "PED1", "CD2", "F1", "X", 20),
                       "P2": Order("P2", "PED2", "CD1", "F2", "X", 20)}
        data.suggestions = {pid: Suggestion(pid, "X", 20, "SUCESSO") for pid in data.orders}
        data.packaging = {"X": Packaging("X", "M", 1, True)}
        data.stock = {("CD1", "X"): 100, ("CD2", "X"): 1}
        data.combos, data.membership = {}, {}
        self.assertEqual([r.qtd_final for r in reconcile(data).decisions], [1, 20])

    def test_shared_stock_between_combos_is_debited_atomically(self):
        data = combo_dataset(p=1, q=1, cap_a=4, cap_b=4, stock_a=5, stock_b=6)
        data.orders.update({"P3": Order("P3", "PED2", "CD1", "F2", "A", 4),
                            "P4": Order("P4", "PED2", "CD1", "F2", "B", 4)})
        data.suggestions.update({pid: Suggestion(pid, data.orders[pid].sku, 4, "SUCESSO") for pid in ("P3", "P4")})
        result = reconcile(data)
        self.assertEqual([r.qtd_final for r in result.decisions], [4, 4, 1, 1])
        self.assertEqual(result.remaining_stock[("CD1", "B")], 1)

    def test_random_feasibility_matches_independent_bruteforce(self):
        rng = random.Random(20261029)
        for trial in range(600):
            p, q, m, n = [rng.randint(1, 6) for _ in range(4)]
            ca, cb, sa, sb = [rng.randint(0, 80) for _ in range(4)]
            data = combo_dataset(p, q, m, n, ca, cb, sa, sb)
            candidates = [k for k in range(81) if k*p <= min(ca, sa) and k*q <= min(cb, sb)
                          and (k*p) % m == 0 and (k*q) % n == 0]
            best = max(candidates)
            with self.subTest(trial=trial):
                self.assertEqual([r.qtd_final for r in reconcile(data).decisions], [best*p, best*q])

    def test_order_of_input_does_not_change_allocation(self):
        data = combo_dataset()
        expected = reconcile(data).decisions
        data.orders = dict(reversed(list(data.orders.items())))
        data.suggestions = dict(reversed(list(data.suggestions.items())))
        self.assertEqual(reconcile(data).decisions, expected)

    def test_postconditions_detect_tampering(self):
        data = combo_dataset()
        result = reconcile(data)
        mutations = (
            [replace(result.decisions[0], qtd_final=4), result.decisions[1]],
            [replace(result.decisions[0], sku="OUTRO"), result.decisions[1]],
            result.decisions[:1], result.decisions + [result.decisions[0]],
        )
        for rows in mutations:
            with self.subTest(rows=rows):
                with self.assertRaises(InvariantError):
                    verify_result(data, rows, result.policy, result.remaining_stock)

    def test_policy_names_are_validated(self):
        with self.assertRaises(ValueError):
            Policy("inventada")
