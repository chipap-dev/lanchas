"""
Parser para la línea 453 de Delta Argentino S.R.L.

Mismo motor de PDF que Jilguero (450) e Interisleña (451/452) — toda la
lógica de extracción vive en `comun.BaseGobiernoParser` (verificado: mismos
colores de fila IDA/VUELTA `(0.004, 0.086, 0.125)`/`(0.074, 0.012, 0.141)`,
mismo layout de tabla). Como Jilguero, esta línea SÍ tiene columna FERIADOS
con horarios reales (a diferencia de Interisleña) — por eso hereda las
mismas 8 columnas de día.
"""

from .comun import BaseGobiernoParser


class DeltaArgentinoParser(BaseGobiernoParser):
    linea_numero = "453"

    DIAS_COLUMNAS = [
        "lunes", "martes", "miercoles", "jueves", "viernes",
        "sabado", "domingo", "feriado",
    ]

    # "Desdoblamiento Ramal 2": la parada real es "Paraná Miní" — "por Canal
    # 4" es solo la referencia de cómo se llega, no un lugar aparte (el
    # Canal 4 ya existe como vía propia por el recorrido de Ramal 2 /
    # Fraccionado Ramal 2, son dos lugares distintos, no hace falta repetirlo
    # acá). En la tabla del PDF el nombre de la fila IDA de lunes a viernes
    # queda cortado en dos filas ("Paraná Miní por Canal" + "4" suelto en la
    # fila siguiente) — termina en "Canal", no en una preposición, así que
    # la fusión automática de `_agrupar_horarios` no aplica acá y hace
    # falta corregir las dos formas a mano; la fila VUELTA sí trae el texto
    # completo en una sola celda ("Paraná Miní por Canal 4"). Confirmado
    # con el usuario 06/07/2026.
    CORRECCIONES_VIA = {
        "Paraná Miní por Canal": "Paraná Miní",
        "Paraná Miní por Canal 4": "Paraná Miní",
        "4": "Paraná Miní",
        # "Ramal 4": mismo patrón — "Arroyo Durazno" es la parada real,
        # "Caraguatá" ya es una vía propia del recorrido de este servicio
        # (no un lugar nuevo a preservar).
        "Arroyo Durazno por Caraguatá": "Arroyo Durazno",
        # "Ramal 2": el fin de semana llega a "Chañá por Canal Arias" (un
        # lugar real y completo, no se toca), pero de lunes a viernes el
        # nombre queda cortado en "... y Ayo." (abreviatura de "Arroyo") sin
        # completar en ninguna fila cercana — se recorta la referencia
        # incompleta y queda solo el nombre real de la parada. Confirmado
        # con el usuario 06/07/2026.
        "Paraná Miní y Ayo.": "Paraná Miní",
        # "Fraccionado Ramal 2": mismo patrón — de lunes a viernes queda
        # "Parana Guazú y Ayo." (incompleto), sábado y domingo llega a
        # "Naranjo" (al que le falta el prefijo "Arroyo").
        "Parana Guazú y Ayo.": "Paraná Guazú",
        "Naranjo": "Arroyo Naranjo",
        # "Ramal 3": mismo patrón de nuevo — de lunes a viernes/parte del
        # fin de semana llega a "Paraná de las Palmas" (ya bien), el resto
        # del día llega a "Arroyo Caraguatá" pero con el "Arroyo" recortado
        # al principio en vez de al final ("por Arroyo Caraguatá" / bien
        # "Caraguatá" suelto en la vuelta). La vuelta de las 13;30 (todos
        # los días) queda con un "por Arroyo" colgante sin completar en
        # ninguna fila cercana — se recorta, ya que "Arroyo Caraguatá" queda
        # cubierto por las otras filas del mismo servicio.
        "por Arroyo Caraguatá": "Arroyo Caraguatá",
        "Caraguatá": "Arroyo Caraguatá",
        "Paraná de las Palmas por Arroyo": "Paraná de las Palmas",
        # "Ramal 5": mismo patrón, "Canal Arias" ya es una vía propia del
        # recorrido de este mismo servicio.
        "por Canal Arias": "Canal Arias",
    }

    # "Fraccionado Ramal 2": la vuelta usa una sola fila para los 7 días y
    # menciona los dos lugares que la ida separa por día ("Parana Guazú y
    # Ayo. Naranjo" = Paraná Guazú entre semana, Arroyo Naranjo el fin de
    # semana) — se duplica el horario para que se pueda encontrar por
    # cualquiera de los dos. Confirmado con el usuario 06/07/2026.
    #
    # "Desdoblamiento Ramal 5": mismo criterio — "Paraná de las Palmas por
    # Rio Capitán" nombra dos lugares reales a la vez (los dos ya existen
    # como vía propia en el recorrido de este servicio), aplicado por igual
    # los 8 días en ida y vuelta, así que se duplica en vez de elegir uno.
    CORRECCIONES_VIA_MULTIPLE = {
        "Parana Guazú y Ayo. Naranjo": ["Paraná Guazú", "Arroyo Naranjo"],
        "Paraná de las Palmas por Rio Capitán": ["Paraná de las Palmas", "Río Capitán"],
        # "Desdoblamiento Ramal 5": el recorrido trae una aclaración de
        # restricción de tráfico ("...entre Puerto Tigre y Río Capitán y
        # Paraná de las Palmas") que el parser toma como si fuera un tramo
        # más del recorrido — no es un lugar nuevo, son los dos mismos
        # lugares que ya están antes en el recorrido de este servicio.
        "Río Capitán y Paraná de las Palmas": ["Río Capitán", "Paraná de las Palmas"],
    }
