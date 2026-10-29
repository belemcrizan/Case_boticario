import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type VisibilityState,
} from '@tanstack/react-table';
import { ArrowDownUp, ArrowRight, Search, SlidersHorizontal } from 'lucide-react';
import {
  api,
  decisionSchema,
  inventorySchema,
  number,
  pageSchema,
  reasonLabels,
  type Decision,
  type Run,
} from './api';
import { Download, Empty, ErrorBox, Loading, Pager, Panel, Status } from './components';

export default function Decisions({
  run,
  exceptions = false,
  onDecision,
}: {
  run: Run;
  exceptions?: boolean;
  onDecision: (d: Decision) => void;
}) {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState(exceptions ? 'REVISAO' : '');
  const [cd, setCd] = useState('');
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const [sort, setSort] = useState('poi_id');
  const [descending, setDescending] = useState(false);
  const [visibility, setVisibility] = useState<VisibilityState>({ cod_franqueado: false, qtd_pedida: false });
  const params = new URLSearchParams({
    search,
    status,
    cd,
    sort,
    descending: String(descending),
    limit: String(size),
    offset: String(page * size),
  });
  const query = useQuery({
    queryKey: ['decisions', run.id, params.toString()],
    queryFn: ({ signal }) =>
      api(`/reconciliations/${run.id}/decisions?${params}`, pageSchema(decisionSchema), { signal }),
    placeholderData: keepPreviousData,
  });
  const change = (fn: () => void) => {
    fn();
    setPage(0);
  };
  const columns: ColumnDef<Decision>[] = [
    {
      accessorKey: 'poi_id',
      header: 'Item de pedido',
      cell: (c) => (
        <>
          <strong>{String(c.getValue())}</strong>
          <small>{c.row.original.pedido_id}</small>
        </>
      ),
    },
    {
      accessorKey: 'sku',
      header: 'SKU',
      cell: (c) => (
        <>
          <span className="mono">{String(c.getValue())}</span>
          {c.row.original.combo_id && <small className="combo-tag">Parte de combo</small>}
        </>
      ),
    },
    { accessorKey: 'cd_origem', header: 'CD' },
    { accessorKey: 'cod_franqueado', header: 'Franqueado' },
    { accessorKey: 'qtd_pedida', header: 'Pedido', cell: (c) => number(c.getValue() as number) },
    { accessorKey: 'qtd_sugerida_otm', header: 'OTM', cell: (c) => number(c.getValue() as number | null) },
    {
      accessorKey: 'qtd_final',
      header: 'Proposta',
      cell: (c) => <b className="emphasis">{number(c.getValue() as number)}</b>,
    },
    { accessorKey: 'status', header: 'Situação', cell: (c) => <Status value={c.row.original.status} /> },
    {
      id: 'reason',
      header: 'Motivo',
      cell: (c) => (
        <span className="reason-cell">
          {reasonLabels[c.row.original.reasons[0]] ??
            (c.row.original.reasons[0] === 'SEM_AJUSTE'
              ? 'Dentro das restrições'
              : c.row.original.reasons[0].replaceAll('_', ' ').toLowerCase())}
        </span>
      ),
    },
    {
      id: 'details',
      header: () => <span className="sr-only">Detalhes</span>,
      cell: (c) => (
        <button
          className="icon-button"
          onClick={() => onDecision(c.row.original)}
          aria-label={`Ver decisão ${c.row.original.poi_id}`}
        >
          <ArrowRight size={17} />
        </button>
      ),
    },
  ];
  const table = useReactTable({
    data: query.data?.items ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    state: { columnVisibility: visibility },
    onColumnVisibilityChange: setVisibility,
  });
  return (
    <>
      <div className="intro-line">
        <div>
          <span className="eyebrow">{exceptions ? 'Conferência humana' : 'Consulta operacional'}</span>
          <h1>{exceptions ? 'Fila de revisão' : 'Conciliação por item'}</h1>
          <p>
            {exceptions
              ? 'Dados que precisam de atenção antes de avançar com a proposta.'
              : 'Explore cada decisão, seus limites e a evidência que a sustenta.'}
          </p>
        </div>
        <Download
          id={run.id}
          name={exceptions ? 'fila_revisao.csv' : undefined}
          label={exceptions ? 'Exportar fila' : undefined}
        />
      </div>
      {exceptions && (
        <aside className="notice">
          <span className="notice-dot" />
          <p>
            Itens em revisão têm proposta zerada. Corrija os dados na origem e gere um novo lote completo.
          </p>
        </aside>
      )}
      <Panel
        title={exceptions ? 'Pendências do lote' : 'Itens de pedido'}
        sub={`${number(query.data?.total)} itens nesta consulta. Quantidades em peças.`}
        action={
          <details className="column-picker">
            <summary>
              <SlidersHorizontal size={15} />
              Colunas
            </summary>
            <div>
              {table
                .getAllLeafColumns()
                .filter((c) => c.getCanHide() && c.id !== 'details')
                .map((c) => (
                  <label key={c.id}>
                    <input
                      type="checkbox"
                      checked={c.getIsVisible()}
                      onChange={c.getToggleVisibilityHandler()}
                    />
                    {typeof c.columnDef.header === 'string' ? c.columnDef.header : c.id}
                  </label>
                ))}
            </div>
          </details>
        }
      >
        <div className="filters">
          <label className="search-input">
            <Search size={17} />
            <input
              aria-label="Buscar itens"
              placeholder="Buscar POI, pedido, SKU ou CD"
              value={search}
              onChange={(e) => change(() => setSearch(e.target.value))}
            />
          </label>
          <label className="select-label">
            <span>Situação</span>
            <select
              aria-label="Filtrar situação"
              value={status}
              disabled={exceptions}
              onChange={(e) => change(() => setStatus(e.target.value))}
            >
              <option value="">Todas</option>
              <option value="MANTIDO">Mantidos</option>
              <option value="AJUSTADO">Ajustados</option>
              <option value="ZERADO">Zerados</option>
              <option value="REVISAO">Em revisão</option>
            </select>
          </label>
          <label className="select-label">
            <span>Centro de distribuição</span>
            <select aria-label="Filtrar CD" value={cd} onChange={(e) => change(() => setCd(e.target.value))}>
              <option value="">Todos os CDs</option>
              {run.summary?.cds.map((cd) => (
                <option key={cd}>{cd}</option>
              ))}
            </select>
          </label>
          {(search || cd || (status && !exceptions)) && (
            <button
              className="text-button"
              onClick={() => {
                setSearch('');
                setCd('');
                setStatus(exceptions ? 'REVISAO' : '');
                setPage(0);
              }}
            >
              Limpar filtros
            </button>
          )}
        </div>
        {query.isPending ? (
          <Loading />
        ) : query.error ? (
          <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
        ) : !query.data?.items.length ? (
          <Empty />
        ) : (
          <div className={`table-wrap ${query.isFetching ? 'refreshing' : ''}`} aria-busy={query.isFetching}>
            <table className="data-table">
              <thead>
                {table.getHeaderGroups().map((g) => (
                  <tr key={g.id}>
                    {g.headers.map((h) => (
                      <th
                        key={h.id}
                        className={h.id.startsWith('qtd_') ? 'numeric' : ''}
                        aria-sort={sort === h.id ? (descending ? 'descending' : 'ascending') : undefined}
                      >
                        {['poi_id', 'sku', 'cd_origem', 'qtd_final'].includes(h.id) ? (
                          <button
                            className="sort-button"
                            onClick={() => {
                              change(() => {
                                setSort(h.id);
                                setDescending(sort === h.id ? !descending : false);
                              });
                            }}
                          >
                            {flexRender(h.column.columnDef.header, h.getContext())}
                            <ArrowDownUp size={12} />
                          </button>
                        ) : (
                          flexRender(h.column.columnDef.header, h.getContext())
                        )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className={cell.column.id.startsWith('qtd_') ? 'numeric' : ''}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager
          total={query.data?.total ?? 0}
          page={page}
          size={size}
          onPage={setPage}
          onSize={(n) => change(() => setSize(n))}
        />
      </Panel>
    </>
  );
}

export function Inventory({ run }: { run: Run }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(20);
  const query = useQuery({
    queryKey: ['inventory', run.id, search, page, size],
    queryFn: () =>
      api(
        `/reconciliations/${run.id}/inventory?${new URLSearchParams({ search, limit: String(size), offset: String(page * size) })}`,
        pageSchema(inventorySchema),
      ),
  });
  return (
    <>
      <div className="intro-line">
        <div>
          <span className="eyebrow">Restrição física</span>
          <h1>Estoque e consumo proposto</h1>
          <p>Saldo simulado por CD e SKU, sem compensação entre centros.</p>
        </div>
        <Download id={run.id} name="balanco_estoque.csv" label="Exportar balanço" />
      </div>
      <aside className="notice">
        <p>
          Esta é uma simulação sobre a foto das 05h, sem data informada. Não constitui reserva de estoque.
        </p>
      </aside>
      <Panel title="Balanço por origem" sub="Unidade: peças">
        <div className="filters">
          <label className="search-input">
            <Search size={17} />
            <input
              aria-label="Buscar estoque"
              placeholder="Buscar SKU ou CD"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
            />
          </label>
        </div>
        {query.isPending ? (
          <Loading />
        ) : query.error ? (
          <ErrorBox error={query.error} />
        ) : !query.data?.items.length ? (
          <Empty />
        ) : (
          <div
            className="table-wrap"
            role="region"
            aria-label="Tabela de dados, use as setas para rolar"
            tabIndex={0}
          >
            <table className="data-table">
              <thead>
                <tr>
                  <th>CD</th>
                  <th>SKU</th>
                  <th className="numeric">Foto inicial</th>
                  <th className="numeric">Consumo proposto</th>
                  <th className="numeric">Saldo simulado</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((r) => (
                  <tr key={r.cd_origem + r.sku}>
                    <td>{r.cd_origem}</td>
                    <td className="mono">{r.sku}</td>
                    <td className="numeric">{number(r.estoque_05h)}</td>
                    <td className="numeric">{number(r.reservado_proposta)}</td>
                    <td className="numeric emphasis">{number(r.saldo_simulado)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager
          total={query.data?.total ?? 0}
          page={page}
          size={size}
          onPage={setPage}
          onSize={(n) => {
            setSize(n);
            setPage(0);
          }}
        />
      </Panel>
    </>
  );
}
