"""PDFs con formato roto o inesperado: el parser debe fallar con una
excepción explícita (ParserError) en vez de devolver datos parciales o
silenciosos, y debe poder recuperarse de fallas puntuales dentro de un
mismo archivo sin abortar todo el parseo."""

import pytest

from lanchas.services.parsers.base import ParserError

from .parser_test_utils import FIXTURES_DIR, GenericParser


def test_pdf_corrupto_levanta_parser_error():
    parser = GenericParser(FIXTURES_DIR / "corrupto_no_es_pdf.pdf")

    with pytest.raises(ParserError):
        parser.parse()


def test_pdf_sin_tablas_levanta_parser_error_explicito():
    parser = GenericParser(FIXTURES_DIR / "sin_tablas.pdf")

    with pytest.raises(ParserError, match="No se pudo extraer ningún servicio"):
        parser.parse()


def test_bloque_sin_recorrido_ni_duracion_levanta_parser_error():
    """Si el único bloque del PDF no tiene las filas RECORRIDO/DURACION,
    no hay ningún servicio recuperable -> debe abortar con ParserError,
    no devolver una lista vacía silenciosa."""
    parser = GenericParser(FIXTURES_DIR / "bloque_incompleto.pdf")

    with pytest.raises(ParserError):
        parser.parse()


def test_bloque_roto_no_aborta_los_bloques_buenos_del_mismo_pdf():
    """Un PDF con dos bloques, uno bien formado y otro roto: el bloque
    bueno se recupera igual, y el roto queda registrado explícitamente en
    self.errores en vez de desaparecer sin dejar rastro."""
    parser = GenericParser(FIXTURES_DIR / "bloque_parcial.pdf")

    servicios = parser.parse()

    assert len(servicios) == 1
    assert servicios[0]["servicio_nombre"] == "Ramal 1"
    assert len(parser.errores) == 1
    assert "RECORRIDO/DURACION" in parser.errores[0]
