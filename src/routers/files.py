import os

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.auth import require_admin

router = APIRouter(prefix="/files", tags=["files"])

ALLOWED_ROOT = os.path.realpath("data")
ALLOWED_EXTENSIONS = {".csv", ".txt", ".json"}
MAX_FILE_READ_BYTES = 1_000_000  # 1 MB
MAX_LISTING_ENTRIES = 1000

CAMINHO_INVALIDO = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Caminho inválido")


def resolve_safe_path(user_path: str) -> str:
    """Resolve `user_path` dentro de ALLOWED_ROOT e garante que não escapa dele.

    Defesa em camadas:
    - Rejeita caminho absoluto no próprio texto (os.path.join descartaria a base
      se deixássemos passar um absoluto — é um erro clássico).
    - Resolve o caminho final de verdade no sistema de arquivos (realpath),
      o que também resolve symlinks.
    - Só aceita se o resultado ainda estiver dentro de ALLOWED_ROOT.
    """
    if os.path.isabs(user_path):
        raise CAMINHO_INVALIDO

    candidate = os.path.realpath(os.path.join(ALLOWED_ROOT, user_path))

    try:
        common = os.path.commonpath([candidate, ALLOWED_ROOT])
    except ValueError:
        raise CAMINHO_INVALIDO

    if common != ALLOWED_ROOT:
        raise CAMINHO_INVALIDO

    return candidate


@router.get("")
def list_directory(path: str = Query(default=""), admin: dict = Depends(require_admin)) -> dict:
    real_path = resolve_safe_path(path)

    if not os.path.isdir(real_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diretório não encontrado")

    entries = []
    with os.scandir(real_path) as scan:
        for entry in scan:
            if entry.is_symlink():
                # Não listamos symlinks: o explorador nunca vai deixar ler o conteúdo deles
                # mesmo (resolve_safe_path bloqueia o alvo fora de ALLOWED_ROOT), então
                # mostrá-los só geraria uma entrada inconsistente e sem utilidade real.
                continue
            if len(entries) >= MAX_LISTING_ENTRIES:
                break
            entries.append(
                {
                    "name": entry.name,
                    "is_dir": entry.is_dir(follow_symlinks=False),
                    "size_bytes": entry.stat(follow_symlinks=False).st_size if entry.is_file(follow_symlinks=False) else None,
                }
            )

    return {"path": path, "entries": entries}


@router.get("/content")
def read_file_content(path: str = Query(...), admin: dict = Depends(require_admin)) -> dict:
    real_path = resolve_safe_path(path)

    if not os.path.isfile(real_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado")

    extension = os.path.splitext(real_path)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tipo de arquivo não permitido")

    size = os.path.getsize(real_path)
    if size > MAX_FILE_READ_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Arquivo grande demais para leitura")

    with open(real_path, encoding="utf-8", errors="replace") as file:
        content = file.read()

    return {"path": path, "content": content}
