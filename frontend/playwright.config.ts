import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:8000', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1100 } } },
  ],
  webServer: {
    command: '.venv/bin/python -m platform_api.api',
    cwd: '..',
    url: 'http://127.0.0.1:8000/readyz',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      OTM_ENV: 'demo',
      OTM_DATA_DIR: '.runtime/e2e',
      OTM_PUBLIC_ORIGIN: 'http://127.0.0.1:8000',
      PORT: '8000',
    },
  },
});
