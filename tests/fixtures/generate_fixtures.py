"""
Genera los PDFs sintéticos de tests/fixtures/*.pdf usando reportlab.

No son PDFs reales de las empresas (no se distribuyen ni se versionan
copias de los originales): reproducen a mano el layout mínimo que
`lanchas.services.parsers.comun.BaseGobiernoParser` espera (grilla con
bordes reales detectable por `page.find_tables()`, filas IDA/VUELTA
coloreadas con los mismos rellenos que usan los PDF reales, y un marcador
triangular + nota al pie para las condiciones), en base a la documentación
del propio parser (ver comun.py).

Se corre una sola vez para generar los binarios versionados en este
directorio - no hace falta re-ejecutarlo salvo que se agregue un fixture
nuevo:

    python tests/fixtures/generate_fixtures.py
"""

from pathlib import Path

from reportlab.pdfgen import canvas

FIXTURES_DIR = Path(__file__).parent

COLOR_IDA = (0.004, 0.086, 0.125)
COLOR_VUELTA = (0.074, 0.012, 0.141)
COLOR_MARCADOR = (0.9, 0.4, 0.1)

LABEL_COLS = ["CANT.SERV", "TIPO DE SERVICIO", "IDA/VUELTA", "LUGAR SALIDA", "LUGAR LLEGADA"]
COL_WIDTHS_FIJAS = [50, 110, 60, 90, 90]
DIA_COL_WIDTH = 55
ROW_H = 20
MARGIN = 40


class BlockLayout:
    """Calcula geometría y dibuja un bloque (tabla) de servicio."""

    def __init__(self, dias_columnas: list[str]):
        self.dias_columnas = dias_columnas
        self.col_widths = COL_WIDTHS_FIJAS + [DIA_COL_WIDTH] * len(dias_columnas)
        self.table_w = sum(self.col_widths)

    def col_x(self, x0, i):
        return x0 + sum(self.col_widths[:i])

    def n_cols(self):
        return len(self.col_widths)


def _row_top_y(top_y, r):
    return top_y - ROW_H * r


def render_block(c, x0, top_y, dias_columnas, cant, tipo, filas_horario,
                  recorrido, duracion, marker_row=None, marker_day_idx=None,
                  omit_recorrido=False, omit_duracion=False):
    """
    Dibuja un bloque de servicio completo (grilla, colores, texto) empezando
    en (x0, top_y). filas_horario: lista de dicts
    {"direccion": "ida"|"vuelta", "salida": str, "llegada": str,
     "horas": {dia_label: valor}}.
    Devuelve el y (reportlab, origen abajo-izquierda) inmediatamente debajo
    del bloque, y el bbox de la tabla en coords reportlab (x0, top, x1, bottom).
    """
    layout = BlockLayout(dias_columnas)
    n_rows = 2 + len(filas_horario) + (0 if omit_recorrido else 1) + (0 if omit_duracion else 1)

    def col_x(i):
        return layout.col_x(x0, i)

    def row_top_y(r):
        return _row_top_y(top_y, r)

    # -- fondos de color IDA/VUELTA
    for i, fila in enumerate(filas_horario):
        r = 2 + i
        color = COLOR_IDA if fila["direccion"] == "ida" else COLOR_VUELTA
        c.setFillColorRGB(*color)
        c.rect(col_x(3), row_top_y(r), layout.table_w - sum(layout.col_widths[:3]), -ROW_H, fill=1, stroke=0)

    # -- marcador de condición (triángulo) junto a una celda de día
    marker_curve_pos = None
    if marker_row is not None and marker_day_idx is not None:
        r = 2 + marker_row
        my = row_top_y(r) - ROW_H / 2 - 3
        mx = col_x(5 + marker_day_idx) - 10
        draw_triangle(c, mx, my, 6, COLOR_MARCADOR)
        marker_curve_pos = (mx, my)

    # -- grilla
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    for r in range(n_rows + 1):
        y = row_top_y(r)
        c.line(x0, y, x0 + layout.table_w, y)
    for i in range(layout.n_cols() + 1):
        x = col_x(i)
        c.line(x, top_y, x, top_y - ROW_H * n_rows)

    # -- texto
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 7)

    header1 = LABEL_COLS + [d.upper() for d in dias_columnas]
    header2 = [""] * layout.n_cols()
    _draw_row(c, col_x, row_top_y, 0, header1)
    _draw_row(c, col_x, row_top_y, 1, header2)

    for i, fila in enumerate(filas_horario):
        r = 2 + i
        row_vals = ["", "", fila["direccion"].upper(), fila["salida"], fila["llegada"]]
        for dia in dias_columnas:
            row_vals.append(fila["horas"].get(dia, ""))
        _draw_row(c, col_x, row_top_y, r, row_vals)

    # cantidad/tipo van en la primera fila de horario
    if filas_horario:
        c.drawString(col_x(0) + 2, row_top_y(2) - ROW_H + 6, cant)
        c.drawString(col_x(1) + 2, row_top_y(2) - ROW_H + 6, tipo)

    r = 2 + len(filas_horario)
    if not omit_recorrido:
        c.drawString(col_x(2) + 2, row_top_y(r) - ROW_H + 6, "RECORRIDO")
        c.drawString(col_x(4) + 2, row_top_y(r) - ROW_H + 6, recorrido)
        r += 1
    if not omit_duracion:
        c.drawString(col_x(2) + 2, row_top_y(r) - ROW_H + 6, "DURACION")
        c.drawString(col_x(4) + 2, row_top_y(r) - ROW_H + 6, duracion)
        r += 1

    bottom_y = row_top_y(n_rows)
    return bottom_y - 10, (x0, top_y, x0 + layout.table_w, bottom_y), marker_curve_pos


def _draw_row(c, col_x, row_top_y, r, values):
    y = row_top_y(r) - ROW_H + 6
    for ci, val in enumerate(values):
        if val:
            c.drawString(col_x(ci) + 2, y, str(val))


def draw_triangle(c, x, y, size, color):
    c.setFillColorRGB(*color)
    p = c.beginPath()
    p.moveTo(x, y)
    p.lineTo(x + size, y)
    p.lineTo(x + size / 2, y + size)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def render_footnote(c, x, y, text, color):
    draw_triangle(c, x, y, 6, color)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 7)
    c.drawString(x + 12, y, text)


def new_canvas(path, width, height):
    return canvas.Canvas(str(path), pagesize=(width, height))


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

def gen_jilguero_450_ok():
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo", "feriado"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 320
    c = new_canvas(FIXTURES_DIR / "jilguero_450_ok.pdf", width, height)
    top_y = height - MARGIN
    filas = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Rio Espera",
         "horas": {d: "08:00" for d in dias}},
        {"direccion": "vuelta", "salida": "Rio Espera", "llegada": "Tigre",
         "horas": {d: "17:30" for d in dias}},
    ]
    bottom_y, table_bbox, marker_pos = render_block(
        c, MARGIN, top_y, dias, "1", "TRONCAL", filas,
        recorrido="Rio Lujan - Arroyo Angostura - Rio Espera.",
        duracion="02:30 hs",
        marker_row=0, marker_day_idx=0,
    )
    render_footnote(c, MARGIN + 2, bottom_y - 20, "Sujeto a mareas.", COLOR_MARCADOR)
    c.showPage()
    c.save()


def gen_interislena_451_ok():
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 300
    c = new_canvas(FIXTURES_DIR / "interislena_451_ok.pdf", width, height)
    top_y = height - MARGIN
    filas = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Rio Carabelas",
         "horas": {d: "09:15" for d in dias}},
        {"direccion": "vuelta", "salida": "Rio Carabelas", "llegada": "Tigre",
         "horas": {d: "16:45" for d in dias}},
    ]
    render_block(
        c, MARGIN, top_y, dias, "1", "RAMAL 1", filas,
        recorrido="Rio Sarmiento - Rio Carabelas.",
        duracion="01:45 hs",
    )
    c.showPage()
    c.save()


def gen_delta_453_ok():
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo", "feriado"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 300
    c = new_canvas(FIXTURES_DIR / "delta_453_ok.pdf", width, height)
    top_y = height - MARGIN
    filas = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Parana Mini",
         "horas": {d: "07:40" for d in dias}},
        {"direccion": "vuelta", "salida": "Parana Mini", "llegada": "Tigre",
         "horas": {d: "18:10" for d in dias}},
    ]
    render_block(
        c, MARGIN, top_y, dias, "1", "RAMAL 2", filas,
        recorrido="Canal 4 - Parana Mini.",
        duracion="03:00 hs",
    )
    c.showPage()
    c.save()


def gen_corrupto_no_es_pdf():
    path = FIXTURES_DIR / "corrupto_no_es_pdf.pdf"
    path.write_bytes(b"esto no es un PDF valido, solo bytes de prueba \x00\x01\x02")


def gen_sin_tablas():
    path = FIXTURES_DIR / "sin_tablas.pdf"
    c = new_canvas(path, 400, 200)
    c.setFont("Helvetica", 10)
    c.drawString(50, 100, "Documento sin ninguna tabla de horarios.")
    c.showPage()
    c.save()


def gen_bloque_incompleto():
    """Tabla con grilla y filas IDA/VUELTA, pero sin fila RECORRIDO ni
    DURACION: el bloque debe fallar con ParserError explícito (no dato
    parcial silencioso)."""
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 220
    c = new_canvas(FIXTURES_DIR / "bloque_incompleto.pdf", width, height)
    top_y = height - MARGIN
    filas = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino Roto",
         "horas": {d: "08:00" for d in dias}},
        {"direccion": "vuelta", "salida": "Destino Roto", "llegada": "Tigre",
         "horas": {d: "17:00" for d in dias}},
    ]
    render_block(
        c, MARGIN, top_y, dias, "1", "RAMAL 1", filas,
        recorrido="", duracion="",
        omit_recorrido=True, omit_duracion=True,
    )
    c.showPage()
    c.save()


def gen_bloque_parcial():
    """Dos bloques en el mismo PDF: uno bien formado y otro roto (sin
    RECORRIDO/DURACION) - el parser debe recuperar el bloque bueno y
    reportar el roto en self.errores, sin abortar todo el archivo."""
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 420
    c = new_canvas(FIXTURES_DIR / "bloque_parcial.pdf", width, height)
    top_y = height - MARGIN

    filas_ok = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino Bueno",
         "horas": {d: "08:00" for d in dias}},
        {"direccion": "vuelta", "salida": "Destino Bueno", "llegada": "Tigre",
         "horas": {d: "17:00" for d in dias}},
    ]
    bottom_y, _, _ = render_block(
        c, MARGIN, top_y, dias, "1", "RAMAL 1", filas_ok,
        recorrido="Rio Test - Destino Bueno.", duracion="01:00 hs",
    )

    filas_roto = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino Roto",
         "horas": {d: "09:00" for d in dias}},
        {"direccion": "vuelta", "salida": "Destino Roto", "llegada": "Tigre",
         "horas": {d: "18:00" for d in dias}},
    ]
    render_block(
        c, MARGIN, bottom_y - 40, dias, "2", "RAMAL 2", filas_roto,
        recorrido="", duracion="",
        omit_recorrido=True, omit_duracion=True,
    )
    c.showPage()
    c.save()


def gen_datos_faltantes():
    """VUELTA solo tiene horarios sábado/domingo (resto de la semana en
    blanco) -- datos faltantes que no deben tumbar el parseo, solo
    resultar en menos horarios para esos días."""
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 260
    c = new_canvas(FIXTURES_DIR / "datos_faltantes.pdf", width, height)
    top_y = height - MARGIN
    filas = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino Parcial",
         "horas": {d: "08:00" for d in dias}},
        {"direccion": "vuelta", "salida": "Destino Parcial", "llegada": "Tigre",
         "horas": {"sabado": "17:00", "domingo": "17:00"}},
    ]
    render_block(
        c, MARGIN, top_y, dias, "1", "RAMAL 1", filas,
        recorrido="Rio Test - Destino Parcial.", duracion="01:00 hs",
    )
    c.showPage()
    c.save()


def gen_horarios_superpuestos():
    """Dos filas IDA distintas ofrecen el mismo dia+hora (lunes 08:00) a
    destinos distintos -- servicio bifurcado / horarios superpuestos: no
    deben pisarse ni perderse entradas."""
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 300
    c = new_canvas(FIXTURES_DIR / "horarios_superpuestos.pdf", width, height)
    top_y = height - MARGIN
    filas = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino A",
         "horas": {"lunes": "08:00", "martes": "08:00"}},
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino B",
         "horas": {"lunes": "08:00", "miercoles": "08:00"}},
        {"direccion": "vuelta", "salida": "Destino A", "llegada": "Tigre",
         "horas": {d: "17:00" for d in dias}},
    ]
    render_block(
        c, MARGIN, top_y, dias, "1", "RAMAL 1", filas,
        recorrido="Rio Test - Destino A - Destino B.", duracion="01:00 hs",
    )
    c.showPage()
    c.save()


def gen_hora_mal_formateada():
    """Typo de punto y coma en vez de dos puntos ('13;30') -- debe
    corregirse a '13:30'. Otra celda con texto no-horario ('S/H') pasa
    literal (el parser no valida formato de hora, solo lo documenta)."""
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 260
    c = new_canvas(FIXTURES_DIR / "hora_mal_formateada.pdf", width, height)
    top_y = height - MARGIN
    filas = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino C",
         "horas": {"lunes": "13;30", "martes": "S/H", "miercoles": "08:00"}},
        {"direccion": "vuelta", "salida": "Destino C", "llegada": "Tigre",
         "horas": {d: "17:00" for d in dias}},
    ]
    render_block(
        c, MARGIN, top_y, dias, "1", "RAMAL 1", filas,
        recorrido="Rio Test - Destino C.", duracion="01:00 hs",
    )
    c.showPage()
    c.save()


def gen_nombres_duplicados():
    """Dos bloques 'TRONCAL' sin número distintivo, cada uno a un destino
    distinto -- deben desambiguarse agregando el destino al nombre."""
    dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    width = sum(COL_WIDTHS_FIJAS) + DIA_COL_WIDTH * len(dias) + 2 * MARGIN
    height = 420
    c = new_canvas(FIXTURES_DIR / "nombres_duplicados.pdf", width, height)
    top_y = height - MARGIN

    filas_1 = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino Uno",
         "horas": {d: "08:00" for d in dias}},
        {"direccion": "vuelta", "salida": "Destino Uno", "llegada": "Tigre",
         "horas": {d: "17:00" for d in dias}},
    ]
    bottom_y, _, _ = render_block(
        c, MARGIN, top_y, dias, "1", "TRONCAL", filas_1,
        recorrido="Rio Test - Destino Uno.", duracion="01:00 hs",
    )

    filas_2 = [
        {"direccion": "ida", "salida": "Tigre", "llegada": "Destino Dos",
         "horas": {d: "09:00" for d in dias}},
        {"direccion": "vuelta", "salida": "Destino Dos", "llegada": "Tigre",
         "horas": {d: "18:00" for d in dias}},
    ]
    render_block(
        c, MARGIN, bottom_y - 40, dias, "2", "TRONCAL", filas_2,
        recorrido="Rio Test - Destino Dos.", duracion="01:00 hs",
    )
    c.showPage()
    c.save()


def main():
    gen_jilguero_450_ok()
    gen_interislena_451_ok()
    gen_delta_453_ok()
    gen_corrupto_no_es_pdf()
    gen_sin_tablas()
    gen_bloque_incompleto()
    gen_bloque_parcial()
    gen_datos_faltantes()
    gen_horarios_superpuestos()
    gen_hora_mal_formateada()
    gen_nombres_duplicados()
    print(f"Fixtures generados en {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
