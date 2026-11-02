from django.urls import path, re_path

from config.api import api
from core import views

urlpatterns = [
    path("login", views.login_page),
    path("app", views.app_shell),
    re_path(r"^app/(?P<path>.*)$", views.app_shell),
    path("", api.urls),
]
