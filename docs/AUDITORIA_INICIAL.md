# Auditoria inicial da evolução

Data: 29/10/2026. Baseline: `cdc7ffc32d101706cf268e026005c8a06b676c91`.
Branch de trabalho: `feat/otm-guard-enterprise`. A branch principal permanece intacta.

## Evidências antes de alterar código

- Árvore completa inspecionada: 48 arquivos versionados, motor, CLI, ingestão, relatórios, testes, contratos, ADR e CI.
- `python -m unittest discover -v`: 48 métodos aprovados, incluindo 600 cenários enumerados independentemente.
- `python scripts/check_examples.py`: ambos os exemplos reproduzidos integralmente em bytes.
- Cenários conferidos: 12 POIs, OTM 297, strict 199, complete-kits 269, dez invariantes aprovadas.
- Benchmark registrado conferido: 100.000 POIs sintéticos, 10,658081 s com tracemalloc, 56,450 MiB adicionais, somente motor e verificador. O hash dos sete fontes coincide com o baseline.
- Não existem infraestrutura, API, persistência de execução, autenticação ou aplicativo React no baseline.

## Riscos e decisões

| Risco | Decisão de evolução |
| --- | --- |
| Alterar regra comercial para melhorar indicador | Manter strict padrão e mesmas quantidades; comparar políticas em execução derivada |
| Regressão de código/hash dos exemplos | Preservar os sete fontes originais; ampliar o produto em pacote independente |
| HTML integral e estruturas repetidas para milhões de linhas | Publicação streaming, relatório offline limitado e paginação no banco |
| Usar memória local como armazenamento cloud | SQLite/arquivos apenas no modo local; Cloud SQL/GCS no modo GCP |
| Recursos de um usuário acessíveis por UUID | Autorizar por proprietário/papel em toda consulta e download |
| Demo confundida com identidade empresarial | Sessão demo explicitamente habilitada apenas em ambiente demo; IAP JWT validado no GCP |
| Upload ou retry duplicar execução | Chave de idempotência, comparação do fingerprint e claim atômico com lease |
| Declarar implantação ou acessibilidade completa sem evidências | Registrar cada nível de validação e limites efetivamente observados |

## Critérios de regressão

Os arquivos de `data/input` e `examples` permanecem intactos. Nenhuma nova camada decide quantidades independentemente do motor. A execução original `python app.py` continua sem dependências externas. A infraestrutura e integrações cloud serão verificadas estaticamente e com testes locais; deploy real exige projeto e ambiente autorizados.
