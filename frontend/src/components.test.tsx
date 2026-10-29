import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DecisionDrawer, Empty, ErrorBox, Help, Pager, Status } from './components';
import { ApiError, decisionSchema, runSchema } from './api';
import fixture from './test-fixtures.json';

describe('Componentes operacionais', () => {
  it('explica status sem depender somente de cor', () => {
    render(<Status value="REVISAO" />);
    expect(screen.getByText('Em revisão')).toBeVisible();
  });
  it('mostra definição de indicador como nome acessível', () => {
    render(<Help text="Quantidade dividida pela sugestão OTM" />);
    expect(screen.getByRole('button', { name: /dividida/ })).toBeInTheDocument();
  });
  it('pagina no servidor sem permitir avançar além do total', () => {
    const go = vi.fn();
    render(<Pager total={12} page={0} size={20} onPage={go} onSize={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Próxima página' })).toBeDisabled();
    expect(screen.getByText('1–12 de 12 itens')).toBeVisible();
  });
  it('navega para a próxima página válida', () => {
    const go = vi.fn();
    render(<Pager total={55} page={0} size={20} onPage={go} onSize={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Próxima página' }));
    expect(go).toHaveBeenCalledWith(1);
  });
  it('mostra uma ação clara no estado vazio', () => {
    render(<Empty />);
    expect(screen.getByText('Ajuste os filtros para ampliar a consulta.')).toBeVisible();
  });
  it('preserva a correlação no erro para suporte', () => {
    render(<ErrorBox error={new ApiError(409, 'INTEGRITY', 'Artefato divergente', 'correlation-123')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('correlation-123');
  });
  it('detalha a conta de caixas com evidência real', () => {
    const decision = decisionSchema.parse(fixture.decisions.items.find((d) => d.poi_id === 'POI-1007'));
    const close = vi.fn();
    render(<DecisionDrawer decision={decision} onClose={close} />);
    expect(screen.getByRole('dialog')).toHaveTextContent('18 caixas');
    expect(screen.getByText('110')).toBeVisible();
    expect(screen.getByText('108')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Fechar decisão' }));
    expect(close).toHaveBeenCalled();
  });
  it('não aceita resposta de quantidade que viole o tipo do contrato', () => {
    expect(decisionSchema.safeParse({ ...fixture.decisions.items[0], qtd_final: '199' }).success).toBe(false);
  });
  it('reconhece os dois cenários reproduzidos', () => {
    const runs = fixture.runs.items.map((r) => runSchema.parse(r));
    expect(runs.find((r) => r.policy === 'strict')?.summary?.metrics.unidades_finais).toBe(199);
    expect(runs.find((r) => r.policy === 'complete-kits')?.summary?.metrics.unidades_finais).toBe(269);
  });
});
