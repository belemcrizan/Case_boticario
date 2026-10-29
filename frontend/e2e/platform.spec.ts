import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import path from 'node:path';
import fs from 'node:fs';

const screenshots = 'test-results/screenshots';
async function login(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Acessar como analista' }).click();
  await expect(page.getByRole('heading', { name: 'Visão geral da conciliação' })).toBeVisible();
}
async function shot(page: Page, name: string) {
  fs.mkdirSync(screenshots, { recursive: true });
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({ path: `${screenshots}/${name}.png`, fullPage: true });
}
async function accessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(results.violations).toEqual([]);
}

test('dashboard, indicadores e acessibilidade', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await login(page);
  await expect(page.locator('.kpi-highlight .kpi-value')).toContainText('199');
  await expect(page.locator('.kpi:first-child .kpi-value')).toContainText('297');
  await accessible(page);
  await shot(page, '01-visao-executiva');
  expect(errors).toEqual([]);
});
test('consulta, filtros, decisão e teclado', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: 'Conciliação por item' }).click();
  await page.getByRole('textbox', { name: 'Buscar itens' }).fill('SKU-D2');
  await expect(page.getByText('POI-1007', { exact: true })).toBeVisible();
  await expect(page.getByText('POI-1001', { exact: true })).not.toBeVisible();
  await page.getByRole('button', { name: 'Ver decisão POI-1007' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText('18 caixas');
  await accessible(page);
  await shot(page, '02-detalhe-decisao');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
});
test('exceção e comparação de políticas reais', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: /Fila de revisão/ }).click();
  await expect(page.getByText('SKU-GHOST', { exact: true })).toBeVisible();
  await shot(page, '03-fila-revisao');
  await page.getByRole('button', { name: 'Simulador de políticas' }).click();
  await expect(page.locator('.scenario').nth(1).locator(':scope > b')).toContainText('269');
  await expect(page.locator('.comparison-result')).toContainText('+70');
  await accessible(page);
  await shot(page, '04-comparacao-politicas');
});
test('importação, validação e execução de ponta a ponta', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: 'Importar lote' }).click();
  const names = [
    'pedidos_oms.csv',
    'saidas_otm.csv',
    'foto_estoque_cd_05h.csv',
    'de_para_combos.csv',
    'regras_embalagem.csv',
  ];
  await page
    .getByLabel('Selecionar cinco arquivos CSV')
    .setInputFiles(names.map((n) => path.resolve('../data/input', n)));
  await page.getByRole('button', { name: 'Validar arquivos', exact: true }).click();
  await expect(page.getByText('Os cinco arquivos atendem ao contrato estrutural.')).toBeVisible();
  await accessible(page);
  await shot(page, '05-importacao-validada');
  await page.getByRole('button', { name: 'Executar conciliação', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Visão geral da conciliação' })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator('.kpi-highlight .kpi-value')).toContainText('199');
});
test('auditoria, integridade e exportação', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: 'Qualidade e auditoria' }).click();
  await expect(page.getByText('10 invariantes do motor')).toBeVisible();
  await page.getByRole('button', { name: 'Verificar integridade' }).click();
  await expect(page.getByText('Os sete artefatos correspondem aos hashes registrados.')).toBeVisible();
  await accessible(page);
  await shot(page, '06-qualidade-auditoria');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Baixar proposta_conciliada.csv', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('proposta_conciliada.csv');
});
test('responsivo, menu móvel, modo escuro e ausência de overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  const overflow = await page.evaluate(() =>
    [...document.querySelectorAll('body *')]
      .filter((e) => {
        const r = e.getBoundingClientRect();
        return (
          r.right > innerWidth + 1 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('.table-wrap')
        );
      })
      .map((e) => ({ tag: e.tagName, class: e.className, right: e.getBoundingClientRect().right }))
      .slice(0, 15),
  );
  expect(overflow).toEqual([]);
  const geometry = await page.evaluate(() => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    overflowing: [...document.querySelectorAll('body *')]
      .filter((e) => e.scrollWidth > e.clientWidth + 1)
      .map((e) => ({
        tag: e.tagName,
        class: String(e.className),
        scroll: e.scrollWidth,
        client: e.clientWidth,
        visibility: getComputedStyle(e).visibility,
        display: getComputedStyle(e).display,
      }))
      .slice(0, 25),
  }));
  expect(geometry.document, JSON.stringify(geometry)).toBeLessThanOrEqual(geometry.viewport);
  await accessible(page);
  await shot(page, '07-dashboard-mobile');
  await page.getByRole('button', { name: 'Abrir menu' }).click();
  await expect(page.getByRole('dialog', { name: 'Navegação principal' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Abrir menu' })).toBeFocused();
  await page.getByRole('button', { name: 'Abrir menu' }).click();
  await page.getByRole('button', { name: 'Estoque por CD' }).click();
  await expect(page.getByRole('heading', { name: 'Estoque e consumo proposto' })).toBeVisible();
  await page.getByRole('button', { name: 'Ativar modo escuro' }).click();
  await accessible(page);
  await shot(page, '08-estoque-mobile-escuro');
});
test('perfil de gestão consulta e não executa', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: 'Arquitetura GCP' }).click();
  await expect(page.getByRole('heading', { name: 'Arquitetura e implantação' })).toBeVisible();
  await accessible(page);
  await shot(page, '09-arquitetura-gcp');
  await page.getByLabel('Perfil demonstrativo').selectOption('viewer');
  await page.getByRole('button', { name: 'Importar lote' }).click();
  await expect(page.getByText(/Seu perfil permite consulta/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Selecionar arquivos', exact: true })).toBeDisabled();
});
