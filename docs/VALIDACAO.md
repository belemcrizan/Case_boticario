# Validação e medição

## Comandos reproduzíveis

```bash
python -m unittest discover -v
python scripts/check_examples.py
python -m compileall -q app.py otm_guard scripts tests
python scripts/benchmark.py --groups 75000
```

A suíte utiliza apenas `unittest`, sem baixar dependências. Os exemplos são recalculados em diretório temporário e comparados **em bytes**, incluindo CSV, JSON, HTML e manifesto.

## Cobertura comportamental

| Área | Evidências |
| --- | --- |
| Aceite do case | Quantidades esperadas dos 12 POIs; 199 no padrão e 269 no alternativo |
| Qualidade de entrada | BOM, colunas reordenadas, encoding, headers, cardinalidade, chaves repetidas, quantidades e regras inválidas |
| Integridade do vínculo | SKU divergente, OTM ausente/órfão, componente ausente e ambiguidade de combo |
| Embalagem e combo | Proporções 1:2, fracionamento, MDC/MMC, saldo insuficiente e política estrita |
| Estoque compartilhado | Pedidos disputando o mesmo CD/SKU, CDs isolados e débitos conjuntos de combos |
| Segurança da saída | Tetos, múltiplos, ledger, POIs e identidade de linhas; adulterações rejeitadas |
| Reprodutibilidade | Mesma saída para reordenação lógica dos mapas; quantidades idempotentes e artefatos idênticos na repetição |
| Interface e falhas | Código 3 no gate de revisão; ausência de saída parcial; destino existente, lock e falha de escrita |
| Exportações | Escape HTML, substituição de template em passagem única e neutralização de fórmulas em CSV |

São **48 métodos de teste**, com múltiplos subcasos. Um deles gera **600 cenários sintéticos com seed 20261029** e compara o motor a uma busca exaustiva independente.

### O oráculo independente

Em cada cenário, proporções e caixas variam de 1 a 6; demanda/OTM e saldos variam de 0 a 80. O teste enumera `k = 0..80`, filtra as soluções que cabem nos limites e respeitam os múltiplos e escolhe a maior. Não reutiliza a fórmula de MDC/MMC do motor. O resultado esperado por componente é `k * proporcao`.

Isso fortalece a validação dos ajustes locais, mas não prova semântica comercial, correção de cadastros reais ou otimização global.

## Medição sintética observada

O arquivo [benchmark_observado.json](benchmark_observado.json) registra uma execução neste ambiente com Python 3.12.14:

| Medida | Resultado |
| --- | ---: |
| Grupos gerados | 75.000 |
| POIs gerados | 100.000 |
| Tempo de motor + verificador, com `tracemalloc` ligado | 10,658081 s |
| Pico adicional rastreado durante `reconcile` | 56,450 MiB |
| Invariantes aprovadas | 10 de 10 |
| POIs em revisão | 0 |

Massa sintética com cinco CDs, mistura de avulsos e combos 1:2, caixas de 6 e 12 e variação de quantidades. Os dados já estão em memória ao iniciar a medição. O pico não inclui a criação do Dataset, RSS total, leitura CSV, geração de HTML ou gravação de arquivos.

Uma medição isolada, em hardware compartilhado e com instrumentação de memória, não estima p95, throughput produtivo ou SLA. O tempo varia entre execuções; os números de negócio e as verificações do conjunto sintético são reproduzíveis com a mesma seed.

## CI

O workflow executa testes, compilação e reprodução dos exemplos em Python 3.11, 3.12 e 3.13. Actions oficiais estão fixadas por SHA; o token tem somente leitura e não é persistido pelo checkout. O resultado remoto deve ser conferido na aba Actions; configurar o workflow não significa, por si só, que uma execução remota passou.

## Validações adicionais antes de produção

Homologar a política de quebra e os vínculos comerciais, certificar a completude dos cadastros, receber timestamps/versões de lote, validar prioridade de estoque e exercitar o consumidor com reserva concorrente, falhas e reenvios. Medir o fluxo completo com volumes e distribuição de SKUs reais, incluindo relatórios paginados e conferência operacional.
