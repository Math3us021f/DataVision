"""Os testes daqui vieram do FastAPI, quase sem mudança: usam o administrador do .env e o MinIO de verdade."""

import os

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture(autouse=True)
def contract_setup(db):
    User = get_user_model()
    if not User.objects.filter(username=os.environ["ADMIN_USERNAME"]).exists():
        User.objects.create_superuser(os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"])
