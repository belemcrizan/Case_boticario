import { useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  CheckCheck,
  Cloud,
  FileSpreadsheet,
  Fingerprint,
  GitCompareArrows,
  Info,
  LockKeyhole,
  Play,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react';
import {
  api,
  artifactsSchema,
  artifactUrl,
  auditSchema,
  comparisonSchema,
  dateLabel,
  integritySchema,
  number,
  policyLabel,
  post,
  runSchema,
  validationSchema,
  type Run,
  type User,
} from './api';
import { Empty, ErrorBox, Loading, Panel } from './components';

const FILES = [
  'pedidos_oms.csv',
  'saidas_otm.csv',
  'foto_estoque_cd_05h.csv',
  'de_para_combos.csv',
  'regras_embalagem.csv',
];
const FILE_LABELS = [
  'Demanda do OMS',
  'Sugestões do OTM',
  'Fotografia do estoque',
  'Estrutura dos combos',
  'Regras de embalagem',
];

export function ImportFlow({ user, onCreated }: { user: User; onCreated: (run: Run) => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [policy, setPolicy] = useState('strict');
  const [localError, setLocalError] = useState('');
  const [validation, setValidation] = useState<Awaited<ReturnType<typeof validateFiles>> | null>(null);
  const key = useRef(crypto.randomUUID());
  const input = useRef<HTMLInputElement>(null);
  async function validateFiles() {
    const body = new FormData();
    files.forEach((f) => body.append('files', f));
    return api('/validations', validationSchema, { method: 'POST', body });
  }
  const validate = useMutation({ mutationFn: validateFiles, onSuccess: setValidation });
  const create = useMutation({
    mutationFn: () => {
      const body = new FormData();
      files.forEach((f) => body.append('files', f));
      return api(`/reconciliations?policy=${policy}`, runSchema, {
        method: 'POST',
        body,
        headers: { 'Idempotency-Key': key.current },
      });
    },
    onSuccess: onCreated,
  });
  const example = useMutation({
    mutationFn: () => post('/examples', runSchema, { policy }, true),
    onSuccess: onCreated,
  });
  const canExecute = ['operator', 'admin'].includes(user.role);
  function choose(incoming: File[]) {
    setValidation(null);
    setLocalError('');
    validate.reset();
    create.reset();
    key.current = crypto.randomUUID();
    if (
      incoming.length !== 5 ||
      new Set(incoming.map((f) => f.name)).size !== 5 ||
      incoming.some((f) => !FILES.includes(f.name))
    ) {
      setFiles([]);
      setLocalError('Selecione os cinco CSVs originais com os nomes indicados abaixo.');
      return;
    }
    if (
      incoming.some((f) => f.size > 64 * 1024 * 1024) ||
      incoming.reduce((n, f) => n + f.size, 0) > 128 * 1024 * 1024
    ) {
      setFiles([]);
      setLocalError('Limite de 64 MiB por arquivo e 128 MiB no conjunto.');
      return;
    }
    setFiles(incoming);
  }
  return (
    <>
      <div className="intro-line">
        <div>
          <span className="eyebrow">Nova proposta</span>
          <h1>Importar e conciliar</h1>
          <p>Cinco fontes, uma sequência clara de validação.</p>
        </div>
        <span className="subtle-pill">
          <LockKeyhole size={13} /> Nenhum envio ao OMS
        </span>
      </div>
      <ol className="steps">
        {['Selecionar arquivos', 'Validar estrutura', 'Definir política', 'Executar proposta'].map((s, i) => (
          <li
            key={s}
            className={
              (files.length ? i === 0 : false) || (validation ? i <= 1 : false) ? 'step-complete' : ''
            }
          >
            <span>{(files.length && i === 0) || (validation && i === 1) ? <Check size={15} /> : i + 1}</span>
            {s}
          </li>
        ))}
      </ol>
      {!canExecute && (
        <aside className="notice">
          <p>Seu perfil permite consulta. Para importar, selecione o perfil demonstrativo de operações.</p>
        </aside>
      )}
      <div className="import-grid">
        <Panel title="1. Arquivos do lote" sub="CSV UTF-8. Até 64 MiB por arquivo e 128 MiB no total.">
          <div
            className="dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (canExecute) choose([...e.dataTransfer.files]);
            }}
          >
            <UploadCloud size={36} />
            <h3>Traga os cinco CSVs para cá</h3>
            <p>Ou selecione os arquivos no seu computador.</p>
            <button
              className="button button-secondary"
              disabled={!canExecute}
              onClick={() => input.current?.click()}
            >
              Selecionar arquivos
            </button>
            <input
              ref={input}
              className="sr-only"
              aria-label="Selecionar cinco arquivos CSV"
              type="file"
              accept=".csv,text/csv"
              multiple
              onChange={(e) => choose([...(e.target.files ?? [])])}
            />
          </div>
          {localError && (
            <p className="field-error" role="alert">
              {localError}
            </p>
          )}
          <ul className="file-list">
            {FILES.map((name, i) => {
              const file = files.find((f) => f.name === name);
              return (
                <li key={name}>
                  <FileSpreadsheet size={19} />
                  <div>
                    <strong>{FILE_LABELS[i]}</strong>
                    <small>{name}</small>
                  </div>
                  {file ? (
                    <span className="file-ready">
                      <Check size={14} />
                      {number(Math.ceil(file.size / 1024))} KB
                    </span>
                  ) : (
                    <span className="muted">Obrigatório</span>
                  )}
                </li>
              );
            })}
          </ul>
          <div className="form-actions">
            <button
              className="button button-primary"
              disabled={files.length !== 5 || validate.isPending || !canExecute}
              onClick={() => validate.mutate()}
            >
              {validate.isPending ? 'Validando…' : 'Validar arquivos'}
              <ArrowRight size={16} />
            </button>
          </div>
          {validate.error && <ErrorBox error={validate.error} />}
        </Panel>
        <div>
          <Panel title="2. Política comercial" sub="A escolha altera o tratamento de lotes incompletos.">
            <fieldset className="policy-options">
              <legend className="sr-only">Política de combo incompleto</legend>
              {[
                [
                  'strict',
                  'Conservadora',
                  'Preserva integralmente o lote viável ou zera o grupo incompleto.',
                ],
                [
                  'complete-kits',
                  'Preservar kits completos',
                  'Reduz o grupo à maior quantidade viável de kits completos.',
                ],
              ].map(([id, title, text]) => (
                <label className={policy === id ? 'selected' : ''} key={id}>
                  <input
                    type="radio"
                    name="policy"
                    value={id}
                    checked={policy === id}
                    onChange={() => {
                      setPolicy(id);
                      key.current = crypto.randomUUID();
                    }}
                  />
                  <div>
                    <strong>
                      {title}
                      {id === 'strict' && <small>Padrão do demonstrador</small>}
                    </strong>
                    <p>{text}</p>
                  </div>
                </label>
              ))}
            </fieldset>
            <aside className="quiet-note">
              <Info size={17} />
              <p>Ambas são premissas do demonstrador. A aplicação não homologa uma regra comercial.</p>
            </aside>
          </Panel>
          <Panel title="Experimentar com o case" sub="Use as cinco bases fornecidas, sem escolher arquivos.">
            <div className="example-card">
              <span>Dados originais</span>
              <b>
                12 <small>itens de pedido</small>
              </b>
              <p>Combos, embalagens e uma exceção de cadastro.</p>
              <button
                className="button button-secondary"
                disabled={!canExecute || example.isPending}
                onClick={() => example.mutate()}
              >
                <Play size={15} />
                {example.isPending ? 'Iniciando…' : 'Executar lote de exemplo'}
              </button>
            </div>
            {example.error && <ErrorBox error={example.error} />}
          </Panel>
        </div>
      </div>
      {validation && (
        <Panel
          title="3. Conferência da validação"
          sub={`${number(validation.orders)} POIs reconhecidos. As regras de quantidade serão aplicadas na execução.`}
        >
          <div className="validation-success">
            <CheckCheck size={20} />
            <strong>Os cinco arquivos atendem ao contrato estrutural.</strong>
          </div>
          {validation.issues.length > 0 && (
            <ul className="quality-list">
              {validation.issues.map((i, n) => (
                <li key={n}>
                  <span className="severity">{i.severity === 'WARNING' ? 'Alerta' : 'Informação'}</span>
                  <span>
                    {i.detail}
                    <small>
                      {i.source}, linha {i.line}
                    </small>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <details className="evidence-details">
            <summary>Prévia de até cinco registros da demanda</summary>
            <div
              className="table-wrap"
              role="region"
              aria-label="Tabela de dados, use as setas para rolar"
              tabIndex={0}
            >
              <table className="data-table">
                <thead>
                  <tr>
                    <th>POI</th>
                    <th>SKU</th>
                    <th>Pedido</th>
                  </tr>
                </thead>
                <tbody>
                  {validation.preview.map((p) => (
                    <tr key={p.poi_id}>
                      <td>{p.poi_id}</td>
                      <td>{p.sku}</td>
                      <td>{p.qtd_pedida}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <aside className="notice">
            <p>{validation.notice}</p>
          </aside>
          <div className="form-actions">
            <span>
              Política selecionada: <strong>{policyLabel(policy)}</strong>
            </span>
            <button
              className="button button-primary"
              disabled={!canExecute || create.isPending}
              onClick={() => create.mutate()}
            >
              <Play size={16} />
              {create.isPending ? 'Iniciando…' : 'Executar conciliação'}
            </button>
          </div>
          {create.error && <ErrorBox error={create.error} />}
        </Panel>
      )}
    </>
  );
}

export function Policies({
  run,
  runs,
  user,
  onRunAdded,
}: {
  run: Run;
  runs: Run[];
  user: User;
  onRunAdded: (r: Run) => void;
}) {
  const [targetId, setTargetId] = useState('');
  const candidate = runs.find(
    (r) =>
      r.id !== run.id &&
      r.state === 'COMPLETED' &&
      r.policy !== run.policy &&
      JSON.stringify(r.summary?.inputs_sha256) === JSON.stringify(run.summary?.inputs_sha256),
  );
  const id = targetId || candidate?.id;
  const target = useQuery({
    queryKey: ['run', id],
    queryFn: () => api(`/reconciliations/${id}`, runSchema),
    enabled: Boolean(id),
    refetchInterval: (q) =>
      q.state.data && !['COMPLETED', 'FAILED'].includes(q.state.data.state) ? 750 : false,
  });
  const comparison = useQuery({
    queryKey: ['comparison', run.id, id],
    queryFn: () => api(`/reconciliations/${run.id}/comparison/${id}`, comparisonSchema),
    enabled: Boolean(id && target.data?.state === 'COMPLETED'),
  });
  const simulate = useMutation({
    mutationFn: () =>
      post(
        `/reconciliations/${run.id}/simulations`,
        runSchema,
        { policy: run.policy === 'strict' ? 'complete-kits' : 'strict' },
        true,
      ),
    onSuccess: (r) => {
      setTargetId(r.id);
      onRunAdded(r);
    },
  });
  const a = run.summary?.metrics.unidades_finais;
  const b = target.data?.summary?.metrics.unidades_finais;
  return (
    <>
      <div className="intro-line">
        <div>
          <span className="eyebrow">Decisão comercial explícita</span>
          <h1>Simulador de políticas</h1>
          <p>Compare o mesmo conjunto de entradas sem alterar a proposta selecionada.</p>
        </div>
        <span className="simulation-label">Simulação não homologada</span>
      </div>
      <aside className="notice">
        <Info size={19} />
        <p>
          “Zerar se incompleto” admite duas interpretações. A segurança física é verificável; a escolha
          comercial exige homologação.
        </p>
      </aside>
      <div className="comparison-grid">
        <section className="scenario current">
          <span className="eyebrow">Proposta selecionada</span>
          <h2>{policyLabel(run.policy)}</h2>
          <b>
            {number(a)} <small>peças</small>
          </b>
          <p>
            {run.policy === 'strict'
              ? 'O lote de combo incompleto é zerado por inteiro.'
              : 'A maior quantidade viável de kits completos é preservada.'}
          </p>
          <span className="subtle-pill">Política {run.policy}</span>
        </section>
        <div className="compare-icon">
          <GitCompareArrows size={27} />
        </div>
        <section className="scenario">
          <span className="eyebrow">Cenário alternativo</span>
          <h2>{policyLabel(run.policy === 'strict' ? 'complete-kits' : 'strict')}</h2>
          <b>
            {number(b)} <small>peças</small>
          </b>
          <p>
            {run.policy === 'strict'
              ? 'Preserva kits completos mesmo quando o lote original é desbalanceado.'
              : 'Exige que o lote proposto esteja completo e proporcional.'}
          </p>
          {!id ? (
            <button
              className="button button-primary"
              disabled={!['operator', 'admin'].includes(user.role) || simulate.isPending}
              onClick={() => simulate.mutate()}
            >
              <Play size={15} />
              Calcular cenário
            </button>
          ) : target.data?.state !== 'COMPLETED' ? (
            <Loading label="Calculando cenário…" />
          ) : (
            <span className="subtle-pill">Mesmos cinco arquivos de entrada</span>
          )}
        </section>
      </div>
      {simulate.error && <ErrorBox error={simulate.error} />}
      {comparison.error && <ErrorBox error={comparison.error} />}
      {comparison.data && (
        <>
          <div className="comparison-result">
            <div>
              <span>Diferença absoluta</span>
              <b>
                {comparison.data.delta_units > 0 ? '+' : ''}
                {number(comparison.data.delta_units)} <small>peças</small>
              </b>
            </div>
            <div>
              <span>Diferença sobre a proposta selecionada</span>
              <b>
                {number(comparison.data.delta_percent)}
                <small>%</small>
              </b>
            </div>
            <div>
              <span>Itens afetados</span>
              <b>
                {number(comparison.data.affected_count)}
                <small>POIs</small>
              </b>
            </div>
            <div>
              <ShieldCheck size={20} />
              <span>Invariantes aprovadas nos dois cenários</span>
            </div>
          </div>
          <Panel
            title="Onde a política faz diferença"
            sub="Quantidades em peças. Até 100 diferenças por consulta."
          >
            {comparison.data.items.length ? (
              <div
                className="table-wrap"
                role="region"
                aria-label="Tabela de dados, use as setas para rolar"
                tabIndex={0}
              >
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>POI</th>
                      <th>SKU / combo</th>
                      <th className="numeric">Selecionada</th>
                      <th className="numeric">Alternativa</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.data.items.map((d) => (
                      <tr key={d.poi_id}>
                        <td>{d.poi_id}</td>
                        <td>
                          {d.sku}
                          <small>{d.combo_id}</small>
                        </td>
                        <td className="numeric">{number(d.before)}</td>
                        <td className="numeric emphasis">{number(d.after)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                title="As políticas produzem as mesmas quantidades"
                text="Neste conjunto de entradas, a interpretação de quebra não altera a proposta."
              />
            )}
          </Panel>
        </>
      )}
      <Panel title="Um exemplo para entender" sub="Números reais das bases do case.">
        <div className="explain-example">
          <div className="example-numbers">
            <span>
              <b>50</b> perfumes
            </span>
            <span>+</span>
            <span>
              <b>35</b> loções
            </span>
          </div>
          <div>
            <h3>Um kit precisa de uma unidade de cada produto.</h3>
            <p>
              A política conservadora zera o lote 50:35. A alternativa preserva 35 kits, ou 70 peças. Essa
              diferença explica a passagem de 199 para 269 peças na amostra original.
            </p>
          </div>
        </div>
      </Panel>
    </>
  );
}

const CHECK_LABELS: Record<string, string> = {
  conservacao_pois: 'Todos os itens preservados',
  identidade_linhas: 'Identidade dos pedidos mantida',
  inteiros_nao_negativos: 'Quantidades inteiras e não negativas',
  limite_demanda_otm: 'Limites de demanda e OTM',
  cadastros_obrigatorios: 'Cadastros obrigatórios respeitados',
  multiplos_caixa: 'Múltiplos de embalagem válidos',
  estoque_agregado_cd_sku: 'Estoque agregado por CD e SKU',
  combos_proporcionais: 'Proporções dos combos preservadas',
  politica_combo_estrita: 'Política de quebra respeitada',
  ledger_reconciliado: 'Consumo e saldo reconciliados',
};

export function Audit({ run }: { run: Run }) {
  const files = useQuery({
    queryKey: ['artifacts', run.id],
    queryFn: () => api(`/reconciliations/${run.id}/artifacts`, artifactsSchema),
  });
  const audit = useQuery({
    queryKey: ['audit', run.id],
    queryFn: () => api(`/reconciliations/${run.id}/audit`, auditSchema),
  });
  const integrity = useMutation({
    mutationFn: () => post(`/reconciliations/${run.id}/integrity`, integritySchema),
  });
  const s = run.summary!;
  return (
    <>
      <div className="intro-line">
        <div>
          <span className="eyebrow">Visão técnica</span>
          <h1>Qualidade e auditoria</h1>
          <p>A decisão pode ser conferida do arquivo de origem ao artefato final.</p>
        </div>
        <button
          className="button button-secondary"
          disabled={integrity.isPending}
          onClick={() => integrity.mutate()}
        >
          <Fingerprint size={17} />
          {integrity.isPending ? 'Verificando…' : 'Verificar integridade'}
        </button>
      </div>
      {integrity.data && (
        <div className={integrity.data.valid ? 'validation-success' : 'error-box'} role="status">
          <CheckCheck size={20} />
          {integrity.data.valid
            ? 'Os sete artefatos correspondem aos hashes registrados.'
            : 'Foi detectada divergência de integridade. Não utilizar os artefatos.'}
        </div>
      )}
      {integrity.error && <ErrorBox error={integrity.error} />}
      <div className="audit-grid">
        <Panel title="10 invariantes do motor" sub="Pós-condições recalculadas antes de publicar.">
          <ul className="check-list">
            {Object.entries(s.checks).map(([key, value]) => (
              <li key={key}>
                <span className={value ? 'check-circle' : 'error-circle'}>
                  <Check size={13} />
                </span>
                <span>{CHECK_LABELS[key] ?? key}</span>
                <strong>{value ? 'Aprovada' : 'Falhou'}</strong>
              </li>
            ))}
          </ul>
        </Panel>
        <div>
          <Panel title="Identidade e contexto">
            <dl className="facts">
              <div>
                <dt>Motor / plataforma</dt>
                <dd>
                  {s.engine_version} / {s.platform_version}
                </dd>
              </div>
              <div>
                <dt>Política / versão</dt>
                <dd>
                  {run.policy} / {s.policy.version}
                </dd>
              </div>
              <div>
                <dt>Início da execução</dt>
                <dd>{dateLabel(run.created_at)}</dd>
              </div>
              <div>
                <dt>Tentativa</dt>
                <dd>{run.attempt}</dd>
              </div>
              <div>
                <dt>Foto de estoque</dt>
                <dd>05h, data não informada</dd>
              </div>
              <div>
                <dt>Estado de conferência</dt>
                <dd>Pendente de validação humana</dd>
              </div>
            </dl>
            <label className="hash-label">
              Identidade determinística do motor<code>{s.engine_run_id}</code>
            </label>
            <details className="evidence-details">
              <summary>Tempos medidos nesta execução</summary>
              {Object.entries(run.timings ?? {}).map(([stage, seconds]) => (
                <div className="timing" key={stage}>
                  <span>{stage}</span>
                  <b>{number(seconds)} s</b>
                </div>
              ))}
            </details>
          </Panel>
          <Panel title="Qualidade das entradas" sub="Normalizações e avisos registrados.">
            <ul className="quality-list">
              {s.quality_issues.map((i, n) => (
                <li key={n}>
                  <span className="severity">{i.severity === 'WARNING' ? 'Alerta' : 'Info'}</span>
                  <span>
                    {i.detail}
                    <small>
                      {i.source}:{i.line}
                    </small>
                  </span>
                </li>
              ))}
            </ul>
            {!s.quality_issues.length && (
              <p className="muted">Nenhuma normalização ou duplicata detectada.</p>
            )}
          </Panel>
        </div>
      </div>
      <Panel
        title="Artefatos e integridade"
        sub="Downloads autenticados. Hashes detectam divergência, sem substituir uma assinatura de origem."
      >
        {files.error ? (
          <ErrorBox error={files.error} />
        ) : (
          <div className="artifact-list">
            {files.data?.items.map((f) => (
              <div key={f.name}>
                <FileSpreadsheet size={22} />
                <div>
                  <strong>{f.name}</strong>
                  <small>{number(Math.ceil(f.size / 1024))} KB</small>
                  <code>{f.sha256}</code>
                </div>
                <a
                  className="icon-button"
                  aria-label={`Baixar ${f.name}`}
                  href={artifactUrl(run.id, f.name)}
                  download
                >
                  <ArrowDownToLine size={18} />
                </a>
              </div>
            ))}
          </div>
        )}
      </Panel>
      <Panel title="Trilha da execução" sub="Ações reais registradas pela aplicação. Últimos 100 eventos.">
        <ul className="timeline">
          {audit.data?.items.map((e) => (
            <li key={e.id}>
              <span className="timeline-dot" />
              <div>
                <strong>{e.action}</strong>
                <p>{dateLabel(e.at)}</p>
                <small>Ator: {e.actor_hash.slice(0, 16)}…</small>
              </div>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Origem das cinco bases">
        <div className="source-hashes">
          {Object.entries(s.inputs_sha256).map(([name, hash]) => (
            <div key={name}>
              <strong>{name}</strong>
              <code>{hash}</code>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}

export function Architecture() {
  return (
    <>
      <div className="intro-line">
        <div>
          <span className="eyebrow">Preparação para Google Cloud</span>
          <h1>Arquitetura e implantação</h1>
          <p>Uma aplicação verificável localmente, com fronteiras explícitas para a nuvem.</p>
        </div>
        <span className="subtle-pill">
          <Cloud size={14} /> Implantação GCP não executada
        </span>
      </div>
      <Panel
        title="Componentes e responsabilidades"
        sub="O mesmo motor atende ao terminal, à API e ao worker."
      >
        <div className="architecture-flow">
          <div className="arch-node">
            <LockKeyhole />
            <h3>IAP</h3>
            <p>Identidade corporativa e acesso autorizado.</p>
          </div>
          <span className="arch-connector">→</span>
          <div className="arch-node accent">
            <Cloud />
            <h3>Cloud Run</h3>
            <p>Frontend e API na mesma origem.</p>
          </div>
          <span className="arch-connector">→</span>
          <div className="arch-node">
            <Play />
            <h3>Cloud Run Jobs</h3>
            <p>Execução assíncrona, com lease e retries limitados.</p>
          </div>
        </div>
        <div className="arch-storage">
          <div>
            <strong>Cloud SQL PostgreSQL</strong>
            <p>Estados, auditoria e consultas paginadas por proprietário.</p>
          </div>
          <div>
            <strong>Cloud Storage</strong>
            <p>Entradas e artefatos imutáveis, versionados e com retenção.</p>
          </div>
          <div>
            <strong>Logging e Monitoring</strong>
            <p>Eventos, métricas e alertas com severidade definida.</p>
          </div>
        </div>
      </Panel>
      <div className="dashboard-columns">
        <Panel title="O que já pode ser conferido">
          <ul className="plain-checks">
            <li>
              <Check size={16} />
              Motor, API e experiência de demonstração locais.
            </li>
            <li>
              <Check size={16} />
              Contratos, identidade de lote e acesso por recurso.
            </li>
            <li>
              <Check size={16} />
              Testes, containers e infraestrutura como código no repositório.
            </li>
            <li>
              <Check size={16} />
              Execução sem modelo de IA e sem serviço pago.
            </li>
          </ul>
        </Panel>
        <Panel title="O que exige ambiente autorizado">
          <ul className="plain-checks">
            <li>
              <Info size={16} />
              Configuração inicial do OAuth/IAP e papéis corporativos.
            </li>
            <li>
              <Info size={16} />
              Deploy, conectividade, migrações e testes no GCP.
            </li>
            <li>
              <Info size={16} />
              Homologação comercial e prioridade de estoque.
            </li>
            <li>
              <Info size={16} />
              Contrato transacional com OMS/WMS para reserva real.
            </li>
          </ul>
        </Panel>
      </div>
      <aside className="notice">
        <ShieldCheck size={20} />
        <p>
          O demonstrador não reserva estoque, não fatura pedidos e não utiliza LLM para alterar quantidades.
          Acesso cloud pronto para configuração não significa operação homologada.
        </p>
      </aside>
      <Panel title="Uma adoção em etapas">
        <div className="adoption">
          <div>
            <span>01</span>
            <h3>Homologar regras</h3>
            <p>Validar a semântica de quebra e o vínculo dos combos.</p>
          </div>
          <div>
            <span>02</span>
            <h3>Operar em sombra</h3>
            <p>Comparar com a conferência manual e medir divergências.</p>
          </div>
          <div>
            <span>03</span>
            <h3>Pilotar com controle</h3>
            <p>Limitar escopo, registrar revisão e ensaiar recuperação.</p>
          </div>
          <div>
            <span>04</span>
            <h3>Integrar com reserva</h3>
            <p>Adicionar idempotência e estoque versionado no destino.</p>
          </div>
        </div>
      </Panel>
    </>
  );
}
