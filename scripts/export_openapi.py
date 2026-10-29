"""Exporta ou verifica o contrato sem iniciar servidor, seed ou conexão GCP."""

import argparse
import json
import tempfile
from pathlib import Path

from platform_api.api import create_app
from platform_api.config import ROOT, Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="otm-openapi-") as temporary:
        app = create_app(Settings(environment="test", data_dir=Path(temporary), seed_demo=False))
        try:
            content = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        finally:
            app.state.service.close()
            app.state.repository.engine.dispose()
    target = ROOT / "docs/api/openapi.json"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != content:
            raise SystemExit("OpenAPI divergiu. Execute python -m scripts.export_openapi e revise o diff.")
        print("OpenAPI versionada corresponde ao código.")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
