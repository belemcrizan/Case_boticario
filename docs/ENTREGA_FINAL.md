# Entrega OTM Guard Enterprise

## Resumo executivo

O case evoluiu de CLI/relatório para uma aplicação de conciliação, com API, persistência, execução assíncrona, interface para gestão/operação/auditoria, segurança por recurso e preparação GCP. O motor determinístico, as cinco bases e os exemplos originais foram preservados.

A aplicação produz **propostas para conferência**, sem reservar estoque, alterar OTM, editar quantidades manualmente ou enviar pedidos ao faturamento. Não houve deploy GCP nem homologação produtiva.

## Comparação objetiva

| Dimensão | Baseline | Evolução entregue |
| --- | --- | --- |
| Quantidades | 297 OTM; 199 strict; 269 kits | Mesmos valores e 12 POIs |
| Motor | Determinístico, dez invariantes | Fontes originais intactos; biblioteca independente |
| Execução | CLI síncrona | CLI preservada + API assíncrona e estados persistidos |
| Conferência | HTML offline completo | React, filtros/páginas SQL e HTML offline limitado em grandes lotes |
| Identidade | Processo local | Demo explícita; IAP e papéis/dono no modo GCP |
| Rastreio | Manifesto e hashes | Mais identidade opaca, tentativas, eventos e integridade no download |
| Testes | 48 métodos e cenários enumerados | 93 Python, 13 componentes, 7 E2E, propriedades e mocks cloud |
| Escala medida | 100 mil, core-only/tracemalloc | 10 mil a 1 milhão, fluxo local completo/RSS |
| Infraestrutura | Sem deploy cloud | Docker, Terraform modular e candidato staging manual |
| Comunicação | Documentação do núcleo | Brief, ADRs, runbooks, screenshots e apresentação de oito slides |

Os benchmarks têm escopos diferentes: a tabela não implica aceleração ou comparação direta entre versões.

## Checklist de aderência

| Exigência | Estado e evidência |
| --- | --- |
| Auditoria anterior à mudança | Implementada: [AUDITORIA_INICIAL.md](AUDITORIA_INICIAL.md), SHA e baseline |
| Cinco bases, 12 POIs e CLI | Preservados; exemplos byte a byte e CI em três Python |
| Demanda/OTM/estoque/kit/caixa | Dez pós-condições e motor original; [matemática](ARQUITETURA.md) |
| Políticas e ambiguidades | Matriz e instâncias futuras em [POLITICAS_COMERCIAIS.md](POLITICAS_COMERCIAIS.md) |
| MILP comparativo | Experimento sintético isolado; não substitui motor |
| API, schemas e documentação | FastAPI/OpenAPI, paginação, erros e contratos em [API_E_DADOS.md](API_E_DADOS.md) |
| Segurança por recurso | Sessão/IAP, papéis, dono, CSRF, limites, hashes e [ameaças](MODELO_AMEACAS.md) |
| Reprocessamento e concorrência | Claims, idempotência, quota global, lease/fencing e retries |
| Frontend e jornadas | Dashboard, importação, decisões, exceções, estoque, políticas, auditoria e arquitetura |
| UX não técnica | Glossário, ajuda, explicações determinísticas, ações e denominadores |
| Responsividade/acessibilidade | Testes desktop/móvel/escuro/teclado/axe; avaliação humana ainda pendente |
| Cloud readiness | Adapters GCS/SQL/Jobs/IAP, Docker, IAM/WIF e Terraform validado |
| SRE e observabilidade | Métricas/eventos/spans opcionais; SLOs e alertas adicionais propostos |
| Segurança de dependências | Locks, hashes, SBOM, pip/npm audit e Trivy em CI |
| Performance | Quatro volumes sintéticos e concorrência independente; sem SLA produtivo |
| IA opcional | ADR somente leitura e fallback; nenhuma integração Vertex/Gemini executada |
| Valor/ROI | Método de piloto e hipóteses ilustrativas; nenhum ganho financeiro alegado |
| Material executivo | [Brief](EXECUTIVE_BRIEF.md), [roteiro](DEMONSTRACAO.md), [PPTX](presentation/OTM_Guard_Executivo_Final.pptx) |
| CI/CD | Gates automatizados; staging manual por WIF, sem execução nesta entrega |
| Entrega GitHub | Branch dedicada e PR para revisão; sem merge na main |

## Evidências e arquivos

- [EVIDENCIAS.md](EVIDENCIAS.md): testes, cobertura, segurança, CI e nove capturas reais.
- [ARQUIVOS_ENTREGA.md](ARQUIVOS_ENTREGA.md): lista integral de arquivos novos/modificados em relação ao baseline.
- [PERFORMANCE_E_CUSTOS.md](PERFORMANCE_E_CUSTOS.md): 1 milhão de POIs em 152,31 s, pico 1.456,53 MiB RSS, escopo local.
- [Arquitetura GCP](ARQUITETURA_GCP.md), [API/dados/sequência](API_E_DADOS.md) e [ADRs](adr/).
- [Guia da interface](GUIA_INTERFACE.md), [README](../README.md) e [demonstração](DEMONSTRACAO.md).

## Níveis de maturidade

| Nível | Situação |
| --- | --- |
| Implementado | CLI, API, UI, adapters, infraestrutura e pipelines |
| Testado | Núcleo, API local, SQL SQLite, propriedades, falhas, UI e mocks SDK |
| Validado em CI | Testes, build, segurança, contrato, Terraform e container |
| Validado em GCP | **Não**: sem projeto/credenciais/ambiente autorizado |
| Pronto para homologação | Candidato técnico documentado; requer provisionar ambiente e aprovar plano |
| Homologado para produção | **Não** |

## Riscos remanescentes e roadmap

**P0 — comercial/dados:** homologar “incompleto”, prioridade, instância comercial e data/versão de snapshot. Autoridade: operação/comercial/OMS.

**P0 — ambiente:** testar IAP real, grants SQL, GCS, Jobs, carga representativa, restore e rollback. Aprovar região, rede, budget, retenção e tratamento de dados. Autoridade: engenharia/SRE/governança.

**P1 — operação contínua:** outbox/reconciliador para dispatch interrompido e UPLOADING abandonado, expurgo SQL, migrações versionadas, observabilidade agregada e rate limit por usuário. Hoje há diagnóstico e recuperação explícita, não automação completa.

**P1 — integração:** reserva transacional/idempotência no responsável pelo estoque, aprovação humana e escrita OMS/WMS somente após contrato e autorização.

**P2 — evolução orientada a dados:** comparar objetivos comerciais em massa representativa, avaliar particionamento seguro e só então eventual IA somente leitura, com avaliação de fidelidade, injection e custo.

## Plano de homologação e adoção

1. Aprovar regras e casos esperados com responsáveis e versão.
2. Provisionar staging autorizado, criar schema/grants, testar identidade e limites.
3. Executar em sombra sobre lotes reais protegidos; medir divergências, tempo e revisão.
4. Repetir invariantes, carga, falhas, restore e rollback; registrar aceite técnico e operacional.
5. Criar candidato sem tráfego, promover progressivamente com métricas aprovadas.
6. Integrar faturamento somente quando houver reserva transacional e autorização específica.

Procedimentos concretos e rollback em [OPERACAO_ENTERPRISE.md](OPERACAO_ENTERPRISE.md). A demonstração local funciona sem GCP ou LLM. Aprovação matemática e CI verde não substituem homologação.
