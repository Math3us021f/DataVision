import os


def read_log_tail(path: str, limit: int, block_size: int = 8192) -> list[str]:
    """Últimas `limit` linhas do arquivo, lendo de trás para frente só o necessário (não o arquivo inteiro)."""
    try:
        with open(path, "rb") as log_file:
            position = log_file.seek(0, os.SEEK_END)
            data = b""
            # limit + 1 quebras de linha garantem `limit` linhas completas (a primeira peça pode vir cortada).
            while position > 0 and data.count(b"\n") <= limit:
                step = min(block_size, position)
                position -= step
                log_file.seek(position)
                data = log_file.read(step) + data
    except FileNotFoundError:
        return []

    # Decodifica só depois de juntar os blocos: um caractere de vários bytes pode ter sido cortado entre dois deles.
    return data.decode("utf-8", errors="replace").splitlines()[-limit:]
