"""
Clase base para parsers de PDFs de horarios de lanchas.

Formato de salida normalizado (lista de dicts):
[
    {
        'servicio_nombre': str,
        'servicio_tipo': 'troncal' | 'ramal' | 'fraccionado' | 'desdoblamiento',
        'vias': [str, ...],        # nombres en orden del recorrido ida
        'servicio_descripcion': str,  # opcional, ej: 'Duración aprox.: 03:30 / 04:00 hs'
        'horarios': [
            {
                'direccion': 'ida' | 'vuelta',
                'tipo_dia': 'lunes' | 'martes' | ... | 'domingo' | 'feriado',
                'hora': 'HH:MM',
                'condicion': str,  # vacío si no aplica
                'destino': str | None,  # nombre de Via, solo si el servicio
                                         # se bifurca en más de un destino
                                         # dentro del mismo IDA/VUELTA
            },
            ...
        ],
    },
    ...
]

Los parsers pueden exponer, luego de parse(), dos atributos de instancia
opcionales que el comando/loader mergean en el ActualizacionLog:
- self.errores: list[str]  - bloques de servicio que fallaron pero no
  abortaron el resto del parseo.
- self.notas: list[str]    - anomalías no bloqueantes del PDF (datos
  faltantes, heurísticas aplicadas) para revisión manual.

Notas de implementación:
- Usar pdfplumber (pip install pdfplumber) para extracción de tablas.
  Es pure-Python vía pdfminer.six, sin servicios externos.
- Los PDFs tienen tablas con layout irregular: columnas por día de semana,
  celdas combinadas para bloques de servicio, y notas al pie con condiciones.
- Cada subclase debe manejar las particularidades del PDF de su empresa.
"""

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ParserError(Exception):
    pass


class BaseParser:
    linea_numero: str = ""

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path

    def hash_pdf(self) -> str:
        sha256 = hashlib.sha256()
        with open(self.pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def parse(self) -> list[dict]:
        try:
            return self.parse_pdf()
        except ParserError:
            raise
        except Exception as exc:
            raise ParserError(
                f"Error inesperado al parsear {self.pdf_path.name}: {exc}"
            ) from exc

    def parse_pdf(self) -> list[dict]:
        raise NotImplementedError
