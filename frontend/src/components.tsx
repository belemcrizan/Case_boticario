import { useEffect, useRef, type ReactNode } from 'react';
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Info,
  LoaderCircle,
  X,
} from 'lucide-react';
import { ApiError, artifactUrl, number, policyLabel, type Decision } from './api';

export const statusLabels = {
  MANTIDO: 'Mantido',
  AJUSTADO: 'Ajustado',
  ZERADO: 'Zerado',
  REVISAO: 'Em revisão',
};
export function Status({ value }: { value: keyof typeof statusLabels }) {
  return (
    <span className={`status status-${value.toLowerCase()}`}>
      <i />
      {statusLabels[value]}
    </span>
  );
}
export function Help({ text }: { text: string }) {
  return (
    <span className="help">
      <button className="icon-button help-trigger" aria-label={text} type="button">
        <Info size={14} />
      </button>
      <span className="tooltip" role="tooltip">
        {text}
      </span>
    </span>
  );
}
export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <AlertCircle size={21} />
      <div>
        <strong>Não foi possível concluir</strong>
        <p>{error instanceof Error ? error.message : 'Tente novamente em alguns instantes.'}</p>
        {error instanceof ApiError && error.correlation && <small>Correlação: {error.correlation}</small>}
        {onRetry && (
          <button className="text-button" onClick={onRetry}>
            Tentar novamente <ArrowUpRight size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
export function Loading({ label = 'Carregando evidências…' }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={24} />
      <span>{label}</span>
    </div>
  );
}
export function Empty({
  title = 'Nenhum item encontrado',
  text = 'Ajuste os filtros para ampliar a consulta.',
}: {
  title?: string;
  text?: string;
}) {
  return (
    <div className="empty">
      <Check size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
export function Panel({
  title,
  sub,
  children,
  action,
  className = '',
}: {
  title: string;
  sub?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {sub && <p>{sub}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Download({
  id,
  name = 'proposta_conciliada.csv',
  label = 'Exportar proposta',
}: {
  id: string;
  name?: string;
  label?: string;
}) {
  return (
    <a className="button button-secondary" href={artifactUrl(id, name)} download>
      <ArrowDownToLine size={16} />
      {label}
    </a>
  );
}
export function Pager({
  total,
  page,
  size,
  onPage,
  onSize,
}: {
  total: number;
  page: number;
  size: number;
  onPage: (n: number) => void;
  onSize: (n: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <div className="pager">
      <span>
        {total ? number(page * size + 1) : '0'}–{number(Math.min(total, (page + 1) * size))} de{' '}
        {number(total)} itens
      </span>
      <div>
        <label>
          Por página{' '}
          <select aria-label="Itens por página" value={size} onChange={(e) => onSize(Number(e.target.value))}>
            <option>20</option>
            <option>50</option>
            <option>100</option>
          </select>
        </label>
        <span>
          {page + 1} / {pages}
        </span>
        <button
          className="icon-button"
          aria-label="Página anterior"
          disabled={page === 0}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft size={18} />
        </button>
        <button
          className="icon-button"
          aria-label="Próxima página"
          disabled={page + 1 >= pages}
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}
export function DecisionDrawer({ decision, onClose }: { decision: Decision | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (decision && !ref.current?.open) ref.current?.showModal();
    if (!decision && ref.current?.open) ref.current.close();
  }, [decision]);
  return (
    <dialog ref={ref} className="drawer" aria-labelledby="decision-title" onCancel={onClose}>
      <div className="drawer-head">
        <span className="eyebrow">Evidência da decisão</span>
        <button className="icon-button" aria-label="Fechar decisão" onClick={onClose}>
          <X size={22} />
        </button>
      </div>
      {decision && (
        <>
          <h2 id="decision-title">{decision.poi_id}</h2>
          <div className="inline">
            <span className="mono">{decision.sku}</span>
            <Status value={decision.status} />
          </div>
          <p className="muted">
            {decision.pedido_id} · {decision.cd_origem} · {decision.cod_franqueado}
          </p>
          <div className="decision-values">
            <div>
              <span>Pedido</span>
              <b>{number(decision.qtd_pedida)}</b>
            </div>
            <div>
              <span>OTM</span>
              <b>{number(decision.qtd_sugerida_otm)}</b>
            </div>
            <div>
              <span>Proposta</span>
              <b>{number(decision.qtd_final)}</b>
            </div>
          </div>
          <section className="explanation">
            <h3>Por que esta quantidade?</h3>
            <p>{decision.explanation}</p>
          </section>
          <h3>Restrições consideradas</h3>
          <dl className="facts">
            <div>
              <dt>Política</dt>
              <dd>{policyLabel(decision.constraints.policy)}</dd>
            </div>
            <div>
              <dt>Estoque informado no CD</dt>
              <dd>{number(decision.constraints.initial_stock)} peças</dd>
            </div>
            <div>
              <dt>Caixa master</dt>
              <dd>{number(decision.constraints.packaging_multiple)} peças</dd>
            </div>
            <div>
              <dt>Fracionamento</dt>
              <dd>
                {decision.constraints.fractionation_allowed == null
                  ? 'Não informado'
                  : decision.constraints.fractionation_allowed
                    ? 'Permitido'
                    : 'Não permitido'}
              </dd>
            </div>
            <div>
              <dt>Combo</dt>
              <dd>{decision.combo_id || 'Item avulso'}</dd>
            </div>
          </dl>
          {decision.combo_id && (
            <div className="ratio-grid">
              {Object.entries(decision.constraints.combo_components).map(([sku, qty]) => (
                <div key={sku}>
                  <b>{qty}×</b>
                  <span>{sku}</span>
                </div>
              ))}
            </div>
          )}
          <aside className="notice notice-compact">
            <Info size={18} />
            <p>{decision.next_action}</p>
          </aside>
          <details className="evidence-details">
            <summary>Fontes e rastreabilidade</summary>
            {decision.input_references.map((r) => (
              <div key={r.file}>
                <strong>{r.file}</strong>
                <small>Chave: {r.key}</small>
                <code>{r.sha256}</code>
              </div>
            ))}
          </details>
        </>
      )}
    </dialog>
  );
}
