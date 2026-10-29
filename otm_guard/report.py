"""Artefatos auditáveis, relatório HTML offline e publicação local atômica."""

import csv
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .models import ContractError, Dataset, Result

REASONS = {
    "SEM_AJUSTE": "Sugestão já atende às restrições.",
    "OTM_AUSENTE": "POI sem retorno do OTM; confirmar processamento.",
    "SKU_DIVERGENTE": "SKU do retorno difere do OMS; conciliar a integração.",
    "STATUS_OTM_NAO_APROVADO": "Retorno diferente de SUCESSO/ZERADO; confirmar situação.",
    "EMBALAGEM_AUSENTE": "Não existe regra de embalagem; completar cadastro.",
    "ESTOQUE_AUSENTE": "Não existe saldo para CD/SKU; confirmar fotografia.",
    "COMPONENTE_COMBO_AUSENTE": "Falta componente no pedido/CD/franqueado.",
    "COMBO_COMPONENTE_EM_REVISAO": "Outro componente do mesmo combo exige revisão.",
    "LIMITE_DEMANDA": "OTM excedia demanda; quantidade limitada ao pedido.",
    "DEMANDA_ZERO": "Quantidade pedida igual a zero.",
    "OTM_ZERO": "OTM já sugeriu zero.",
    "COMBO_LOTE_INCOMPLETO_ZERADO": "Política estrita: lote proporcional inviável foi zerado.",
    "POLITICA_PRESERVAR_KITS_COMPLETOS": "Cenário alternativo autorizado pela opção complete-kits.",
    "AJUSTE_COMBO_COMPLETO": "Redução ao maior número de kits completos compatível.",
    "LIMITE_ESTOQUE_COMPARTILHADO": "Estoque remanescente do CD/SKU limitou o grupo.",
    "COMPATIBILIDADE_COMBO_CAIXA": "Número de kits ajustado ao MMC das caixas e proporções.",
    "ARREDONDAMENTO_CAIXA_PARA_BAIXO": "Quantidade reduzida ao múltiplo inferior da caixa.",
}


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def source_hashes() -> dict[str, str]:
    package = Path(__file__).parent
    paths = [package.parent / "app.py", *sorted(package.glob("*.py"))]
    return {p.relative_to(package.parent).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths}


def _safe_cell(value: object) -> object:
    # Aspas de CSV não neutralizam fórmulas em planilhas. IDs são validados à entrada.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({k: _safe_cell(row.get(k, "")) for k in fields} for row in rows)


def _html(data: Dataset, result: Result, run_id: str) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    m = result.metrics
    rows = []
    for r in result.decisions:
        reasons = " ".join(REASONS.get(code, code) for code in r.reasons)
        original = "ausente" if r.qtd_sugerida_otm is None else r.qtd_sugerida_otm
        rows.append(
            f'<tr data-status="{esc(r.status)}"><td>{esc(r.poi_id)}</td>'
            f'<td>{esc(r.pedido_id)}<small>{esc(r.cd_origem)} · {esc(r.cod_franqueado)}</small></td>'
            f'<td>{esc(r.sku)}<small>{esc(r.combo_id or "Avulso")}</small></td>'
            f'<td class="num">{r.qtd_pedida}</td><td class="num">{original}</td>'
            f'<td class="num final">{r.qtd_final}</td>'
            f'<td><span class="badge {esc(r.status)}">{esc(r.status)}</span></td>'
            f'<td class="reason">{esc(reasons)}</td></tr>'
        )
    issues = "".join(
        f'<li><strong>{esc(i.code)}</strong>: {esc(i.detail)} '
        f'<small>{esc(i.source)}:{i.line} · {esc(i.key)}</small></li>' for i in data.issues
    ) or "<li>Nenhuma ocorrência de normalização ou deduplicação.</li>"
    checks = "".join(f'<li>OK · {esc(key)}</li>' for key in result.checks)
    policy_label = "Estrita: zerar lote incompleto" if result.policy.incomplete_policy == "strict" else "Alternativa: preservar kits completos"
    template = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conciliação pós-OTM | Evidência do lote</title><style>
:root{font-family:system-ui,-apple-system,sans-serif;color:#173c35;background:#f1f5f2;line-height:1.5}
*{box-sizing:border-box}body{margin:0}main{max-width:1450px;margin:auto;padding:38px 28px}
header{padding:30px;background:#123e33;color:#fff;border-radius:18px}h1{font-size:30px;margin:6px 0 10px}
h2{font-size:21px;margin:0 0 14px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#ace5c6}
header p{max-width:850px;margin:10px 0;color:#dcebe4}.run{font-family:monospace;font-size:12px;overflow-wrap:anywhere}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}.card,section{background:#fff;border:1px solid #d9e6dc;border-radius:14px;padding:23px}
.card b{display:block;font-size:33px;line-height:1.2}.card span{display:block;font-size:14px;margin-top:10px;color:#4a635a}
.notice{background:#fff7db;border-left:5px solid #bd8700;border-radius:10px;padding:17px 21px;margin:20px 0;color:#654710}
section{margin:22px 0}.toolbar{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}
input,select{font:inherit;padding:10px;border:1px solid #a9bdb1;border-radius:7px;max-width:100%}input{min-width:240px}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;min-width:1050px;text-align:left}
th{background:#ecf4ee;font-size:11px;text-transform:uppercase;letter-spacing:.5px;padding:13px 10px}
td{padding:14px 10px;border-bottom:1px solid #e5ece7;vertical-align:top}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.final{font-weight:750;font-size:16px}.reason{min-width:230px;max-width:420px}small{display:block;color:#5d7166;font-size:11px;margin-top:4px}
.badge{display:inline-block;padding:4px 8px;border-radius:5px;font-size:10px;font-weight:800;background:#e6efea}
.REVISAO{background:#fff0c3;color:#7b5100}.ZERADO{background:#fbe2dd;color:#94392c}.AJUSTADO{background:#ddecff;color:#214b83}
.MANTIDO{background:#dff2e4;color:#246541}.columns{display:grid;grid-template-columns:1fr 1fr;gap:22px}
ul{padding-left:20px}li{margin:10px 0}footer{font-size:12px;color:#546b5e;padding:10px 0 30px}a{color:#156044}
[hidden]{display:none!important}@media(max-width:850px){main{padding:18px 12px}.grid{grid-template-columns:1fr 1fr}.columns{grid-template-columns:1fr}header{padding:22px}h1{font-size:25px}}
@media print{.toolbar{display:none}main{padding:0}.table-wrap{overflow:visible}table{min-width:0;font-size:9px}.reason{min-width:100px}section,header{break-inside:avoid}}
</style></head><body><main>
<header><span class="eyebrow">Operações &amp; logística · Case técnico</span>
<h1>Conciliação pós-OTM</h1><p>Quantidades fisicamente viáveis, decisões explicadas por POI e estoque reconciliado por CD/SKU.</p>
<p>Política: <strong>POLICY</strong></p><p class="run">Identificador do lote: RUNID</p></header>
<div class="grid"><div class="card"><b>OTM</b><span>peças sugeridas pelo OTM</span></div>
<div class="card"><b>FINAL</b><span>peças na proposta conciliada</span></div>
<div class="card"><b>REVIEW</b><span>POIs bloqueados para revisão</span></div>
<div class="card"><b>CHECKS/CHECKS</b><span>invariantes verificadas</span></div></div>
<aside class="notice"><strong>Proposta para conferência operacional.</strong> Não constitui reserva de estoque ou autorização de faturamento.
O saldo é limitado à fotografia das 05h, sem data fornecida. Confirmar a política de combo e a atualidade da foto antes de integrar ao OMS.</aside>
<section><h2>Decisões por item de pedido</h2><div class="toolbar">
<label>Buscar <input id="search" type="search" placeholder="POI, SKU, pedido ou motivo"></label>
<label>Status <select id="status"><option value="">Todos</option><option>MANTIDO</option><option>AJUSTADO</option><option>ZERADO</option><option>REVISAO</option></select></label></div>
<p id="count" aria-live="polite"></p><div class="table-wrap"><table><thead><tr><th>POI</th><th>Pedido / origem</th><th>SKU / combo</th>
<th class="num">Pedido</th><th class="num">OTM</th><th class="num">Final</th><th>Status</th><th>Explicação</th></tr></thead><tbody>ROWS</tbody></table></div></section>
<div class="columns"><section><h2>Qualidade dos dados</h2><ul>ISSUES</ul></section>
<section><h2>Verificações de saída</h2><ul>CHECKLIST</ul></section></div>
<section><h2>Como interpretar o resultado</h2><p>Redução de peças mede adequação às restrições; não comprova ganho financeiro, redução de trabalho manual ou otimização global.
Itens em revisão permanecem com zero peças. A prioridade entre pedidos é lexical e reproduzível; não representa uma regra comercial validada.</p>
<p>O arquivo <a href="proposta_conciliada.csv">proposta_conciliada.csv</a> preserva todos os POIs.
Consulte também <a href="resumo.json">resumo.json</a>, <a href="qualidade_dados.json">qualidade_dados.json</a> e <a href="manifest.json">manifest.json</a>.</p></section>
<footer>Motor determinístico · Python padrão · Sem chamadas a modelos ou serviços externos · Versão VERSION</footer>
</main><script>
const search=document.getElementById('search'),status=document.getElementById('status');
const rows=[...document.querySelectorAll('tbody tr')];
function filter(){let shown=0;const query=search.value.toLocaleLowerCase('pt-BR');for(const row of rows){
row.hidden=!(row.textContent.toLocaleLowerCase('pt-BR').includes(query)&&(!status.value||row.dataset.status===status.value));if(!row.hidden)shown++;}
document.getElementById('count').textContent=shown+' de '+rows.length+' itens';}
search.addEventListener('input',filter);status.addEventListener('change',filter);filter();
</script></body></html>"""
    replacements = {
        "POLICY": esc(policy_label), "RUNID": esc(run_id),
        "OTM</b>": f'{m["unidades_otm"]}</b>', "FINAL</b>": f'{m["unidades_finais"]}</b>',
        "REVIEW</b>": f'{m["linhas_revisao"]}</b>', "CHECKS": str(len(result.checks)),
        "ROWS": "".join(rows), "ISSUES": issues, "CHECKLIST": checks, "VERSION": __version__,
    }
    # Substituição de uma só passagem: conteúdo inserido não vira novo placeholder.
    return re.sub("|".join(re.escape(k) for k in replacements),
                  lambda match: replacements[match.group()], template)


def write_bundle(data: Dataset, result: Result, output: Path) -> str:
    """Prepara tudo num diretório temporário e publica só o lote completo.

    Lock exclusivo impede concorrência entre duas execuções desta aplicação para
    o mesmo destino. Diretórios existentes nunca são sobrescritos.
    """
    output = output.absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output.parent / f".{output.name}.lock"
    lock_fd = None
    staging = None
    try:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ContractError("Destino em uso ou lock residual; escolha outro --output-dir") from exc
        if output.exists() or output.is_symlink():
            raise ContractError(f"Destino já existe: {output}; escolha outro --output-dir")
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
        identity = {
            "application_version": __version__, "policy": asdict(result.policy),
            "inputs_sha256": dict(sorted(data.input_hashes.items())), "source_sha256": source_hashes(),
        }
        run_id = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
        rows = []
        for row in result.decisions:
            record = asdict(row)
            record["reasons"] = ";".join(row.reasons)
            record["explicacao"] = " ".join(REASONS.get(code, code) for code in row.reasons)
            rows.append(record)
        _csv(staging / "proposta_conciliada.csv", rows, list(rows[0]))
        review = [r for r in rows if r["status"] == "REVISAO"]
        _csv(staging / "fila_revisao.csv", review, list(rows[0]))
        stock_rows = [
            {"cd_origem": cd, "sku": sku, "estoque_05h": quantity,
             "reservado_proposta": quantity - result.remaining_stock[(cd, sku)],
             "saldo_simulado": result.remaining_stock[(cd, sku)]}
            for (cd, sku), quantity in sorted(data.stock.items())
        ]
        _csv(staging / "balanco_estoque.csv", stock_rows,
             ["cd_origem", "sku", "estoque_05h", "reservado_proposta", "saldo_simulado"])
        summary = {
            "run_id": run_id, "policy": asdict(result.policy), "metrics": result.metrics,
            "checks": result.checks, "requires_review": bool(review),
            "stock_snapshot_timestamp": None,
            "limitations": ["Fotografia sem data; não é estoque em tempo real",
                            "Proposta sem reserva transacional e sem envio ao OMS",
                            "Desempate lexical; não maximiza objetivo global"],
        }
        (staging / "resumo.json").write_text(canonical_json(summary), encoding="utf-8")
        (staging / "qualidade_dados.json").write_text(
            canonical_json([asdict(i) for i in data.issues]), encoding="utf-8")
        (staging / "relatorio.html").write_text(_html(data, result, run_id), encoding="utf-8")
        artifacts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(staging.iterdir())}
        manifest = {**identity, "run_id": run_id, "artifacts_sha256": artifacts,
                    "hash_scope": "manifest.json exclui a si próprio para evitar autorreferência"}
        (staging / "manifest.json").write_text(canonical_json(manifest), encoding="utf-8")
        os.rename(staging, output)
        staging = None
        return run_id
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        if lock_fd is not None:
            os.close(lock_fd)
            lock_path.unlink(missing_ok=True)
