from django.conf import settings
from django.db import models


class Dataset(models.Model):
    """Um arquivo enviado (o original fica no MinIO, em `object_key`)."""

    # PROTECT: não dá para excluir um usuário que ainda tem datasets. A exclusão forçada apaga os datasets
    # explicitamente antes (e os arquivos no MinIO), depois a conta.
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="datasets")
    original_name = models.TextField()
    object_key = models.CharField(max_length=255, unique=True)  # nome gerado pelo servidor (nunca o do usuário)
    format = models.CharField(max_length=10)  # ".csv" ou ".xlsx"
    size_bytes = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.original_name


class DatasetProfile(models.Model):
    """Resultado do perfilamento: números gerais do arquivo. Um por dataset."""

    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE, related_name="profile")
    row_count = models.PositiveIntegerField()
    duplicate_row_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class DatasetColumn(models.Model):
    """Estatísticas de uma coluna do dataset."""

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="columns")
    column_name = models.TextField()
    inferred_type = models.CharField(max_length=20)  # integer, float, text, datetime, boolean...
    null_count = models.PositiveIntegerField()
    distinct_count = models.PositiveIntegerField()
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    mean_value = models.FloatField(null=True, blank=True)
    median_value = models.FloatField(null=True, blank=True)
    histogram = models.JSONField(null=True, blank=True)  # {"bin_edges": [...], "counts": [...]}


class DatasetColumnTopValue(models.Model):
    """Os valores mais frequentes de uma coluna de texto."""

    column = models.ForeignKey(DatasetColumn, on_delete=models.CASCADE, related_name="top_values")
    value = models.TextField()
    occurrence_count = models.PositiveIntegerField()


class Dashboard(models.Model):
    """O dashboard salvo de um dataset (um por dataset). `spec` guarda os gráficos e filtros; o servidor
    valida cada um contra o perfil antes de salvar."""

    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE, related_name="dashboard")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dashboards")
    spec = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
