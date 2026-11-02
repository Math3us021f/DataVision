"""Cria o administrador inicial, se ainda não existir nenhum usuário."""

import os

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Cria o administrador inicial a partir de ADMIN_USERNAME e ADMIN_PASSWORD, só se o banco ainda não tiver usuários."

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write("Já existem usuários: nenhum administrador criado.")
            return
        username, password = os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"]
        User.objects.create_superuser(username, password)
        self.stdout.write(f"Administrador inicial criado: {username!r}.")
