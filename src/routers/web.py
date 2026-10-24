from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from src.auth import get_current_user_optional

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/login")
def login_page(request: Request, user: dict | None = Depends(get_current_user_optional)):
    if user is not None:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request, "login.html")


@router.get("/")
def home_page(request: Request, user: dict | None = Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(request, "home.html", {"user": user})


def _admin_page(request: Request, user: dict | None, template: str):
    # A página só controla a navegação; a proteção real continua nas rotas da API
    # (require_admin), que barram qualquer chamada de quem não é admin.
    if user is None:
        return RedirectResponse(url="/login")
    if not user["is_admin"]:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request, template, {"user": user})


@router.get("/admin")
def admin_index(user: dict | None = Depends(get_current_user_optional)):
    if user is None:
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/admin/users")


@router.get("/admin/users")
def admin_users_page(request: Request, user: dict | None = Depends(get_current_user_optional)):
    return _admin_page(request, user, "admin/users.html")


@router.get("/admin/metrics")
def admin_metrics_page(request: Request, user: dict | None = Depends(get_current_user_optional)):
    return _admin_page(request, user, "admin/metrics.html")


@router.get("/admin/logs")
def admin_logs_page(request: Request, user: dict | None = Depends(get_current_user_optional)):
    return _admin_page(request, user, "admin/logs.html")


@router.get("/admin/files")
def admin_files_page(request: Request, user: dict | None = Depends(get_current_user_optional)):
    return _admin_page(request, user, "admin/files.html")
