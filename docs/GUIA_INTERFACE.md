# Guia da interface

## Começar

Execute conforme o README e entre como analista. O seletor superior oferece strict e complete-kits do case, compartilhados somente no demo. O rodapé troca a perspectiva demonstrativa entre operação, gestão e auditoria. Perfis de consulta não executam conciliações.

O tema claro/escuro persiste no navegador. No celular, abra o menu no topo. Use Tab, Enter/Espaço e Escape para fechar a decisão. Há link “Ir para o conteúdo” ao receber foco.

## Jornadas

1. **Visão geral:** confira OTM, proposta, retenção e situação. Ajuda contextual explica unidades e denominadores. Causas podem se sobrepor: sua soma não é o total de itens.
2. **Importar lote:** selecione os cinco nomes originais, valide, confira prévias/problemas, escolha política e execute. Limites: 64 MiB/arquivo, 128 MiB/envio. A tela acompanha o estado assíncrono.
3. **Conciliação por item:** busque POI/pedido/SKU, filtre situação/CD, ordene e escolha colunas. Paginação no servidor. Abra a seta para conferir demanda, OTM, proposta, caixa, combo, saldo, cálculo, hashes e ação recomendada.
4. **Fila de revisão:** SKU-GHOST está zero por dados ausentes. Corrija a origem e crie outro lote; a interface não libera quantidade manualmente.
5. **Estoque por CD:** saldo inicial, consumo proposto e saldo simulado. Não há reserva nem estoque em tempo real.
6. **Simulador:** mesmas entradas sob duas políticas. Novo cenário exige operador/admin e preserva a origem. 199/269 peças; dois componentes mudam em 35 cada.
7. **Qualidade e auditoria:** dez verificações, qualidade, versão, identidade, tempos e eventos. Verifique integridade e baixe os sete artefatos.
8. **Arquitetura GCP:** componentes e adoção propostos, sem alegação de deploy.

## Indicadores

| Nome | Definição / unidade | Cuidado |
| --- | --- | --- |
| OTM | Soma de sugestão associada aos POIs, peças | Retornos órfãos ficam em qualidade |
| Proposta | Soma das quantidades finais, peças | Não é aprovação operacional |
| Retenção | 100 × proposta / OTM | Sem OTM não há percentual; não é economia |
| Situação | POIs por status / total de POIs | Revisão representa dado faltante/ambíguo |
| Redução | OTM − proposta, peças | Não converter em reais sem medição |
| Invariantes | Pós-condições aprovadas / verificações | Aprovação técnica não homologa política |

## Glossário

**POI:** item rastreável do pedido. **CD:** centro de distribuição. **Combo:** componentes em proporção comercial. **Caixa master:** múltiplo obrigatório sem fracionamento. **Foto de estoque:** saldo do arquivo, sem data real fornecida. **Hash:** identifica conteúdo e detecta alteração. **Simulação:** proposta derivada não homologada.

Bloqueio exige corrigir informação; alerta pede conferência; informação contextualiza. Etiquetas possuem texto além da cor.

## Erros e limites

Arquivo/coluna inválida: corrija e revalide os cinco. Permissão negada: use identidade autorizada. Falha inesperada: informe correlation ID à engenharia sem dados sensíveis. Retry é limitado e não substitui corrigir a causa.

Não há aprovação de faturamento nem edição de quantidade. O seletor lista os 100 lotes mais recentes acessíveis; a API pagina o histórico. Testes automatizados de acessibilidade não equivalem a certificação WCAG; leitor de tela e avaliação humana permanecem no plano de homologação.
