import { z } from 'zod';

export const userSchema = z.object({
  name: z.string(),
  role: z.enum(['operator', 'viewer', 'auditor', 'admin']),
  csrf_token: z.string(),
  environment: z.string(),
});
export type User = z.infer<typeof userSchema>;
const issueSchema = z.object({
  code: z.string(),
  severity: z.string(),
  source: z.string(),
  line: z.number(),
  key: z.string(),
  detail: z.string(),
});
const summarySchema = z.object({
  engine_run_id: z.string(),
  engine_version: z.string(),
  platform_version: z.string(),
  metrics: z.record(z.string(), z.number().nullable()),
  checks: z.record(z.string(), z.boolean()),
  policy: z.object({ incomplete_policy: z.string(), version: z.string() }),
  requires_review: z.boolean(),
  snapshot_timestamp: z.string().nullable(),
  review_state: z.string(),
  reasons: z.array(z.object({ code: z.string(), count: z.number() })),
  quality_issues: z.array(issueSchema),
  inputs_sha256: z.record(z.string(), z.string()),
  cds: z.array(z.string()),
  notice: z.string(),
  report_scope: z.object({ displayed_rows: z.number(), total_rows: z.number() }),
});
export const runSchema = z.object({
  id: z.string(),
  label: z.string(),
  policy: z.enum(['strict', 'complete-kits']),
  state: z.string(),
  kind: z.string(),
  parent_id: z.string().nullable(),
  created_at: z.number(),
  updated_at: z.number(),
  attempt: z.number(),
  summary: summarySchema.nullable(),
  failure: z.object({ code: z.string(), detail: z.string() }).nullable(),
  timings: z.record(z.string(), z.number()).nullable(),
  snapshot: z.string().nullable(),
});
export type Run = z.infer<typeof runSchema>;
export const decisionSchema = z.object({
  poi_id: z.string(),
  pedido_id: z.string(),
  cd_origem: z.string(),
  cod_franqueado: z.string(),
  sku: z.string(),
  qtd_pedida: z.number(),
  qtd_sugerida_otm: z.number().nullable(),
  qtd_final: z.number(),
  status: z.enum(['MANTIDO', 'AJUSTADO', 'ZERADO', 'REVISAO']),
  combo_id: z.string(),
  reasons: z.array(z.string()),
  explanation: z.string(),
  next_action: z.string(),
  constraints: z.object({
    demand_cap: z.number(),
    otm_cap: z.number().nullable(),
    initial_stock: z.number().nullable(),
    packaging_multiple: z.number().nullable(),
    fractionation_allowed: z.boolean().nullable(),
    combo_components: z.record(z.string(), z.number()),
    combo_rule: z.string().nullable(),
    policy: z.string(),
    stock_snapshot_timestamp: z.string().nullable(),
  }),
  input_references: z.array(z.object({ file: z.string(), key: z.string(), sha256: z.string() })),
});
export type Decision = z.infer<typeof decisionSchema>;
export const inventorySchema = z.object({
  cd_origem: z.string(),
  sku: z.string(),
  estoque_05h: z.number(),
  reservado_proposta: z.number(),
  saldo_simulado: z.number(),
});
export const pageSchema = <T extends z.ZodType>(schema: T) =>
  z.object({ items: z.array(schema), total: z.number(), limit: z.number(), offset: z.number() });
export const artifactsSchema = z.object({
  items: z.array(z.object({ name: z.string(), size: z.number(), sha256: z.string() })),
});
export const auditSchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      at: z.number(),
      action: z.string(),
      actor_hash: z.string(),
      detail: z.record(z.string(), z.unknown()),
    }),
  ),
});
export const validationSchema = z.object({
  valid: z.boolean(),
  orders: z.number(),
  files: z.record(z.string(), z.string()),
  issues: z.array(issueSchema),
  preview: z.array(z.object({ poi_id: z.string(), sku: z.string(), qtd_pedida: z.number() })),
  notice: z.string(),
});
export const integritySchema = z.object({
  valid: z.boolean(),
  artifacts: z.array(z.object({ name: z.string(), valid: z.boolean() })),
});
export const comparisonSchema = z.object({
  source_id: z.string(),
  target_id: z.string(),
  delta_units: z.number(),
  delta_percent: z.number().nullable(),
  affected_count: z.number(),
  items: z.array(
    z.object({
      poi_id: z.string(),
      sku: z.string(),
      before: z.number(),
      after: z.number(),
      combo_id: z.string(),
    }),
  ),
  limit: z.number(),
  notice: z.string(),
});

let csrfToken = '';
export const setCsrf = (token: string) => {
  csrfToken = token;
};
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public correlation = '',
  ) {
    super(message);
  }
}

export async function api<T>(path: string, schema: z.ZodType<T>, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api/v1${path}`, { credentials: 'same-origin', ...options, headers });
  const data: unknown = await response.json();
  if (!response.ok) {
    const parsed = z
      .object({ code: z.string().optional(), detail: z.string(), correlation_id: z.string().optional() })
      .safeParse(data);
    throw new ApiError(
      response.status,
      parsed.success ? (parsed.data.code ?? 'REQUEST_FAILED') : 'REQUEST_FAILED',
      parsed.success ? parsed.data.detail : 'Não foi possível completar a solicitação.',
      parsed.success ? parsed.data.correlation_id : undefined,
    );
  }
  const parsed = schema.safeParse(data);
  if (!parsed.success)
    throw new ApiError(
      502,
      'RESPONSE_CONTRACT',
      'A resposta não corresponde ao contrato. Atualize a página ou informe o suporte.',
    );
  return parsed.data;
}
export const post = <T>(path: string, schema: z.ZodType<T>, body: unknown = {}, idempotent = false) =>
  api(path, schema, {
    method: 'POST',
    body: JSON.stringify(body),
    headers: idempotent ? { 'Idempotency-Key': crypto.randomUUID() } : {},
  });
export const artifactUrl = (id: string, name: string) =>
  `/api/v1/reconciliations/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(name)}`;
export const number = (n: number | null | undefined) =>
  n == null ? '—' : new Intl.NumberFormat('pt-BR').format(n);
export const policyLabel = (policy: string) => (policy === 'strict' ? 'Conservadora' : 'Kits completos');
export const dateLabel = (seconds: number) =>
  new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(seconds * 1000);
export const reasonLabels: Record<string, string> = {
  COMBO_LOTE_INCOMPLETO_ZERADO: 'Lote de combo incompleto',
  AJUSTE_COMBO_COMPLETO: 'Proporção do combo',
  ARREDONDAMENTO_CAIXA_PARA_BAIXO: 'Múltiplo de embalagem',
  OTM_AUSENTE: 'Retorno OTM ausente',
  EMBALAGEM_AUSENTE: 'Cadastro de embalagem ausente',
  ESTOQUE_AUSENTE: 'Saldo não informado',
  DEMANDA_ZERO: 'Demanda zerada',
  OTM_ZERO: 'Sugestão zerada',
  LIMITE_ESTOQUE_COMPARTILHADO: 'Limite de estoque',
  POLITICA_PRESERVAR_KITS_COMPLETOS: 'Kits completos preservados',
  LIMITE_DEMANDA: 'Limite da demanda',
  SKU_DIVERGENTE: 'SKU divergente',
  COMPONENTE_COMBO_AUSENTE: 'Componente ausente',
};
