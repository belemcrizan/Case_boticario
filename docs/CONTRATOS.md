# Contratos de dados e tratamento de falhas

## Formato físico

Cinco arquivos CSV de nomes fixos, UTF-8 com ou sem BOM, separados por vírgula e com cabeçalho. A ordem das colunas pode mudar; o conjunto de colunas deve coincidir exatamente com o contrato. Coluna extra, ausente ou repetida interrompe o lote. Linhas vazias são ignoradas pelo parser CSV.

Todos os campos são obrigatórios em registros existentes. Removem-se apenas espaços externos, com registro da ocorrência. Não se alteram caixa, zeros de identificadores ou caracteres internos. Textos de negócio têm limite de 1.024 caracteres e não admitem controles internos. Identificadores têm até 128 caracteres e seguem `[A-Za-z0-9][A-Za-z0-9_.:/-]*`.

Quantidades e estoque são inteiros decimais ASCII entre 0 e `10^12`; proporções e múltiplos precisam ser positivos. `1.0`, negativos, notação científica, strings vazias e valores não finitos são rejeitados, sem conversão silenciosa. Cada arquivo admite até 64 MiB; para volume maior, evoluir a ingestão antes de aumentar o limite indiscriminadamente.

## Contratos lógicos

| Base | Chave única / campos | Regras |
| --- | --- | --- |
| OMS | `poi_id`; pedido, CD, franqueado, SKU, quantidade | Um SKU por pedido/CD/franqueado; carteira não vazia |
| OTM | `poi_id`; SKU, quantidade, status | Join 0:1 com OMS; SKU deve conferir; somente `SUCESSO` e `ZERADO` liberam |
| Estoque | `(cd_origem, sku)`; saldo | Soma de estoque duplicado é proibida; saldo de outro CD não compensa falta |
| Combo | `(id_combo_comercial, sku_componente)` | Proporção positiva; descrição e regra iguais no mesmo combo; ao menos 2 componentes |
| Embalagem | `sku`; marca, múltiplo, fracionamento | Flags `SIM`, `NÃO` ou `NAO`; múltiplo positivo |

Regras de combo aceitas exatamente: `Zerar se incompleto` e `Ajustar para maior combo completo`. Status diferente de `SUCESSO`/`ZERADO` gera revisão do POI; `ZERADO` com quantidade positiva é contraditório e interrompe o lote.

## Falha estrutural versus revisão operacional

| Situação | Ação | Justificativa |
| --- | --- | --- |
| Arquivo ausente, encoding inválido, cabeçalho incorreto ou quantidade inválida | Interromper, código 2, sem proposta | Contrato físico não confiável |
| POI, saldo ou embalagem com chave repetida | Interromper, mesmo se linhas iguais | Não há política autorizada de soma ou seleção |
| Componente de combo exatamente repetido após normalização | Deduplicar e avisar | Caso explícito da amostra; mesma regra e proporção |
| Mesmo componente com proporção/descrição/regra conflitante | Interromper | Não há regra de precedência confiável |
| Mesmo SKU em mais de um combo | Interromper | OMS não informa qual instância comercial foi comprada |
| Mesmo SKU em dois POIs no mesmo pedido/CD/franqueado | Interromper | Pode significar venda avulsa + combo ou duas instâncias; não presumir |
| POI sem OTM | Manter POI com zero e revisão | Ausência não é sucesso nem sugestão de zero |
| SKU do OTM diferente do OMS | Zero e revisão | Conciliação por POI não autoriza trocar o produto |
| Embalagem ou estoque ausente | Zero e revisão | Não presumir fracionamento ou disponibilidade |
| Estoque explicitamente zero | Aplicar regra com zero; sem revisão por ausência | Dado conhecido difere de dado faltante |
| Componente ausente no escopo do pedido | Zerar componentes presentes e revisar o grupo | Não completar entre pedidos/CDs/franqueados |
| OTM sem POI no OMS | Registrar `OTM_ORFAO` e ignorar para alocação e métricas OTM | Não criar pedido a partir do otimizador |
| Invariante de saída violada | Interromper, código 1, sem proposta | Erro de implementação ou resultado corrompido |

## O que a base não permite inferir

- Não existe `id_instancia_combo` no OMS. Assume-se que um SKU presente no mapa comercial pertence àquele combo no escopo do pedido; venda avulsa desse componente não é distinguível.
- Um SKU fora do mapa é tratado como avulso. A completude do cadastro comercial precisa de certificação externa; registros faltantes no mapa não são detectáveis apenas pelo CSV.
- Não há lote, data ou horário de geração do OTM e da carteira. A foto indica “05h” no nome, mas não traz data. A aplicação registra timestamp desconhecido, sem inventá-lo.
- Não há SLA, margem, prazo prometido, prioridade de rede ou peso comercial. A ordem lexical é técnica e precisa ser substituída por critério homologado se houver competição real.
- Não há significado documentado de `status_otm` além dos valores observados. Valores novos ficam em revisão até terem contrato definido.

## Proteção das exportações

O HTML escapa texto antes de inseri-lo. Células textuais que poderiam iniciar fórmulas de planilha são prefixadas por apóstrofo; identificadores operacionais são validados na entrada e não precisam dessa transformação. CSVs de saída usam BOM UTF-8 para facilitar abertura no Excel. JSONs usam UTF-8 e não contêm valores NaN/Infinity.

Os relatórios podem conter identificadores de pedidos e franqueados. Em produção, acesso, retenção e descarte devem seguir as políticas da empresa; dados reais não devem ser adicionados ao repositório público do case.
