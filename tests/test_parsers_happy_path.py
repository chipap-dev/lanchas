"""Parseo correcto de un PDF bien formado de cada una de las 3 empresas."""

from lanchas.services.parsers import DeltaArgentinoParser, InterislenaParser, JilgueroParser

from .parser_test_utils import FIXTURES_DIR


def test_jilguero_parsea_servicio_completo():
    parser = JilgueroParser(FIXTURES_DIR / "jilguero_450_ok.pdf")

    servicios = parser.parse()

    assert len(servicios) == 1
    servicio = servicios[0]
    assert servicio["servicio_nombre"] == "Troncal"
    assert servicio["servicio_tipo"] == "troncal"
    assert servicio["servicio_descripcion"] == "Duración aprox.: 02:30 hs"
    assert servicio["vias"] == ["Rio Lujan", "Arroyo Angostura", "Rio Espera"]
    # 8 columnas de día (incluye feriado) x 2 filas (ida/vuelta)
    assert len(servicio["horarios"]) == 16
    assert {h["tipo_dia"] for h in servicio["horarios"]} == {
        "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo", "feriado",
    }
    assert not parser.errores
    assert not parser.notas


def test_jilguero_detecta_direccion_por_color_de_fila():
    parser = JilgueroParser(FIXTURES_DIR / "jilguero_450_ok.pdf")
    servicios = parser.parse()
    horarios = servicios[0]["horarios"]

    idas = [h for h in horarios if h["direccion"] == "ida"]
    vueltas = [h for h in horarios if h["direccion"] == "vuelta"]
    assert len(idas) == 8
    assert len(vueltas) == 8
    assert all(h["hora"] == "08:00" for h in idas)
    assert all(h["hora"] == "17:30" for h in vueltas)
    assert all(h["destino"] == "Rio Espera" for h in idas)


def test_jilguero_asocia_condicion_por_marcador_de_color():
    parser = JilgueroParser(FIXTURES_DIR / "jilguero_450_ok.pdf")
    servicios = parser.parse()
    horarios = servicios[0]["horarios"]

    con_condicion = [h for h in horarios if h["condicion"]]
    assert len(con_condicion) == 8  # toda la fila IDA comparte la nota
    assert all(h["condicion"] == "Sujeto a mareas." for h in con_condicion)
    assert all(h["direccion"] == "ida" for h in con_condicion)


def test_interislena_parsea_servicio_sin_columna_feriado():
    parser = InterislenaParser(FIXTURES_DIR / "interislena_451_ok.pdf")

    servicios = parser.parse()

    assert len(servicios) == 1
    servicio = servicios[0]
    assert servicio["servicio_nombre"] == "Ramal 1"
    assert servicio["servicio_tipo"] == "ramal"
    assert servicio["vias"] == ["Rio Sarmiento", "Rio Carabelas"]
    assert "feriado" not in {h["tipo_dia"] for h in servicio["horarios"]}
    assert len(servicio["horarios"]) == 14  # 7 dias x 2 filas
    assert not parser.errores


def test_interislena_combina_dos_pdfs_si_se_pasa_el_segundo():
    parser = InterislenaParser(
        FIXTURES_DIR / "interislena_451_ok.pdf",
        FIXTURES_DIR / "interislena_451_ok.pdf",
    )

    servicios = parser.parse()

    # mismo bloque leído de los 2 archivos -> mismo nombre duplicado ->
    # se desambigua agregando el destino, tal como con dos bloques reales.
    assert len(servicios) == 2
    assert all("Ramal 1 (" in s["servicio_nombre"] for s in servicios)


def test_delta_parsea_servicio_completo():
    parser = DeltaArgentinoParser(FIXTURES_DIR / "delta_453_ok.pdf")

    servicios = parser.parse()

    assert len(servicios) == 1
    servicio = servicios[0]
    assert servicio["servicio_nombre"] == "Ramal 2"
    assert servicio["vias"] == ["Canal 4", "Parana Mini"]
    assert len(servicio["horarios"]) == 16
    assert not parser.errores
