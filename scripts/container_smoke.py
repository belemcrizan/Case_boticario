"""Verifica container em CI, incluindo acesso autenticado e baseline."""

import http.cookiejar
import json
import time
import urllib.error
import urllib.request

base = "http://127.0.0.1:8080"
for attempt in range(45):
    try:
        with urllib.request.urlopen(base + "/readyz", timeout=2) as response:
            assert response.status == 200
        break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(1)
else:
    raise SystemExit("Container não ficou pronto")
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
login = urllib.request.Request(base + "/api/v1/auth/demo-session", data=b'{"profile":"operator"}',
                               headers={"Content-Type": "application/json"})
assert opener.open(login, timeout=10).status == 200
summary = json.load(opener.open(base + "/api/v1/reconciliations/demo-strict/summary", timeout=10))
assert summary["metrics"]["unidades_finais"] == 199
assert all(summary["checks"].values())
print("Container: readiness, sessão e dez invariantes aprovadas; 199 peças no baseline.")
