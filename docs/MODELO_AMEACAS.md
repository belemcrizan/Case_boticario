# Modelo de ameaças e controles

Escopo: aplicação demonstrativa, API, pipeline e preparação GCP. Ativos: entradas do lote, decisões, inventário simulado, artefatos, identidade e trilha de auditoria. Fronteiras: navegador/API, API/SQL, API/Storage, API/Job e GitHub/GCP.

| Ameaça | Controle implementado | Evidência / limite |
| --- | --- | --- |
| Ler lote de outro usuário por UUID conhecido | Autorização por proprietário em cada recurso; 404 uniforme | Teste percorre consulta, decisão, inventário, artefatos, auditoria, simulação, retry e integridade |
| Forjar papel pelo frontend | Papel vem da sessão opaca ou de JWT IAP validado e mapa corporativo | Perfis somente leitura não executam; demo desativada em GCP |
| CSRF | Cookie HttpOnly/SameSite, token de sessão, verificação de Origin e Sec-Fetch-Site | GCP usa identidade IAP e origem HTTPS; testes cobrem origens e tokens inválidos |
| JWT falso, expirado ou de outro serviço | Verificação criptográfica pelo google-auth, audiência e issuer exatos, exp/iat e vida máxima | Contratos testados com claims e falhas simuladas; integração IAP real ainda pendente |
| Path traversal e arquivo arbitrário | Cinco nomes exatos; nenhum nome livre vira caminho; raiz de storage validada | Upload de `../pedidos_oms.csv` rejeitado |
| Consumo excessivo em uploads | 64 MiB por arquivo, 128 MiB por envio, cinco arquivos, parsing estrito | O proxy de produção deve reforçar tamanho e timeout; arquivo multipart é limitado pelo serviço |
| SQL injection | SQLAlchemy com parâmetros e allowlist de filtros/ordenação | Busca contendo SQL e wildcards literais testada |
| Fórmula maliciosa em planilha | IDs validados; textos perigosos prefixados por apóstrofo | Mantém o mecanismo original de CSV injection |
| XSS | Escape no relatório, renderização textual React, CSP, no HTML arbitrário | Testes de texto malicioso e análise de acessibilidade/fluxos |
| Alteração de entradas após validação | Fingerprint SHA-256 recalculado antes do cálculo | Entrada adulterada bloqueia execução |
| Artefato alterado | Hash antes do download, geração condicionada, armazenamento imutável | Download adulterado retorna 409; verificação de integridade reporta divergência |
| Duas execuções para a mesma requisição | Chave única por proprietário e fingerprint de dados/política | Repetição devolve mesma execução; conflito retorna 409 |
| Dois workers publicando o mesmo lote | Claim atômico, lease, fencing por tentativa, transação SQL | Testes concorrentes e worker antigo impedido de publicar |
| Custo por duplicação de Jobs | Admissão global limitada a quatro lotes, quota por proprietário, retries limitados | Não substitui rate limit do gateway ou budget financeiro |
| Exposição de segredos/logs | IAM/ADC/WIF, sem chaves estáticas; logs não recebem corpo, token, email ou DSN | Erro inesperado é reduzido a categoria; ator de auditoria usa hash |
| Dependência comprometida | Lockfiles, hashes Python, bases por digest e Actions fixadas | Scanning e SBOM em CI, com escopo explícito |

## Separação entre demo e acesso corporativo

O modo demo oferece perfis conhecidos e serve para execução local/entrevista. Não deve receber dados operacionais reais em uma rede pública. A configuração GCP exige identidade IAP, lista de papéis, origem HTTPS, bucket, Job e Cloud SQL. Falta de configuração interrompe a inicialização.

O frontend contém somente dados de teste em seus testes. Nenhum segredo de autenticação corporativa está no repositório. O exemplo de conta demo não equivale a autenticação de produção.

## Riscos residuais

- Administradores do banco/bucket podem alterar ou apagar dados; hashes não são assinaturas. Logs corporativos devem ter retenção e acesso separados para resistir a adulteração administrativa.
- O SQL contém identificadores operacionais. IAM, grants SQL, backup, retenção e restauração exigem verificação na organização.
- O limite de tamanho e as quotas não substituem proteção contra ataques de rede. Para exposição além do IAP corporativo, revisar políticas de gateway e limite por usuário/IP.
- Dumps e exports autorizados ainda podem conter informação sensível; não publicar bases reais neste repositório.
- A auditoria não implementa log criptográfico encadeado ou garantia de não repúdio.
- O modo demo local usa HTTP; o modo GCP depende do TLS gerenciado do serviço, com HSTS na aplicação.

## Segurança da extensão de IA

Nenhum modelo é usado no fluxo atual. A eventual extensão Vertex AI deve receber somente evidências autorizadas, tratar descrições como dados não confiáveis, responder em schema, conferir números contra o motor e cair em explicação determinística quando houver erro. Não terá ferramentas para alterar, reservar ou faturar. O desenho está em ADR-004.
