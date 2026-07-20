"""Tests unitarios de la lógica pura más frágil de comun.py: regex de
clasificación y parseo de vías/recorrido, sin pasar por un PDF real."""

from .parser_test_utils import GenericParser


def _parser():
    return GenericParser(pdf_path=None)


def test_clasificar_tipo_reconoce_las_variantes_conocidas():
    p = _parser()
    assert p._clasificar_tipo("TRONCAL") == "troncal"
    assert p._clasificar_tipo("RAMAL 3") == "ramal"
    assert p._clasificar_tipo("FRACCIONADO 2") == "fraccionado"
    assert p._clasificar_tipo("FRACCIONADO DE RAMAL 2") == "desdoblamiento"


def test_clasificar_tipo_desconocido_cae_a_ramal_y_deja_nota():
    p = _parser()
    p.notas = []

    tipo = p._clasificar_tipo("ALGO RARO")

    assert tipo == "ramal"
    assert any("no reconocido" in n for n in p.notas)


def test_formatear_nombre_capitaliza_y_respeta_minusculas_de_conectores():
    p = _parser()
    assert p._formatear_nombre("RAMAL DE LA COSTA") == "Ramal de la Costa"
    assert p._formatear_nombre("TRONCAL") == "Troncal"


def test_bloques_de_tabla_divide_por_reaparicion_de_encabezado():
    filas = [
        ["CANT.SERV", "x", "", "", ""],
        ["", "", "", "", ""],
        ["1", "TRONCAL", "IDA", "A", "B"],
        ["CANT.SERV", "y", "", "", ""],
        ["", "", "", "", ""],
        ["2", "RAMAL", "IDA", "C", "D"],
    ]

    bloques = GenericParser._bloques_de_tabla(filas)

    assert bloques == [(0, 3), (3, 6)]


def test_bloques_de_tabla_sin_reaparicion_es_un_solo_bloque():
    filas = [["", "x", "", "", ""], ["1", "TRONCAL", "IDA", "A", "B"]]

    bloques = GenericParser._bloques_de_tabla(filas)

    assert bloques == [(0, 2)]


def test_limpiar_colapsa_espacios_y_saltos_de_linea():
    p = _parser()
    assert p._limpiar("  Río   Luján\ny  algo  ") == "Río Luján y algo"
    assert p._limpiar(None) == ""
    assert p._limpiar("") == ""


def test_parse_vias_separa_tramos_por_guion_y_agrega_destino_final():
    p = _parser()

    vias = p._parse_vias(
        "Río Luján - Arroyo Angostura - Río Espera.",
        lugares_llegada={"Río Espera"},
    )

    assert vias == ["Río Luján", "Arroyo Angostura", "Río Espera"]


def test_parse_vias_separa_por_hasta_y_por_coma_pegada_a_prefijo():
    p = _parser()

    vias = p._parse_vias(
        "Arroyo Durazno hasta Canal de la Serna",
        lugares_llegada=set(),
    )

    assert vias == ["Arroyo Durazno", "Canal de la Serna"]


def test_parse_vias_agrega_destino_no_fluvial_cuando_no_hay_bifurcacion():
    """Servicio no bifurcado (un solo destino final): si el destino real
    no tiene forma de 'Río/Arroyo/Canal...' (ej. un muelle), igual se
    agrega como último tramo del recorrido."""
    p = _parser()

    vias = p._parse_vias("Río Luján.", lugares_llegada={"Muelle Municipal"})

    assert vias == ["Río Luján", "Muelle Municipal"]
