import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  Boxes,
  ChevronDown,
  CircleHelp,
  Cloud,
  FileCheck2,
  GitCompareArrows,
  LayoutDashboard,
  Menu,
  Moon,
  Plus,
  ShieldCheck,
  Sun,
  TriangleAlert,
  UploadCloud,
  X,
} from 'lucide-react';
import {
  ApiError,
  api,
  number,
  pageSchema,
  post,
  runSchema,
  setCsrf,
  userSchema,
  type Decision,
  type Run,
  type User,
} from './api';
import { DecisionDrawer, Empty, ErrorBox, Loading } from './components';
import Overview from './Overview';
import Decisions, { Inventory } from './Decisions';
import { Architecture, Audit, ImportFlow, Policies } from './Workflows';

const NAV = [
  { id: 'overview', label: 'Visão geral', icon: LayoutDashboard },
  { id: 'import', label: 'Importar lote', icon: UploadCloud },
  { id: 'decisions', label: 'Conciliação por item', icon: FileCheck2 },
  { id: 'exceptions', label: 'Fila de revisão', icon: TriangleAlert },
  { id: 'inventory', label: 'Estoque por CD', icon: Boxes },
  { id: 'policies', label: 'Simulador de políticas', icon: GitCompareArrows },
  { id: 'audit', label: 'Qualidade e auditoria', icon: ShieldCheck },
  { id: 'architecture', label: 'Arquitetura GCP', icon: Cloud },
];

function Login({
  onLogin,
  error,
  pending,
}: {
  onLogin: (profile: User['role']) => void;
  error: unknown;
  pending: boolean;
}) {
  return (
    <main className="login-screen">
      <div className="login-story">
        <div className="brand">
          <span className="brand-mark">
            <ShieldCheck size={25} />
          </span>
          <span>
            otm<span className="brand-guard">guard</span>
          </span>
        </div>
        <span className="eyebrow">Conciliação operacional</span>
        <h1>
          Entenda cada decisão.
          <br />
          Confira cada quantidade.
        </h1>
        <p>Uma camada de confiança entre o rateio do OTM e a realidade da operação.</p>
        <div className="login-proof">
          <ShieldCheck size={20} />
          <span>Regras determinísticas. Evidências por item.</span>
        </div>
        <small>
          Projeto demonstrativo de Crizan Belém Ribeiro.
          <br />
          Sem vínculo com um produto oficial do Grupo Boticário.
        </small>
      </div>
      <section className="login-form">
        <span className="subtle-pill">Ambiente demonstrativo local</span>
        <h2>Explore o OTM Guard</h2>
        <p>Use os dados fornecidos pelo case. A demonstração funciona sem conectar ao GCP.</p>
        <button
          className="button button-primary login-primary"
          disabled={pending}
          onClick={() => onLogin('operator')}
        >
          {pending ? 'Abrindo demonstração…' : 'Acessar como analista'}
          <ArrowRight size={18} />
        </button>
        <div className="login-other">
          <span>Ou escolha uma perspectiva</span>
          <button onClick={() => onLogin('viewer')} disabled={pending}>
            Gestão e diretoria <ArrowRight size={16} />
          </button>
          <button onClick={() => onLogin('auditor')} disabled={pending}>
            Engenharia e auditoria <ArrowRight size={16} />
          </button>
        </div>
        {Boolean(error) && <ErrorBox error={error} />}
        <p className="login-disclosure">
          <CircleHelp size={16} />
          As identidades desta tela são demonstrativas. No GCP, o acesso exige identidade corporativa validada
          pelo IAP.
        </p>
      </section>
    </main>
  );
}

export default function App() {
  const client = useQueryClient();
  const [view, setView] = useState('overview');
  const [selectedId, setSelectedId] = useState('demo-strict');
  const [decision, setDecision] = useState<Decision | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('otm-theme') ?? 'light');
  const me = useQuery({ queryKey: ['me'], queryFn: () => api('/me', userSchema) });
  useEffect(() => {
    if (me.data) setCsrf(me.data.csrf_token);
  }, [me.data]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('otm-theme', theme);
  }, [theme]);
  const login = useMutation({
    mutationFn: (profile: User['role']) => post('/auth/demo-session', userSchema, { profile }),
    onSuccess: (user) => {
      setCsrf(user.csrf_token);
      client.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' });
      client.setQueryData(['me'], user);
      setSelectedId('demo-strict');
      setView('overview');
    },
  });
  const runs = useQuery({
    queryKey: ['runs', me.data?.role],
    queryFn: () => api('/reconciliations?limit=100', pageSchema(runSchema)),
    enabled: Boolean(me.data),
  });
  const activeId = runs.data?.items.some((r) => r.id === selectedId) ? selectedId : runs.data?.items[0]?.id;
  const run = useQuery({
    queryKey: ['selected-run', activeId, me.data?.role],
    queryFn: () => api(`/reconciliations/${activeId}`, runSchema),
    enabled: Boolean(activeId && me.data),
    refetchInterval: (q) =>
      q.state.data && !['COMPLETED', 'FAILED'].includes(q.state.data.state) ? 750 : false,
  });
  const navigate = (page: string) => {
    setView(page);
    setMobileNav(false);
    setDecision(null);
    document.getElementById('main-content')?.focus();
  };
  const created = (r: Run) => {
    client.setQueryData(['runs', me.data?.role], (old: typeof runs.data) =>
      old
        ? { ...old, items: [r, ...old.items.filter((i) => i.id !== r.id)], total: old.total + 1 }
        : { items: [r], total: 1, limit: 100, offset: 0 },
    );
    setSelectedId(r.id);
    navigate('overview');
    void client.invalidateQueries({ queryKey: ['runs'] });
  };
  if (me.isPending) return <Loading label="Abrindo o centro de conciliação…" />;
  if (!me.data) {
    if (me.error && (!(me.error instanceof ApiError) || me.error.status !== 401))
      return (
        <div className="standalone-error">
          <ErrorBox error={me.error} onRetry={() => void me.refetch()} />
        </div>
      );
    return <Login onLogin={(p) => login.mutate(p)} pending={login.isPending} error={login.error} />;
  }
  const user = me.data;
  const current = run.data;
  const requiresRun = !['import', 'architecture'].includes(view);
  const approved = current?.summary && Object.values(current.summary.checks).every(Boolean);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Ir para o conteúdo
      </a>
      {mobileNav && (
        <button className="nav-backdrop" aria-label="Fechar navegação" onClick={() => setMobileNav(false)} />
      )}
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <a
            href="#main-content"
            className="brand-link"
            aria-label="OTM Guard, início"
            onClick={() => navigate('overview')}
          >
            <span className="brand-mark">
              <ShieldCheck size={23} />
            </span>
            <span>
              otm<span className="brand-guard">guard</span>
            </span>
          </a>
          <button
            className="mobile-close icon-button"
            aria-label="Fechar menu"
            onClick={(e) => {
              e.preventDefault();
              setMobileNav(false);
            }}
          >
            <X size={19} />
          </button>
        </div>
        <div className="workspace">
          <span className="workspace-icon">
            <Boxes size={19} />
          </span>
          <div>
            <strong>Operações & logística</strong>
            <small>Centro de conciliação</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <span className="nav-label">Workspace</span>
        <nav aria-label="Navegação principal">
          {NAV.map(({ id, label, icon: Icon }, i) => (
            <div key={id}>
              {i === 5 && <span className="nav-label nav-label-second">Inteligência e controle</span>}
              <button
                className={view === id ? 'nav-active' : ''}
                aria-current={view === id ? 'page' : undefined}
                onClick={() => navigate(id)}
              >
                <Icon size={18} />
                <span>{label}</span>
                {id === 'exceptions' && Boolean(current?.summary?.metrics.linhas_revisao) && (
                  <b className="nav-count">{current?.summary?.metrics.linhas_revisao}</b>
                )}
              </button>
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-assurance">
            <ShieldCheck size={22} />
            <strong>Confiança por evidência</strong>
            <p>Cada quantidade pode ser explicada e conferida.</p>
          </div>
          <button className="nav-help" onClick={() => navigate('architecture')}>
            <CircleHelp size={18} />
            Como funciona
            <ArrowRight size={14} />
          </button>
          <small>v2.0 · Projeto demonstrativo</small>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu icon-button"
              aria-label="Abrir menu"
              onClick={() => setMobileNav(true)}
            >
              <Menu size={22} />
            </button>
            <span>Operações</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{NAV.find((n) => n.id === view)?.label}</strong>
          </div>
          <div className="topbar-actions">
            <span className={`engine-state ${approved ? '' : 'engine-pending'}`}>
              <i />
              {approved ? 'Motor verificado' : 'Aguardando resultado'}
            </span>
            <button
              className="icon-button"
              aria-label={theme === 'light' ? 'Ativar modo escuro' : 'Ativar modo claro'}
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <div className="avatar" aria-label={user.name}>
              {user.role === 'viewer' ? 'GE' : user.role === 'auditor' ? 'AU' : 'OP'}
            </div>
          </div>
        </header>
        <div className="contextbar">
          <label>
            <span>Lote selecionado</span>
            <select
              aria-label="Lote selecionado"
              value={activeId ?? ''}
              onChange={(e) => {
                setSelectedId(e.target.value);
                setDecision(null);
              }}
              disabled={!runs.data?.items.length}
            >
              {runs.data?.items.length ? (
                runs.data.items.map((r) => (
                  <option value={r.id} key={r.id}>
                    {r.label}
                    {r.state !== 'COMPLETED' ? ` · ${r.state}` : ''}
                  </option>
                ))
              ) : (
                <option>Nenhum lote disponível</option>
              )}
            </select>
          </label>
          <div>
            <span className="demo-indicator">
              <i />
              {user.environment === 'gcp' ? 'Acesso corporativo' : 'Demonstração'}
            </span>
            <button className="button button-primary button-small" onClick={() => navigate('import')}>
              <Plus size={15} />
              Nova conciliação
            </button>
          </div>
        </div>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {runs.error ? (
            <ErrorBox error={runs.error} onRetry={() => void runs.refetch()} />
          ) : view === 'import' ? (
            <ImportFlow user={user} onCreated={created} />
          ) : view === 'architecture' ? (
            <Architecture />
          ) : requiresRun && !activeId ? (
            <Empty
              title="Comece com uma conciliação"
              text="Importe os cinco CSVs ou execute o lote de exemplo pela tela de importação."
            />
          ) : run.isPending ? (
            <Loading />
          ) : run.error ? (
            <ErrorBox error={run.error} onRetry={() => void run.refetch()} />
          ) : current?.state === 'FAILED' ? (
            <ErrorBox
              error={new Error(current.failure?.detail ?? 'A execução falhou. Consulte a auditoria.')}
            />
          ) : current?.state !== 'COMPLETED' ? (
            <section className="processing">
              <Loading label="Conciliação em processamento" />
              <h1>Estamos verificando a proposta.</h1>
              <p>Os resultados só ficam disponíveis depois das verificações e da publicação completa.</p>
              <span className="subtle-pill">
                {current?.state} · tentativa {current?.attempt}
              </span>
            </section>
          ) : (
            current.summary && (
              <>
                {current.kind === 'SIMULATION' && (
                  <aside className="notice">
                    <GitCompareArrows size={18} />
                    <p>Simulação não homologada. A proposta de origem permanece intacta.</p>
                  </aside>
                )}
                {view === 'overview' && (
                  <Overview run={current} onNavigate={navigate} onDecision={setDecision} />
                )}
                {['decisions', 'exceptions'].includes(view) && (
                  <Decisions
                    key={`${view}:${current.id}`}
                    run={current}
                    exceptions={view === 'exceptions'}
                    onDecision={setDecision}
                  />
                )}
                {view === 'inventory' && <Inventory key={current.id} run={current} />}
                {view === 'policies' && (
                  <Policies
                    key={current.id}
                    run={current}
                    runs={runs.data?.items ?? []}
                    user={user}
                    onRunAdded={() => void client.invalidateQueries({ queryKey: ['runs'] })}
                  />
                )}
                {view === 'audit' && <Audit key={current.id} run={current} />}
              </>
            )
          )}
        </main>
        <footer className="app-footer">
          <span>
            OTM Guard <span>·</span> Propostas verificáveis, conferência humana.
          </span>
          <div>
            {user.environment !== 'gcp' && (
              <label>
                Perfil demonstrativo{' '}
                <select
                  aria-label="Perfil demonstrativo"
                  value={user.role}
                  onChange={(e) => login.mutate(e.target.value as User['role'])}
                >
                  <option value="operator">Operações</option>
                  <option value="viewer">Gestão</option>
                  <option value="auditor">Auditoria</option>
                </select>
              </label>
            )}
            <span>{number(current?.summary?.metrics.linhas_oms)} POIs no lote</span>
          </div>
        </footer>
      </div>
      <DecisionDrawer decision={decision} onClose={() => setDecision(null)} />
    </div>
  );
}
