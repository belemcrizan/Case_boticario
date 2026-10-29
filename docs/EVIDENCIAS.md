# Evidências e critérios de qualidade

Data da verificação: 29/10/2026. Baseline preservado: cdc7ffc32d101706cf268e026005c8a06b676c91. Fonte automatizada: workflows [Validacao do case](https://github.com/belemcrizan/Case_boticario/actions/workflows/ci.yml) e [Enterprise quality gates](https://github.com/belemcrizan/Case_boticario/actions/workflows/enterprise.yml).

## Resultado verificado

| Verificação | Resultado / alcance |
| --- | --- |
| Python | **93 testes aprovados**, 634 subtests; estes incluem os 600 cenários enumerados originais |
| Propriedades adicionais | 300 exemplos Hypothesis com limites/proporções/caixas e ótimo local por enumeração |
| Cobertura com branches | **93,9%** total; motor **100%**; meta global 90% |
| SDKs GCP | Mocks de GCS, Jobs e Connector; cloud.py 100% no escopo simulado |
| Frontend | **13 testes** de componentes/jornadas, lint, formato, TypeScript e build |
| Navegador | **7 jornadas Playwright** com API real, Chromium, desktop e 390×844 |
| Regressão | 12 POIs, 199/269 peças, dez invariantes; exemplos reproduzidos integralmente em bytes |
| CLI sem dependências | CI Python 3.11/3.12/3.13; unittest discovery também passou com python -S (sem site-packages) |
| Mutação amostral | Três mutantes representativos eliminados; não é score completo |
| API | OpenAPI versionada e conferida automaticamente contra o código |
| Terraform | fmt/init/validate em CI; valid=true, zero erros e warnings |
| Container | Build e smoke /healthz, /readyz, sessão, consulta de resultados |
| Dependências | pip-audit sem vulnerabilidades conhecidas nas 63 dependências de runtime; npm audit aprovado |
| Imagem | Trivy: zero achados CRITICAL no snapshot registrado; não alegar ausência de toda severidade |
| Apresentação | Oito slides renderizados/inspecionados; gráfico e tabelas nativos, pacote validado |

Cobertura exclui somente os entrypoints worker.py e manage.py: não foram executados contra serviços GCP. A disponibilidade das bibliotecas, configuração e mocks não validam OAuth, grants, rede, quotas, restauração ou deploy. Warning atual de teste: integração httpx/TestClient marcada como deprecated pelo Starlette; não impede execução.

A CI registra o SHA efetivamente avaliado. Os arquivos em [security](security/) têm proveniência própria; consultar seu README. Os checks do PR devem estar verdes no último commit antes da revisão. A apresentação não foi aberta em PowerPoint/Google Slides nesta sessão.

## Cenários adversariais

Autorização cobre consulta, detalhe, inventário, auditoria, comparação, download, simulação, retry e integridade de lote alheio com 404 uniforme. Perfis somente leitura não executam. Sessão expirada, origem/CSRF inválidos e claims IAP falsos ou incompatíveis são rejeitados.

Entrada cobre nomes/caminhos inválidos, arquivos ausentes/duplicados, schema incorreto, limites e multipart sem Content-Length. O limite conta bytes recebidos, não apenas header. Dados adulterados são detectados antes do motor. Artefato alterado é bloqueado antes de responder download.

Concorrência cobre replay simultâneo, um único claim, quota global entre donos distintos, lease, fencing de tentativa antiga e teto de retry. Falha inesperada é redigida, não publica artefatos e pode recuperar em nova tentativa válida.

Testes de mutação usam cópias temporárias: crédito em vez de débito de estoque, remoção de arredondamento de caixa e desativação de strict. As três mudanças são detectadas. Ver [mutation_smoke.json](mutation_smoke.json).

## Acessibilidade e evidência visual

Axe com tags WCAG 2 A/AA, 2.1 AA e 2.2 AA não encontrou violações automatizáveis nos estados exercitados. Testes cobrem Escape no detalhe/menu, devolução de foco, tabelas roláveis por teclado, busca, permissões, modo escuro e ausência de rolagem horizontal da página móvel. O menu móvel contém foco e deixa o conteúdo de fundo inerte.

**Isso não certifica conformidade integral WCAG 2.2 AA.** Leitor de tela, ampliação/reflow em diferentes navegadores, toque, ordem de leitura e avaliação humana ainda precisam de homologação.

| Captura real | Arquivo |
| --- | --- |
| Visão executiva | [01](screenshots/01-visao-executiva.png) |
| Evidência de decisão | [02](screenshots/02-detalhe-decisao.png) |
| Fila de revisão | [03](screenshots/03-fila-revisao.png) |
| Comparação de políticas | [04](screenshots/04-comparacao-politicas.png) |
| Importação validada | [05](screenshots/05-importacao-validada.png) |
| Qualidade e auditoria | [06](screenshots/06-qualidade-auditoria.png) |
| Dashboard móvel | [07](screenshots/07-dashboard-mobile.png) |
| Estoque móvel escuro | [08](screenshots/08-estoque-mobile-escuro.png) |
| Arquitetura proposta | [09](screenshots/09-arquitetura-gcp.png) |

## Reprodução

Instale os extras e o frontend conforme o README. Execute os comandos de verificação do README, os exemplos e:

```bash
.venv/bin/python scripts/mutation_smoke.py
.venv/bin/python experiments/compare_milp.py
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
```

Playwright inicia a API pelo webServer configurado e usa diretório local isolado. A suíte não envia pedidos ao OMS nem usa credenciais GCP. O ambiente de edição gerenciado não ofereceu um preview Python compatível; QA de navegador foi realizada no runner GitHub com evidências, sem declarar preview interativo publicado.

Benchmarks têm comandos, escopo, versões, hashes, tempos e RSS em [PERFORMANCE_E_CUSTOS.md](PERFORMANCE_E_CUSTOS.md). Uma rodada sintética não prova SLA. Deploy/rollback e restore reais permanecem não executados.
