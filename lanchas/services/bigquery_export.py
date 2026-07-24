"""
Aplanado de Horario (vía Postgres/ORM) para la carga full-refresh a
BigQuery (`lanchas_raw.horarios`). No es usado por la app Django para
servir al visitante - solo por el management command
`lanchas_cargar_bigquery`.

La fuente es Postgres, no los PDFs: el pipeline (`pipeline/downloader.py`
+ `pipeline/loader.py` + `services/parsers/`) ya normalizó y validó los
datos ahí, así que esta capa lee lo que ya está cargado en vez de
re-parsear.

Grano de una fila: (horario, vía). Un Horario no pertenece a una sola
vía - pertenece a un Servicio que recorre N vías (`Servicio.tramos`, ver
`lanchas/models/servicio.py`), y además puede fijar un destino puntual
propio (`Horario.destino`, para ramas bifurcadas como "Fraccionado 1 ->
Sala 1º Auxilios / Escuela 13"). Un Horario cuyo servicio recorre 3 vías
genera 3 filas - igual que `services/horarios._filtro_via` ya trata
"pasa por acá" como "es un tramo del servicio O es el destino puntual
de esta fila".

`tipo_dia` se copia tal cual de `Horario.tipo_dia` ('lunes'…'domingo' o
'feriado' - ver `lanchas/models/horario.py` TIPO_DIA_CHOICES). No existe
en el modelo real un campo agregado "hábil/sábado/domingo/feriado":
Interisleña resuelve sus feriados en tiempo de consulta reasignándolos a
'sabado'/'domingo' (`services/feriados.resolver_tipo_dia`), sin guardar
una fila propia - por eso esta capa refleja el dato crudo tal como está
en la base, no una interpretación calculada.
"""

from datetime import datetime, timezone

from lanchas.models import Horario

TABLE_SCHEMA_FIELDS = [
    ("empresa_nombre", "STRING"),
    ("empresa_slug", "STRING"),
    ("linea_numero", "STRING"),
    ("servicio_nombre", "STRING"),
    ("servicio_tipo", "STRING"),
    ("via_nombre", "STRING"),
    ("tipo_dia", "STRING"),
    ("hora", "TIME"),
    ("direccion", "STRING"),
    ("fecha_carga", "TIMESTAMP"),
]


def _vias_del_horario(horario):
    """Vías relevantes para esta fila: los tramos del servicio, más el
    destino puntual de la fila si no es ya uno de esos tramos."""
    vias = {tramo.via_id: tramo.via for tramo in horario.servicio.tramos.all()}
    if horario.destino_id and horario.destino_id not in vias:
        vias[horario.destino_id] = horario.destino
    return vias.values()


def flatten_horarios(loaded_at_iso: str | None = None) -> list[dict]:
    """
    Lee todos los Horario (vía ORM, con select_related/prefetch_related
    para evitar N+1) y los aplana a filas listas para BigQuery. Devuelve
    una lista de dicts con las columnas de `TABLE_SCHEMA_FIELDS`.
    """
    if loaded_at_iso is None:
        loaded_at_iso = datetime.now(timezone.utc).isoformat()

    horarios = (
        Horario.objects.select_related(
            "servicio", "servicio__linea", "servicio__linea__empresa", "destino"
        )
        .prefetch_related("servicio__tramos__via")
        .order_by("servicio__linea__numero", "tipo_dia", "direccion", "hora")
    )

    rows = []
    for horario in horarios:
        servicio = horario.servicio
        linea = servicio.linea
        empresa = linea.empresa

        for via in _vias_del_horario(horario):
            rows.append(
                {
                    "empresa_nombre": empresa.nombre,
                    "empresa_slug": empresa.slug,
                    "linea_numero": linea.numero,
                    "servicio_nombre": servicio.nombre,
                    "servicio_tipo": servicio.tipo,
                    "via_nombre": via.nombre,
                    "tipo_dia": horario.tipo_dia,
                    "hora": horario.hora.isoformat(),
                    "direccion": horario.direccion,
                    "fecha_carga": loaded_at_iso,
                }
            )
    return rows
