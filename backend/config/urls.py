from django.urls import path, re_path

from config.api import api
from core import views

# A tela de entrada (GET /login) é registrada na própria API (accounts/api.py), junto do POST /login: uma mesma
# URL do Django não distingue o método HTTP, então os dois precisam morar no mesmo lugar.
urlpatterns = [
    path("", views.home_redirect),
    path("app", views.app_shell),
    re_path(r"^app/(?P<path>.*)$", views.app_shell),
    path("meus-datasets", views.datasets_redirect),
    path("meus-datasets/<int:dataset_id>/dashboard", views.dataset_dashboard_redirect),
    path("account", views.account_redirect),
    path("admin", views.admin_index),
    path("admin/<str:page>", views.admin_page),
    path("", api.urls),
]
