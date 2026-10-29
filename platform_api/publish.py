"""Exportação streaming e explicações determinísticas, sem alterar o motor."""

import hashlib
from collections.abc import Iterator
from dataclasses import asdict, replace
from pathlib import Path

from otm_guard import __version__
from otm_guard.models import Dataset, Result
from otm_guard.report import REASONS, _csv, _html, canonical_json, source_hashes, write_bundle

from .storage import digest


def enriched_rows(data: Dataset, result: Result, include_references: bool = True) -> Iterator[dict]:
    for decision in result.decisions:
        row = asdict(decision)
        order = data.orders[decision.poi_id]
        pack = data.packaging.get(order.sku)
        stock = data.stock.get((order.cd_origem, order.sku))
        combo = data.combos.get(decision.combo_id)
        explanation = " ".join(REASONS.get(code, code) for code in decision.reasons)
        if pack and not pack.fractionation and not combo and decision.qtd_sugerida_otm is not None:
            explanation += (
                f" O OTM sugeriu {decision.qtd_sugerida_otm} peças. A caixa exige {pack.multiple}. "
                f"A proposta contém {decision.qtd_final} peças, equivalentes a {decision.qtd_final // pack.multiple} caixas."
            )
        if combo:
            ratio = combo.components[order.sku]
            explanation += f" Cada kit contém {ratio} peça(s) deste SKU; a proposta representa {decision.qtd_final // ratio} kits completos."
        row.update(
            explanation=explanation,
            next_action=(
                "Conferir dados ausentes ou divergentes na origem e gerar novo lote."
                if decision.status == "REVISAO"
                else "Conferir a proposta e homologar a política antes de integrar ao faturamento."
            ),
            constraints={
                "demand_cap": order.qtd_pedida,
                "otm_cap": decision.qtd_sugerida_otm,
                "initial_stock": stock,
                "packaging_multiple": pack.multiple if pack else None,
                "fractionation_allowed": pack.fractionation if pack else None,
                "combo_components": combo.components if combo else {},
                "combo_rule": combo.rule if combo else None,
                "policy": result.policy.incomplete_policy,
                "stock_snapshot_timestamp": None,
            },
            input_references=[
                {
                    "file": name,
                    "sha256": checksum,
                    "key": order.poi_id
                    if name in {"pedidos_oms.csv", "saidas_otm.csv"}
                    else f"{order.cd_origem}/{order.sku}"
                    if name.startswith("foto_")
                    else order.sku,
                }
                for name, checksum in sorted(data.input_hashes.items())
            ],
        )
        if not include_references:
            row.pop("input_references")
        yield row


def stock_rows(data: Dataset, result: Result) -> Iterator[dict]:
    for (cd, sku), initial in sorted(data.stock.items()):
        remaining = result.remaining_stock[(cd, sku)]
        yield {
            "cd_origem": cd,
            "sku": sku,
            "estoque_05h": initial,
            "reservado_proposta": initial - remaining,
            "saldo_simulado": remaining,
        }


def publish(data: Dataset, result: Result, output: Path) -> str:
    if len(result.decisions) <= 500:
        return write_bundle(data, result, output)
    output.mkdir()
    identity = {
        "application_version": __version__,
        "policy": asdict(result.policy),
        "inputs_sha256": dict(sorted(data.input_hashes.items())),
        "source_sha256": source_hashes(),
    }
    engine_id = hashlib.sha256(canonical_json(identity).encode()).hexdigest()
    fields = [*asdict(result.decisions[0]), "explicacao"]

    def export_rows(review_only=False):
        for decision in result.decisions:
            if review_only and decision.status != "REVISAO":
                continue
            row = asdict(decision)
            row["reasons"] = ";".join(decision.reasons)
            row["explicacao"] = " ".join(REASONS.get(code, code) for code in decision.reasons)
            yield row

    _csv(output / "proposta_conciliada.csv", export_rows(), fields)
    _csv(output / "fila_revisao.csv", export_rows(True), fields)
    _csv(
        output / "balanco_estoque.csv",
        stock_rows(data, result),
        ["cd_origem", "sku", "estoque_05h", "reservado_proposta", "saldo_simulado"],
    )
    summary = {
        "run_id": engine_id,
        "policy": asdict(result.policy),
        "metrics": result.metrics,
        "checks": result.checks,
        "requires_review": bool(result.metrics["linhas_revisao"]),
        "stock_snapshot_timestamp": None,
        "report_scope": {"total_rows": len(result.decisions), "displayed_rows": 200},
    }
    (output / "resumo.json").write_text(canonical_json(summary), encoding="utf-8")
    (output / "qualidade_dados.json").write_text(
        canonical_json([asdict(i) for i in data.issues]), encoding="utf-8"
    )
    report = _html(data, replace(result, decisions=result.decisions[:200]), engine_id)
    notice = (
        f'<p role="note">Relatório resumido: 200 de {len(result.decisions)} POIs. '
        "O CSV contém todos os itens. Use a aplicação para consulta paginada.</p>"
    )
    report = report.replace("<section><h2>Decisões", notice + "<section><h2>Decisões", 1)
    (output / "relatorio.html").write_text(report, encoding="utf-8")
    manifest = {
        **identity,
        "run_id": engine_id,
        "artifacts_sha256": {p.name: digest(p) for p in sorted(output.iterdir())},
        "hash_scope": "manifest.json exclui a si próprio para evitar autorreferência",
    }
    (output / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
    return engine_id
