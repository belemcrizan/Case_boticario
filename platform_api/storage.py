"""Porta de arquivos imutáveis; nomes de upload nunca determinam caminhos livres."""

import hashlib
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol

from .domain import AppError


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


class Storage(Protocol):
    def put(self, key: str, path: Path) -> None: ...
    def get(self, key: str, path: Path) -> None: ...
    def open(self, key: str) -> BinaryIO: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or key.startswith("/") or ".." in key.split("/"):
            raise AppError(400, "INVALID_STORAGE_KEY", "Referência de arquivo inválida.")
        return path

    def put(self, key: str, path: Path) -> None:
        dest = self.path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("rb") as src, dest.open("xb") as out:
                shutil.copyfileobj(src, out)
        except FileExistsError:
            if digest(path) != digest(dest):
                raise AppError(
                    409, "IMMUTABLE_OBJECT", "Tentativa de alterar um artefato imutável."
                ) from None

    def get(self, key: str, path: Path) -> None:
        shutil.copyfile(self.path(key), path)

    def open(self, key: str) -> BinaryIO:
        return self.path(key).open("rb")


@contextmanager
def verified_stream(store: Storage, key: str, expected: str):
    """Verifica o objeto antes de enviar bytes. Pico de memória é um chunk."""
    with store.open(key) as stream:
        checksum = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
        if checksum.hexdigest() != expected:
            raise AppError(
                409, "ARTIFACT_INTEGRITY_FAILURE", "Artefato diverge do hash registrado. Não utilizar."
            )
    with store.open(key) as stream:
        yield stream
