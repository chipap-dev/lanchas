"""
Lista empresas, líneas y servicios con estado de datos.

    python manage.py lanchas_listar
    python manage.py lanchas_listar --empresa interislena
    python manage.py lanchas_listar --via rio-sarmiento
"""

from django.core.management.base import BaseCommand

from lanchas.models import Empresa, Horario, ActualizacionLog, Via
from lanchas.services.horarios import lineas_por_via


class Command(BaseCommand):
    help = "Lista empresas, líneas y servicios de lanchas con estado de datos."

    def add_arguments(self, parser):
        parser.add_argument("--empresa", dest="empresa_slug")
        parser.add_argument("--via", dest="via_slug", help="Listar servicios que pasan por una vía")

    def handle(self, *args, **options):
        if options["via_slug"]:
            self._listar_por_via(options["via_slug"])
            return

        empresas = Empresa.objects.prefetch_related(
            "lineas__servicios__tramos__via"
        ).order_by("nombre")
        if options["empresa_slug"]:
            empresas = empresas.filter(slug=options["empresa_slug"])

        for empresa in empresas:
            self.stdout.write(f"\n{'=' * 60}")
            self.stdout.write(f"{empresa.nombre}")
            if empresa.razon_social:
                self.stdout.write(f"  {empresa.razon_social}")

            for linea in empresa.lineas.filter(activa=True):
                log = (
                    ActualizacionLog.objects
                    .filter(linea=linea)
                    .order_by("-fecha")
                    .first()
                )
                estado_log = f"actualizado {log.fecha:%Y-%m-%d}" if log else "sin datos"
                n_horarios = Horario.objects.filter(servicio__linea=linea).count()
                self.stdout.write(
                    f"\n  Línea {linea.numero} — {estado_log} — {n_horarios} horarios"
                )

                for servicio in linea.servicios.filter(activo=True).order_by("orden"):
                    n = Horario.objects.filter(servicio=servicio).count()
                    vias = " → ".join(
                        t.via.nombre for t in servicio.tramos.order_by("orden")
                    )
                    self.stdout.write(
                        f"    [{servicio.tipo:<14}] {servicio.nombre} ({n} horarios)"
                    )
                    if vias:
                        self.stdout.write(f"                     {vias}")

    def _listar_por_via(self, via_slug: str):
        try:
            via = Via.objects.get(slug=via_slug)
        except Via.DoesNotExist:
            self.stderr.write(f"Vía '{via_slug}' no encontrada.")
            vias_disponibles = Via.objects.order_by("nombre").values_list("slug", "nombre")
            self.stdout.write("Vías disponibles:")
            for slug, nombre in vias_disponibles:
                self.stdout.write(f"  {slug} — {nombre}")
            return

        self.stdout.write(f"\nServicios que pasan por: {via.nombre}")
        servicios = lineas_por_via(via_slug)
        for s in servicios:
            n = Horario.objects.filter(servicio=s).count()
            self.stdout.write(
                f"  Línea {s.linea.numero} ({s.linea.empresa.nombre}) — "
                f"{s.nombre} [{s.tipo}] — {n} horarios"
            )
