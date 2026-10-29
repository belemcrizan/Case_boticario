# Roteiro de apresentação | 5–7 minutos

## 1. Problema e decisão de arquitetura — 45 segundos

“O OTM faz o rateio matemático por SKU, mas o faturamento precisa respeitar o conjunto comercial e a embalagem física. Minha proposta é uma camada tática após o OTM. Ela não muda o legado: recebe os cinco arquivos, aplica restrições e produz uma proposta auditável, com fila de exceções.”

“Usei um motor determinístico porque estamos decidindo quantidades sujeitas a regras exatas. A solução não depende de modelo, credencial ou serviço externo para funcionar.”

## 2. Demonstrar o fluxo — 1 minuto

```bash
python app.py --output-dir output-demonstracao
```

Abrir o `relatorio.html` gerado. Mostrar os indicadores, filtrar `AJUSTADO` e depois `REVISAO`.

“A saída conserva os 12 POIs. Cada linha traz a demanda, o retorno original, a quantidade final e o motivo. O item sem dados não desaparece no join: ele fica visível e bloqueado.”

## 3. Explicar com números reais — 90 segundos

“No combo de barba, cada kit leva um aparelho e duas cargas. Vieram 5 e 7 do OTM. Tenho aparelhos para 5 kits, mas cargas para 3 kits. Por isso, a saída é 3 aparelhos e 6 cargas. A unidade de decisão é o kit completo.”

“Na embalagem de SKU-D2, recebi 110 peças e a caixa comporta múltiplos de 6. A saída é 108, ou 18 caixas. Já SKU-D1 tem só 8 peças para uma caixa de 12: a saída é zero. Arredondar para 12 inventaria peças que o OTM e o estoque não autorizaram.”

## 4. Explicitar a ambiguidade comercial — 1 minuto

“A regra ‘Zerar se incompleto’ permite duas leituras. No padrão conservador, interpretei que o lote 50:35 não deve ser parcialmente faturado e zerei o grupo. Isso gera 199 peças no total. Se a operação quiser preservar os kits completos, a configuração alternativa gera 35:35 nesse grupo e 269 peças no total. Ambas respeitam estoque e proporções; a escolha depende da regra comercial.”

“Eu registraria essa decisão com Comercial e Logística antes de integrar a proposta ao faturamento. Ela está versionada, aparece nos motivos e muda a identidade do lote.”

## 5. Demonstrar rigor — 1 minuto

“Há dez verificações antes de publicar a saída. O consumo é recalculado pela soma dos POIs e comparado ao estoque por CD e SKU. Não basta conferir cada linha isoladamente.”

“Os testes incluem os dados originais e 600 cenários em que comparo o resultado de combos a uma enumeração independente das soluções possíveis. Também verifico falhas de cadastro, duplicação, gravação interrompida e reprodução exata dos artefatos.”

Se houver tempo, executar:

```bash
python -m unittest discover -v
python scripts/check_examples.py
```

## 6. Fechar com limites e implantação — 45 segundos

“O demonstrador entrega proposta e evidência. A foto de estoque não traz data nem reserva concorrente. Para produção, eu começaria em sombra, mediria divergências contra o processo manual e só depois adicionaria estoque versionado e reserva transacional. Também precisaria do identificador explícito do combo no pedido.”

“O benchmark sintético exercitou 100 mil POIs, mas eu não apresentaria esse teste como prova de capacidade produtiva ou de ROI. Essas duas afirmações exigem validação no fluxo completo.”

## Perguntas prováveis

| Pergunta | Resposta objetiva |
| --- | --- |
| Por que não usar um LLM? | As quantidades obedecem restrições exatas. Um modelo pode explicar evidências, mas não é necessário para decidir este rateio com segurança. |
| Você maximizou o faturamento? | Calculo o maior número de kits viável para cada grupo elegível com o saldo atual. A política estrita pode zerar lotes; não prometo ótimo global entre pedidos. |
| E se dois pedidos disputarem o mesmo saldo? | Existe um único ledger por CD/SKU; os grupos consomem na ordem lexical estável. Em produção, prioridade comercial e reserva concorrente precisam ser homologadas. |
| Por que SKU-E2 não vale duas unidades? | A linha duplicada tem a mesma chave e todos os mesmos atributos. Deduplico e registro o aviso; conflito de atributos interromperia o lote. |
| Dá para faturar o mesmo lote duas vezes? | A aplicação não envia ao faturamento. O hash identifica a proposta; uma integração precisa de chave de idempotência e estado transacional persistido. |
| Como medir o sucesso? | Primeiro, zero violações físicas. Depois, medir tempo manual, toques por mil linhas, pendências por causa e aderência ao faturamento aprovado. |
| Por que não usar pandas ou solver? | A amostra e as regras podem ser resolvidas com índices e aritmética inteira. Evita dependências para a implantação tática; um solver faz sentido com objetivo comercial global definido. |
| Como isso escala? | A ordenação custa O(N log N), mas o demonstrador usa memória e HTML integral. Evoluiria partição por CD, ledger transacional e paginação com teste de carga do fluxo completo. |

Antes da reunião, execute o comando de demonstração com um diretório novo. Não memorize um ganho comercial não medido; priorize explicar os números, as premissas e os limites.
