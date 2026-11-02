from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from src.core.auth import (
    create_session_token,
    get_current_user,
    hash_password,
    set_session_cookie,
    validate_new_password,
    verify_password,
)
from src.core.db import get_connection
from src.core.logging_config import logger

router = APIRouter(prefix="/me", tags=["account"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_own_password(data: ChangePasswordRequest, response: Response, user: dict = Depends(get_current_user)) -> None:
    with get_connection() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],)).fetchone()

        # Exigir a senha atual impede que alguém com acesso a uma sessão aberta
        # (ex: computador destravado) troque a senha e tome a conta.
        if not verify_password(data.current_password, row["password_hash"]):
            logger.warning("Troca de senha recusada (senha atual incorreta): user_id=%s", user["id"])
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta.")

        if data.new_password == data.current_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A nova senha precisa ser diferente da atual.")

        validate_new_password(data.new_password)

        updated = conn.execute(
            """
            UPDATE users
            SET password_hash = %s, session_version = session_version + 1
            WHERE id = %s
            RETURNING session_version
            """,
            (hash_password(data.new_password), user["id"]),
        ).fetchone()
        conn.execute(
            "INSERT INTO audit_logs (actor_user_id, action, target_user_id) VALUES (%s, 'change_own_password', %s)",
            (user["id"], user["id"]),
        )
        conn.commit()

    # Outras sessões ficam inválidas; esta recebe um cookie novo com a versão atual.
    set_session_cookie(response, create_session_token(user["id"], updated["session_version"]))
    logger.info("Senha trocada pelo próprio usuário: user_id=%s", user["id"])
