# Matriz de aderência ao enunciado

Não foi fornecida uma rubrica de pontuação ou senioridade. Esta matriz cobre os requisitos explícitos do PDF e acrescenta verificações de engenharia proporcionais a uma entrega de nível sênior.

| Exigência / problema | Implementação | Evidência verificável |
| --- | --- | --- |
| Solução tática sem alterar OTM | Processador local pós-OTM, sem integração de escrita no core | `app.py`; execução offline |
| Aplicação `.html` ou `.py` de terminal | Entrada `.py` com argumentos e ajuda | `python app.py --help` |
| Consumir demanda OMS | POI é identidade primária; demanda é teto | `ingest.py`; teste `test_demand_is_a_hard_upper_bound` |
| Consumir retorno OTM | Join 0:1 por POI, conferência de SKU e status | Testes de OTM ausente, divergente e status não aprovado |
| Usar foto de estoque | Ledger compartilhado por CD/SKU | `test_same_sku_different_orders_share_one_cd_balance` |
| Respeitar combos e proporções | Grupo por pedido/CD/franqueado/combo; componentes debitados em conjunto | Aceite dos combos Mães, Barba e SkinCare |
| Respeitar regra de quebra | Duas regras reconhecidas; política estrita padrão e alternativa explícita | `docs/adr/001-politica-combos.md`; exemplos das duas políticas |
| Respeitar caixa master e fracionamento | Inteiros e arredondamento inferior; composição com proporções por MMC | Teste `test_coupled_packaging_requires_lcm` |
| Evitar consumo anômalo | Nunca aumentar OTM/demanda; verificar soma por CD/SKU | 10 invariantes antes de publicar |
| Explicar premissas | Premissa de quebra, escopo do combo, prioridade e ausência de dados explícitos | README, contratos e ADR |
| Discutir qualidade | Testes de contrato, integração, falhas, propriedades e oráculo independente | `tests/`; `docs/VALIDACAO.md` |
| Discutir evolução / implementação | Rollout em sombra, reconciliação, reserva transacional e escala | `docs/OPERACAO.md` |
| Facilitar uso pelo time operacional | CSV de proposta, fila de revisão, saldo e relatório offline | `examples/strict/` |
| Ser auditável e reproduzível | Motivos por POI; hashes de dados, código, política e saídas | `manifest.json`; `scripts/check_examples.py` |

## Critérios de aceite executados

1. Os 12 POIs aparecem uma única vez e sem criação de demanda.
2. Os finais padrão, na ordem POI-1001 a POI-1012, são `0, 0, 10, 3, 6, 0, 108, 30, 30, 12, 0, 0`.
3. `SKU-E2` no SkinCare tem proporção 1, não 2; a duplicata é registrada.
4. `SKU-X1 ` encontra o cadastro de `SKU-X1`; as duas normalizações são registradas.
5. `SKU-GHOST` não recebe quantidade inventada e permanece em revisão.
6. Nenhum estoque de outro CD é utilizado; o saldo agregado é não negativo.
7. Componentes de um combo são reduzidos conjuntamente; caixa e proporção continuam válidas.
8. Rodar com as mesmas entradas, código e política gera artefatos idênticos em bytes.
9. A aplicação recusa duplicações conflitantes e não publica um lote parcial.
10. O cenário alternativo gera 269 peças, com política e identidade de execução distintas.

Revisar a premissa de quebra com a banca demonstra compreensão do negócio; não é necessário ocultar a ambiguidade do enunciado ou prometer um único número como verdade operacional.
