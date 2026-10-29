import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import fixture from './test-fixtures.json';

afterEach(() => vi.unstubAllGlobals());
function setup(authenticated = true) {
  let logged = authenticated;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      if (url === '/api/v1/me')
        return new Response(
          JSON.stringify(
            logged ? fixture.user : { code: 'AUTHENTICATION_REQUIRED', detail: 'Abra uma sessão' },
          ),
          { status: logged ? 200 : 401 },
        );
      if (url === '/api/v1/auth/demo-session') {
        logged = true;
        return new Response(JSON.stringify(fixture.user));
      }
      if (url.startsWith('/api/v1/reconciliations?')) return new Response(JSON.stringify(fixture.runs));
      if (url === '/api/v1/reconciliations/demo-strict')
        return new Response(JSON.stringify(fixture.runs.items.find((r) => r.id === 'demo-strict')));
      if (url.includes('/decisions?')) return new Response(JSON.stringify(fixture.decisions));
      if (options?.method === 'POST') return new Response('{}');
      return new Response(JSON.stringify({ code: 'NOT_FOUND', detail: 'Não encontrado' }), { status: 404 });
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}
describe('Jornada principal', () => {
  it('oferece acesso demonstrativo explícito sem exigir GCP', async () => {
    setup(false);
    expect(await screen.findByRole('button', { name: 'Acessar como analista' })).toBeVisible();
    expect(screen.getByText(/As identidades desta tela são demonstrativas/)).toBeVisible();
  });
  it('conecta a sessão ao dashboard com dados reais', async () => {
    setup(false);
    await userEvent.click(await screen.findByRole('button', { name: 'Acessar como analista' }));
    expect(await screen.findByRole('heading', { name: 'Visão geral da conciliação' })).toBeVisible();
    expect(screen.getByText('Quantidade sugerida')).toBeVisible();
    expect(screen.getByText('Proposta conciliada')).toBeVisible();
  });
  it('permite navegar à importação sem conhecimento técnico', async () => {
    setup();
    await screen.findByRole('heading', { name: 'Visão geral da conciliação' });
    await userEvent.click(screen.getByRole('button', { name: 'Importar lote' }));
    expect(await screen.findByRole('heading', { name: 'Importar e conciliar' })).toBeVisible();
    expect(screen.getByText('Fotografia do estoque')).toBeVisible();
  });
  it('alterna o tema mantendo a preferência', async () => {
    setup();
    await screen.findByRole('heading', { name: 'Visão geral da conciliação' });
    await userEvent.click(screen.getByRole('button', { name: 'Ativar modo escuro' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(screen.getByRole('button', { name: 'Ativar modo claro' })).toBeVisible();
    localStorage.clear();
  });
});
