"""
Valida integridad de los datos de lanchas en la base de datos.

    python manage.py lanchas_validar
"""

from django.core.management.base import BaseCommand

from lanchas.models import Empresa, Linea, Servicio, Horario, Via, ActualizacionLog
from lanchas.pipeline.downloader import get_pdf_dir


class Command(BaseCommand):
    help = "Valida integridad de los datos de horarios de lanchas en la base de datos."

    def handle(self, *args, **options):
        advertencias = 0

        self.stdout.write("\n── RESUMEN ─────────────────────────────")
        self.stdout.write(f"  Empresas:         {Empresa.objects.count()}")
        self.stdout.write(f"  Líneas activas:   {Linea.objects.filter(activa=True).count()}")
        self.stdout.write(f"  Servicios activos:{Servicio.objects.filter(activo=True).count()}")
        self.stdout.write(f"  Horarios:         {Horario.objects.count()}")
        self.stdout.write(f"  Vías:             {Via.objects.count()}")

        self.stdout.write("\n── CHECKS ──────────────────────────────")

        # Servicios activos sin horarios
        sin_horarios = Servicio.objects.filter(activo=True, horarios__isnull=True).distinct()
        if sin_horarios.exists():
            self._warn(f"{sin_horarios.count()} servicio(s) sin horarios:")
            for s in sin_horarios[:10]:
                self._warn(f"    {s}")
            advertencias += 1
        else:
            self.stdout.write("  OK - todos los servicios tienen horarios")

        # Servicios activos sin recorrido
        sin_recorrido = Servicio.objects.filter(activo=True, tramos__isnull=True).distinct()
        if sin_recorrido.exists():
            self._warn(f"{sin_recorrido.count()} servicio(s) sin recorrido de vías:")
            for s in sin_recorrido[:10]:
                self._warn(f"    {s}")
            advertencias += 1
        else:
            self.stdout.write("  OK - todos los servicios tienen recorrido")

        # PDFs en disco
        pdf_dir = get_pdf_dir()
        for linea in Linea.objects.filter(activa=True):
            archivos = [linea.pdf_filename]
            if linea.pdf_filename_2:
                archivos.append(linea.pdf_filename_2)
            for nombre in archivos:
                pdf = pdf_dir / nombre
                if not pdf.exists():
                    self._warn(f"PDF no encontrado para línea {linea.numero}: {pdf}")
                    advertencias += 1

        # Última actualización por línea
        self.stdout.write("\n── ÚLTIMAS ACTUALIZACIONES ─────────────")
        for linea in Linea.objects.filter(activa=True).order_by("numero"):
            log = (
                ActualizacionLog.objects
                .filter(linea=linea)
                .order_by("-fecha")
                .first()
            )
            if log:
                estado = "OK" if log.exito else "ERROR"
                self.stdout.write(
                    f"  Línea {linea.numero}: {log.fecha:%Y-%m-%d %H:%M} [{estado}]"
                    f" - +{log.horarios_agregados} / -{log.horarios_eliminados}"
                )
            else:
                self._warn(f"  Línea {linea.numero}: sin actualizaciones registradas")
                advertencias += 1

        self.stdout.write("\n────────────────────────────────────────")
        if advertencias:
            self.stdout.write(f"Validación completada con {advertencias} advertencia(s).")
        else:
            self.stdout.write("Validación OK.")

    def _warn(self, msg: str):
        self.stderr.write(f"  ADVERTENCIA: {msg}")
