import anyio
from fastapi import APIRouter, Depends, HTTPException, status

from src.core.auth import get_current_user
from src.core.db import get_connection
from src.schemas.analytics import DashboardOut, DashboardSpec, QueryResult, QuerySpec, WidgetSuggestion
from src.services.analytics import runtime
from src.services.analytics.engine import run_query
from src.services.analytics.runtime import QueryBusyError, load_dataframe_cached, run_limited
from src.services.dashboards import delete_saved_dashboard, get_saved_dashboard, save_dashboard, validate_dashboard
from src.services.analytics.suggestions import suggest_dashboard
from src.services.analytics.validator import InvalidQueryError
from src.services.datasets import get_column_types, get_owned_dataset, get_stored_profile

router = APIRouter(prefix="/datasets", tags=["analytics"])


@router.get("/{dataset_id}/suggested-dashboard", response_model=list[WidgetSuggestion])
def suggested_dashboard(dataset_id: int, user: dict = Depends(get_current_user)) -> list[WidgetSuggestion]:
    """Painel inicial por regras sobre o perfil salvo. Devolve só as specs: cada widget busca seus dados em /query."""
    with get_connection() as conn:
        get_owned_dataset(conn, dataset_id, user["id"])
        if get_column_types(conn, dataset_id) is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Perfile o dataset antes de gerar o painel")
        profile = get_stored_profile(conn, dataset_id)
    return suggest_dashboard(profile)


@router.get("/{dataset_id}/dashboard", response_model=DashboardOut | None)
def get_dashboard(dataset_id: int, user: dict = Depends(get_current_user)) -> dict | None:
    """O dashboard salvo, ou null se o dataset ainda não tem um."""
    with get_connection() as conn:
        get_owned_dataset(conn, dataset_id, user["id"])
        return get_saved_dashboard(conn, dataset_id)


@router.put("/{dataset_id}/dashboard", response_model=DashboardOut)
def put_dashboard(dataset_id: int, spec: DashboardSpec, user: dict = Depends(get_current_user)) -> dict:
    with get_connection() as conn:
        get_owned_dataset(conn, dataset_id, user["id"])
        types = get_column_types(conn, dataset_id)
        if types is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Perfile o dataset antes de salvar o dashboard")
        try:
            validate_dashboard(spec, types)
        except InvalidQueryError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        saved = save_dashboard(conn, dataset_id, user["id"], spec)
        conn.commit()
    return saved


@router.delete("/{dataset_id}/dashboard", status_code=status.HTTP_204_NO_CONTENT)
def delete_dashboard(dataset_id: int, user: dict = Depends(get_current_user)) -> None:
    with get_connection() as conn:
        get_owned_dataset(conn, dataset_id, user["id"])
        delete_saved_dashboard(conn, dataset_id)
        conn.commit()


def _execute_query(dataset_id: int, spec: QuerySpec, user_id: int) -> dict:
    with get_connection() as conn:
        dataset = get_owned_dataset(conn, dataset_id, user_id)
        types = get_column_types(conn, dataset_id)

    if types is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Perfile o dataset antes de consultar")

    def task() -> dict:
        df = load_dataframe_cached(dataset["object_key"], dataset["format"])
        return run_query(df, spec, types)

    try:
        return run_limited(task)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except QueryBusyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="O servidor está ocupado com outras consultas. Tente de novo em instantes."
        ) from exc


@router.post("/{dataset_id}/query", response_model=QueryResult)
async def query_dataset(dataset_id: int, spec: QuerySpec, user: dict = Depends(get_current_user)) -> dict:
    """Só lê: usa POST apenas porque a spec vai no corpo da requisição.

    O trabalho roda em outra thread e a resposta tem prazo: se estourar, o cliente recebe 504 na hora.
    A thread não pode ser interrompida, mas segue segurando a sua vaga até acabar, então o servidor
    nunca executa mais do que `MAX_CONCURRENT_QUERIES` consultas ao mesmo tempo."""
    try:
        with anyio.fail_after(runtime.QUERY_TIMEOUT_SECONDS):
            return await anyio.to_thread.run_sync(_execute_query, dataset_id, spec, user["id"], abandon_on_cancel=True)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="A consulta demorou demais. Tente um filtro que reduza os dados."
        ) from exc
