"""Alocação inteira e conservadora com reserva conjunta de componentes."""

from collections import Counter, defaultdict
from math import gcd, lcm

from .models import (
    STRICT_RULE, Dataset, Decision, InvariantError, Order, Policy, Result,
)


def blocking_reasons(data: Dataset, order: Order) -> list[str]:
    """Ausência de dado nunca significa autorização para faturar."""
    reasons = []
    suggestion = data.suggestions.get(order.poi_id)
    if suggestion is None:
        reasons.append("OTM_AUSENTE")
    elif suggestion.sku != order.sku:
        reasons.append("SKU_DIVERGENTE")
    elif suggestion.status not in {"SUCESSO", "ZERADO"}:
        reasons.append("STATUS_OTM_NAO_APROVADO")
    if order.sku not in data.packaging:
        reasons.append("EMBALAGEM_AUSENTE")
    if (order.cd_origem, order.sku) not in data.stock:
        reasons.append("ESTOQUE_AUSENTE")
    return reasons


def _groups(data: Dataset) -> list[tuple[str, list[Order]]]:
    groups: dict[tuple, list[Order]] = defaultdict(list)
    for order in data.orders.values():
        combo = data.membership.get(order.sku, "")
        group_id = f"combo:{combo}" if combo else f"poi:{order.poi_id}"
        groups[(*order.scope, group_id)].append(order)
    # Ordem lexical é um desempate reproduzível, não prioridade comercial.
    return [(key[-1], sorted(items, key=lambda x: x.poi_id))
            for key, items in sorted(groups.items())]


def _decision(data: Dataset, order: Order, final: int, reasons: list[str], review: bool) -> Decision:
    suggestion = data.suggestions.get(order.poi_id)
    original = suggestion.quantity if suggestion else None
    if review:
        status = "REVISAO"
    elif original == final:
        status = "MANTIDO"
    elif final == 0:
        status = "ZERADO"
    else:
        status = "AJUSTADO"
    return Decision(
        order.poi_id, order.pedido_id, order.cd_origem, order.cod_franqueado, order.sku,
        order.qtd_pedida, original, final, status, data.membership.get(order.sku, ""),
        tuple(sorted(set(reasons))) or ("SEM_AJUSTE",),
    )


def reconcile(data: Dataset, policy: Policy | None = None) -> Result:
    policy = policy or Policy()
    available = dict(data.stock)
    decisions = []
    for _, orders in _groups(data):
        combo_id = data.membership.get(orders[0].sku)
        combo = data.combos[combo_id] if combo_id else None
        reasons = {o.poi_id: blocking_reasons(data, o) for o in orders}
        missing_component = bool(combo and set(combo.components) != {o.sku for o in orders})
        any_blocked = any(reasons.values()) or missing_component
        if any_blocked:
            for order in orders:
                if missing_component:
                    reasons[order.poi_id].append("COMPONENTE_COMBO_AUSENTE")
                if combo and not reasons[order.poi_id]:
                    reasons[order.poi_id].append("COMBO_COMPONENTE_EM_REVISAO")
                decisions.append(_decision(data, order, 0, reasons[order.poi_id], True))
            continue
        caps = {}
        for order in orders:
            suggestion = data.suggestions[order.poi_id]
            caps[order.sku] = min(order.qtd_pedida, suggestion.quantity)
            if suggestion.quantity > order.qtd_pedida:
                reasons[order.poi_id].append("LIMITE_DEMANDA")
            if order.qtd_pedida == 0:
                reasons[order.poi_id].append("DEMANDA_ZERO")
            if suggestion.quantity == 0:
                reasons[order.poi_id].append("OTM_ZERO")
        if combo:
            # p_i * n deve ser múltiplo de m_i. Logo n é múltiplo de
            # m_i / gcd(m_i, p_i); combinar todas as exigências por MMC.
            step = lcm(*(data.packaging[sku].step // gcd(data.packaging[sku].step, p)
                         for sku, p in combo.components.items()))
            max_cap_kits = min(caps[sku] // p for sku, p in combo.components.items())
            max_stock_kits = min(available[(orders[0].cd_origem, sku)] // p
                                 for sku, p in combo.components.items())
            kits = min(max_cap_kits, max_stock_kits) // step * step
            strict = combo.rule == STRICT_RULE and policy.incomplete_policy == "strict"
            if strict:
                # Lote proposto é indivisível nesta interpretação conservadora.
                proportional = all(caps[sku] == max_cap_kits * p
                                   for sku, p in combo.components.items())
                if not proportional or kits != max_cap_kits:
                    kits = 0
                    for reason in reasons.values():
                        reason.append("COMBO_LOTE_INCOMPLETO_ZERADO")
            elif combo.rule == STRICT_RULE:
                for reason in reasons.values():
                    reason.append("POLITICA_PRESERVAR_KITS_COMPLETOS")
            for order in orders:
                final = kits * combo.components[order.sku]
                if final < caps[order.sku] and not strict:
                    reasons[order.poi_id].append("AJUSTE_COMBO_COMPLETO")
                if max_stock_kits < max_cap_kits:
                    reasons[order.poi_id].append("LIMITE_ESTOQUE_COMPARTILHADO")
                if min(max_cap_kits, max_stock_kits) % step:
                    reasons[order.poi_id].append("COMPATIBILIDADE_COMBO_CAIXA")
                # Só há débito depois de determinar uma quantidade conjunta viável.
                available[(order.cd_origem, order.sku)] -= final
                decisions.append(_decision(data, order, final, reasons[order.poi_id], False))
        else:
            order = orders[0]
            key = order.cd_origem, order.sku
            limited = min(caps[order.sku], available[key])
            step = data.packaging[order.sku].step
            final = limited // step * step
            if limited < caps[order.sku]:
                reasons[order.poi_id].append("LIMITE_ESTOQUE_COMPARTILHADO")
            if final < limited:
                reasons[order.poi_id].append("ARREDONDAMENTO_CAIXA_PARA_BAIXO")
            available[key] -= final
            decisions.append(_decision(data, order, final, reasons[order.poi_id], False))
    decisions.sort(key=lambda r: r.poi_id)
    checks = verify_result(data, decisions, policy, available)
    original = sum(s.quantity for pid, s in data.suggestions.items() if pid in data.orders)
    demand = sum(o.qtd_pedida for o in data.orders.values())
    final = sum(r.qtd_final for r in decisions)
    statuses = Counter(r.status for r in decisions)
    metrics = {
        "linhas_oms": len(decisions), "linhas_otm_associadas": sum(
            pid in data.suggestions for pid in data.orders),
        "linhas_mantidas": statuses["MANTIDO"], "linhas_ajustadas": statuses["AJUSTADO"],
        "linhas_zeradas": statuses["ZERADO"], "linhas_revisao": statuses["REVISAO"],
        "unidades_demandadas": demand, "unidades_otm": original, "unidades_finais": final,
        "unidades_reduzidas_vs_otm": original - final,
        "retencao_vs_otm_pct": round(100 * final / original, 2) if original else None,
        "atendimento_demanda_pct": round(100 * final / demand, 2) if demand else None,
    }
    return Result(decisions, available, policy, checks, metrics)


def verify_result(data: Dataset, decisions: list[Decision], policy: Policy,
                  remaining_stock: dict[tuple[str, str], int]) -> dict[str, bool]:
    """Pós-condições recalculadas sem confiar no ledger produzido pelo alocador."""
    checks = {name: True for name in (
        "conservacao_pois", "identidade_linhas", "inteiros_nao_negativos", "limite_demanda_otm",
        "cadastros_obrigatorios", "multiplos_caixa", "estoque_agregado_cd_sku",
        "combos_proporcionais", "politica_combo_estrita", "ledger_reconciliado",
    )}
    index = {r.poi_id: r for r in decisions}
    checks["conservacao_pois"] = len(index) == len(decisions) and set(index) == set(data.orders)
    if not checks["conservacao_pois"]:
        raise InvariantError("POIs perdidos, repetidos ou adicionados")
    used: Counter = Counter()
    for poi_id, order in data.orders.items():
        row = index[poi_id]
        q = row.qtd_final
        checks["inteiros_nao_negativos"] &= type(q) is int and q >= 0
        suggestion = data.suggestions.get(poi_id)
        checks["identidade_linhas"] &= (
            (row.pedido_id, row.cd_origem, row.cod_franqueado, row.sku, row.qtd_pedida,
             row.qtd_sugerida_otm, row.combo_id) ==
            (order.pedido_id, order.cd_origem, order.cod_franqueado, order.sku, order.qtd_pedida,
             suggestion.quantity if suggestion else None, data.membership.get(order.sku, ""))
        )
        checks["limite_demanda_otm"] &= q <= order.qtd_pedida and q <= (suggestion.quantity if suggestion else 0)
        checks["cadastros_obrigatorios"] &= not blocking_reasons(data, order) or q == 0
        pack = data.packaging.get(order.sku)
        checks["multiplos_caixa"] &= q == 0 or (pack is not None and q % pack.step == 0)
        used[(order.cd_origem, order.sku)] += q
    for key in set(data.stock) | set(used):
        checks["estoque_agregado_cd_sku"] &= used[key] <= data.stock.get(key, 0)
        checks["ledger_reconciliado"] &= (
            remaining_stock.get(key, 0) == data.stock.get(key, 0) - used[key]
        )
    for _, orders in _groups(data):
        combo_id = data.membership.get(orders[0].sku)
        if not combo_id:
            continue
        combo = data.combos[combo_id]
        by_sku = {o.sku: o for o in orders}
        qs = {sku: index[by_sku[sku].poi_id].qtd_final if sku in by_sku else 0
              for sku in combo.components}
        first = next(iter(combo.components))
        p_first = combo.components[first]
        checks["combos_proporcionais"] &= all(
            qs[sku] % p == 0 and qs[sku] * p_first == qs[first] * p
            for sku, p in combo.components.items()
        )
        if combo.rule == STRICT_RULE and policy.incomplete_policy == "strict" and any(qs.values()):
            checks["politica_combo_estrita"] &= all(
                sku in by_sku and by_sku[sku].poi_id in data.suggestions
                and qs[sku] == min(by_sku[sku].qtd_pedida, data.suggestions[by_sku[sku].poi_id].quantity)
                for sku in combo.components
            )
    failed = [key for key, passed in checks.items() if not passed]
    if failed:
        raise InvariantError("Pós-condições violadas: " + ", ".join(failed))
    return checks
