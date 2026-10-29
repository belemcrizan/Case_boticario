"""Comandos explícitos para bootstrap SQL. Nunca executa migração no startup cloud."""

import argparse

from sqlalchemy import insert, select

from .config import Settings
from .repository import capacity, make_engine, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["migrate"])
    parser.parse_args()
    engine = make_engine(Settings.from_env())
    try:
        metadata.create_all(engine)
        with engine.begin() as db:
            if not db.scalar(select(capacity.c.id).where(capacity.c.id == "global")):
                db.execute(insert(capacity).values(id="global", version=0))
        print("Schema v1 disponível. Alterações futuras exigem migração versionada explícita.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
