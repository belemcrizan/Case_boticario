# Performance e custos

## Metodologia reproduzível

`scripts/benchmark_e2e.py` gera cinco CSVs sintéticos e abre processo novo por volume. Cronometra ingestão, motor, verificador, publicação/cópia imutável, persistência SQLite e primeira página. RSS vem de resource.getrusage no Linux. O tempo do verificador é capturado via profiler: sua sobrecarga está incluída. Geração da massa e verificação adicional de hashes ficam fora do total.

```bash
.venv/bin/python scripts/benchmark_e2e.py --help
.venv/bin/python scripts/benchmark_e2e.py --sizes 10000,100000,500000,1000000 --output docs/benchmark_e2e_observado.json
```

Verifique os argumentos com --help antes de repetir em outro sistema. O JSON registra ambiente, método e resultados. Uma rodada por volume não permite calcular p95, variância ou SLA. Não há banco/rede GCP nesta medição.

| POIs | Ingestão s | Cálculo s | Verificação s | Publicação s | SQL s | Página s | Total s | Pico RSS MiB |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10.000 | 0,328 | 0,219 | 0,163 | 0,182 | 0,410 | 0,012 | 1,314 | 50,65 |
| 100.000 | 3,426 | 4,150 | 1,971 | 1,809 | 3,565 | 0,013 | 14,935 | 182,86 |
| 500.000 | 18,322 | 15,490 | 9,643 | 8,487 | 19,169 | 0,043 | 71,153 | 751,61 |
| 1.000.000 | 34,925 | 31,652 | 18,233 | 20,620 | 46,801 | 0,079 | **152,309** | **1.456,53** |

Fonte: [medição integral](benchmark_e2e_observado.json). Taxa aproximada do total: 7.609, 6.696, 7.027 e 6.566 POIs/s, respectivamente. Pequenas diferenças entre soma e total decorrem de setup/overhead.

Artefatos: 1,61 / 15,40 / 76,65 / 153,21 MB decimais. SQLite: 11,00 / 109,69 / 548,33 / 1.097,08 MB. O banco preserva JSON explicativo e índices, com custo relevante. O HTML é limitado a 200 linhas quando o lote supera 500; CSVs permanecem completos.

## Concorrência

[Observação](benchmark_concorrencia.json): dois processos independentes de 10 mil POIs terminaram em 1,754 s de parede, com 50,88 MiB RSS cada e mesmas métricas. Não compartilham estoque nem banco. Disputa no mesmo banco é verificada por testes de claim, idempotência e quota; isso não prova throughput PostgreSQL sob usuários concorrentes.

## Gargalos e próximos testes

Persistência representa cerca de 31% do total em 1 milhão. Ingestão, cálculo e verificação continuam em memória. A eliminação de cinco hashes repetidos por linha reduziu amplificação no SQL. A paginação evita enviar milhões de decisões para o navegador.

Antes de produção: repetir volumes com dados representativos e percentis, medir Cloud SQL/índices/rede, carga concorrente, pico de temporários e disco, upload HTTP e recuperação. Particionar apenas por grupos independentes CD/SKU e componentes conectados; dividir pedidos arbitrariamente quebra conservação de saldo. Esse particionamento não foi implementado.

O benchmark original [core-only](benchmark_observado.json), de 100 mil POIs, usa tracemalloc e outro escopo. Não comparar diretamente com RSS/fluxo completo.

## Estimativa econômica ilustrativa

Sem projeto e faturamento reais, não há custo observado por lote. A região proposta é southamerica-east1. Os valores abaixo são **referências de preço padrão Iowa/us-central1**, consultadas em 29/10/2026, e não orçamento para São Paulo. Recalcular no Pricing Calculator com região, modalidade, câmbio, tributos e descontos vigentes.

Fórmula: custo/lote = Job + API + SQL mensal/N + armazenamento/operações + logs/rede. Não omitir custo fixo do banco quando o web service está em zero instâncias.

Exemplo **hipotético**, sem free tier/descontos: Job de 180 s, 2 vCPUs e 4 GiB; usando referências de US$ 0,000018/vCPU-s e US$ 0,000002/GiB-s, custo computacional = 180 × (2 × 0,000018 + 4 × 0,000002) = **US$ 0,00792**. Não inclui API, inicialização adicional, SQL, disco, GCS, logs ou rede; 180 s não é runtime GCP medido.

Referência igualmente ilustrativa de SQL: 1 vCPU a US$ 0,0413/h e 3,75 GiB a US$ 0,007/GiB-h por 730h resultam em **US$ 49,31/mês**, antes de disco, backups e HA. Não tratar como preço total ou regional contratado.

Fontes primárias: [Cloud Run](https://cloud.google.com/run/pricing), [Cloud SQL](https://cloud.google.com/sql/pricing), [calculadora](https://cloud.google.com/products/calculator). Configurar budget, alertas e teto de disco; max_instances e quota de quatro lotes não garantem teto financeiro.
