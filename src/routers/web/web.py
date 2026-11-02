from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from src.core.auth import get_current_user_optional

router = APIRouter(tags=["web"])

REACT_APP_INDEX = Path("src/static/app/index.html")


def _react_shell():
    """Casca da interface (React). O servidor só entrega o HTML; os dados vêm da API, que valida
    permissões em cada rota. O roteamento interno (/app/...) e a tela de login são feitos no navegador."""
    if not REACT_APP_INDEX.is_file():
        return HTMLResponse(
            "Interface ainda não gerada. Rode: docker compose --profile frontend run --rm frontend",
            status_code=503,
        )
    return FileResponse(REACT_APP_INDEX, media_type="text/html")


@router.get("/login")
def login_page(user: dict | None = Depends(get_current_user_optional)):
    if user is not None:
        return RedirectResponse(url="/app")
    return _react_shell()


# Endereços antigos continuam existindo (favoritos, links salvos) e levam para a interface nova.
# Sem sessão, vão para o login como qualquer outra página.
def _to_new_ui(user: dict | None, destination: str) -> RedirectResponse:
    return RedirectResponse(url="/login" if user is None else destination)


@router.get("/")
def home_page(user: dict | None = Depends(get_current_user_optional)):
    return _to_new_ui(user, "/app")


@router.get("/meus-datasets")
def datasets_page(user: dict | None = Depends(get_current_user_optional)):
    return _to_new_ui(user, "/app/datasets")


@router.get("/meus-datasets/{dataset_id}/dashboard")
def dataset_dashboard_page(dataset_id: int, user: dict | None = Depends(get_current_user_optional)):
    return _to_new_ui(user, f"/app/datasets/{dataset_id}/dashboard")


@router.get("/account")
def account_page(user: dict | None = Depends(get_current_user_optional)):
    return _to_new_ui(user, "/app/account")


@router.get("/app")
@router.get("/app/{path:path}")
def react_app(user: dict | None = Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login")
    return _react_shell()


ADMIN_PAGES = {"users", "metrics", "logs", "files", "audit"}


def _admin_destination(user: dict | None, destination: str) -> RedirectResponse:
    # Só controla a navegação; a proteção real continua nas rotas da API (require_admin),
    # que barram qualquer chamada de quem não é admin. A tela também confere no navegador.
    if user is None:
        return RedirectResponse(url="/login")
    if not user["is_admin"]:
        return RedirectResponse(url="/app")
    return RedirectResponse(url=destination)


@router.get("/admin")
def admin_index(user: dict | None = Depends(get_current_user_optional)):
    return _admin_destination(user, "/app/admin/users")


@router.get("/admin/{page}")
def admin_page(page: str, user: dict | None = Depends(get_current_user_optional)):
    if page not in ADMIN_PAGES:
        raise HTTPException(status_code=404, detail="Página não encontrada")
    return _admin_destination(user, f"/app/admin/{page}")
