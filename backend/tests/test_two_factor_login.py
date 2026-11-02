"""Login em dois passos: o código enviado por e-mail (rotas /login, /login/verify, /login/resend) e os códigos em si."""

import logging
import re
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db.models import F
from django.utils import timezone

from accounts import login_flow
from accounts.models import EmailCode, LoginEvent
from accounts.verification import (
    CodeCooldownError,
    CodeRejectedError,
    InvalidEmailError,
    TooManyCodesError,
    check_code,
    issue_code,
    mask_email,
    normalize_email,
)
from core.mailer import MailNotConfiguredError, MailSendError
from tests.conftest import PASSWORD, ApiClient, code_of

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_user(email="pessoa@exemplo.com", username="tf"):
    return User.objects.create_user(username, PASSWORD, email=email)


def first_step(username="tf", password=PASSWORD):
    cliente = ApiClient()
    return cliente, cliente.post("/login", json={"username": username, "password": password})


def age_code(user, **campos):
    """Envelhece o código no banco (em vez de esperar de verdade)."""
    EmailCode.objects.filter(user=user, purpose="login").update(**campos)


# ---------- funções puras ----------


def test_mascara_do_email():
    assert mask_email("maria@gmail.com") == "m***@gmail.com"
    assert mask_email("a@b.co") == "a***@b.co"
    assert mask_email(None) is None and mask_email("") is None


@pytest.mark.parametrize("ruim", ["", "   ", "sem-arroba", "a@b", "a b@c.com", "a@b c.com", "x" * 250 + "@a.com", "a@b.com\nBcc: alguem@x.com"])
def test_email_invalido_e_recusado(ruim):
    with pytest.raises(InvalidEmailError):
        normalize_email(ruim)


def test_email_e_normalizado_para_minusculas():
    assert normalize_email("  Maria.Souza@Gmail.COM ") == "maria.souza@gmail.com"


# ---------- etapa da senha ----------


def test_conta_sem_email_continua_entrando_so_com_a_senha(outbox):
    User.objects.create_user("sem", PASSWORD)
    cliente, resposta = first_step("sem")
    assert resposta.json() == {"status": "ok"} and cliente.get("/me").status_code == 200 and outbox == []


def test_com_email_a_senha_certa_nao_da_sessao_e_envia_o_codigo(outbox):
    make_user()
    cliente, resposta = first_step()
    corpo = resposta.json()
    assert corpo == {"status": "2fa_required", "email_hint": "p***@exemplo.com", "resend_in": 30}
    assert cliente.get("/me").status_code == 401  # ainda não há sessão
    assert "session" not in resposta.cookies and "pending_login" in resposta.cookies
    assert len(outbox) == 1 and outbox[0][0] == "pessoa@exemplo.com"
    assert re.fullmatch(r"\d{6}", code_of(outbox[0])) and code_of(outbox[0]) not in resposta.content.decode()


def test_senha_errada_com_email_nao_envia_nada(outbox):
    make_user()
    _, resposta = first_step(password="errada-1234")
    assert resposta.status_code == 401 and outbox == []


# ---------- etapa do código ----------


def test_codigo_certo_conclui_o_login_e_so_vale_uma_vez(outbox):
    make_user()
    cliente, _ = first_step()
    codigo = code_of(outbox[0])
    pronto = cliente.post("/login/verify", json={"code": codigo})
    assert pronto.status_code == 200 and pronto.json() == {"status": "ok"}
    assert cliente.get("/me").json()["username"] == "tf"
    assert LoginEvent.objects.filter(success=True).count() == 1

    outro, _ = first_step()
    assert outro.post("/login/verify", json={"code": codigo}).status_code == 401  # já consumido (e o novo login pediu outro)


def test_codigo_aceita_espacos_ao_redor(outbox):
    make_user()
    cliente, _ = first_step()
    codigo = code_of(outbox[0])
    assert cliente.post("/login/verify", json={"code": f" {codigo[:3]} {codigo[3:]} "}).status_code == 200


def test_codigo_errado_conta_tentativas_e_esgota_na_quinta(outbox):
    usuario = make_user()
    cliente, _ = first_step()
    real = code_of(outbox[0])
    errado = "000000" if real != "000000" else "111111"

    for restante in ("4 tentativas", "3 tentativas", "2 tentativas", "1 tentativa"):
        resposta = cliente.post("/login/verify", json={"code": errado})
        assert resposta.status_code == 401 and restante in resposta.json()["detail"]
    ultima = cliente.post("/login/verify", json={"code": errado})
    assert ultima.status_code == 401 and "Muitas tentativas" in ultima.json()["detail"]

    assert cliente.post("/login/verify", json={"code": real}).status_code == 401  # esgotado: nem o certo vale
    assert cliente.get("/me").status_code == 401
    assert not EmailCode.objects.filter(user=usuario, purpose="login").exists()
    assert LoginEvent.objects.filter(user=usuario, success=False).count() == 1  # o esgotamento entra no histórico


def test_tentativa_errada_continua_contada_apesar_da_transacao(outbox):
    """Regressão da armadilha do Django: uma exceção dentro de `atomic()` desfaz tudo, inclusive o contador. Se isso
    voltasse a acontecer, o código poderia ser adivinhado sem limite."""
    usuario = make_user()
    cliente, _ = first_step()
    errado = "000000" if code_of(outbox[0]) != "000000" else "111111"
    cliente.post("/login/verify", json={"code": errado})
    cliente.post("/login/verify", json={"code": errado})
    assert EmailCode.objects.get(user=usuario, purpose="login").attempts == 2


def test_formato_invalido_conta_como_tentativa_errada(outbox):
    make_user()
    cliente, _ = first_step()
    for lixo in ("abc", "12345", "1234567", "' OR 1=1 --", ""):
        assert cliente.post("/login/verify", json={"code": lixo}).status_code == 401
    assert cliente.get("/me").status_code == 401


def test_codigo_vencido_e_recusado(outbox):
    usuario = make_user()
    cliente, _ = first_step()
    age_code(usuario, expires_at=timezone.now() - timedelta(minutes=1))
    resposta = cliente.post("/login/verify", json={"code": code_of(outbox[0])})
    assert resposta.status_code == 401 and "expirou" in resposta.json()["detail"]


def test_verificar_sem_ter_passado_pela_senha_nao_funciona(outbox):
    make_user()
    first_step()
    sem_cookie = ApiClient()
    assert sem_cookie.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 401
    adulterado = ApiClient()
    adulterado.cookies["pending_login"] = "valor.adulterado.qualquer"
    assert adulterado.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 401


def test_cookie_da_etapa_nao_serve_como_sessao(outbox):
    make_user()
    cliente, _ = first_step()
    assert "pending_login" in cliente.cookies
    for caminho in ("/me", "/app"):
        resposta = cliente.get(caminho)
        assert resposta.status_code in (401, 302), caminho  # nem a API nem as páginas o aceitam
    assert cliente.get("/me").status_code == 401
    assert cliente.post("/login/resend").status_code == 429  # a rota da etapa o reconhece (só pede a pausa do reenvio)


def test_codigo_de_um_usuario_nao_serve_para_outro(outbox):
    make_user(username="a", email="a@exemplo.com")
    make_user(username="b", email="b@exemplo.com")
    cliente_a, _ = first_step("a")
    cliente_b, _ = first_step("b")
    codigo_a, codigo_b = code_of(outbox[0]), code_of(outbox[1])
    if codigo_a != codigo_b:  # (6 dígitos: coincidir é raro, e nesse caso o teste não prova nada)
        assert cliente_b.post("/login/verify", json={"code": codigo_a}).status_code == 401
    assert cliente_a.post("/login/verify", json={"code": codigo_a}).status_code == 200


# ---------- reenvio e limites ----------


def test_reenvio_so_depois_da_pausa_e_invalida_o_codigo_anterior(outbox):
    usuario = make_user()
    cliente, _ = first_step()
    antigo = code_of(outbox[0])
    assert cliente.post("/login/resend").status_code == 429 and len(outbox) == 1

    age_code(usuario, last_sent_at=timezone.now() - timedelta(seconds=31))
    ok = cliente.post("/login/resend")
    assert ok.status_code == 200 and ok.json() == {"resend_in": 30} and len(outbox) == 2
    novo = code_of(outbox[1])
    if novo != antigo:
        assert cliente.post("/login/verify", json={"code": antigo}).status_code == 401
    assert cliente.post("/login/verify", json={"code": novo}).status_code == 200


def test_entrar_de_novo_logo_em_seguida_nao_manda_outro_email(outbox):
    make_user()
    first_step()
    cliente, segunda = first_step()
    assert segunda.json()["status"] == "2fa_required" and segunda.json()["resend_in"] == 0
    assert len(outbox) == 1  # o primeiro código continua valendo
    assert cliente.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 200


def test_limite_de_codigos_por_hora(outbox):
    usuario = make_user()
    first_step()
    age_code(usuario, last_sent_at=timezone.now() - timedelta(minutes=1), sends_in_window=10)
    _, resposta = first_step()
    assert resposta.status_code == 429 and len(outbox) == 1


def test_a_janela_de_uma_hora_recomeca(outbox):
    usuario = make_user()
    first_step()
    age_code(usuario, last_sent_at=timezone.now() - timedelta(minutes=61), window_started_at=timezone.now() - timedelta(minutes=61), sends_in_window=10)
    _, resposta = first_step()
    assert resposta.status_code == 200 and len(outbox) == 2
    assert EmailCode.objects.get(user=usuario).sends_in_window == 1


# ---------- falhas e privacidade ----------


@pytest.mark.parametrize("erro", [MailSendError, MailNotConfiguredError])
def test_falha_no_envio_bloqueia_o_login_sem_sessao_nem_codigo_pendente(monkeypatch, erro):
    usuario = make_user()

    def quebra(*args):
        raise erro

    monkeypatch.setattr(login_flow, "send_email", quebra)
    cliente, resposta = first_step()
    assert resposta.status_code == 503 and "session" not in resposta.cookies and "pending_login" not in resposta.cookies
    assert cliente.get("/me").status_code == 401
    assert not EmailCode.objects.filter(user=usuario).exists()


def test_codigo_e_guardado_so_como_hash_e_nao_vai_para_o_log(outbox, caplog):
    usuario = make_user()
    with caplog.at_level(logging.DEBUG, logger="datavision"):
        first_step()
    codigo = code_of(outbox[0])
    guardado = EmailCode.objects.get(user=usuario).code_hash
    assert guardado != codigo and len(guardado) == 64 and codigo not in guardado
    assert codigo not in caplog.text


def test_conta_desativada_ou_senha_trocada_no_meio_derruba_a_verificacao(outbox):
    a = make_user(username="a", email="a@exemplo.com")
    cliente_a, _ = first_step("a")
    User.objects.filter(pk=a.pk).update(is_active=False)
    assert cliente_a.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 401

    b = make_user(username="b", email="b@exemplo.com")
    cliente_b, _ = first_step("b")
    User.objects.filter(pk=b.pk).update(session_version=F("session_version") + 1)
    assert cliente_b.post("/login/verify", json={"code": code_of(outbox[1])}).status_code == 401


def test_etapas_do_dois_passos_exigem_o_token_csrf(outbox):
    make_user()
    cliente = ApiClient(enforce_csrf_checks=True)
    cliente.get("/login")
    token = cliente.cookies["csrftoken"].value
    assert cliente.post("/login", json={"username": "tf", "password": PASSWORD}).status_code == 403
    assert cliente.post("/login", json={"username": "tf", "password": PASSWORD}, HTTP_X_CSRFTOKEN=token).status_code == 200
    assert cliente.post("/login/verify", json={"code": code_of(outbox[0])}).status_code == 403
    assert cliente.post("/login/resend").status_code == 403
    pronto = cliente.post("/login/verify", json={"code": code_of(outbox[0])}, HTTP_X_CSRFTOKEN=token)
    assert pronto.status_code == 200


# ---------- os códigos em si (sem passar pela API) ----------


def test_pedir_outro_codigo_antes_da_pausa_e_recusado():
    usuario = make_user()
    issue_code(usuario, "login")
    with pytest.raises(CodeCooldownError) as erro:
        issue_code(usuario, "login")
    assert 1 <= erro.value.seconds_left <= 31


def test_o_limite_por_hora_levanta_erro_proprio():
    usuario = make_user()
    issue_code(usuario, "login")
    EmailCode.objects.filter(user=usuario).update(last_sent_at=timezone.now() - timedelta(minutes=1), sends_in_window=10)
    with pytest.raises(TooManyCodesError):
        issue_code(usuario, "login")


def test_codigo_de_login_nao_confirma_troca_de_email_e_vice_versa():
    usuario = make_user()
    codigo = issue_code(usuario, "login")
    with pytest.raises(CodeRejectedError) as erro:
        check_code(usuario, "email_change", codigo)  # outra finalidade: não existe código pendente para ela
    assert erro.value.reason == "missing"
    assert check_code(usuario, "login", codigo) is None  # na finalidade certa, vale


def test_troca_de_email_devolve_o_endereco_novo_guardado():
    usuario = make_user()
    codigo = issue_code(usuario, "email_change", new_email="novo@exemplo.com")
    assert check_code(usuario, "email_change", codigo) == "novo@exemplo.com"
    with pytest.raises(CodeRejectedError):  # uso único
        check_code(usuario, "email_change", codigo)
