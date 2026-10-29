"""Leitura dos cinco CSVs, normalização rastreável e contratos de dados."""

import csv
import hashlib
import io
import re
from collections import defaultdict
from pathlib import Path

from .models import (
    MAX_RULE, STRICT_RULE, Combo, ContractError, Dataset, Issue,
    Order, Packaging, Suggestion,
)

SCHEMAS = {
    "pedidos_oms.csv": (
        "poi_id", "pedido_id", "cd_origem", "cod_franqueado", "sku", "qtd_pedida",
    ),
    "saidas_otm.csv": ("poi_id", "sku", "qtd_sugerida_otm", "status_otm"),
    "foto_estoque_cd_05h.csv": ("cd_origem", "sku", "estoque_disponivel_05h"),
    "de_para_combos.csv": (
        "id_combo_comercial", "descricao_combo", "sku_componente",
        "proporcao_no_combo", "regra_quebra",
    ),
    "regras_embalagem.csv": (
        "sku", "marca", "multiplo_caixa_master", "permite_fracionamento",
    ),
}
ID_FIELDS = {
    "poi_id", "pedido_id", "cd_origem", "cod_franqueado", "sku",
    "id_combo_comercial", "sku_componente",
}
NUMBER_FIELDS = {
    "qtd_pedida", "qtd_sugerida_otm", "estoque_disponivel_05h",
    "proporcao_no_combo", "multiplo_caixa_master",
}
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_QUANTITY = 10**12


def _table(path: Path, issues: list[Issue]) -> tuple[list[tuple[int, dict]], str]:
    """Usa os mesmos bytes para parsing e hash; evita inconsistência de releitura."""
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_FILE_BYTES + 1)
        if len(payload) > MAX_FILE_BYTES:
            raise ContractError(f"{path.name}: limite de 64 MiB por arquivo excedido")
        decoded = payload.decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"Não foi possível ler {path.name} como UTF-8: {exc}") from exc
    expected = SCHEMAS[path.name]
    rows: list[tuple[int, dict]] = []
    try:
        reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ContractError(f"{path.name}: cabeçalho ausente ou duplicado")
        if set(reader.fieldnames) != set(expected):
            raise ContractError(f"{path.name}: colunas esperadas: {', '.join(expected)}")
        for raw in reader:
            line = reader.line_num
            if None in raw or any(v is None for v in raw.values()):
                raise ContractError(f"{path.name}:{line}: quantidade de colunas inválida")
            row = {}
            for key, value in raw.items():
                clean = value.strip()
                if clean != value:
                    issues.append(Issue(
                        "INFO", "ESPACO_NORMALIZADO", path.name, line,
                        raw.get("poi_id", raw.get("sku", "")).strip(),
                        f"Espaços externos removidos do campo {key}",
                    ))
                if not clean or len(clean) > 1024 or any(ord(c) < 32 for c in clean):
                    raise ContractError(f"{path.name}:{line}: campo {key} vazio ou inválido")
                if key in ID_FIELDS and not ID_PATTERN.fullmatch(clean):
                    raise ContractError(f"{path.name}:{line}: identificador inválido em {key}")
                if key in NUMBER_FIELDS:
                    if len(clean) > 13 or not re.fullmatch(r"[0-9]+", clean):
                        raise ContractError(f"{path.name}:{line}: {key} deve ser inteiro não negativo")
                    number = int(clean)
                    if number > MAX_QUANTITY:
                        raise ContractError(f"{path.name}:{line}: {key} excede 10^12")
                    if key in {"proporcao_no_combo", "multiplo_caixa_master"} and number == 0:
                        raise ContractError(f"{path.name}:{line}: {key} deve ser positivo")
                    row[key] = number
                else:
                    row[key] = clean
            rows.append((line, row))
    except (csv.Error, OverflowError) as exc:
        raise ContractError(f"{path.name}: CSV inválido: {exc}") from exc
    return rows, hashlib.sha256(payload).hexdigest()


def _insert_unique(target: dict, key: object, value: object, source: str, line: int) -> None:
    if key in target:
        raise ContractError(f"{source}:{line}: chave duplicada {key!r}; não será somada")
    target[key] = value


def load_dataset(directory: Path) -> Dataset:
    issues: list[Issue] = []
    tables, hashes = {}, {}
    for name in SCHEMAS:
        tables[name], hashes[name] = _table(directory / name, issues)
    orders, suggestions, stock, packaging = {}, {}, {}, {}
    scope_skus = set()
    for line, row in tables["pedidos_oms.csv"]:
        order = Order(**row)
        _insert_unique(orders, order.poi_id, order, "pedidos_oms.csv", line)
        key = (*order.scope, order.sku)
        if key in scope_skus:
            raise ContractError(
                f"pedidos_oms.csv:{line}: SKU repetido no mesmo pedido/CD/franqueado; "
                "é necessário identificar instâncias de combo"
            )
        scope_skus.add(key)
    if not orders:
        raise ContractError("pedidos_oms.csv: carteira vazia")
    for line, row in tables["saidas_otm.csv"]:
        value = Suggestion(row["poi_id"], row["sku"], row["qtd_sugerida_otm"], row["status_otm"])
        if value.status == "ZERADO" and value.quantity != 0:
            raise ContractError(f"saidas_otm.csv:{line}: status ZERADO com quantidade positiva")
        _insert_unique(suggestions, value.poi_id, value, "saidas_otm.csv", line)
        if value.poi_id not in orders:
            issues.append(Issue("WARNING", "OTM_ORFAO", "saidas_otm.csv", line,
                                value.poi_id, "POI sem demanda; sugestão ignorada"))
    for line, row in tables["foto_estoque_cd_05h.csv"]:
        _insert_unique(stock, (row["cd_origem"], row["sku"]), row["estoque_disponivel_05h"],
                       "foto_estoque_cd_05h.csv", line)
    for line, row in tables["regras_embalagem.csv"]:
        flag = row["permite_fracionamento"]
        if flag not in {"SIM", "NÃO", "NAO"}:
            raise ContractError(f"regras_embalagem.csv:{line}: flag de fracionamento desconhecida")
        value = Packaging(row["sku"], row["marca"], row["multiplo_caixa_master"], flag == "SIM")
        _insert_unique(packaging, value.sku, value, "regras_embalagem.csv", line)
    grouped: dict[str, list[dict]] = defaultdict(list)
    seen = {}
    for line, row in tables["de_para_combos.csv"]:
        key = row["id_combo_comercial"], row["sku_componente"]
        if key in seen:
            if row != seen[key]:
                raise ContractError(f"de_para_combos.csv:{line}: componente duplicado conflitante: {key}")
            issues.append(Issue("WARNING", "COMBO_DUPLICADO_REMOVIDO", "de_para_combos.csv", line,
                                "/".join(key), "Duplicata idêntica removida; proporção não somada"))
            continue
        seen[key] = row
        grouped[key[0]].append(row)
    combos, membership = {}, {}
    for combo_id, components in grouped.items():
        rules = {row["regra_quebra"] for row in components}
        descriptions = {row["descricao_combo"] for row in components}
        if len(rules) != 1 or len(descriptions) != 1 or not rules <= {STRICT_RULE, MAX_RULE}:
            raise ContractError(f"de_para_combos.csv: regra/descrição inconsistente ou desconhecida em {combo_id}")
        if len(components) < 2:
            raise ContractError(f"de_para_combos.csv: {combo_id} deve ter ao menos dois componentes")
        combo = Combo(combo_id, components[0]["descricao_combo"], components[0]["regra_quebra"],
                      {r["sku_componente"]: r["proporcao_no_combo"] for r in components})
        combos[combo_id] = combo
        for sku in combo.components:
            if sku in membership:
                raise ContractError(f"SKU {sku} em mais de um combo: vínculo comercial ambíguo")
            membership[sku] = combo_id
    return Dataset(orders, suggestions, stock, packaging, combos, membership, hashes, issues)
