from django.urls import path, re_path

from config.api import api
from core import views

# A tela de entrada (GET /login) é registrada na própria API (config/api.py), junto do POST /login: uma mesma
# URL do Django não distingue o método HTTP, então os dois precisam morar no mesmo lugar.
urlpatterns = [
    path("app", views.app_shell),
    re_path(r"^app/(?P<path>.*)$", views.app_shell),
    path("", api.urls),
]
