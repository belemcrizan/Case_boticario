import { useQuery } from '@tanstack/react-query';
import {
  ArrowDownRight,
  ArrowRight,
  Boxes,
  CheckCheck,
  CircleHelp,
  FileCheck2,
  PackageCheck,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react';
import {
  api,
  decisionSchema,
  number,
  pageSchema,
  policyLabel,
  reasonLabels,
  type Decision,
  type Run,
} from './api';
import { Download, Help, Panel, Status } from './components';

export default function Overview({
  run,
  onNavigate,
  onDecision,
}: {
  run: Run;
  onNavigate: (page: string) => void;
  onDecision: (d: Decision) => void;
}) {
  const summary = run.summary!;
  const m = summary.metrics;
  const { data } = useQuery({
    queryKey: ['recent', run.id],
    queryFn: () => api(`/reconciliations/${run.id}/decisions?limit=5`, pageSchema(decisionSchema)),
  });
  const statuses = [
    { code: 'MANTIDO', name: 'Mantidos', value: m.linhas_mantidas ?? 0, color: 'var(--chart-green)' },
    { code: 'AJUSTADO', name: 'Ajustados', value: m.linhas_ajustadas ?? 0, color: 'var(--chart-blue)' },
    { code: 'ZERADO', name: 'Zerados', value: m.linhas_zeradas ?? 0, color: 'var(--chart-neutral)' },
    { code: 'REVISAO', name: 'Em revisão', value: m.linhas_revisao ?? 0, color: 'var(--chart-amber)' },
  ];
  const circumference = 2 * Math.PI * 66;
  let used = 0;
  const arcs = statuses.map((s) => {
    const fraction = s.value / (m.linhas_oms || 1);
    const offset = used;
    used += fraction * circumference;
    return { ...s, length: fraction * circumference, offset };
  });
  const causes = summary.reasons
    .filter((r) => !['OTM_ZERO', 'DEMANDA_ZERO', 'POLITICA_PRESERVAR_KITS_COMPLETOS'].includes(r.code))
    .slice(0, 5);
  const maxCause = Math.max(1, ...causes.map((r) => r.count));
  return (
    <>
      <div className="intro-line">
        <div>
          <span className="eyebrow">Controle do fechamento de ciclo</span>
          <h1>Visão geral da conciliação</h1>
          <p>Uma proposta verificável, do rateio matemático à realidade da operação.</p>
        </div>
        <Download id={run.id} />
      </div>
      <section className="run-banner">
        <div className="run-banner-icon">
          <ShieldCheck size={26} />
        </div>
        <div>
          <div className="inline">
            <strong>{run.label}</strong>
            <span className="subtle-pill">
              {run.label.includes('Case original') ? 'Dados do case' : 'Lote importado'}
            </span>
          </div>
          <p>
            {number(m.linhas_oms)} itens de pedido <span>·</span> Política{' '}
            {policyLabel(run.policy).toLowerCase()} <span>·</span> Proposta para conferência
          </p>
        </div>
        <button className="text-button" onClick={() => onNavigate('audit')}>
          Ver evidências <ArrowRight size={16} />
        </button>
      </section>
      <div className="kpi-grid">
        <article className="kpi">
          <div className="kpi-top">
            <span>Quantidade sugerida</span>
            <Boxes size={18} />
          </div>
          <div className="kpi-value">
            {number(m.unidades_otm)}
            <span>peças</span>
          </div>
          <p>
            Retorno original do OTM{' '}
            <Help text="Soma das sugestões dos POIs presentes no OMS. Não inclui sugestões órfãs." />
          </p>
        </article>
        <article className="kpi kpi-highlight">
          <div className="kpi-top">
            <span>Proposta conciliada</span>
            <PackageCheck size={19} />
          </div>
          <div className="kpi-value">
            {number(m.unidades_finais)}
            <span>peças</span>
          </div>
          <p>
            <ArrowDownRight size={14} /> {number(m.unidades_reduzidas_vs_otm)} peças ajustadas às restrições{' '}
            <Help text="Diferença entre a quantidade OTM e a proposta. Não representa economia financeira." />
          </p>
        </article>
        <article className="kpi">
          <div className="kpi-top">
            <span>Retenção sobre o OTM</span>
            <FileCheck2 size={18} />
          </div>
          <div className="kpi-value">
            {number(m.retencao_vs_otm_pct)}
            <span>%</span>
          </div>
          <p>
            {number(m.unidades_finais)} ÷ {number(m.unidades_otm)} peças{' '}
            <Help text="Percentual da sugestão OTM preservado na proposta. O denominador é a quantidade sugerida associada ao OMS." />
          </p>
        </article>
        <article className="kpi">
          <div className="kpi-top">
            <span>Itens em revisão</span>
            <TriangleAlert size={18} />
          </div>
          <div className="kpi-value">
            {number(m.linhas_revisao)}
            <span>POI</span>
          </div>
          <p>
            De {number(m.linhas_oms)} itens no lote{' '}
            <Help text="Itens bloqueados por falta ou divergência de dados. Cada POI é contado uma única vez, mesmo com várias causas." />
          </p>
          <button className="kpi-link" onClick={() => onNavigate('exceptions')}>
            Conferir pendências <ArrowRight size={13} />
          </button>
        </article>
      </div>
      <div className="dashboard-columns">
        <Panel
          title="Situação dos itens"
          sub="Cada item de pedido aparece uma única vez."
          action={
            <Help text="POI significa item de pedido. Ajustado: quantidade reduzida e positiva. Zerado: quantidade reduzida a zero por uma regra válida. Revisão: dados insuficientes ou divergentes." />
          }
        >
          <div className="distribution">
            <div className="donut">
              <svg
                viewBox="0 0 164 164"
                role="img"
                aria-label={statuses.map((s) => `${s.value} ${s.name.toLowerCase()}`).join(', ')}
              >
                <circle cx="82" cy="82" r="66" fill="none" stroke="var(--line)" strokeWidth="16" />
                {arcs.map((s) => (
                  <circle
                    key={s.code}
                    cx="82"
                    cy="82"
                    r="66"
                    fill="none"
                    stroke={s.color}
                    strokeWidth="16"
                    strokeDasharray={`${Math.max(0, s.length - 2)} ${circumference}`}
                    strokeDashoffset={-s.offset}
                    transform="rotate(-90 82 82)"
                  />
                ))}
              </svg>
              <div>
                <b>{number(m.linhas_oms)}</b>
                <span>itens no lote</span>
              </div>
            </div>
            <div className="status-legend">
              {statuses.map((s) => (
                <button
                  key={s.code}
                  onClick={() => onNavigate(s.code === 'REVISAO' ? 'exceptions' : 'decisions')}
                >
                  <span>
                    <i style={{ background: s.color }} />
                    {s.name}
                  </span>
                  <b>{number(s.value)}</b>
                  <small>{number(Math.round((100 * s.value) / (m.linhas_oms || 1)))}%</small>
                </button>
              ))}
            </div>
          </div>
          <div className="panel-foot">
            <CheckCheck size={15} />
            <span>Todos os {number(m.linhas_oms)} POIs foram preservados na proposta.</span>
          </div>
        </Panel>
        <Panel
          title="O que explica os ajustes?"
          sub="Ocorrências por motivo, incluindo bloqueios."
          action={
            <Help text="Um POI pode ter mais de um motivo. A soma das ocorrências pode superar o total de itens." />
          }
        >
          <div className="reason-chart">
            {causes.map((c) => (
              <div key={c.code}>
                <div>
                  <span>{reasonLabels[c.code] ?? c.code}</span>
                  <b>{c.count}</b>
                </div>
                <div className="bar-track">
                  <span style={{ width: `${(100 * c.count) / maxCause}%` }} />
                </div>
              </div>
            ))}
          </div>
          <button className="panel-action" onClick={() => onNavigate('decisions')}>
            Explorar as decisões <ArrowRight size={15} />
          </button>
        </Panel>
      </div>
      <div className="next-actions">
        <div>
          <span className="eyebrow">Próximos passos</span>
          <h2>Da proposta à conferência</h2>
        </div>
        <button onClick={() => onNavigate('exceptions')}>
          <span className="action-number">01</span>
          <div>
            <strong>Resolver pendências de dados</strong>
            <p>{number(m.linhas_revisao)} item(ns) exige(m) conferência na origem.</p>
          </div>
          <ArrowRight size={18} />
        </button>
        <button onClick={() => onNavigate('policies')}>
          <span className="action-number">02</span>
          <div>
            <strong>Homologar a política comercial</strong>
            <p>Compare o efeito de preservar kits completos.</p>
          </div>
          <ArrowRight size={18} />
        </button>
      </div>
      <Panel
        title="Decisões do lote"
        sub="Do número original à justificativa da proposta."
        action={
          <button className="text-button" onClick={() => onNavigate('decisions')}>
            Ver todos os itens <ArrowRight size={15} />
          </button>
        }
      >
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Item / SKU</th>
                <th>Origem</th>
                <th className="numeric">OTM</th>
                <th className="numeric">Proposta</th>
                <th>Situação</th>
                <th>
                  <span className="sr-only">Detalhes</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((d) => (
                <tr key={d.poi_id}>
                  <td>
                    <strong>{d.poi_id}</strong>
                    <small>{d.sku}</small>
                  </td>
                  <td>{d.cd_origem}</td>
                  <td className="numeric">{number(d.qtd_sugerida_otm)}</td>
                  <td className="numeric emphasis">{number(d.qtd_final)}</td>
                  <td>
                    <Status value={d.status} />
                  </td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Ver decisão ${d.poi_id}`}
                      onClick={() => onDecision(d)}
                    >
                      <ArrowRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <aside className="quiet-note">
        <CircleHelp size={16} />
        <p>
          A fotografia de estoque não informa uma data. Confirme sua atualidade antes de qualquer integração.
          Os valores desta tela são calculados sobre os arquivos fornecidos.
        </p>
      </aside>
    </>
  );
}
