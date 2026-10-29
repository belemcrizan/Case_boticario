import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
const python = fileURLToPath(new URL('../.venv/bin/python', import.meta.url));
const child = spawn(python, ['-m', 'platform_api.api'], {
  cwd: root, stdio: 'inherit', env: { ...process.env, OTM_BIND: '0.0.0.0', PORT: process.env.PORT ?? '3000' },
});
process.on('SIGTERM', () => child.kill('SIGTERM'));
process.on('SIGINT', () => child.kill('SIGINT'));
child.on('exit', code => process.exit(code ?? 0));
