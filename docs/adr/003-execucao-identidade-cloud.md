# ADR 003 — Jobs, identidade e objetos imutáveis

Status: código/Terraform implementados; validação sintática em CI; deploy não executado.

A API registra a execução antes do dispatch ao Cloud Run Jobs. Claim SQL torna duplicatas inofensivas. Tentativa e lease impedem publicação por worker obsoleto. FAILED recebe diagnóstico e retry explícito até três tentativas. Cloud Tasks não é necessário sem evidência de pressão de admissão ou agenda automática.

A janela SQL→dispatch pode deixar QUEUED sem job. O runbook prevê redispatch idempotente autorizado. Outbox/recuperação automática é requisito antes de produção contínua.

IAP direto no Cloud Run e validação JWT no servidor substituem perfis demo no GCP. GCS usa geração condicional, IAM sem overwrite e leitura presa à geração. WIF restringe CI a repositório e ambiente. Sem chaves estáticas.

Cloud SQL exige IAM/Connector e grants SQL. API e worker têm identidades separadas, mas o primeiro schema ainda usa DML amplo; refinar por tabela após homologar fluxos. Secret Manager é habilitado sem criar segredo artificial: o fluxo atual usa IAM sem senha estática.
