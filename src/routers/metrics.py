import psutil
from fastapi import APIRouter, Depends

from src.auth import require_admin

router = APIRouter(prefix="/metrics", tags=["metrics"])

AVISO_ESCOPO = (
    "Estes valores são lidos de dentro do container da aplicação via psutil. "
    "O Compose atual não define limites de CPU/memória para o container, então "
    "estes números não são isolados por container — refletem o ambiente Linux "
    "que o container enxerga. No Windows com Docker Desktop, isso é a VM Linux "
    "interna (WSL2), não o hardware real do Windows. No Ubuntu Server (produção "
    "futura), será o host de fato, por não haver essa camada de VM."
)


@router.get("/system")
def system_metrics(admin: dict = Depends(require_admin)) -> dict:
    disk = psutil.disk_usage("/")
    memory = psutil.virtual_memory()
    network = psutil.net_io_counters()

    return {
        "aviso_escopo": AVISO_ESCOPO,
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "memory": {
            "total_bytes": memory.total,
            "used_bytes": memory.used,
            "percent": memory.percent,
        },
        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "percent": disk.percent,
        },
        "network": {
            "bytes_sent": network.bytes_sent,
            "bytes_recv": network.bytes_recv,
        },
    }
