# Resultados e interpretação

Números desta seção são calculados a partir dos cinco CSVs originais. Política padrão: `strict`, versão de regra `1.0.0`.

| POI | SKU | Pedido | OTM | Final | Status | Motivo principal |
| --- | --- | ---: | ---: | ---: | --- | --- |
| POI-1001 | SKU-A1 | 50 | 50 | 0 | ZERADO | Combo 1:1 com lote 50:35; política estrita |
| POI-1002 | SKU-A2 | 50 | 35 | 0 | ZERADO | Mesmo grupo do POI-1001 |
| POI-1003 | SKU-B1 | 20 | 10 | 10 | MANTIDO | Limites respeitados |
| POI-1004 | SKU-K1 | 10 | 5 | 3 | AJUSTADO | Maior combo de barba: 3 kits |
| POI-1005 | SKU-K2 | 20 | 7 | 6 | AJUSTADO | Duas cargas por kit |
| POI-1006 | SKU-D1 | 10 | 8 | 0 | ZERADO | 8 peças não formam caixa de 12 |
| POI-1007 | SKU-D2 | 120 | 110 | 108 | AJUSTADO | 18 caixas de 6 |
| POI-1008 | SKU-E1 | 30 | 30 | 30 | MANTIDO | SkinCare completo 1:1 |
| POI-1009 | SKU-E2 | 30 | 30 | 30 | MANTIDO | Duplicata de cadastro removida, sem somar proporções |
| POI-1010 | SKU-X1 | 15 | 12 | 12 | MANTIDO | SKU normalizado; 2 caixas de 6 |
| POI-1011 | SKU-GHOST | 100 | ausente | 0 | REVISAO | OTM, embalagem e estoque ausentes |
| POI-1012 | SKU-B1 | 0 | 0 | 0 | MANTIDO | Demanda e sugestão zeradas |
| **Total** | | **455** | **297** | **199** | | |

## Métricas e seus denominadores

- Retenção sobre o OTM: `199 / 297 = 67,00%`. Considera apenas sugestões de POIs presentes no OMS; OTM órfão não entra.
- Atendimento da demanda: `199 / 455 = 43,74%`. Inclui toda a demanda, inclusive os 100 itens de `SKU-GHOST` bloqueados.
- Redução em relação ao OTM: `297 - 199 = 98 peças`. Não é economia financeira nem comprovação de menor retrabalho.
- Revisão: 1 de 12 POIs, com três causas associadas. Contar cada causa como uma linha distinta inflaria a fila.
- Mantidos: 5 POIs, incluindo o item já zerado. “Mantido” significa quantidade preservada, não quantidade positiva.

Não há preço, tempo de trabalho, curva de demanda ou histórico de faturamento na base. ROI, redução de falsos positivos e ganho de produtividade dependem de medição adicional.

## Sensibilidade da política de combo

Com `complete-kits`, apenas o combo Dia das Mães muda nesta amostra: 35 perfumes e 35 loções substituem os dois zeros. O saldo de `SKU-A2` em `CD_SP` cai de 35 para 0 e a proposta sobe em 70 peças, de 199 para **269**.

O resultado alternativo mantém a segurança física e as proporções, mas muda a interpretação comercial da quebra. A escolha deve ser homologada pela operação, registrada por versão de política e aplicada a um lote inteiro.

## Diagnóstico das anomalias fornecidas

| Anomalia observada | Tratamento | Por que isso importa |
| --- | --- | --- |
| `SKU-E2` repetido no mesmo combo com os mesmos atributos | Deduplicar em memória e registrar aviso | Evita dobrar a proporção ou multiplicar linhas no join |
| Espaço ao final de `SKU-X1` no OMS e no OTM | `strip` antes dos joins e duas ocorrências de auditoria | Evita falso cadastro inexistente |
| Demanda `SKU-GHOST` sem retorno e cadastros | Zero + revisão, preservando POI e quantidade pedida | Evita desaparecer com demanda em um inner join |
| `SKU-D1`: OTM 8, caixa 12, estoque 8 | Zero, sem arredondar para 12 | Arredondar para cima excederia OTM, demanda e estoque |
| `SKU-D2`: OTM 110, caixa 6 | 108 | Respeita embalagem sem inventar 4 peças para chegar a 114 |
| OTM já zerado em pedido de quantidade zero | Manter zero com motivos explícitos | Evita dividir por zero ou inventar consumo |
