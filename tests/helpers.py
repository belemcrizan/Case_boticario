import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from otm_guard.models import MAX_RULE, Combo, Dataset, Order, Packaging, Suggestion

ROOT = Path(__file__).resolve().parents[1]


class FilesCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        shutil.copytree(ROOT / "data/input", self.inputs)

    def rows(self, name):
        with (self.inputs / name).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def write(self, name, rows):
        with (self.inputs / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def combo_dataset(p=1, q=2, m=1, n=1, cap_a=5, cap_b=7, stock_a=100, stock_b=100,
                  rule=MAX_RULE):
    orders = {
        "P1": Order("P1", "PED1", "CD1", "F1", "A", cap_a),
        "P2": Order("P2", "PED1", "CD1", "F1", "B", cap_b),
    }
    return Dataset(
        orders, {pid: Suggestion(pid, order.sku, order.qtd_pedida, "SUCESSO")
                 for pid, order in orders.items()},
        {("CD1", "A"): stock_a, ("CD1", "B"): stock_b},
        {"A": Packaging("A", "Marca", m, False), "B": Packaging("B", "Marca", n, False)},
        {"C": Combo("C", "Combo", rule, {"A": p, "B": q})}, {"A": "C", "B": "C"},
    )
