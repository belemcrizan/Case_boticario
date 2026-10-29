# Observabilidade, SRE e medição de valor

## Instrumentação implementada

Métricas Prometheus em /api/v1/metrics, restritas a auditor/admin, sem POI/SKU/usuário como label: otm_http_requests_total(method,status), otm_http_duration_seconds(method), otm_jobs_total(state), otm_stage_seconds(stage). O processo exporta seus histogramas e contadores; agregação de vários Jobs exige coletor/monitoramento central, ainda não configurado. Tempos por execução também ficam no SQL.

Eventos JSON registram correlation ID, método/status/duração ou identidade opaca do lote/etapas/tipo de falha. Não registram CSV, JWT, DSN ou stacktrace com dados. Auditoria SQL armazena hash do ator. OpenTelemetry cria spans por etapa somente com OTEL_EXPORTER_OTLP_ENDPOINT configurado; sem endpoint não há exportação de rede. Coletor e correlação distribuída completa ainda exigem integração de ambiente.

Resumo do lote contém POIs, situações, motivos, redução, qualidade, dez verificações e estado de aprovação humana pendente. Motivos se sobrepõem. Idade da foto é **desconhecida**, pois não existe timestamp confiável no contrato; não substituir por horário do upload. Memória/CPU devem vir das métricas de plataforma no GCP, e custos do Billing Export; não são ganhos medidos na UI.

## SLI/SLO propostos, não observados

| Indicador | Objetivo inicial para homologar | Alerta / resposta |
| --- | --- | --- |
| Invariantes | 100% antes de publicar | P1: bloquear publicação, investigar evidência |
| HTTP 5xx / requisições válidas | < 1% em janela de 30 dias | P2: > 5% por 5 min, investigar dependências |
| Consulta paginada p95 | < 500 ms em carga homologada | P2: > 1 s por 10 min |
| Lotes concluídos sem falha técnica | ≥ 99% após excluir contrato inválido | P2: falhas persistentes |
| QUEUED/RUNNING sem progresso | Menor que lease/timeout aprovado | P2: conferir Job, claim e redispatch |
| Snapshot | Data/versão e idade dentro de regra comercial | P1 para integração se desconhecido/expirado |
| Orçamento | Budget definido pelo responsável | P2: 50/80/100% do orçamento, não é kill switch |

Terraform implementa canal configurável e alerta de log run_failed. A tabela propõe alertas adicionais; não alegar que todos foram implantados. Não foi enviado alerta a destinatário nesta entrega.

## Metodologia de valor

Separar: **real do case** (12 POIs, 199/269 peças), **sintético** (benchmarks e MILP), **hipótese** (esforço e ROI).

No piloto em sombra, coletar amostras pareadas de lotes comparáveis com política aprovada. Registrar tempo ativo e espera, revisor, tamanho, número de exceções, contexto e erros posteriores. Comparar baseline manual e conferência assistida, com intervalo de confiança e sem misturar aprendizagem ou mudança de política.

| KPI proposto | Fórmula / coleta |
| --- | --- |
| Minutos por mil POIs | 1.000 × minutos de trabalho ativo / POIs |
| Intervenção humana | POIs revisados por pessoa / POIs processados |
| Divergência | Linhas divergentes da proposta aprovada / linhas faturadas |
| Combos/caixas inconsistentes evitados | Ocorrências confirmadas pela operação antes da liberação |
| Ciclo | Hora de encerramento aprovado − recebimento das entradas |
| Custo por lote | Computação + parcela SQL + armazenamento + operação |
| Revisão por causa | POIs distintos por motivo / POIs; causas podem se sobrepor |

Ilustração, não resultado: 10 mil itens, conferência de 5h para 2h → redução de tempo 60%, três horas liberadas. Valor financeiro só existe após validar custo-hora, utilização efetiva, qualidade e custos adicionais. Quantidades reduzidas não são receita recuperada, perda evitada ou economia automaticamente.
