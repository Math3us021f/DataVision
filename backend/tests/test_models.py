"""Modelos: regras que o banco precisa garantir (únicos, exclusão em cascata, proteção e limites)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from accounts.models import EmailCode, LoginEvent, Notification
from audit.models import AuditLog
from datasets.models import Dashboard, Dataset, DatasetColumn, DatasetColumnTopValue, DatasetProfile

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user("dona", "senha-123-x")


@pytest.fixture
def dataset(user):
    return Dataset.objects.create(owner=user, original_name="vendas.csv", object_key="abc123.csv", format=".csv", size_bytes=120)


def full_dataset(dataset, user):
    """Dataset com tudo pendurado nele: perfil, coluna, valor frequente e dashboard."""
    DatasetProfile.objects.create(dataset=dataset, row_count=10, duplicate_row_count=0)
    column = DatasetColumn.objects.create(
        dataset=dataset, column_name="cidade", inferred_type="text", null_count=0, distinct_count=3,
        histogram={"bin_edges": [0, 1], "counts": [5]},
    )
    DatasetColumnTopValue.objects.create(column=column, value="SP", occurrence_count=6)
    Dashboard.objects.create(dataset=dataset, owner=user, spec={"widgets": [], "filters": []})
    return column


# ---------- exclusão em cascata e proteção ----------


def test_apagar_o_dataset_apaga_perfil_colunas_valores_e_dashboard(dataset, user):
    full_dataset(dataset, user)
    dataset.delete()
    assert not DatasetProfile.objects.exists() and not DatasetColumn.objects.exists()
    assert not DatasetColumnTopValue.objects.exists() and not Dashboard.objects.exists()
    assert User.objects.filter(pk=user.pk).exists()  # o dono continua existindo


def test_usuario_com_datasets_nao_pode_ser_excluido(user, dataset):
    with pytest.raises(ProtectedError):
        user.delete()
    assert User.objects.filter(pk=user.pk).exists()

    dataset.delete()  # a exclusão forçada apaga os datasets antes
    user.delete()
    assert not User.objects.filter(pk=user.pk).exists()


def test_excluir_usuario_leva_acessos_codigos_e_notificacoes_junto(user):
    LoginEvent.objects.create(user=user, success=True, browser="Chrome · Windows")
    EmailCode.objects.create(user=user, purpose="login", code_hash="x" * 64, expires_at=timezone.now())
    Notification.objects.create(user=user, kind="k", message="m")
    user.delete()
    assert not LoginEvent.objects.exists() and not EmailCode.objects.exists() and not Notification.objects.exists()


def test_auditoria_sobrevive_a_exclusao_do_usuario_com_referencias_vazias():
    admin = User.objects.create_superuser("chefe", "senha-123-x")
    alvo = User.objects.create_user("alvo", "senha-123-x")
    AuditLog.objects.create(actor=admin, action="delete_user", target=alvo, details="id=9 username='alvo'")
    alvo.delete()
    admin.delete()
    registro = AuditLog.objects.get()
    assert registro.actor is None and registro.target is None  # as referências ficam vazias...
    assert registro.details == "id=9 username='alvo'"  # ...e o histórico (com o nome) permanece


# ---------- únicos ----------


def test_object_key_e_unico(user, dataset):
    with pytest.raises(IntegrityError), transaction.atomic():
        Dataset.objects.create(owner=user, original_name="outro.csv", object_key="abc123.csv", format=".csv", size_bytes=1)


def test_um_perfil_e_um_dashboard_por_dataset(dataset, user):
    DatasetProfile.objects.create(dataset=dataset, row_count=1, duplicate_row_count=0)
    with pytest.raises(IntegrityError), transaction.atomic():
        DatasetProfile.objects.create(dataset=dataset, row_count=2, duplicate_row_count=0)
    Dashboard.objects.create(dataset=dataset, owner=user, spec={})
    with pytest.raises(IntegrityError), transaction.atomic():
        Dashboard.objects.create(dataset=dataset, owner=user, spec={})


def test_um_codigo_pendente_por_usuario_e_finalidade(user):
    base = {"code_hash": "x" * 64, "expires_at": timezone.now() + timedelta(minutes=10)}
    EmailCode.objects.create(user=user, purpose=EmailCode.Purpose.LOGIN, **base)
    EmailCode.objects.create(user=user, purpose=EmailCode.Purpose.EMAIL_CHANGE, new_email="n@exemplo.com", **base)  # outra finalidade: ok
    with pytest.raises(IntegrityError), transaction.atomic():
        EmailCode.objects.create(user=user, purpose=EmailCode.Purpose.LOGIN, **base)


# ---------- limites e padrões ----------


def test_numeros_negativos_sao_recusados_pelo_proprio_banco(user):
    with pytest.raises(IntegrityError), transaction.atomic():
        Dataset.objects.create(owner=user, original_name="x.csv", object_key="neg.csv", format=".csv", size_bytes=-1)


def test_padroes_dos_campos(user):
    assert user.session_version == 0 and user.preferences == {} and user.last_login is None
    assert user.created_at is not None and user.is_active and not user.is_admin
    aviso = Notification.objects.create(user=user, kind="k", message="m")
    assert aviso.read_at is None and aviso.created_at is not None
    codigo = EmailCode.objects.create(user=user, purpose="login", code_hash="x" * 64, expires_at=timezone.now())
    assert codigo.attempts == 0 and codigo.sends_in_window == 1


def test_campos_json_guardam_e_devolvem_a_estrutura(dataset, user):
    column = full_dataset(dataset, user)
    column.refresh_from_db()
    assert column.histogram == {"bin_edges": [0, 1], "counts": [5]}
    user.preferences = {"avatar_color": "violet"}
    user.save()
    user.refresh_from_db()
    assert user.preferences == {"avatar_color": "violet"}


def test_dashboard_atualiza_updated_at_e_mantem_created_at(dataset, user):
    full_dataset(dataset, user)
    dashboard = Dashboard.objects.get()
    criado, atualizado = dashboard.created_at, dashboard.updated_at
    dashboard.spec = {"widgets": [1], "filters": []}
    dashboard.save()
    dashboard.refresh_from_db()
    assert dashboard.created_at == criado and dashboard.updated_at > atualizado


def test_auditoria_vem_dos_mais_recentes_para_os_mais_antigos():
    for acao in ("create_user", "activate_user", "delete_user"):
        AuditLog.objects.create(action=acao)
    assert [a.action for a in AuditLog.objects.all()] == ["delete_user", "activate_user", "create_user"]


# ---------- paridade com o FastAPI ----------


def test_acoes_de_auditoria_sao_as_mesmas_do_fastapi():
    esperadas = [
        "create_user", "activate_user", "deactivate_user", "delete_user", "force_delete_user_datasets",
        "reset_password", "change_own_password", "revoke_other_sessions", "change_own_email", "admin_change_email",
    ]  # src/services/audit.py::KNOWN_ACTIONS
    assert [valor for valor, _ in AuditLog.Action.choices] == esperadas


def test_indices_de_consulta_existem_no_banco():
    with connection.cursor() as cursor:
        nomes = set(connection.introspection.get_constraints(cursor, "accounts_loginevent")) | set(
            connection.introspection.get_constraints(cursor, "accounts_notification")
        )
    assert {"login_events_user_idx", "notifications_user_idx"} <= nomes
