"""
Carga el calendario oficial de feriados de Argentina en la base de datos.

    python manage.py lanchas_sincronizar_feriados
    python manage.py lanchas_sincronizar_feriados --anios 2026 2027
"""

from django.core.management.base import BaseCommand

from lanchas.services.feriados import sincronizar_feriados


class Command(BaseCommand):
    help = "Sincroniza la tabla Feriado con el calendario oficial de Argentina."

    def add_arguments(self, parser):
        parser.add_argument("--anios", nargs="+", type=int, default=None)

    def handle(self, *args, **options):
        agregados = sincronizar_feriados(anios=options["anios"])
        self.stdout.write(f"Feriados: +{agregados} nuevo(s).")
