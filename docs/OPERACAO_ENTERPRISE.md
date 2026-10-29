# Operação, homologação e implantação

## Escopo de execução

Demo local: SQLite e objetos privados em disco, sessões de perfis conhecidos, dois lotes do case. Usar somente em máquina de demonstração ou rede controlada. GCP: JWT IAP obrigatório, mapa de identidades, GCS, PostgreSQL e Jobs; demo e criação automática de schema desativados.

| Variável | Demo / GCP |
| --- | --- |
| OTM_ENV | demo ou gcp |
| OTM_DATA_DIR | Temporários/dados locais; GCP não persiste nesse disco |
| OTM_DATABASE_URL | Override local opcional; nunca registrar DSN |
| OTM_PUBLIC_ORIGIN | Origem exata; HTTPS obrigatório GCP |
| OTM_IAP_AUDIENCE | Audiência exata do serviço protegido |
| OTM_IDENTITIES_JSON | Mapa email → operator/viewer/auditor/admin, administrado no servidor |
| GOOGLE_CLOUD_PROJECT, OTM_REGION | Projeto e região autorizados |
| OTM_BUCKET, OTM_JOB_NAME | Objetos e worker |
| OTM_SQL_INSTANCE, OTM_SQL_USER, OTM_SQL_DATABASE | Connector IAM, usuário sem sufixo .gserviceaccount.com |
| OTEL_EXPORTER_OTLP_ENDPOINT | Opcional; configurar coletor autorizado |

Requisições mutáveis exigem origem autorizada e papel; no demo, cookie HttpOnly/SameSite Strict e X-CSRF-Token. Criação exige Idempotency-Key (8–128 caracteres). Replay da mesma chave/entradas retorna a mesma execução; chave reutilizada com conteúdo diferente falha 409.

## Limites e recuperação

Máximo de quatro execuções ativas no banco, dois workers locais, até três tentativas, lease e timeout inicial de 30 min. Cada tentativa publica em prefixo próprio e usa fencing. Nenhuma mudança manual em quantidade ou estado pelo navegador.

| Estado / incidente | Procedimento |
| --- | --- |
| FAILED por contrato | Corrigir as cinco entradas e criar nova execução |
| FAILED transitório | Conferir eventos/correlation ID e solicitar POST /api/v1/reconciliations/{id}/retry, operador/admin |
| RUNNING com lease válido | Aguardar; não concorrer nem apagar evidências |
| RUNNING com lease expirado | Confirmar Job anterior parado e usar retry autorizado |
| QUEUED sem Job | Confirmar ausência de execução no GCP; redisparar o mesmo run_id com adapter dispatch_job, sem mudar SQL |
| UPLOADING abandonado | Investigar processo e objetos; recuperação/expurgo administrativo ainda não automatizados |
| Hash divergente | Bloquear download/uso, preservar evidência e investigar acesso |
| SQL indisponível | /readyz retorna 503; corrigir dependência antes de promover tráfego |

Redispatch deve ser executado por operador técnico com identidade da API e parâmetros de ambiente, não pelo usuário final. Claim torna duplicatas inofensivas. A ausência de outbox/reconciliador automático de UPLOADING/QUEUED é limitação explícita para operação contínua.

## Preparar GCP em ambiente autorizado

1. Criar projetos separados dev/staging/production, faturamento, budget, estado Terraform remoto com controle de acesso e lock. Os tfvars.example são modelos, não credenciais nem projetos reais.
2. Configurar identidade corporativa/IAP e revisar política de rede, região e retenção. Público em run.app continua protegido por IAP; validar esse comportamento efetivamente.
3. Construir/scannear imagem, publicar no Artifact Registry e obter digest imutável. Bootstrap inicial do registry/IaC requer operador autorizado; não há autoapply em CI.
4. Executar init/fmt/validate, revisar plan e somente então apply autorizado. Terraform validate verifica configuração e schema, sem comprovar recursos, quotas ou permissões reais.
5. Criar schema com identidade temporária de migração autorizada e `python -m platform_api.manage migrate`, usando variáveis GCP e privilégios DDL. O comando inicial usa create_all; mudanças futuras exigem migração versionada.
6. DBA concede CONNECT no banco, USAGE no schema public e SELECT/INSERT/UPDATE/DELETE nas tabelas às identidades API/worker criadas por Terraform; grants adicionais para sequências se aplicáveis. Usar identificadores SQL entre aspas e os nomes IAM retornados pelo provisionamento. Remover DDL do runtime; não conceder superuser.
7. Configurar ambiente GitHub staging com revisores/proteção de branch e variáveis dos outputs: GCP_PROJECT_ID, GCP_REGION, GCP_ARTIFACT_REPOSITORY, GCP_SERVICE_NAME, GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_DEPLOY_SERVICE_ACCOUNT.
8. Workflow manual staging exige gates aprovados no SHA e usa WIF. Cria revisão sem tráfego. Não executado nesta entrega.

As service accounts de runtime não armazenam chaves. Secret Manager fica disponível para futuras integrações, sem segredo fictício. Não colocar token, senha ou tfvars reais no git.

## Homologação e promoção progressiva

Testar: usuários válidos/inválidos, audiência/expiração JWT, acesso entre donos, grants DML, limites CSV, conexão Connector, escrita GCS sem overwrite, Job duplicado, morte durante publicação, retry/lease, integridade, restauração de backup, lifecycle, carga representativa e faturamento em sombra. Registrar evidências e responsáveis.

Candidato API sem tráfego deve usar a mesma versão aprovada de worker; a atualização do Job exige procedimento separado. Evitar mistura de schema incompatível. Após aceite, operador autorizado promove 5%, 25% e 100%, observando métricas/erros e um lote sintético. Nenhuma promoção ocorre automaticamente.

Rollback: manter digest e nomes da revisão anterior e da imagem do Job, retornar tráfego à revisão anterior e atualizar Job para o digest compatível. Pausar novos lotes, verificar claims e não reaplicar lote ao OMS. Migrations devem ser compatíveis com versão anterior; restaurar backup somente com plano aprovado, para não perder auditoria recente. Testar rollback em staging antes do aceite produtivo.

Terraform declara tráfego latest=100 no bootstrap. Um apply posterior pode sobrescrever distribuição manual: revisar plan e coordenar com promoção. Não executar apply incidental durante canário.

## Retenção e dados

Bucket: lifecycle padrão 30 dias, versionamento e soft delete de sete dias. A remoção física pode ocorrer depois da janela e gerar custo adicional. Objetos órfãos expiram; não há rotina de expurgo SQL automatizada. Definir política de metadados/auditoria, legal hold, backup e anonimização com governança antes de dados reais. Idade de snapshot desconhecida impede liberação operacional.

O estado SQL é fonte das consultas; arquivos são evidência imutável. Backup sem teste de restauração não é garantia de recuperação. Não foi feito restore ou rollback GCP nesta entrega.
