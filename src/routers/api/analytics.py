from fastapi import APIRouter, Depends, HTTPException, status

from src.core.auth import get_current_user
from src.core.db import get_connection
from src.schemas.analytics import QueryResult, QuerySpec, WidgetSuggestion
from src.services.analytics.engine import run_query
from src.services.analytics.suggestions import suggest_dashboard
from src.services.analytics.validator import InvalidQueryError
from src.services.datasets import get_column_types, get_owned_dataset, get_stored_profile
from src.services.profiling import load_dataframe

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


@router.post("/{dataset_id}/query", response_model=QueryResult)
def query_dataset(dataset_id: int, spec: QuerySpec, user: dict = Depends(get_current_user)) -> dict:
    """Só lê: usa POST apenas porque a spec vai no corpo da requisição."""
    with get_connection() as conn:
        dataset = get_owned_dataset(conn, dataset_id, user["id"])
        types = get_column_types(conn, dataset_id)

    if types is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Perfile o dataset antes de consultar")

    df = load_dataframe(dataset["object_key"], dataset["format"])
    try:
        return run_query(df, spec, types)
    except InvalidQueryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
