# Proveniência das verificações

Snapshot inicial aprovado do workflow [40907929789](https://github.com/belemcrizan/Case_boticario/actions/runs/40907929789), commit e945671e08dd4ef49bee308dd6883ab8956b6cf7, em 29/10/2026. Os checks do PR repetem os gates no último commit.

- python-audit.json: 63 dependências runtime API/GCP, zero vulnerabilidades conhecidas reportadas.
- sbom-python.json: CycloneDX das dependências de runtime fixadas por hash.
- sbom-node.json: CycloneDX do npm, incluindo dependências de desenvolvimento.
- trivy-image.json: scan OS/Python da imagem construída; filtro CRITICAL, zero achados no snapshot. Severidades inferiores não são descartadas nem declaradas inexistentes.
- terraform-validation.json: valid=true, zero erros e warnings; apenas configuração/schema.

A primeira imagem Bookworm falhou no gate por CVE-2025-7458 (sqlite) e CVE-2023-45853 (zlib). A entrega atual usa runtime Python sobre Debian Trixie, digest fixado, novamente construída e scanneada. Não foi criada allowlist para esconder os achados.

Referências primárias consultadas: [Debian/sqlite](https://security-tracker.debian.org/tracker/CVE-2025-7458), [Debian/zlib](https://security-tracker.debian.org/tracker/CVE-2023-45853). Manter scans periódicos: o resultado depende da base de vulnerabilidades e da data, não é garantia permanente.
