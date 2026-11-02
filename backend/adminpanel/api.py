"""Métricas do sistema, logs, explorador de arquivos (só administradores) e o resumo do painel inicial."""

import psutil
from django.conf import settings
from ninja import Query, Router, Schema
from pydantic import Field

from accounts.auth import AdminAuth, SessionAuth
from adminpanel import files
from adminpanel.logtail import read_log_tail
from adminpanel.summary import build_summary

router = Router(tags=["painel"])
admin = AdminAuth()

AVISO_ESCOPO = (
    "Estes valores são lidos de dentro do container da aplicação via psutil. "
    "O Compose atual não define limites de CPU/memória para o container, então "
    "estes números não são isolados por container — refletem o ambiente Linux "
    "que o container enxerga. No Windows com Docker Desktop, isso é a VM Linux "
    "interna (WSL2), não o hardware real do Windows. No Ubuntu Server (produção "
    "futura), será o host de fato, por não haver essa camada de VM."
)


class LogParams(Schema):
    limit: int = Field(default=100, ge=1, le=1000)


@router.get("/dashboard/summary", auth=SessionAuth(), summary="Resumo do painel inicial")
def dashboard_summary(request):
    return build_summary(request.auth)


@router.get("/metrics/system", auth=admin, summary="CPU, memória, disco e rede")
def system_metrics(request):
    disk, memory, network = psutil.disk_usage("/"), psutil.virtual_memory(), psutil.net_io_counters()
    return {
        "aviso_escopo": AVISO_ESCOPO,
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory": {"total_bytes": memory.total, "used_bytes": memory.used, "percent": memory.percent},
        "disk": {"total_bytes": disk.total, "used_bytes": disk.used, "percent": disk.percent},
        "network": {"bytes_sent": network.bytes_sent, "bytes_recv": network.bytes_recv},
    }


@router.get("/logs/app", auth=admin, summary="Últimas linhas do log (caminho fixo no código)")
def read_app_logs(request, params: Query[LogParams]):
    return {"lines": read_log_tail(str(settings.LOG_DIR / "app.log"), params.limit)}


@router.get("/files", auth=admin, summary="Lista uma pasta de data/")
def list_directory(request, path: str = ""):
    return files.list_directory(path)


@router.get("/files/content", auth=admin, summary="Lê um arquivo de texto de data/")
def read_file_content(request, path: str):
    return files.read_file_content(path)
