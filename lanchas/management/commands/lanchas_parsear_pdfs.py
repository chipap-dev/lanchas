"""
Parsea los PDFs descargados y carga los horarios en la base de datos.
Solo reprocesa si el PDF cambió desde la última carga (por hash SHA-256).

    python manage.py lanchas_parsear_pdfs
    python manage.py lanchas_parsear_pdfs --linea 451
    python manage.py lanchas_parsear_pdfs --forzar   # reprocesa aunque no haya cambios
"""

from django.core.management.base import BaseCommand, CommandError

from lanchas.models import Linea, ActualizacionLog
from lanchas.pipeline.downloader import get_pdf_dir, hash_archivo, hash_combinado
from lanchas.pipeline.loader import cargar_servicios, registrar_sin_cambios
from lanchas.services.parsers import (
    InterislenaParser,
    JilgueroParser,
    DeltaArgentinoParser,
    ParserError,
)

PARSERS = {
    "450": JilgueroParser,
    "451/452": InterislenaParser,  # combina LINEA_451.pdf + LINEA_452.pdf
    "453": DeltaArgentinoParser,
}


class Command(BaseCommand):
    help = "Parsea los PDFs descargados y carga los horarios en la base de datos."

    def add_arguments(self, parser):
        parser.add_argument("--linea", dest="linea_numero")
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Reprocesar aunque el PDF no haya cambiado desde la última carga.",
        )

    def handle(self, *args, **options):
        lineas = Linea.objects.filter(activa=True).select_related("empresa")
        if options["linea_numero"]:
            lineas = lineas.filter(numero=options["linea_numero"])
            if not lineas.exists():
                raise CommandError(f"Línea {options['linea_numero']} no encontrada.")

        pdf_dir = get_pdf_dir()
        total_errores: list[str] = []

        for linea in lineas:
            pdf_path = pdf_dir / linea.pdf_filename
            pdf_path_2 = pdf_dir / linea.pdf_filename_2 if linea.pdf_filename_2 else None

            if not pdf_path.exists() or (pdf_path_2 and not pdf_path_2.exists()):
                self.stderr.write(
                    f"Línea {linea.numero}: PDF no encontrado en {pdf_dir}. "
                    "Ejecutar lanchas_descargar_pdfs primero."
                )
                continue

            hash_actual = hash_combinado([pdf_path, pdf_path_2]) if pdf_path_2 else hash_archivo(pdf_path)

            if not options["forzar"]:
                ultimo = (
                    ActualizacionLog.objects
                    .filter(linea=linea, exito=True)
                    .order_by("-fecha")
                    .first()
                )
                if ultimo and ultimo.pdf_hash == hash_actual:
                    self.stdout.write(f"Línea {linea.numero}: sin cambios, omitiendo.")
                    continue

            parser_factory = PARSERS.get(linea.numero)
            if not parser_factory:
                self.stderr.write(
                    f"Línea {linea.numero}: sin parser implementado, omitiendo."
                )
                continue

            try:
                parser = parser_factory(pdf_path, pdf_path_2) if pdf_path_2 else parser_factory(pdf_path)
                servicios_data = parser.parse()
                resultado = cargar_servicios(
                    linea, servicios_data, hash_actual,
                    errores_previos=getattr(parser, "errores", None),
                    notas_previas=getattr(parser, "notas", None),
                )
                self.stdout.write(
                    f"Línea {linea.numero}: "
                    f"+{resultado['agregados']} / -{resultado['eliminados']} horarios, "
                    f"{len(resultado['errores'])} error(es)"
                )
                for err in resultado["errores"]:
                    self.stderr.write(f"  {err}")
                total_errores.extend(resultado["errores"])
            except NotImplementedError as exc:
                self.stderr.write(f"Línea {linea.numero}: {exc}")
            except ParserError as exc:
                self.stderr.write(f"Línea {linea.numero}: error de parseo — {exc}")
                total_errores.append(str(exc))

        if total_errores:
            raise CommandError(f"Completado con {len(total_errores)} error(es).")
