from datetime import datetime

from django.db.models import Q
from django.utils.timezone import localtime, now

from lanchas.models import Via, Empresa, Linea
from .horarios import (
    DIAS_SEMANA,
    empresas_por_via,
    horarios_por_via_fecha,
    horario_semanal_por_via,
    unificar_ramales,
)


_DIAS_ES = {
    0: "lun", 1: "mar", 2: "mié", 3: "jue", 4: "vie", 5: "sáb", 6: "dom",
}
_MESES_ES = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}


def _vias_de_empresa(empresa: Empresa | None) -> list:
    # Cualquier lugar que aparezca en el recorrido: tramos reales (ríos,
    # arroyos, canales) y también destinos puntuales sin tramo propio
    # (ej. "Sala 1º Auxilios Km.12"), que solo se referencian vía
    # Horario.destino cuando un servicio se bifurca. Si se pasa una
    # empresa, se acota a los lugares que esa línea realmente toca.
    filtro = Q(tramos__isnull=False) | Q(horarios_destino__isnull=False)
    if empresa:
        filtro &= (
            Q(tramos__servicio__linea__empresa=empresa)
            | Q(horarios_destino__servicio__linea__empresa=empresa)
        )
    return list(Via.objects.filter(filtro).distinct().order_by("nombre"))


def get_lanchas_context(
    via_slug: str | None = None,
    vista: str = "hoy",
    empresa_slug: str | None = None,
) -> dict:
    empresas = list(Empresa.objects.order_by("nombre"))
    vista = vista if vista in ("hoy", "semana_ida", "semana_vuelta") else "hoy"
    empresa_activa = next((e for e in empresas if e.slug == empresa_slug), None)

    # Recorrido "abierto" en el dropdown de cada línea del sidebar (todas se
    # calculan siempre para poder mostrarlas plegadas, no solo la activa).
    vias_todas = _vias_de_empresa(None)
    empresas_con_vias = [(empresa, _vias_de_empresa(empresa)) for empresa in empresas]

    # Fuentes PDF originales, para que cualquiera pueda verificar los datos
    # contra el archivo del gobierno del que salieron (sección "DETALLE
    # TÉCNICO" del landing).
    todos_pdfs = []
    for linea in Linea.objects.filter(activa=True).order_by("numero"):
        todos_pdfs.append({"filename": linea.pdf_filename, "url": linea.pdf_url})
        if linea.pdf_url_2:
            todos_pdfs.append({"filename": linea.pdf_filename_2, "url": linea.pdf_url_2})

    # Vías vigentes para esta vista (todas, o acotadas si hay una línea
    # elegida) - de acá sale la vía activa y las chips del tablet.
    vias = vias_todas if not empresa_activa else next(
        (vs for e, vs in empresas_con_vias if e == empresa_activa), vias_todas
    )

    ahora = localtime(now())
    fecha_actual = ahora.date()
    dia = _DIAS_ES[fecha_actual.weekday()]
    mes = _MESES_ES[fecha_actual.month]
    fecha_label = f"{dia} {fecha_actual.day} {mes} · {fecha_actual.year}"

    contexto = {
        "estaciones": vias,
        "estacion_activa": None,
        "vista": vista,
        "empresas": empresas,
        "empresa_activa": empresa_activa,
        "vias_todas": vias_todas,
        "empresas_con_vias": empresas_con_vias,
        "todos_pdfs": todos_pdfs,
        "empresas_de_via": [],
        "todas_salidas": [],
        "filas_semana": [],
        "dias_semana": DIAS_SEMANA,
        "proxima": None,
        "siguiente": None,
        "eta_minutos": None,
        "proxima_ida": None,
        "proxima_vuelta": None,
        "hora_actual": ahora.strftime("%H:%M"),
        "fecha_label": fecha_label,
    }

    if not vias:
        contexto["hora_actual"] = ""
        contexto["fecha_label"] = ""
        return contexto

    estacion_activa = next((v for v in vias if v.slug == via_slug), vias[0])
    contexto["estacion_activa"] = estacion_activa
    # Filtros de línea contextuales al lugar elegido: si Delta Argentino no
    # pasa por acá, no tiene sentido ofrecerlo como filtro (pedido explícito
    # del usuario 06/07/2026).
    contexto["empresas_de_via"] = list(empresas_por_via(estacion_activa.slug))

    hora_actual = ahora.time()

    def _eta_minutos(horario):
        if not horario:
            return None
        dt_horario = datetime.combine(fecha_actual, horario.hora)
        dt_ahora = datetime.combine(fecha_actual, hora_actual)
        return max(0, int((dt_horario - dt_ahora).total_seconds() // 60))

    # Próxima salida (Ida) y próxima llegada (Vuelta) a Tigre: se calculan
    # siempre, sin importar la vista (Hoy / Semana), porque el usuario pidió
    # verlas al mismo tiempo en cualquier pestaña, no solo en "Hoy".
    horarios_hoy = horarios_por_via_fecha(estacion_activa.slug, fecha_actual)
    ida_futuras = sorted(
        (h for h in horarios_hoy["ida"] if h.hora >= hora_actual), key=lambda h: h.hora
    )
    vuelta_futuras = sorted(
        (h for h in horarios_hoy["vuelta"] if h.hora >= hora_actual), key=lambda h: h.hora
    )
    proxima_ida = ida_futuras[0] if ida_futuras else None
    proxima_vuelta = vuelta_futuras[0] if vuelta_futuras else None

    contexto.update({
        "proxima_ida": proxima_ida,
        "proxima_vuelta": proxima_vuelta,
    })

    if vista in ("semana_ida", "semana_vuelta"):
        direccion = "ida" if vista == "semana_ida" else "vuelta"
        contexto["filas_semana"] = horario_semanal_por_via(estacion_activa.slug, direccion)
        return contexto

    todas_salidas = sorted(horarios_hoy["ida"] + horarios_hoy["vuelta"], key=lambda h: h.hora)
    futuras = [h for h in todas_salidas if h.hora >= hora_actual]
    proxima = futuras[0] if futuras else None
    siguiente = futuras[1] if len(futuras) > 1 else None

    contexto.update({
        # Unificado (ver unificar_ramales) solo para esta tabla - proxima/
        # siguiente siguen usando el Horario "crudo" tal cual, para no
        # complicar los widgets de arriba con filas fusionadas.
        "todas_salidas": unificar_ramales(todas_salidas),
        "proxima": proxima,
        "siguiente": siguiente,
        "eta_minutos": _eta_minutos(proxima),
    })
    return contexto
