"""Casos borde: datos faltantes, horarios superpuestos y horas/fechas mal
formateadas dentro de un PDF por lo demás bien estructurado."""

from .parser_test_utils import FIXTURES_DIR, GenericParser


def test_datos_faltantes_no_rompe_el_parseo():
    """La fila VUELTA solo trae horario sábado/domingo (el resto de la
    semana quedó en blanco en el PDF) - debe faltar solo esos días, sin
    lanzar ni completar con datos inventados."""
    parser = GenericParser(FIXTURES_DIR / "datos_faltantes.pdf")

    servicios = parser.parse()

    assert len(servicios) == 1
    vuelta_dias = {
        h["tipo_dia"] for h in servicios[0]["horarios"] if h["direccion"] == "vuelta"
    }
    assert vuelta_dias == {"sabado", "domingo"}
    ida_dias = {h["tipo_dia"] for h in servicios[0]["horarios"] if h["direccion"] == "ida"}
    assert len(ida_dias) == 7
    assert not parser.errores


def test_horarios_superpuestos_no_se_pisan():
    """Dos filas IDA distintas ofrecen el mismo día+hora (lunes 08:00) a
    destinos distintos (servicio bifurcado) - ambas entradas deben
    conservarse, no perderse ni fusionarse."""
    parser = GenericParser(FIXTURES_DIR / "horarios_superpuestos.pdf")

    servicios = parser.parse()

    lunes_ida = [
        h for h in servicios[0]["horarios"]
        if h["direccion"] == "ida" and h["tipo_dia"] == "lunes"
    ]
    assert len(lunes_ida) == 2
    assert {h["destino"] for h in lunes_ida} == {"Destino A", "Destino B"}
    assert all(h["hora"] == "08:00" for h in lunes_ida)


def test_hora_con_punto_y_coma_se_corrige_a_dos_puntos():
    """Typo real visto en los PDFs de origen: '13;30' en vez de '13:30'."""
    parser = GenericParser(FIXTURES_DIR / "hora_mal_formateada.pdf")

    servicios = parser.parse()

    horas = {
        h["tipo_dia"]: h["hora"]
        for h in servicios[0]["horarios"] if h["direccion"] == "ida"
    }
    assert horas["lunes"] == "13:30"
    assert horas["miercoles"] == "08:00"


def test_texto_no_horario_se_preserva_literal_sin_validar_formato():
    """El parser no valida que una celda de día sea un horario válido -
    documenta el comportamiento actual: el texto se guarda tal cual para
    que quede visible en self.notas/revisión manual, no se descarta."""
    parser = GenericParser(FIXTURES_DIR / "hora_mal_formateada.pdf")

    servicios = parser.parse()

    horas = {
        h["tipo_dia"]: h["hora"]
        for h in servicios[0]["horarios"] if h["direccion"] == "ida"
    }
    assert horas["martes"] == "S/H"


def test_nombres_de_servicio_duplicados_se_desambiguan_con_el_destino():
    """Dos bloques 'TRONCAL' sin número que los distinga, cada uno con un
    destino distinto: si no se desambiguaran, uno pisaría al otro al
    cargar (se identifican por (linea, nombre))."""
    parser = GenericParser(FIXTURES_DIR / "nombres_duplicados.pdf")

    servicios = parser.parse()

    nombres = {s["servicio_nombre"] for s in servicios}
    assert len(servicios) == 2
    assert nombres == {"Troncal (Destino Uno)", "Troncal (Destino Dos)"}
    assert any("duplicado" in n for n in parser.notas)
