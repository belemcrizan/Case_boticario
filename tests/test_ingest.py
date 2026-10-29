from otm_guard.ingest import load_dataset
from otm_guard.models import ContractError

from .helpers import FilesCase


class IngestTests(FilesCase):
    def test_supplied_anomalies_are_visible(self):
        data = load_dataset(self.inputs)
        self.assertEqual(data.orders["POI-1010"].sku, "SKU-X1")
        self.assertEqual(data.combos["CMB-SKIN-01"].components["SKU-E2"], 1)
        codes = [i.code for i in data.issues]
        self.assertEqual(codes.count("ESPACO_NORMALIZADO"), 2)
        self.assertEqual(codes.count("COMBO_DUPLICADO_REMOVIDO"), 1)
        self.assertEqual(len(data.input_hashes), 5)

    def test_missing_file(self):
        (self.inputs / "saidas_otm.csv").unlink()
        with self.assertRaises(ContractError):
            load_dataset(self.inputs)

    def test_duplicate_transactional_and_stock_keys(self):
        for name in ("pedidos_oms.csv", "saidas_otm.csv", "foto_estoque_cd_05h.csv", "regras_embalagem.csv"):
            with self.subTest(name=name):
                original = (self.inputs / name).read_bytes()
                rows = self.rows(name)
                self.write(name, rows + [rows[0]])
                with self.assertRaises(ContractError):
                    load_dataset(self.inputs)
                (self.inputs / name).write_bytes(original)

    def test_invalid_quantities_are_never_coerced(self):
        name = "pedidos_oms.csv"
        rows = self.rows(name)
        for invalid in ("", "-1", "1.0", "1e3", "nan", "１２", "1000000000001", "1\n2"):
            with self.subTest(value=invalid):
                rows[0]["qtd_pedida"] = invalid
                self.write(name, rows)
                with self.assertRaises(ContractError):
                    load_dataset(self.inputs)

    def test_zero_multiples_and_proportions(self):
        for name, field in (("regras_embalagem.csv", "multiplo_caixa_master"),
                            ("de_para_combos.csv", "proporcao_no_combo")):
            with self.subTest(field=field):
                original = (self.inputs / name).read_bytes()
                rows = self.rows(name)
                rows[0][field] = "0"
                self.write(name, rows)
                with self.assertRaises(ContractError):
                    load_dataset(self.inputs)
                (self.inputs / name).write_bytes(original)

    def test_unknown_fractionation(self):
        rows = self.rows("regras_embalagem.csv")
        rows[0]["permite_fracionamento"] = "TALVEZ"
        self.write("regras_embalagem.csv", rows)
        with self.assertRaises(ContractError):
            load_dataset(self.inputs)

    def test_unknown_rule_and_conflicting_description(self):
        name = "de_para_combos.csv"
        original = (self.inputs / name).read_bytes()
        for field, value in (("regra_quebra", "IGNORAR"), ("descricao_combo", "Outro combo")):
            with self.subTest(field=field):
                (self.inputs / name).write_bytes(original)
                rows = self.rows(name)
                rows[0][field] = value
                self.write(name, rows)
                with self.assertRaises(ContractError):
                    load_dataset(self.inputs)

    def test_conflicting_duplicate_combo_is_not_summed(self):
        rows = self.rows("de_para_combos.csv")
        rows[-1]["proporcao_no_combo"] = "2"
        self.write("de_para_combos.csv", rows)
        with self.assertRaises(ContractError):
            load_dataset(self.inputs)

    def test_overlapping_combos_are_ambiguous(self):
        rows = self.rows("de_para_combos.csv")
        rows[2]["sku_componente"] = "SKU-A1"
        self.write("de_para_combos.csv", rows)
        with self.assertRaisesRegex(ContractError, "mais de um combo"):
            load_dataset(self.inputs)

    def test_repeated_order_scope_sku_is_ambiguous(self):
        rows = self.rows("pedidos_oms.csv")
        rows.append({**rows[0], "poi_id": "POI-9999"})
        self.write("pedidos_oms.csv", rows)
        with self.assertRaisesRegex(ContractError, "SKU repetido"):
            load_dataset(self.inputs)

    def test_zerado_with_positive_quantity_is_invalid(self):
        rows = self.rows("saidas_otm.csv")
        rows[0]["status_otm"] = "ZERADO"
        self.write("saidas_otm.csv", rows)
        with self.assertRaises(ContractError):
            load_dataset(self.inputs)

    def test_orphan_otm_is_recorded_without_join_multiplication(self):
        rows = self.rows("saidas_otm.csv")
        rows.append({**rows[0], "poi_id": "POI-ORFAO"})
        self.write("saidas_otm.csv", rows)
        data = load_dataset(self.inputs)
        self.assertEqual(len(data.orders), 12)
        self.assertIn("OTM_ORFAO", {i.code for i in data.issues})

    def test_invalid_headers_and_cardinality(self):
        path = self.inputs / "saidas_otm.csv"
        for payload in ("poi_id,poi_id\na,b\n", "poi_id,sku\na,b\n",
                        "poi_id,sku,qtd_sugerida_otm,status_otm\na,b,1,SUCESSO,extra\n",
                        "poi_id,sku,qtd_sugerida_otm,status_otm\na,b\n"):
            with self.subTest(payload=payload):
                path.write_text(payload)
                with self.assertRaises(ContractError):
                    load_dataset(self.inputs)

    def test_bom_and_reordered_columns(self):
        name = "saidas_otm.csv"
        rows = self.rows(name)
        self.write(name, [dict(reversed(list(row.items()))) for row in rows])
        path = self.inputs / name
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        self.assertEqual(len(load_dataset(self.inputs).suggestions), 11)

    def test_formula_identifier_is_rejected(self):
        rows = self.rows("pedidos_oms.csv")
        rows[0]["poi_id"] = "=HYPERLINK(1)"
        self.write("pedidos_oms.csv", rows)
        with self.assertRaises(ContractError):
            load_dataset(self.inputs)

    def test_invalid_utf8_and_empty_orders(self):
        path = self.inputs / "pedidos_oms.csv"
        original = path.read_bytes()
        path.write_bytes(b"\xff")
        with self.assertRaises(ContractError):
            load_dataset(self.inputs)
        path.write_bytes(original.splitlines(keepends=True)[0])
        with self.assertRaisesRegex(ContractError, "vazia"):
            load_dataset(self.inputs)
