"""
Crea los registros iniciales de Empresa y Linea en la base de datos.
Idempotente - seguro ejecutar múltiples veces.

Ejecutar una vez antes del primer lanchas_descargar_pdfs:
    python manage.py lanchas_inicializar
"""

from django.core.management.base import BaseCommand

from lanchas.pipeline.loader import inicializar_catalogo, LINEAS_CONFIG


class Command(BaseCommand):
    help = "Inicializa el catálogo de empresas y líneas de lanchas (idempotente)."

    def handle(self, *args, **options):
        inicializar_catalogo()
        for cfg in LINEAS_CONFIG:
            for l in cfg["lineas"]:
                self.stdout.write(f"  [{cfg['empresa_slug']}] Línea {l['numero']} - {l['pdf_url']}")
        self.stdout.write("Catálogo listo.")
