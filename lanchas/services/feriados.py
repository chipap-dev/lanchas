from datetime import date

import holidays

from lanchas.models import Feriado, Linea

_DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

SLUG_INTERISLENA = "interislena"


def es_feriado(fecha: date) -> bool:
    return Feriado.objects.filter(fecha=fecha).exists()


def resolver_tipo_dia(linea: Linea, fecha: date, _es_feriado: bool | None = None) -> str:
    """
    Devuelve el tipo_dia ('lunes'…'domingo' o 'feriado') a consultar para
    una línea y fecha, aplicando la lógica de feriados por empresa.

    Interisleña (451, 452) — sin columna de feriados en los PDFs:
        · feriado que cae viernes → usa horario 'sabado'
        · cualquier otro feriado  → usa horario 'domingo'

    Jilguero (450) y Delta Argentino (453) — tienen columna propia:
        · cualquier feriado → 'feriado'

    Pasar _es_feriado=True/False para evitar la consulta a DB cuando ya
    se conoce el resultado (útil al resolver múltiples líneas para una fecha).
    """
    dia_semana = _DIAS_SEMANA[fecha.weekday()]

    feriado = _es_feriado if _es_feriado is not None else es_feriado(fecha)
    if not feriado:
        return dia_semana

    if linea.empresa.slug == SLUG_INTERISLENA:
        return "sabado" if fecha.weekday() == 4 else "domingo"

    return "feriado"


def sincronizar_feriados(anios: list[int] | None = None) -> int:
    """
    Carga en `Feriado` el calendario oficial de Argentina (paquete
    `holidays`: feriados fijos, móviles — Carnaval, Semana Santa — y "con
    fines turísticos" ya decretados) para los años pedidos. Por defecto,
    año actual y siguiente, para tener margen sin depender de que alguien
    lo corra a fin de año. Devuelve la cantidad de feriados nuevos.

    No hay forma automática de saber si el gobierno corrigió el nombre de
    un feriado ya cargado, así que solo agrega fechas nuevas — no pisa
    registros existentes.
    """
    if anios is None:
        anio_actual = date.today().year
        anios = [anio_actual, anio_actual + 1]

    calendario = holidays.Argentina(years=anios)
    existentes = set(Feriado.objects.filter(
        fecha__in=calendario.keys()
    ).values_list("fecha", flat=True))

    nuevos = [
        Feriado(fecha=fecha, nombre=nombre)
        for fecha, nombre in calendario.items()
        if fecha not in existentes
    ]
    Feriado.objects.bulk_create(nuevos)
    return len(nuevos)
