"""Interface de terminal. Sem instalação, rede, credenciais ou efeitos no OMS."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .engine import reconcile
from .ingest import load_dataset
from .models import ContractError, InvariantError, Policy
from .report import write_bundle


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Concilia OTM, combos, caixas master e estoque por CD/SKU.",
    )
    parser.add_argument("--input-dir", type=Path, default=root / "data/input", help="Diretório dos cinco CSVs")
    parser.add_argument("--output-dir", type=Path, default=root / "output", help="Novo diretório de evidências")
    parser.add_argument("--incomplete-policy", choices=("strict", "complete-kits"), default="strict",
                        help="Interpretação de 'Zerar se incompleto'; padrão: strict")
    parser.add_argument("--fail-on-review", action="store_true", help="Retorna código 3 se houver POIs em revisão")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    try:
        data = load_dataset(args.input_dir)
        result = reconcile(data, Policy(incomplete_policy=args.incomplete_policy))
        run_id = write_bundle(data, result, args.output_dir)
        print(json.dumps({
            "event": "reconciliation_completed", "run_id": run_id,
            "output_dir": str(args.output_dir.absolute()), "policy": args.incomplete_policy,
            **result.metrics, "all_invariants_passed": all(result.checks.values()),
            "requires_review": bool(result.metrics["linhas_revisao"]),
        }, ensure_ascii=False, sort_keys=True))
        return 3 if args.fail_on_review and result.metrics["linhas_revisao"] else 0
    except ContractError as exc:
        print(json.dumps({"event": "input_or_output_rejected", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except InvariantError as exc:
        print(json.dumps({"event": "invariant_failure", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    except OSError as exc:
        print(json.dumps({"event": "io_failure", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
