"""Smoke test: descarga los PDF reales de las 3 empresas y verifica que el
parser todavía los puede leer.

Marcado @pytest.mark.smoke - no corre en el CI de cada push/PR (excluido
explícitamente en .github/workflows/ci.yml con `-m "not smoke"`), porque
depende de una fuente externa (minfra.gba.gob.ar) que puede estar caída
sin que eso signifique que el código esté roto. Corre solo en el cron
semanal (.github/workflows/smoke-test.yml): si alguna empresa cambió el
formato de su PDF, este test lo detecta ahí, no en medio de un deploy.
"""

from pathlib import Path

import pytest
import requests

from lanchas.services.parsers import (
    DeltaArgentinoParser,
    InterislenaParser,
    JilgueroParser,
    ParserError,
)

TIMEOUT_SEGUNDOS = 30

FUENTES = {
    "Jilguero (450)": (
        JilgueroParser,
        ["https://www.minfra.gba.gob.ar/web/Transporte/Fluvial/LINEA_450.pdf"],
    ),
    "Delta Argentino (453)": (
        DeltaArgentinoParser,
        ["https://www.minfra.gba.gob.ar/web/Transporte/Fluvial/LINEA_453.pdf"],
    ),
    "Interisleña (451/452)": (
        InterislenaParser,
        [
            "https://www.minfra.gba.gob.ar/web/Transporte/Fluvial/LINEA_451.pdf",
            "https://www.minfra.gba.gob.ar/web/Transporte/Fluvial/LINEA_452.pdf",
        ],
    ),
}


def _descargar(url: str, destino: Path) -> Path:
    resp = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
    resp.raise_for_status()
    destino.write_bytes(resp.content)
    return destino


@pytest.mark.smoke
@pytest.mark.parametrize("nombre", list(FUENTES.keys()))
def test_parser_sigue_funcionando_contra_el_pdf_real(nombre, tmp_path):
    parser_cls, urls = FUENTES[nombre]
    paths = [_descargar(url, tmp_path / f"linea_{i}.pdf") for i, url in enumerate(urls)]

    parser = parser_cls(*paths)

    try:
        servicios = parser.parse()
    except ParserError as exc:
        pytest.fail(
            f"{nombre}: el parser no pudo leer el PDF real - la empresa "
            f"puede haber cambiado el formato. Error original: {exc}"
        )

    assert servicios, f"{nombre}: el parser no extrajo ningún servicio del PDF real."
