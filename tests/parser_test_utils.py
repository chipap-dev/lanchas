from pathlib import Path

from lanchas.services.parsers.comun import BaseGobiernoParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class GenericParser(BaseGobiernoParser):
    """Subclase mínima de BaseGobiernoParser para testear la lógica
    compartida (comun.py) sin atarse a las particularidades de ninguna
    empresa real."""

    linea_numero = "TEST"
    DIAS_COLUMNAS = [
        "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    ]
