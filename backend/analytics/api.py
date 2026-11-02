"""Consulta analítica, painel padrão sugerido e dashboard salvo de um dataset do próprio usuário."""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from ninja import Router, Status
from ninja.errors import HttpError

from accounts.auth import SessionAuth
from analytics import runtime
from analytics.dashboards import delete_saved_dashboard, get_saved_dashboard, save_dashboard, validate_dashboard
from analytics.engine import run_query
from analytics.schemas import DashboardOut, DashboardSpec, QueryResult, QuerySpec, WidgetSuggestion
from analytics.suggestions import suggest_dashboard
from analytics.validator import InvalidQueryError
from datasets.services import get_column_types, get_owned_dataset, get_stored_profile

router = Router(tags=["análise"])
session_auth = SessionAuth()

# Threads só para o trabalho pesado (ler o arquivo e rodar o Pandas), que não toca no banco. A vaga de verdade é o
# semáforo de runtime.run_limited; estas threads a mais só esperam por ele até desistir com 503.
_executor = ThreadPoolExecutor(max_workers=runtime.MAX_CONCURRENT_QUERIES * 2, thread_name_prefix="consulta")


@router.get("/datasets/{int:dataset_id}/suggested-dashboard", auth=session_auth, response=list[WidgetSuggestion], summary="Painel inicial por regras")
def suggested_dashboard(request, dataset_id: int):
    """Regras sobre o perfil salvo. Devolve só as specs: cada gráfico busca seus dados em /query."""
    dataset = get_owned_dataset(dataset_id, request.auth)
    if get_column_types(dataset) is None:
        raise HttpError(409, "Perfile o dataset antes de gerar o painel")
    return suggest_dashboard(get_stored_profile(dataset))


@router.get("/datasets/{int:dataset_id}/dashboard", auth=session_auth, response=DashboardOut | None, summary="Dashboard salvo (ou null)")
def get_dashboard(request, dataset_id: int):
    return get_saved_dashboard(get_owned_dataset(dataset_id, request.auth))


@router.put("/datasets/{int:dataset_id}/dashboard", auth=session_auth, response=DashboardOut, summary="Salva o dashboard")
def put_dashboard(request, dataset_id: int, spec: DashboardSpec):
    dataset = get_owned_dataset(dataset_id, request.auth)
    types = get_column_types(dataset)
    if types is None:
        raise HttpError(409, "Perfile o dataset antes de salvar o dashboard")
    try:
        validate_dashboard(spec, types)
    except InvalidQueryError as exc:
        raise HttpError(422, str(exc)) from exc
    return save_dashboard(dataset, request.auth, spec)


@router.delete("/datasets/{int:dataset_id}/dashboard", auth=session_auth, response={204: None}, summary="Volta ao painel padrão")
def delete_dashboard(request, dataset_id: int):
    delete_saved_dashboard(get_owned_dataset(dataset_id, request.auth))
    return Status(204, None)


@router.post("/datasets/{int:dataset_id}/query", auth=session_auth, response=QueryResult, summary="Consulta (só lê)")
def query_dataset(request, dataset_id: int, spec: QuerySpec):
    """Só lê: usa POST apenas porque a spec vai no corpo.

    O trabalho roda em outra thread e a resposta tem prazo: se estourar, o cliente recebe 504 na hora. A thread não
    pode ser interrompida, mas segue segurando a sua vaga até acabar, então o servidor nunca executa mais do que
    MAX_CONCURRENT_QUERIES consultas ao mesmo tempo."""
    dataset = get_owned_dataset(dataset_id, request.auth)
    types = get_column_types(dataset)
    if types is None:
        raise HttpError(409, "Perfile o dataset antes de consultar")

    object_key, file_format = dataset.object_key, dataset.format

    def task() -> dict:
        return run_query(runtime.load_dataframe_cached(object_key, file_format), spec, types)

    future = _executor.submit(runtime.run_limited, task)
    try:
        return future.result(timeout=runtime.QUERY_TIMEOUT_SECONDS)
    except FutureTimeout as exc:
        raise HttpError(504, "A consulta demorou demais. Tente um filtro que reduza os dados.") from exc
    except runtime.QueryBusyError as exc:
        raise HttpError(503, "O servidor está ocupado com outras consultas. Tente de novo em instantes.") from exc
    except InvalidQueryError as exc:
        raise HttpError(422, str(exc)) from exc
