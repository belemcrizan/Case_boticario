"""Entrada para Cloud Run Jobs. Um claim atômico torna duplicatas inofensivas."""

import argparse
import logging

from .cloud import GCSStorage
from .config import Settings
from .observability import configure_tracing
from .repository import Repository, make_engine
from .service import Service
from .storage import LocalStorage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings.from_env()
    configure_tracing()
    repo = Repository(make_engine(settings))
    storage = (
        GCSStorage(settings.bucket)
        if settings.environment == "gcp"
        else LocalStorage(settings.data_dir / "objects")
    )
    service = Service(settings, repo, storage)
    try:
        service.execute(args.run_id)
        if repo.get(args.run_id)["state"] == "FAILED":
            raise SystemExit(1)
    finally:
        service.close()
        repo.engine.dispose()


if __name__ == "__main__":
    main()
