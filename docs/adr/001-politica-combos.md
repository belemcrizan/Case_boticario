# ADR-001 | Semântica de quebra e limite de atuação

Status: implementada como premissa do demonstrador; depende de homologação comercial para produção.

## Contexto

O arquivo comercial contém “Zerar se incompleto” e “Ajustar para maior combo completo”. Para a primeira regra, o enunciado não distingue incompletude do lote proposto de incompletude de um kit individual. Também não informa como priorizar pedidos, recompor sugestões ou identificar instâncias de combo no OMS.

## Decisão

1. O padrão `strict` interpreta “Zerar se incompleto” como lote indivisível: depois do teto por demanda, todas as quantidades propostas precisam formar um mesmo número inteiro de kits, respeitar caixas e caber integralmente no saldo remanescente. Caso contrário, zera o grupo inteiro.
2. A opção `complete-kits` permite reduzir também esses lotes ao maior número de kits completos viável. A mudança é registrada nos motivos, na política e no `run_id`.
3. Para “Ajustar para maior combo completo”, ambos os modos usam o maior número de kits viável naquele ponto da alocação.
4. Não aumentar nenhum POI acima da sugestão do OTM ou da demanda. Não redistribuir sobras para compensar a redução de outro POI.
5. Agrupar por pedido, CD, franqueado e combo. Um mesmo SKU em múltiplos combos ou repetido no escopo do pedido é ambíguo e bloqueia o lote na ingestão.

## Exemplo e consequência

Dia das Mães 1:1, OTM 50:35: `strict` gera 0:0 e `complete-kits` gera 35:35. Barba 1:2, OTM 5:7: a regra explícita de ajuste gera 3:6 em ambos os modos.

A política estrita pode reduzir desnecessariamente o atendimento se a intenção comercial for preservar kits completos. É uma escolha conservadora e reversível de configuração, não uma garantia de maximização comercial.

## Alternativas descartadas nesta entrega

- Arredondar componentes isoladamente: pode quebrar proporções.
- Completar sempre por cima: pode exceder pedido, OTM e estoque.
- Inferir uma política silenciosamente: oculta uma decisão material do negócio.
- Redistribuir estoque liberado: altera o rateio e exige prioridade/objetivo ainda não fornecidos.
- Usar LLM para decidir quantidades: acrescenta incerteza a restrições exatas.

## Próxima decisão necessária

Homologar a semântica de quebra com Comercial/Logística e substituir a inferência de pertencimento por `id_instancia_combo` no pedido. Versionar política, carteira, retorno OTM e fotografia de estoque como um único lote fechado.
