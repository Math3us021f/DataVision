from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scalar = str | int | float | bool
AggName = Literal["sum", "mean", "count", "min", "max", "count_distinct"]
FilterOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"]
ChartType = Literal["bar", "line", "pie", "kpi"]
TimeGrain = Literal["day", "month", "year"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FilterSpec(_Strict):
    column: str = Field(max_length=200)
    op: FilterOp
    value: Scalar | Annotated[list[Scalar], Field(max_length=100)]


class MetricSpec(_Strict):
    column: str = Field(max_length=200)
    agg: AggName


class DimensionSpec(_Strict):
    column: str = Field(max_length=200)
    time_grain: TimeGrain | None = None


class QuerySpec(_Strict):
    chart: ChartType
    dimension: DimensionSpec | None = None
    metrics: list[MetricSpec] = Field(min_length=1, max_length=4)
    filters: list[FilterSpec] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=20, ge=1, le=50)

    @model_validator(mode="after")
    def _check_shape(self) -> "QuerySpec":
        if self.chart == "kpi":
            if self.dimension is not None or len(self.metrics) != 1:
                raise ValueError("kpi: sem dimensão e com exatamente 1 métrica")
        elif self.dimension is None:
            raise ValueError("Informe a dimensão do gráfico")
        if self.chart == "pie" and len(self.metrics) != 1:
            raise ValueError("pie: exatamente 1 métrica")
        return self


class QueryResult(BaseModel):
    categories: list[str]
    series: list["SeriesOut"]
    total_rows_matched: int
    truncated: bool


class SeriesOut(BaseModel):
    name: str
    data: list[float | None]


QueryResult.model_rebuild()
