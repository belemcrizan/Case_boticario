# Operação, rollout e evolução

> Referência do motor e da CLI originais. A plataforma v2, sua operação e as evidências adicionais estão em [ENTREGA_FINAL.md](ENTREGA_FINAL.md).

## Executar o demonstrador

```bash
python app.py --help
python app.py --input-dir data/input --output-dir output-ciclo-01
python app.py --input-dir data/input --output-dir output-ciclo-01-alternativo --incomplete-policy complete-kits
```

Use um diretório de saída novo por execução. Não existe opção de sobrescrita. Saídas relativas são resolvidas a partir do diretório atual; o input padrão é relativo ao projeto.

Para validar em um pipeline que deve parar quando existem pendências:

```bash
python app.py --output-dir output-gate --fail-on-review
```

| Código | Significado |
| --- | --- |
| 0 | Resultado calculado, invariantes aprovadas e evidências geradas; ainda pode haver revisão se o gate não foi solicitado |
| 1 | Invariante violada; não foi publicado lote |
| 2 | Entrada, argumentos ou destino inválidos / falha de I/O |
| 3 | Resultado e evidências gerados, mas há revisão com `--fail-on-review` |

Na base original, o gate retorna 3 por causa de `SKU-GHOST`. Isso não é falha de cálculo. A fila é parte do resultado esperado. A execução padrão retorna 0, registra `requires_review: true` e mantém o item bloqueado.

## Conferência operacional

1. Confirmar se os cinco arquivos são da mesma carteira/lote e se o saldo da foto ainda é válido.
2. Confirmar a interpretação de “Zerar se incompleto” e a prioridade entre pedidos.
3. Executar em modo de proposta e conferir `resumo.json`, `qualidade_dados.json` e `fila_revisao.csv`.
4. Validar os casos de combo e caixa no relatório, incluindo o contraste entre políticas quando aplicável.
5. Resolver pendências na origem e gerar **novo lote completo**. Não editar manualmente quantidade de um componente dentro do artefato publicado.
6. Somente após homologação, integrar com reserva transacional e validação de versão de estoque no sistema de destino.

Uma aprovação parcial futura precisa operar sobre grupos de combo inteiros e reservar o saldo do lote aprovado. O demonstrador não implementa aprovação, integração ou reenvio.

## Gravação e recuperação

Um lock exclusivo por destino impede dois escritores da aplicação no mesmo diretório. Os artefatos são preparados em um diretório temporário irmão e publicados por rename após a conclusão. Exceções comuns limpam o temporário e o lock. Diretórios existentes são recusados.

Essa publicação é local, não uma transação distribuída ou garantia de durabilidade contra falha de hardware. Uma interrupção forçada do processo pode deixar um lock ou temporário residual. Preferir novo diretório; remover resíduos apenas após confirmar que não há execução ativa e que as evidências foram preservadas. Nenhum mecanismo local impede outro sistema de consumir a mesma foto simultaneamente.

O `run_id` identifica entradas, política e código; não implementa sozinho exactly-once no OMS. Uma integração deve ter uma chave de idempotência persistida e comparar o estado do lote/estoque antes do commit de faturamento.

## Plano tático para a próxima semana

| Fase | Entrega / critério de saída |
| --- | --- |
| Homologar premissas | Operação e Comercial concordam com quebra, escopo e prioridade; fechar exemplos esperados |
| Rodar em sombra | Comparar propostas ao ajuste manual em lotes reais sem enviar ao faturamento |
| Revisar divergências | Classificar divergências por regra, cadastro e fotografia; nenhuma violação física aceita |
| Piloto controlado | Escopo limitado de CDs/ciclo, conferência humana e plano de reversão definido |
| Integração | Reserva/versão do estoque e consumidor idempotente antes de automatizar liberação |

O cronograma depende do acesso aos dados e da capacidade de validação da operação. O case entrega o processador e evidências para iniciar essa homologação, sem declarar que o fluxo produtivo já está aprovado.

## Observabilidade e avaliação de valor

O terminal emite um evento JSON de conclusão com política, `run_id`, métricas e diretório de saída; erros saem em stderr. Os JSONs mantêm resultados detalhados para análise posterior.

Monitorar quantidade de POIs por status, motivos de ajuste/revisão, violações (tolerância zero), disponibilidade e idade das entradas, duração e falhas por lote. Para medir valor, comparar tempo de conferência manual por mil linhas, toques manuais por motivo e divergência entre proposta aprovada e faturamento.

**Exemplo ilustrativo, não medido pelo case:** se um lote de 10 mil linhas exige 5 horas de intervenção e o piloto reduzir para 2 horas, a economia de tempo será `(5 - 2) / 5 = 60%`. É necessário medir os dois tempos e a qualidade do faturamento para sustentar essa afirmação.

## Evoluções priorizadas

| Prioridade | Evolução | Por que vem nessa ordem |
| --- | --- | --- |
| P0 | ID de instância de combo, política homologada, lote/data e prioridade comercial | Remove inferências que alteram quantidade |
| P0 | Foto com versão, estoque líquido reservável e reserva concorrente no destino | Evita depender de saldo obsoleto ou alocação dupla |
| P1 | Armazenamento de lotes e aprovação por grupo; integração idempotente | Torna a proposta um fluxo operacional controlado |
| P1 | Partição por CD, ledger transacional e relatórios paginados | Permite testar escala sem perder conservação de estoque |
| P2 | Otimização com CP-SAT/MILP, se houver autorização para alterar rateio | Requer objetivo explícito: atendimento, equidade, SLA ou margem |
| P2 | Assistente somente leitura para explicação e triagem | Reduz navegação operacional sem delegar restrições físicas ao modelo |

Reversão: interromper o consumidor automático e retornar ao processo homologado de conferência; preservar lotes e decisões para reconciliar o que já foi reservado/faturado. A aplicação atual apenas produz arquivos locais e não precisa de rollback no core.
