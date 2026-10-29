# Dados do case

Os cinco CSVs de `input/` foram extraídos do ZIP fornecido no desafio, sem editar os bytes originais. O enunciado e o ZIP original não são necessários para executar a solução e não integram o repositório.

| Arquivo | Registros sem cabeçalho |
| --- | ---: |
| `pedidos_oms.csv` | 12 |
| `saidas_otm.csv` | 11 |
| `foto_estoque_cd_05h.csv` | 11 |
| `de_para_combos.csv` | 7, sendo 1 duplicata idêntica |
| `regras_embalagem.csv` | 10 |

O parsing normaliza somente espaços externos em memória, registra as ocorrências e remove apenas a duplicata idêntica de componente do mesmo combo. A camada de origem permanece intacta.

Para executar com dados novos, crie outro diretório com esses mesmos cinco nomes e use `--input-dir`. Não publique dados operacionais reais neste repositório público.
