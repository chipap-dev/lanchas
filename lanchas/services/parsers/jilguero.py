"""
Parser para la línea 450 de Jilguero (Francisco Buiatti e Hijos S.A.).

Toda la lógica de extracción es compartida con Interisleña (mismo motor de
generación de PDF) — ver `comun.BaseGobiernoParser`. La única particularidad
de esta línea es que sí tiene una columna FERIADOS con horarios reales
(Interisleña no: ahí "feriado" se resuelve mapeando a sábado/domingo, ver
`services.feriados.resolver_tipo_dia`).
"""

from .comun import BaseGobiernoParser


class JilgueroParser(BaseGobiernoParser):
    linea_numero = "450"

    DIAS_COLUMNAS = [
        "lunes", "martes", "miercoles", "jueves", "viernes",
        "sabado", "domingo", "feriado",
    ]

    # El recorrido del servicio Tigre↔Río Espera mete a "Espera" en la lista
    # de "Arroyos" ("Desvío en los Arroyos Angostura, Esperita y Espera"),
    # pero es un río, no un arroyo (Angostura y Esperita sí son arroyos,
    # esos quedan igual) — confirmado a mano con el usuario 06/07/2026.
    CORRECCIONES_VIA = {
        "Arroyo Espera": "Río Espera",
    }
