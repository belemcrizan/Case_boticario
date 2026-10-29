# Case AI Engineer | Operações & Logística

Camada tática **pós-OTM** para produzir uma proposta de faturamento compatível com combos comerciais, caixas master, demanda e estoque por CD/SKU. O algoritmo do OTM permanece intacto.

**Execução local, Python padrão, sem instalação de bibliotecas, sem credenciais e sem chamadas externas.** Cada POI recebe quantidade final, status e motivos. Um verificador recalcula as restrições antes de publicar qualquer saída.

## Começar em um minuto

Requisito: Python **3.11 ou superior**. Desenvolvimento e validação local em Python 3.12.14. A CI está configurada para 3.11, 3.12 e 3.13.

```bash
git clone https://github.com/belemcrizan/Case_boticario.git
cd Case_boticario
python app.py
```

Abra `output/relatorio.html` no navegador. O relatório funciona offline, com busca, filtro por status, decisões por POI e verificações de saída. No Windows, também é possível usar `py -3 app.py`.

Para repetir, escolha um diretório novo: as evidências anteriores nunca são sobrescritas.

```bash
python app.py --output-dir output-nova-execucao
python -m unittest discover -v
python scripts/check_examples.py
```

Já existem [exemplos completos](examples/strict/) e um [relatório pronto para baixar e abrir](examples/strict/relatorio.html). O visualizador de arquivos do GitHub mostra o código HTML; para ver o relatório, baixe o arquivo ou gere-o localmente.

## Resultado real das cinco bases fornecidas

| Indicador | Padrão conservador |
| --- | ---: |
| POIs preservados na saída | 12 de 12 |
| Demanda total | 455 peças |
| Sugestão OTM associada aos pedidos | 297 peças |
| Proposta conciliada | **199 peças** |
| POIs mantidos / ajustados / zerados / em revisão | 5 / 3 / 3 / 1 |
| Invariantes verificadas | 10 de 10 |

O item `SKU-GHOST` permanece com zero e exige revisão por ausência de OTM, embalagem e estoque. O motor registra a deduplicação de `SKU-E2` no combo e a remoção de espaços externos de `SKU-X1` em dois arquivos.

**Exemplo didático com números reais:** o combo de barba exige 1 aparelho e 2 cargas. O OTM oferece 5 aparelhos e 7 cargas. Cabem `min(5, 7 // 2) = 3` kits; a proposta fica **3 aparelhos e 6 cargas**. Para `SKU-D2`, 110 peças em caixas de 6 viram **108**, sempre arredondando para baixo.

### Premissa comercial que muda o resultado

“Zerar se incompleto” não define se deve ser zerado o lote inteiro ou apenas a parte que não forma kits. A implementação torna essa ambiguidade explícita:

| Política | Combo Dia das Mães, OTM 50:35 e proporção 1:1 | Total do lote |
| --- | --- | ---: |
| `strict`, padrão | 0:0; preservar integralmente o lote limitado pela demanda ou zerá-lo | **199** |
| `complete-kits`, cenário alternativo | 35:35; preservar os kits completos viáveis | **269** |

```bash
python app.py --incomplete-policy complete-kits --output-dir output-kits
```

A alternativa fica identificada no relatório e no manifesto. O padrão é uma **premissa conservadora de negócio**, não uma interpretação confirmada pela operação. A regra explícita “Ajustar para maior combo completo” sempre utiliza o maior número viável de kits, em ambas as políticas. Veja a [decisão de arquitetura](docs/adr/001-politica-combos.md).

## O que é entregue

| Arquivo gerado | Finalidade |
| --- | --- |
| `proposta_conciliada.csv` | Todos os POIs, quantidade original/final, status e explicações |
| `fila_revisao.csv` | Subconjunto bloqueado por insuficiência ou inconsistência de dados |
| `balanco_estoque.csv` | Saldo inicial, consumo proposto e saldo simulado por CD/SKU |
| `resumo.json` | Métricas, política e resultado das verificações |
| `qualidade_dados.json` | Normalizações, duplicatas removidas e OTM órfão |
| `manifest.json` | SHA-256 das entradas, código e artefatos; identidade reproduzível do lote |
| `relatorio.html` | Conferência operacional offline |

Esses arquivos são uma **proposta para conferência**. Não há reserva transacional nem envio automático ao OMS ou ao faturamento.

## Critérios técnicos

- Quantidades inteiras; nunca aumentar o sugerido pelo OTM ou o pedido.
- Nunca superar o estoque agregado do mesmo CD/SKU, mesmo com pedidos concorrendo pelo saldo.
- Respeitar proporção de componentes e embalagem **simultaneamente** usando MDC/MMC.
- Não presumir fracionamento, estoque ou sucesso do OTM quando faltam dados.
- Não multiplicar linhas por joins de cardinalidade ambígua.
- Gerar um resultado por POI; separar revisão de dado faltante e redução por regra válida.
- Usar desempate lexical estável, sem alegar otimização global ou prioridade comercial.
- Publicar o diretório completo após verificar as pós-condições, sem sobrescrever evidências.

## Documentação para avaliação e apresentação

| Material | O que explica |
| --- | --- |
| [Matriz de aderência](docs/ADERENCIA.md) | Requisitos do enunciado, implementação e evidência |
| [Resultados por POI](docs/RESULTADOS.md) | Quantidades dos 12 itens, premissas e interpretação dos indicadores |
| [Arquitetura e formulação](docs/ARQUITETURA.md) | Restrições, prova do ajuste conjunto, limites e complexidade |
| [Contratos de dados](docs/CONTRATOS.md) | Chaves, formatos, normalização, falhas bloqueantes e quarentena |
| [Operação e evolução](docs/OPERACAO.md) | Comandos, códigos de saída, rollout, observabilidade e próximos passos |
| [Roteiro de apresentação](docs/APRESENTACAO.md) | Explicação de 5–7 minutos e respostas para perguntas técnicas |
| [Validação](docs/VALIDACAO.md) | Testes, busca exaustiva e medição sintética com limites explícitos |

## Por que um motor determinístico em um case de AI Engineer?

O problema apresentado contém restrições conhecidas e verificáveis; o enunciado não exige um LLM. A decisão de quantidade deve ser exata, reproduzível e barata de operar. Um assistente de IA pode evoluir para explicar decisões, agrupar causas de retrabalho e consultar procedimentos, sempre usando as evidências do motor e sem poder alterar quantidades ou autorizar faturamento. Essa extensão é discutida em [Arquitetura](docs/ARQUITETURA.md).

## Validação e limites

Os testes cobrem os dados originais, cadastros conflitantes, ausência de dados, concorrência pelo saldo, combos com caixas incompatíveis, códigos de saída, escrita interrompida e adulteração do resultado. Há também **600 cenários sintéticos** cuja solução é comparada a uma enumeração independente de todos os números viáveis de kits.

O volume de 12 POIs não permite estimar economia financeira, redução de tempo manual ou capacidade em milhões de linhas. O benchmark reproduzível mede apenas o motor e seu verificador, com massa sintética. Produção exige validação da política comercial, vínculo explícito de combo nos pedidos, data/versão da foto e reserva de estoque transacional.

Autoria da entrega: **Crizan Belém Ribeiro**. Case demonstrativo; não é um produto oficial do Grupo Boticário.
