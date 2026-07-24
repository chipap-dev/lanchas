from datetime import date, time
from typing import Optional

from django.db.models import Q, QuerySet

from lanchas.models import Empresa, Horario, Servicio
from .feriados import es_feriado, resolver_tipo_dia

# Un lugar puede ser un tramo de recorrido (río/arroyo/canal, común a todos
# los horarios del servicio) o un destino puntual sin tramo propio (un
# muelle final, solo relevante para las filas cuyo Horario.destino coincide
# - típicamente una rama de un servicio bifurcado). `_filtro_via` arma el Q
# que matchea ambos casos; `_acotar_a_destino` reduce un queryset de Horario
# a las filas relevantes cuando el lugar elegido no es un tramo del servicio.

def _filtro_via(via_slug: str) -> Q:
    return Q(tramos__via__slug=via_slug) | Q(horarios__destino__slug=via_slug)


def unificar_ramales(horarios: list[Horario]) -> list[dict]:
    """
    Si más de un ramal pasa por este lugar al mismo horario, se unifican en
    una sola fila con los nombres de servicio distintos separados por "/"
    (pedido explícito del usuario) - cubre dos casos reales:
    - El mismo servicio bifurcado en varios destinos a la misma hora (ej.
      "Troncal" hacia Canal 5 / Río Carabelas / Arroyo Grande, todo a las
      04:30): antes salían 3 filas idénticas porque el destino de cada
      rama no se muestra en esta tabla - ahora colapsan solas (mismo
      nombre de servicio → 1 sola etiqueta).
    - Ramales distintos de la misma línea que coinciden en el horario (ej.
      "Ramal 3" y "Ramal 4" ambos a las 05:30): antes 2 filas separadas,
      ahora "Ramal 3 / Ramal 4" en una sola.
    Se agrupa por (línea, dirección, hora) - no por empresa a secas, para
    no mezclar dos líneas distintas que casualmente compartan horario.
    Si la duración (`servicio.descripcion`) no es la misma para todos los
    ramales agrupados, se omite en vez de mostrar una que no aplica a
    todos; las condiciones (notas al pie) se concatenan.
    """
    grupos: dict[tuple, dict] = {}
    orden: list[tuple] = []
    for h in horarios:
        clave = (h.servicio.linea_id, h.direccion, h.hora)
        if clave not in grupos:
            grupos[clave] = {
                "hora": h.hora, "direccion": h.direccion, "linea": h.servicio.linea,
                "_nombres": {}, "_descripciones": set(), "_condiciones": {},
            }
            orden.append(clave)
        g = grupos[clave]
        g["_nombres"].setdefault(h.servicio.nombre, None)
        g["_descripciones"].add(h.servicio.descripcion)
        if h.condicion:
            g["_condiciones"].setdefault(h.condicion, None)

    filas = []
    for clave in orden:
        g = grupos[clave]
        filas.append({
            "hora": g["hora"],
            "direccion": g["direccion"],
            "linea": g["linea"],
            "nombre": " / ".join(g["_nombres"]),
            "descripcion": next(iter(g["_descripciones"])) if len(g["_descripciones"]) == 1 else None,
            "condicion": "; ".join(g["_condiciones"]),
        })
    return filas


def _acotar_a_destino(qs_horarios: QuerySet, servicio: Servicio, via_slug: str) -> QuerySet:
    es_tramo = servicio.tramos.filter(via__slug=via_slug).exists()
    if es_tramo:
        return qs_horarios
    return qs_horarios.filter(destino__slug=via_slug)


def horarios_por_via(via_slug: str, tipo_dia: str) -> list[Horario]:
    """
    Todos los horarios de servicios activos relevantes para un lugar (tramo de
    recorrido o destino puntual) en un tipo de día. Devuelve ida y vuelta
    mezclados, ordenados por hora.
    """
    servicios = Servicio.objects.filter(_filtro_via(via_slug), activo=True).distinct()
    horarios = []
    for servicio in servicios:
        qs = _acotar_a_destino(
            Horario.objects.filter(servicio=servicio, tipo_dia=tipo_dia), servicio, via_slug
        )
        horarios.extend(qs.select_related("servicio", "servicio__linea", "servicio__linea__empresa"))
    return sorted(horarios, key=lambda h: h.hora)


def horarios_por_via_fecha(via_slug: str, fecha: date) -> dict:
    """
    Devuelve {'ida': [Horario...], 'vuelta': [Horario...]} para un lugar
    (tramo de recorrido o destino puntual) y fecha, resolviendo el tipo_dia
    por línea (necesario porque Interisleña y las demás tienen lógica de
    feriados diferente).
    """
    servicios = (
        Servicio.objects.filter(_filtro_via(via_slug), activo=True)
        .select_related("linea__empresa")
        .distinct()
    )

    # Una sola consulta a feriados para todas las líneas
    feriado_hoy = es_feriado(fecha)

    ids_ida: list[int] = []
    ids_vuelta: list[int] = []

    for servicio in servicios:
        tipo_dia = resolver_tipo_dia(servicio.linea, fecha, feriado_hoy)
        qs = _acotar_a_destino(
            Horario.objects.filter(servicio=servicio, tipo_dia=tipo_dia), servicio, via_slug
        )
        ids_ida.extend(qs.filter(direccion="ida").values_list("id", flat=True))
        ids_vuelta.extend(qs.filter(direccion="vuelta").values_list("id", flat=True))

    base = Horario.objects.select_related(
        "servicio", "servicio__linea", "servicio__linea__empresa"
    ).order_by("hora")

    return {
        "ida": list(base.filter(id__in=ids_ida)),
        "vuelta": list(base.filter(id__in=ids_vuelta)),
    }


DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo", "feriado"]


def horario_semanal_por_via(via_slug: str, direccion: str | None = None) -> list[dict]:
    """
    Cronograma semanal completo (todos los tipo_dia, sin resolver feriados
    por fecha) para un lugar: una única lista de filas (no una tabla por
    servicio/ramal) para que un lugar por el que pasan varios ramales se vea
    como un solo cuadro.

    Se agrupa por (línea, dirección, hora) - igual que `unificar_ramales()`
    para la tabla "Hoy" - así que si más de un ramal pasa por acá a la
    misma hora (el mismo servicio bifurcado en destinos distintos, o
    ramales distintos de la misma línea que coinciden en el horario) se
    unifican en una sola fila con los nombres separados por "/", en vez de
    filas repetidas (pedido explícito del usuario, confirmado también acá
    después de arreglarlo en la tabla "Hoy"). El set de `dias` de cada
    ramal agrupado se UNE (si el lunes pasa uno de los ramales y el martes
    otro, a esta hora "sí hay lancha" los dos días - no hace falta que sea
    el mismo ramal exacto todos los días para que la fila diga que sí).

    `direccion`: 'ida' (sale de Tigre), 'vuelta' (llega a Tigre) o None
    (ambas, ida primero).

    Devuelve una lista de filas, ordenadas ida primero y por hora:
        {'linea': Linea, 'direccion': 'ida'|'vuelta', 'hora': time,
         'nombre': str, 'descripcion': str|None, 'condicion': str,
         'dias': {tipo_dia, ...}}
    """
    servicios = (
        Servicio.objects.filter(_filtro_via(via_slug), activo=True)
        .distinct()
        .select_related("linea__empresa")
        .order_by("linea__numero", "orden")
    )

    direcciones = (direccion,) if direccion else ("ida", "vuelta")

    grupos: dict[tuple, dict] = {}
    orden: list[tuple] = []
    for servicio in servicios:
        for direccion_fila in direcciones:
            qs = _acotar_a_destino(
                Horario.objects.filter(servicio=servicio, direccion=direccion_fila).select_related("destino"),
                servicio, via_slug,
            )
            for h in qs:
                clave = (servicio.linea_id, direccion_fila, h.hora)
                if clave not in grupos:
                    grupos[clave] = {
                        "linea": servicio.linea, "direccion": direccion_fila, "hora": h.hora,
                        "_nombres": {}, "_descripciones": set(), "_condiciones": {}, "dias": set(),
                    }
                    orden.append(clave)
                g = grupos[clave]
                g["_nombres"].setdefault(servicio.nombre, None)
                g["_descripciones"].add(servicio.descripcion)
                if h.condicion:
                    g["_condiciones"].setdefault(h.condicion, None)
                g["dias"].add(h.tipo_dia)

    filas = []
    for clave in orden:
        g = grupos[clave]
        filas.append({
            "linea": g["linea"], "direccion": g["direccion"], "hora": g["hora"],
            "nombre": " / ".join(g["_nombres"]),
            "descripcion": next(iter(g["_descripciones"])) if len(g["_descripciones"]) == 1 else None,
            "condicion": "; ".join(g["_condiciones"]),
            "dias": g["dias"],
        })

    return sorted(
        filas,
        key=lambda f: (0 if f["direccion"] == "ida" else 1, f["hora"], f["linea"].numero),
    )


def empresas_por_via(via_slug: str) -> QuerySet:
    """
    Empresas con al menos un servicio activo relevante para un lugar (tramo
    de recorrido o destino puntual). Para armar los filtros de "qué línea"
    contextuales a un lugar puntual, en vez de listar siempre todas.
    """
    return (
        Empresa.objects.filter(
            lineas__servicios__in=Servicio.objects.filter(_filtro_via(via_slug), activo=True)
        )
        .distinct()
        .order_by("nombre")
    )


def lineas_por_via(via_slug: str) -> QuerySet:
    """
    Búsqueda inversa: servicios activos relevantes para un lugar (tramo de
    recorrido o destino puntual), con su línea y empresa. Para la vista
    "elegí un lugar → qué lanchas pasan".
    """
    return (
        Servicio.objects.filter(_filtro_via(via_slug), activo=True)
        .select_related("linea", "linea__empresa")
        .prefetch_related("tramos__via")
        .distinct()
        .order_by("linea__numero", "orden")
    )


def proximos_servicios(
    via_slug: str,
    tipo_dia: str,
    hora_desde: time,
    direccion: str = "vuelta",
    limit: int = 5,
) -> list[Horario]:
    """
    Próximos servicios en una dirección desde un lugar, a partir de una hora.
    Tipo de uso: widget "próximas lanchas desde mi muelle".
    """
    servicios = Servicio.objects.filter(_filtro_via(via_slug), activo=True).distinct()
    horarios = []
    for servicio in servicios:
        qs = _acotar_a_destino(
            Horario.objects.filter(
                servicio=servicio, tipo_dia=tipo_dia, direccion=direccion, hora__gte=hora_desde,
            ),
            servicio, via_slug,
        )
        horarios.extend(qs.select_related("servicio", "servicio__linea", "servicio__linea__empresa"))
    return sorted(horarios, key=lambda h: h.hora)[:limit]


def proximo_servicio_a_tigre(
    via_slug: str,
    tipo_dia: str,
    hora_desde: time,
) -> Optional[Horario]:
    """Próxima vuelta hacia Tigre desde una vía. Wrapper de proximos_servicios."""
    resultado = proximos_servicios(via_slug, tipo_dia, hora_desde, "vuelta", 1)
    return resultado[0] if resultado else None
