"""API em JSON (Django Ninja). As rotas ficam na raiz (/health, /me, /users...) iguais às do FastAPI, para a
interface React e os testes não perceberem a troca de backend."""

from django.conf import settings
from ninja import NinjaAPI

from config.renderers import Utf8JSONRenderer

from accounts.api import router as accounts_router

# Em produção a documentação interativa some: /docs e /openapi.json são públicos e listariam todas as rotas.
api = NinjaAPI(
    title="DataVision",
    version="0.1.0",
    description="API para análise automática de arquivos de dados.",
    docs_url=None if settings.PRODUCTION else "/docs",
    openapi_url=None if settings.PRODUCTION else "/openapi.json",
    urls_namespace="api",
    renderer=Utf8JSONRenderer(),
)


@api.get("/health", tags=["saúde"], auth=None)
def health_check(request) -> dict[str, str]:
    return {"status": "ok", "application": "DataVision"}


api.add_router("", accounts_router)
