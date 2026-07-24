"""
Descarga los PDFs de horarios desde el servidor de la provincia de Buenos Aires.

    python manage.py lanchas_descargar_pdfs
    python manage.py lanchas_descargar_pdfs --linea 451
"""

from django.core.management.base import BaseCommand, CommandError

from lanchas.models import Linea
from lanchas.pipeline.downloader import descargar_todos


class Command(BaseCommand):
    help = "Descarga los PDFs de horarios de lanchas desde el servidor oficial."

    def add_arguments(self, parser):
        parser.add_argument(
            "--linea",
            dest="linea_numero",
            help="Número de línea a descargar (ej: 451). Omitir para todas.",
        )

    def handle(self, *args, **options):
        lineas = Linea.objects.filter(activa=True).select_related("empresa")
        if options["linea_numero"]:
            lineas = lineas.filter(numero=options["linea_numero"])
            if not lineas.exists():
                raise CommandError(
                    f"Línea {options['linea_numero']} no encontrada. "
                    "Ejecutar lanchas_inicializar primero."
                )

        resultados = descargar_todos(list(lineas))

        for r in resultados:
            if r["ok"]:
                estado = "modificado" if r["modificado"] else "sin cambios"
                self.stdout.write(
                    f"Línea {r['linea'].numero}: {estado} - {r['bytes']:,} bytes"
                )
            else:
                self.stderr.write(f"Línea {r['linea'].numero}: ERROR - {r['error']}")

        errores = [r for r in resultados if not r["ok"]]
        if errores:
            raise CommandError(f"{len(errores)} PDF(s) no pudieron descargarse.")
