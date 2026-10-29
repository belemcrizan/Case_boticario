# Políticas e ambiguidades comerciais

| Condição | strict, padrão | complete-kits | Classificação / aceite |
| --- | --- | --- | --- |
| Combo íntegro e dentro dos limites | Preserva quantidade viável | Idem | Restrições confirmadas |
| “Zerar se incompleto”, 1:1, limites 50:35 | 0:0 | 35:35 | Interpretações; homologação comercial pendente |
| “Maior combo completo”, 1:2, limites 5:7 | 3:6 | 3:6 | Regra explícita do case |
| Caixa 6, sem fracionamento, limite 110 | 108 | 108 | Arredondamento para baixo |
| Falta OTM, embalagem ou estoque | Zero e revisão | Idem | Ausência não autoriza faturamento |
| Componente ausente ou vínculo ambíguo | Bloqueio conservador | Idem | Corrigir origem |
| Pedidos disputam saldo | Desempate lexical estável | Idem | Premissa sem prioridade homologada |

Strict continua padrão. A alternativa é explícita e registrada em manifesto, resumo e identidade. Simular não substitui a origem.

## Formulação preservada

Quantidade final inteira, não negativa, limitada por demanda e OTM; consumo agregado por CD/SKU não supera saldo. Para razão r e caixa c sem fracionamento, o número de kits deve ser múltiplo de c/MDC(c,r). O passo comum é o MMC desses fatores nos componentes. Arredondar o maior número viável para baixo. Prova e pós-condições em [ARQUITETURA.md](ARQUITETURA.md); motor original preservado.

## Contrato futuro de instância

Os cinco CSVs não distinguem dois kits iguais, SKU avulso e de kit no mesmo pedido ou SKU compartilhado por kits. Não inferir esses vínculos.

Um contrato futuro deve incluir combo_instance_id, combo_id, combo_version, component_id, quantity_per_kit e vínculo de cada POI. Uma instância deve ter pedido, composição e versão consistentes; a chave separa venda avulsa de componente. Validar unicidade, cobertura e cardinalidade antes de calcular. É desenho futuro: nenhum campo foi inventado nas bases.

## Comparação MILP isolada

`experiments/compare_milp.py` usa SciPy/HiGHS fora da API. Exemplo **sintético**: quatro pedidos de 6,2,2,2 kits de duas peças, saldo para seis kits. xᵢ inteiro, 0 ≤ xᵢ ≤ demandaᵢ e Σxᵢ ≤ 6; cada componente recebe xᵢ.

| Objetivo | Kits por pedido observados | Peças | Pedidos completos |
| --- | --- | ---: | ---: |
| Lexical determinístico | 6,0,0,0 | 12 | 1 |
| Maximizar peças: 2Σxᵢ | 2,0,2,2 | 12 | 2 |
| Maximizar pedidos completos | 0,2,2,2 | 12 | 3 |
| Prioridade: Σwᵢxᵢ, pesos 1,4,3,2 | 0,2,2,2 | 12 | 3 |
| Equidade: maior fração mínima atendida | 3,1,1,1 | 12 | 0 |

Maximizar peças admite empates; não há solução única alegada. Pedidos completos usam binárias zᵢ com xᵢ ≥ demandaᵢzᵢ. Equidade exige xᵢ ≥ t·demandaᵢ. O experimento não implementa todo o domínio CSV nem prova ganho operacional. Demonstra conflitos entre objetivos.

Reproduzir: `.venv/bin/python experiments/compare_milp.py`. [Resultado](solver_experimental.json). Nenhum solver altera quantidades da plataforma.

## Homologação

Comercial aprova semântica de incompletude, saldos, prioridades e instâncias. Operação confere exemplos e exceções. Engenharia repete invariantes e regressões. Registrar versão, aprovadores, data e evidências antes de promover política.
