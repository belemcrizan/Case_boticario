# OTM Guard: decisão operacional verificável

O problema é transformar o rateio matemático do OTM em uma proposta compatível com a composição comercial dos kits e com a operação física de embalagem. A camada externa recebe os mesmos cinco arquivos do case e preserva o algoritmo legado.

## Resultado demonstrado

Na amostra de 12 itens, o OTM sugere 297 peças. A política conservadora produz **199 peças** e a alternativa que preserva kits completos produz **269 peças**. Um item permanece bloqueado para revisão por falta de retorno OTM e cadastros. As duas propostas respeitam as dez verificações do motor.

Exemplo real: 5 aparelhos e 7 cargas formam três kits de barba, pois cada kit exige duas cargas. A proposta fica em 3 aparelhos e 6 cargas. Para um SKU com caixa de seis peças, 110 peças são reduzidas a 108. Nenhuma peça é inventada para completar embalagem.

## O que funciona

A aplicação reúne consulta executiva, fila operacional, detalhes de decisão, importação validada, simulação de políticas e auditoria. A API autoriza acesso por lote, controla idempotência e concorrência, registra eventos e verifica a integridade de artefatos. O terminal original continua disponível sem bibliotecas externas.

O motor é a única autoridade quantitativa. A plataforma usa explicações determinísticas ligadas aos dados de origem. Não depende de LLM para funcionar e não envia pedidos ao faturamento.

## Evidências e seus limites

O aceite preserva integralmente os cenários originais e os arquivos de origem. Os testes abrangem também acessos indevidos, alterações de arquivos, falhas e retomadas. Há comparação com busca exaustiva e testes de propriedades. O registro atualizado de testes e CI fica em [EVIDENCIAS.md](EVIDENCIAS.md).

Uma medição sintética com 1 milhão de itens levou 152,3 segundos no fluxo local completo, com pico de 1.456,5 MiB RSS. Ela inclui CSV, cálculo instrumentado, relatórios, SQL SQLite e consulta paginada. Não inclui rede GCP, Cloud SQL real, autenticação corporativa ou carga de usuários. Portanto, não é SLA de produção.

## Riscos que exigem decisão

“Zerar se incompleto” precisa de homologação comercial: zerar o lote inteiro e preservar kits completos são escolhas diferentes. O OMS também precisa identificar explicitamente as instâncias de combo, e a fotografia de estoque precisa de data e versão confiáveis. A ordem de prioridade entre pedidos ainda é uma premissa lexical do demonstrador.

A proposta não equivale a reserva de estoque. Qualquer integração com OMS/WMS deve acrescentar transação e idempotência no sistema responsável. Dados reais, prioridade comercial, autenticação corporativa e fluxos de aprovação dependem de um ambiente autorizado.

## Evolução para GCP

A configuração proposta usa IAP, Cloud Run, Cloud Run Jobs, Cloud SQL PostgreSQL e Cloud Storage. A infraestrutura inclui IAM, versionamento, limites de recursos e observabilidade. O workflow de staging exige acionamento manual e cria candidato sem promover tráfego. Não foi realizado deploy no GCP.

## Como medir valor

Medir tempo manual por mil itens, intervenções por causa, divergência entre proposta e faturamento aprovado, tempo de fechamento e custo por lote. Unidades reduzidas indicam adequação a restrições, sem comprovar economia financeira.

Exemplo **ilustrativo**: se a conferência de 10 mil itens cair de 5 para 2 horas, a redução de tempo será de 60%. O piloto precisa medir ambos os tempos e confirmar a qualidade do faturamento antes de atribuir esse ganho à solução.

## Plano de adoção

1. Homologar semântica de quebra, vínculos de combo e prioridade.
2. Executar em sombra contra lotes reais, sem escrita no core.
3. Investigar divergências com a operação e estabelecer critérios de aceite.
4. Implantar um piloto limitado com identidade, rastreabilidade e recuperação testadas.
5. Integrar reserva e faturamento somente com contrato transacional e autorização específica.
