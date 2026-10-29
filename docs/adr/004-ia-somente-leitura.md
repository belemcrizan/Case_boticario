# ADR 004 — Inteligência opcional somente leitura

Status: desenho futuro; **nenhuma chamada a Vertex AI/Gemini implementada**.

Motor determinístico é autoridade exclusiva. Explicações atuais são derivadas de campos verificáveis, sem LLM ou rede.

Um módulo futuro poderá receber apenas resumo, motivos e referências autorizadas de execução COMPLETED. Sua identidade não terá escrita ou ferramentas transacionais. Saída proposta: summary, claims[{text,evidence_ids}], uncertainties, refusal_reason. Referências devem existir na mesma execução acessível; números devem corresponder ao resumo. Rejeitar qualquer quantidade ou conclusão sem evidência.

Textos de CSV/documentos são dados não confiáveis: recusar instruções embutidas, URLs, mudança de papel e ferramentas. Minimizar dados pessoais, limitar tokens, tempo e custo, registrar prompt/modelo e desligar por padrão.

Antes de habilitar: corpus aprovado e adversarial para fidelidade numérica, cobertura de fontes, vazamento entre donos, injection, alucinação e latência. Falha volta à explicação determinística. Não há alegação de avaliação de alucinação ou integração Gemini executada.
