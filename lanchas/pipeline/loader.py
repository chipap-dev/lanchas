"""
Carga datos parseados en la base de datos.

Estrategia de actualización: reemplazo completo de horarios por servicio.
Cuando un PDF cambia, se eliminan todos los Horario del servicio y se insertan
los nuevos. Los objetos Servicio, Via y RecorridoTramo se actualizan in-place.
"""

import logging
import re
from datetime import time

from django.db import transaction
from django.utils.text import slugify

from lanchas.models import (
    Empresa,
    Linea,
    Via,
    Servicio,
    RecorridoTramo,
    Horario,
    ActualizacionLog,
)

logger = logging.getLogger(__name__)

# Fuente de verdad del catálogo de empresas y líneas.
# inicializar_catalogo() usa este dict para crear los registros si no existen.
LINEAS_CONFIG = [
    {
        "empresa_nombre": "Interisleña S.A.C.I.",
        "empresa_slug": "interislena",
        "razon_social": "Interisleña S.A.C.I.",
        "lineas": [
            {
                # Interisleña publica sus servicios en dos PDF (451 y 452);
                # se tratan como una sola Línea combinada, no dos líneas
                # separadas — pdf_url/pdf_filename son el 451, pdf_url_2/
                # pdf_filename_2 el 452.
                "numero": "451/452",
                "pdf_url": "https://www.minfra.gba.gob.ar/web/Transporte/Fluvial/LINEA_451.pdf",
                "pdf_filename": "LINEA_451.pdf",
                "pdf_url_2": "https://www.minfra.gba.gob.ar/web/Transporte/Fluvial/LINEA_452.pdf",
                "pdf_filename_2": "LINEA_452.pdf",
            },
        ],
    },
    {
        "empresa_nombre": "Jilguero",
        "empresa_slug": "jilguero",
        "razon_social": "Francisco Buiatti e Hijos S.A.",
        "lineas": [
            {
                "numero": "450",
                "pdf_url": "https://www.minfra.gba.gob.ar/web/Transporte/Fluvial/LINEA_450.pdf",
                "pdf_filename": "LINEA_450.pdf",
            },
        ],
    },
    {
        "empresa_nombre": "Delta Argentino",
        "empresa_slug": "delta-argentino",
        "razon_social": "Delta Argentino S.R.L.",
        "lineas": [
            {
                "numero": "453",
                "pdf_url": "https://www.minfra.gba.gob.ar/web/Transporte/Fluvial/LINEA_453.pdf",
                "pdf_filename": "LINEA_453.pdf",
            },
        ],
    },
]


def inicializar_catalogo():
    """
    Crea o actualiza Empresa y Linea del catálogo oficial. Idempotente.
    Llamar antes del primer lanchas_descargar_pdfs.
    """
    for cfg in LINEAS_CONFIG:
        empresa, _ = Empresa.objects.update_or_create(
            slug=cfg["empresa_slug"],
            defaults={
                "nombre": cfg["empresa_nombre"],
                "razon_social": cfg["razon_social"],
            },
        )
        for l_cfg in cfg["lineas"]:
            Linea.objects.update_or_create(
                empresa=empresa,
                numero=l_cfg["numero"],
                defaults={
                    "pdf_url": l_cfg["pdf_url"],
                    "pdf_filename": l_cfg["pdf_filename"],
                    "pdf_url_2": l_cfg.get("pdf_url_2", ""),
                    "pdf_filename_2": l_cfg.get("pdf_filename_2", ""),
                },
            )
    logger.info("Catálogo inicializado: %d empresas", len(LINEAS_CONFIG))


def cargar_servicios(
    linea: Linea,
    servicios_data: list[dict],
    pdf_hash: str,
    errores_previos: list[str] | None = None,
    notas_previas: list[str] | None = None,
) -> dict:
    """
    Carga la lista de servicios parseados para una línea en la DB.
    Retorna {'agregados': int, 'eliminados': int, 'errores': [str]}.

    `errores_previos`/`notas_previas` permiten que el parser reporte
    anomalías detectadas durante el parseo (por bloque de servicio fallido,
    o datos ambiguos) para que queden asentadas en el mismo ActualizacionLog.
    """
    total_agregados = 0
    total_eliminados = 0
    errores: list[str] = list(errores_previos or [])

    with transaction.atomic():
        for orden, srv_data in enumerate(servicios_data):
            try:
                # Savepoint por servicio: si uno falla, Postgres deja la
                # transacción externa inutilizable hasta hacer rollback —
                # sin este atomic() anidado, el primer error arrastra a
                # todos los servicios siguientes (y al ActualizacionLog
                # final) con el mismo error genérico de transacción rota,
                # tapando el error real. SQLite no tiene este problema, por
                # eso no se detectó hasta correr contra Postgres.
                with transaction.atomic():
                    agregados, eliminados = _cargar_servicio(linea, srv_data, orden)
                total_agregados += agregados
                total_eliminados += eliminados
            except Exception as exc:
                msg = f"Error cargando '{srv_data.get('servicio_nombre', '?')}': {exc}"
                logger.error(msg)
                errores.append(msg)

        ActualizacionLog.objects.create(
            linea=linea,
            pdf_hash=pdf_hash,
            pdf_modificado=True,
            exito=len(errores) == 0,
            horarios_agregados=total_agregados,
            horarios_eliminados=total_eliminados,
            errores=errores,
            notas="\n".join(notas_previas or []),
        )

    return {
        "agregados": total_agregados,
        "eliminados": total_eliminados,
        "errores": errores,
    }


def registrar_sin_cambios(linea: Linea, pdf_hash: str):
    """Registra que el PDF fue verificado pero no hubo cambios."""
    ActualizacionLog.objects.create(
        linea=linea,
        pdf_hash=pdf_hash,
        pdf_modificado=False,
        exito=True,
        horarios_agregados=0,
        horarios_eliminados=0,
    )


def _cargar_servicio(linea: Linea, srv_data: dict, orden: int) -> tuple[int, int]:
    servicio, _ = Servicio.objects.update_or_create(
        linea=linea,
        nombre=srv_data["servicio_nombre"],
        defaults={
            "tipo": srv_data["servicio_tipo"],
            "descripcion": srv_data.get("servicio_descripcion", ""),
            "orden": orden,
            "activo": True,
        },
    )

    _cargar_recorrido(servicio, srv_data.get("vias", []))

    eliminados = Horario.objects.filter(servicio=servicio).count()
    Horario.objects.filter(servicio=servicio).delete()

    nuevos = [
        Horario(
            servicio=servicio,
            direccion=h["direccion"],
            tipo_dia=h["tipo_dia"],
            hora=_parse_hora(h["hora"]),
            condicion=h.get("condicion", ""),
            destino=_get_or_create_via(h["destino"]) if h.get("destino") else None,
        )
        for h in srv_data.get("horarios", [])
    ]
    Horario.objects.bulk_create(nuevos)

    return len(nuevos), eliminados


def _cargar_recorrido(servicio: Servicio, nombres_vias: list[str]):
    RecorridoTramo.objects.filter(servicio=servicio).delete()
    tramos = [
        RecorridoTramo(servicio=servicio, via=_get_or_create_via(nombre), orden=orden)
        for orden, nombre in enumerate(nombres_vias)
    ]
    RecorridoTramo.objects.bulk_create(tramos)


def _normalizar_nombre_via(nombre: str) -> str:
    """
    Los PDFs no siempre nombran el mismo lugar igual en todos lados (ej.
    "Boca Arroyo Durazno" en el texto de recorrido de un servicio vs
    "Boca de Arroyo Durazno" en la columna "Lugar salida/llegada" de otro).
    Se usa para detectar que es el mismo lugar y no crear una Via duplicada.
    """
    t = nombre.lower()
    t = re.sub(r"\b(de|del)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _get_or_create_via(nombre: str) -> Via:
    slug = slugify(nombre)
    via = Via.objects.filter(slug=slug).first()
    if via:
        return via

    normalizado = _normalizar_nombre_via(nombre)
    for existente in Via.objects.all():
        if _normalizar_nombre_via(existente.nombre) == normalizado:
            return existente

    return Via.objects.create(slug=slug, nombre=nombre)


def _parse_hora(hora_str: str) -> time:
    h, m = hora_str.split(":")
    return time(int(h), int(m))
