"""Explorador de arquivos: somente leitura, restrito à pasta data/."""

import os

from ninja.errors import HttpError

ALLOWED_ROOT = os.path.realpath("data")
ALLOWED_EXTENSIONS = {".csv", ".txt", ".json"}
MAX_FILE_READ_BYTES = 1_000_000  # 1 MB
MAX_LISTING_ENTRIES = 1000


def resolve_safe_path(user_path: str) -> str:
    """Resolve `user_path` dentro de ALLOWED_ROOT e garante que não escapa dele.

    Defesa em camadas: rejeita caminho absoluto no próprio texto (os.path.join descartaria a base), resolve o caminho
    final de verdade no sistema de arquivos (realpath, o que também resolve symlinks) e só aceita se o resultado ainda
    estiver dentro de ALLOWED_ROOT."""
    invalid = HttpError(400, "Caminho inválido")
    if os.path.isabs(user_path) or "\x00" in user_path:
        raise invalid
    candidate = os.path.realpath(os.path.join(ALLOWED_ROOT, user_path))
    try:
        common = os.path.commonpath([candidate, ALLOWED_ROOT])
    except ValueError:
        raise invalid
    if common != ALLOWED_ROOT:
        raise invalid
    return candidate


def list_directory(path: str) -> dict:
    real_path = resolve_safe_path(path)
    if not os.path.isdir(real_path):
        raise HttpError(404, "Diretório não encontrado")

    entries = []
    with os.scandir(real_path) as scan:
        for entry in scan:
            if entry.is_symlink():
                continue  # o explorador nunca deixaria ler o alvo: mostrar só geraria uma entrada inútil
            if len(entries) >= MAX_LISTING_ENTRIES:
                break
            is_file = entry.is_file(follow_symlinks=False)
            entries.append(
                {
                    "name": entry.name,
                    "is_dir": entry.is_dir(follow_symlinks=False),
                    "size_bytes": entry.stat(follow_symlinks=False).st_size if is_file else None,
                }
            )
    return {"path": path, "entries": entries}


def read_file_content(path: str) -> dict:
    real_path = resolve_safe_path(path)
    if not os.path.isfile(real_path):
        raise HttpError(404, "Arquivo não encontrado")
    if os.path.splitext(real_path)[1].lower() not in ALLOWED_EXTENSIONS:
        raise HttpError(403, "Tipo de arquivo não permitido")
    if os.path.getsize(real_path) > MAX_FILE_READ_BYTES:
        raise HttpError(413, "Arquivo grande demais para leitura")
    with open(real_path, encoding="utf-8", errors="replace") as file:
        return {"path": path, "content": file.read()}
