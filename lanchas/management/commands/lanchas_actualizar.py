"""
Descarga PDFs y parsea horarios en un solo paso. Punto de entrada del cron semanal.

    python manage.py lanchas_actualizar
    python manage.py lanchas_actualizar --linea 451
    python manage.py lanchas_actualizar --forzar
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Descarga PDFs y carga horarios en la base de datos (download + parse)."

    def add_arguments(self, parser):
        parser.add_argument("--linea", dest="linea_numero")
        parser.add_argument("--forzar", action="store_true")

    def handle(self, *args, **options):
        kwargs = {}
        if options["linea_numero"]:
            kwargs["linea"] = options["linea_numero"]

        self.stdout.write("→ Verificando catálogo de empresas/líneas...")
        call_command(
            "lanchas_inicializar",
            stdout=self.stdout, stderr=self.stderr,
        )

        self.stdout.write("→ Descargando PDFs...")
        call_command(
            "lanchas_descargar_pdfs", **kwargs,
            stdout=self.stdout, stderr=self.stderr,
        )

        self.stdout.write("→ Parseando y cargando en base de datos...")
        if options["forzar"]:
            kwargs["forzar"] = True
        call_command(
            "lanchas_parsear_pdfs", **kwargs,
            stdout=self.stdout, stderr=self.stderr,
        )

        self.stdout.write("→ Sincronizando calendario de feriados...")
        call_command(
            "lanchas_sincronizar_feriados",
            stdout=self.stdout, stderr=self.stderr,
        )

        self.stdout.write("Actualización completada.")
