# Demonstração de 5–7 minutos

Instale/construa antes da entrevista, inicie localmente e confira os dois cenários. Não depende de GCP, LLM ou serviços pagos. Use somente dados do case e massas sintéticas identificadas.

| Tempo | Tela / ação | Mensagem |
| --- | --- | --- |
| 0:00–0:45 | Login → Visão geral strict | OTM distribui; camada externa verifica consistência operacional |
| 0:45–1:30 | Cards e situações | 12 POIs, 297 sugeridas, 199 propostas, 1 revisão; redução não é economia |
| 1:30–2:15 | Buscar SKU-D2 → abrir decisão | 110 → 108 peças, 18 caixas de seis; evidência por item |
| 2:15–3:00 | Combo de barba e Simulador | 5:7 → 3:6 em kits 1:2; comparar 199/269 com premissa comercial |
| 3:00–3:40 | Fila de revisão | SKU-GHOST zero; ausência não autoriza faturamento |
| 3:40–4:30 | Auditoria | Dez invariantes, hashes; verificar e exportar CSV/HTML |
| 4:30–5:20 | Importar os cinco CSVs | Validar prévia, escolher política e executar outro lote |
| 5:20–6:00 | Arquitetura GCP | IAP, API, Job, SQL e GCS; nenhum deploy executado |
| 6:00–6:40 | Adoção | Piloto em sombra, regras homologadas e valor medido |

## Perguntas difíceis

**Por que não alterar OTM?** Consistência comercial/física ocorre após rateio. Camada externa preserva core e permite conferência independente.

**Por que não LLM no cálculo?** Quantidades exigem exatidão e prova. Explicações atuais são determinísticas; IA futura somente leitura.

**199 ou 269 é melhor?** Políticas diferentes e ambas tecnicamente válidas. Homologar “zerar se incompleto”; padrão preservado.

**Há ótimo global?** Não alegado. Desempate lexical; MILP isolado demonstra conflito entre peças, pedidos completos e equidade.

**Um milhão está homologado?** Não. Benchmark sintético local: 152,31 s e 1,42 GiB RSS. Rede, SQL real e usuários exigem carga própria.

**Duas execuções reservam saldo?** Não há reserva. Cada lote propõe sobre seus arquivos; integração exige transação no sistema de estoque.

**Pode ir para produção?** Faltam homologação comercial, instâncias/snapshot, identidade, grants, carga, restauração, rollback e contrato OMS/WMS.
