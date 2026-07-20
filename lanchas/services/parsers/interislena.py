"""
Parser para Interisleña S.A.C.I. — combina los PDF de las líneas 451 y 452
en un solo conjunto de servicios (se tratan como una única Línea en la app,
no dos, por decisión del usuario: la empresa opera ambas rutas como un todo).

Toda la lógica de extracción es compartida con Jilguero (mismo motor de
generación de PDF) — ver `comun.BaseGobiernoParser`. Particularidades de
Interisleña frente a Jilguero:
- Sin columna FERIADOS real: la tabla tiene esa columna en el encabezado
  pero cada fila solo trae una nota fija "(*1) Ver aclaración debajo del
  cuadro" (no horarios), y el pie de página explica la regla real:
  "Si el feriado cae lunes, se repiten los horarios del domingo" /
  "Si cae viernes, se repiten los de sábado" — exactamente lo que ya hace
  `services.feriados.resolver_tipo_dia()` para esta empresa. Por eso acá
  solo se leen 7 columnas de día (no se crea tipo_dia='feriado').
- El PDF de Interisleña tiene un sello/logo decorativo hecho de cientos de
  curvas de color "sucio" cerca del pie — `_es_color_marcador` (en
  BaseGobiernoParser) ya filtra eso y solo usa curvas de color puro como
  marcador real de condición.
"""

from .comun import BaseGobiernoParser


class InterislenaParser(BaseGobiernoParser):
    linea_numero = "451/452"

    DIAS_COLUMNAS = [
        "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    ]

    # El recorrido del Ramal 4 dice "Arroyo Espera", pero es el mismo Río
    # Espera al que llega Jilguero (por otra rama del recorrido, vía Río
    # Sarmiento en vez de Río Carapachay) — confirmado con el usuario
    # 06/07/2026. Se apunta a la misma Via que ya usa JilgueroParser.
    CORRECCIONES_VIA = {
        "Arroyo Espera": "Río Espera",
    }

    # "Ramal 1": el destino queda partido en dos filas por el salto de
    # línea del PDF ("Arroyo Arroyón y" + "Fondeadero" suelto en la fila
    # siguiente, cada una con su propia hora) — son dos lugares reales
    # (el arroyo y un fondeadero/amarradero aparte), no un lugar solo con
    # nombre largo, así que se preservan los dos por separado en vez de
    # quedarse con uno. Confirmado con el usuario 06/07/2026.
    #
    # "Ramal 2": mismo patrón, en una sola fila completa (sin partir) —
    # "Recreo Yacaré y Cangrejo" son dos recreos distintos.
    #
    # "Troncal (Canal 5 / Carabelas / Arroyo Grande)": el recorrido ya
    # marca los tres como lugares propios ("... Canal 5 hasta Río
    # Carabelas ... Desvío Arroyo Grande hasta la Horqueta"); el destino
    # los repite todos juntos con "y"/"o" en vez de elegir uno.
    #
    # "Fraccionado (Paraná de las Palmas / Arroyo Antequera)": ida parte el
    # nombre en dos filas con horas distintas ("Parana de las Palmas x
    # Arroyo" + "Antequera o hasta Arroyo Estudiante"); la vuelta trae el
    # texto completo en una sola fila ("...x Arroyo Antequera o hasta Arroyo
    # Estudiante"). "Arroyo Estudiante" ya es una vía propia por el
    # recorrido de otros servicios de esta misma línea, así que no hace
    # falta repetirlo acá — los dos lugares de este servicio son Paraná de
    # las Palmas y Arroyo Antequera.
    #
    # "Ramal 4": mismo patrón — ida parte "Arroyo Cruz" + "Colorada - Casa
    # Bellini" en dos filas con horas distintas; la vuelta trae el texto
    # completo ("Arroyo Cruz Colorada - Casa Bellini"). Son dos lugares
    # reales (el arroyo y una casa/embarcadero particular).
    CORRECCIONES_VIA_MULTIPLE = {
        "Arroyo Arroyón y Fondeadero": ["Arroyo Arroyón", "Fondeadero"],
        "Recreo Yacaré y Cangrejo": ["Recreo Yacaré", "Recreo Cangrejo"],
        "Canal 5 y Carabelas o Ayo. Grande": ["Canal 5", "Río Carabelas", "Arroyo Grande"],
        "Parana de las Palmas x Arroyo": ["Paraná de las Palmas", "Arroyo Antequera"],
        "Antequera o hasta Arroyo Estudiante": ["Paraná de las Palmas", "Arroyo Antequera"],
        "Parana de las Palmas x Arroyo Antequera o hasta Arroyo Estudiante": [
            "Paraná de las Palmas", "Arroyo Antequera",
        ],
        "Arroyo Cruz": ["Arroyo Cruz Colorada", "Casa Bellini"],
        "Colorada - Casa Bellini": ["Arroyo Cruz Colorada", "Casa Bellini"],
        "Arroyo Cruz Colorada - Casa Bellini": ["Arroyo Cruz Colorada", "Casa Bellini"],
    }

    def __init__(self, pdf_path, pdf_path_2=None):
        super().__init__(pdf_path)
        self.pdf_path_2 = pdf_path_2

    def _pdf_paths(self) -> list:
        paths = [self.pdf_path]
        if self.pdf_path_2:
            paths.append(self.pdf_path_2)
        return paths
