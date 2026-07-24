"""
Lógica compartida entre parsers de PDFs de horarios de lanchas generados por
el mismo motor/plantilla del gobierno (verificado sobre Jilguero línea 450 e
Interisleña líneas 451/452 - layouts casi idénticos, con pequeñas diferencias
de columnas que cada subclase ajusta vía `DIAS_COLUMNAS`).

Puntos no obvios (verificados manualmente sobre los PDFs reales):
- Grillas con bordes reales -> se usa `page.find_tables()` como vía principal
  (más robusto que texto plano, que rompe la alineación de columnas por día).
- Cada tabla del PDF = un bloque de servicio (CANT.SERV, TIPO, IDA/VUELTA,
  DETALLE SERVICIO, columnas de día, RECORRIDO, DURACION APROX. DEL VIAJE).
- Los textos de "TIPO DE SERVICIO" y de dirección (IDA/VUELTA) + lugar de
  salida/llegada quedan anclados por pdfplumber a la fila cuyo centro
  vertical coincide con el de la celda combinada real (no necesariamente la
  primera fila del grupo, ni el centro geométrico exacto del bloque cuando
  IDA y VUELTA tienen distinta cantidad de filas). Por eso NO hay que
  inferir el límite IDA/VUELTA por posición de la etiqueta: cada fila tiene
  un rectángulo de fondo (fill) cuyo color es constante dentro del bloque
  IDA y cambia exactamente en el límite real con VUELTA - ese color es la
  señal confiable para clasificar la dirección fila por fila (ver
  `_direccion_por_color`); lugar de salida/llegada sí se reconstruye con
  forward+backward fill, pero sin cruzar ese límite ya resuelto.
- La celda de RECORRIDO usa a veces un tracking de fuente tan condensado que
  `extract_tables()` (tolerancia x por defecto) pega palabras sin espacio
  ("RíoTigre-RíoLuján..."). Se resuelve recortando el bbox de esa celda
  (columna 4+, no la fila entera, porque columnas 0-3 tienen celdas altas
  fusionadas) y re-extrayendo texto con `x_tolerance` chico. Si el recorrido
  ocupa 2 líneas visuales, la etiqueta "RECORRIDO"/"DURACION..." puede quedar
  en el medio del texto re-extraído (no solo al principio) - se remueve con
  `\bRECORRIDO\b` (regex sin ancla `^`).
- Las condiciones por fila (nota al pie) se marcan con un pequeño triángulo
  (`page.curves`) delante del horario y delante de la nota - no hay que
  interpretar el color, solo usarlo para emparejar (mismo color = misma
  fila <-> misma nota). El color del marcador NO es siempre "puro"/primario
  (Interisleña usa verde, casi-negro, cian según el PDF) así que no sirve
  para distinguirlo de curvas decorativas; lo que sí es constante es la
  posición: el triángulo de cada nota está pegado al margen izquierdo de la
  página (x0≈50-60), bien afuera de cualquier sello/logo decorativo que
  algunos PDFs (Interisleña) tienen cerca del pie de página, hecho de
  cientos de curvas con colores "sucios" (ej. (0.754, 0.098, 0.223)) pero
  siempre pegadas al margen derecho - `_MARGEN_IZQUIERDO_MARCADOR` filtra
  por esa posición, no por color.
"""

import logging
import re

import pdfplumber

from .base import BaseParser, ParserError

logger = logging.getLogger(__name__)

TIPO_MAP = [
    (re.compile(r"^TRONCAL$", re.IGNORECASE), "troncal"),
    (re.compile(r"^FRACCIONADO\s+DE\s+RAMAL\s*\d*$", re.IGNORECASE), "desdoblamiento"),
    (re.compile(r"^FRACCIONADO\s*\d*$", re.IGNORECASE), "fraccionado"),
    (re.compile(r"^RAMAL\s*\d*$", re.IGNORECASE), "ramal"),
]

_PALABRAS_MINUSCULA = {"de", "del", "la", "el", "los", "las", "y"}

_VIA_PREFIJO_PLURAL = {
    "rios": "Río", "ríos": "Río",
    "arroyos": "Arroyo",
    "canales": "Canal",
    "riachos": "Riacho",
    "lagunas": "Laguna",
    "pasos": "Paso",
}

_PREFIJOS_VIA = r"R[ií]os?|Arroyos?|Canal(?:es)?|Riachos?|Lagunas?|Pasos?|Boca"

_RE_PREFIJO_VIA = re.compile(rf"\b({_PREFIJOS_VIA})\b", re.IGNORECASE)

# Separador entre tramos del recorrido: guion (con o sin espacios), a veces
# solo una coma sin guion delante del próximo tramo (typo visto en
# Interisleña: "Río Luján,Río Sarmiento" en vez de "Río Luján - Río Sarmiento"),
# o "hasta" (ej. "Arroyo Durazno hasta Canal de la Serna" son dos tramos, no
# uno). Sin espacio obligatorio antes de "hasta": el tracking de fuente tan
# condensado de algunos PDF (Delta) a veces lo pega a la palabra anterior
# ("Duraznohasta").
_RE_SEPARADOR_TRAMO = re.compile(
    rf"\s*-\s*|,(?=\s*(?:{_PREFIJOS_VIA})\b)|\s*hasta\s*", re.IGNORECASE
)

# Color de fondo (fill) constante para todas las filas de un mismo bloque
# IDA/VUELTA - ver nota en _direccion_por_color. Verificado igual en los
# PDFs de Jilguero e Interisleña (mismo motor de generación).
_COLOR_FONDO_IDA = (0.004, 0.086, 0.125)
_COLOR_FONDO_VUELTA = (0.074, 0.012, 0.141)

# Cola colgante que indica que el nombre de un lugar quedó cortado por un
# salto de línea del PDF (ver uso en _agrupar_horarios).
_RE_FRAGMENTO_COLGANTE = re.compile(r"\s*\b(por|de|del|hasta|y)$", re.IGNORECASE)


class BaseGobiernoParser(BaseParser):
    """
    Subclases deben definir `DIAS_COLUMNAS` (nombres de tipo_dia en el mismo
    orden que las columnas de día de la tabla, empezando en la columna 5) y
    pueden sobreescribir `_nombre_tipo_sin_clasificar` si el PDF tiene
    bloques sin número/tipo impreso (ver Jilguero línea 450).
    """

    DIAS_COLUMNAS: list[str] = [
        "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    ]

    # Correcciones puntuales a nombres de vía que el PDF mismo escribe mal
    # (ej. Jilguero línea 450 mete "Espera" en la lista de "Arroyos" del
    # recorrido, pero es un río - confirmado a mano con el usuario). Se van
    # a ir sumando casuística por casuística; cada subclase define la suya.
    CORRECCIONES_VIA: dict = {}

    # Igual que CORRECCIONES_VIA, pero para el caso puntual de una fila cuyo
    # destino en el PDF ya viene mencionando dos lugares reales a la vez (ej.
    # una vuelta que aplica a todos los días y el texto dice "Lugar A y
    # Lugar B"): en vez de elegir uno solo, se duplica el horario para que
    # ambos lugares sean encontrables por separado.
    CORRECCIONES_VIA_MULTIPLE: dict = {}

    def _corregir_via(self, nombre: str) -> str:
        return self.CORRECCIONES_VIA.get(nombre, nombre)

    def parse_pdf(self) -> list[dict]:
        self.errores: list[str] = []
        self.notas: list[str] = []
        servicios: list[dict] = []

        for pdf_path in self._pdf_paths():
            servicios.extend(self._parse_archivo(pdf_path))

        if not servicios:
            raise ParserError(f"No se pudo extraer ningún servicio de la línea {self.linea_numero}.")

        self._desambiguar_nombres(servicios)
        return servicios

    def _desambiguar_nombres(self, servicios: list[dict]) -> None:
        """
        `Servicio` se carga por (linea, nombre) - si dos bloques (del mismo
        PDF o, al combinar varios archivos en una sola línea, de PDFs
        distintos) resuelven el mismo nombre genérico (ej. dos "TRONCAL", o
        dos "FRACCIONADO" sin número dentro del mismo PDF), uno pisaría al
        otro al cargar. Se desambigua agregando el destino final entre
        paréntesis, tomado del primer horario de cada bloque.
        """
        por_nombre: dict[str, list[dict]] = {}
        for s in servicios:
            por_nombre.setdefault(s["servicio_nombre"], []).append(s)

        for nombre, grupo in por_nombre.items():
            if len(grupo) < 2:
                continue
            for s in grupo:
                destino = s["horarios"][0]["destino"] if s["horarios"] else None
                if destino:
                    s["servicio_nombre"] = f"{nombre} ({destino})"
                    self.notas.append(
                        f"Nombre de servicio duplicado ('{nombre}') - renombrado a "
                        f"'{s['servicio_nombre']}' usando el destino para no pisar datos."
                    )

    def _pdf_paths(self) -> list:
        """Archivos a parsear. Por defecto uno solo (self.pdf_path)."""
        return [self.pdf_path]

    def _parse_archivo(self, pdf_path) -> list[dict]:
        servicios = []
        with pdfplumber.open(pdf_path) as pdf:
            for num_pagina, page in enumerate(pdf.pages, start=1):
                condiciones_pagina = self._extraer_condiciones(page)
                for tabla in page.find_tables():
                    filas = tabla.extract()
                    if len(filas) < 4:
                        continue
                    # Algunos PDF (Delta) no siempre detectan un límite claro
                    # entre dos bloques de servicio visualmente separados y
                    # los devuelven como una sola `Table` con el encabezado
                    # ("CANT. SERV." / "TIPO DE SERVICIO" / ...) repetido en
                    # el medio - hay que partirla en sub-bloques donde
                    # reaparece ese encabezado, si no el texto de un bloque
                    # se mezcla con el del otro.
                    for inicio, fin in self._bloques_de_tabla(filas):
                        sub_filas = filas[inicio:fin]
                        sub_meta = tabla.rows[inicio:fin]
                        try:
                            servicio = self._parse_bloque(page, sub_filas, sub_meta, condiciones_pagina)
                        except Exception as exc:
                            msg = f"{pdf_path.name} página {num_pagina}: error al parsear bloque de servicio - {exc}"
                            logger.error(msg)
                            self.errores.append(msg)
                            continue
                        servicios.append(servicio)
        return servicios

    @staticmethod
    def _bloques_de_tabla(filas: list) -> list:
        inicios = [i for i, f in enumerate(filas) if "CANT" in (f[0] or "").upper()]
        if not inicios:
            inicios = [0]
        limites = inicios + [len(filas)]
        return list(zip(limites[:-1], limites[1:]))

    # ------------------------------------------------------------------
    # Bloque de servicio
    # ------------------------------------------------------------------

    def _parse_bloque(self, page, filas: list, filas_meta: list, condiciones_pagina: dict) -> dict:
        filas_datos = filas[2:]  # descarta las 2 filas de encabezado
        filas_meta = filas_meta[2:]

        idx_recorrido = next(
            (i for i, f in enumerate(filas_datos) if self._limpiar(f[2]) == "RECORRIDO"),
            None,
        )
        idx_duracion = next(
            (i for i, f in enumerate(filas_datos) if self._limpiar(f[2]).startswith("DURACION")),
            None,
        )
        if idx_recorrido is None or idx_duracion is None:
            raise ParserError("no se encontraron las filas RECORRIDO/DURACION del bloque")

        filas_horario = filas_datos[:idx_recorrido]

        tipo_texto = " ".join(
            self._limpiar(f[1]) for f in filas_datos if self._limpiar(f[1])
        ).strip()

        recorrido_texto = self._extraer_texto_fila(
            page, self._bbox_texto_fila(filas_meta[idx_recorrido], page), r"\bRECORRIDO\b"
        )
        duracion_texto = self._extraer_texto_fila(
            page, self._bbox_texto_fila(filas_meta[idx_duracion], page),
            r"\bDURACION\s+APROX\.?\s+DEL\s+VIAJE\b",
        )
        duracion_texto = re.sub(r"(\d):\s+(\d)", r"\1:\2", duracion_texto)
        duracion_texto = re.sub(r"\bHS\b", "hs", duracion_texto, flags=re.IGNORECASE)

        filas_agrupadas = self._agrupar_horarios(page, filas_horario, filas_meta[:idx_recorrido])
        condiciones_por_fila = self._condiciones_por_fila(
            page, filas_meta[:idx_recorrido], condiciones_pagina
        )
        horarios, lugares_llegada = self._construir_horarios(filas_agrupadas, condiciones_por_fila)
        if not horarios:
            raise ParserError("el bloque no contiene ningún horario válido")

        vias = self._parse_vias(recorrido_texto, lugares_llegada)

        if tipo_texto:
            tipo = self._clasificar_tipo(tipo_texto)
            nombre = self._formatear_nombre(tipo_texto)
        else:
            nombre, tipo = self._nombre_tipo_sin_clasificar(lugares_llegada)

        return {
            "servicio_nombre": nombre,
            "servicio_tipo": tipo,
            "servicio_descripcion": f"Duración aprox.: {duracion_texto}" if duracion_texto else "",
            "vias": vias,
            "horarios": horarios,
        }

    def _nombre_tipo_sin_clasificar(self, lugares_llegada) -> tuple:
        """Hook: nombre/tipo cuando el bloque no trae número/tipo impreso."""
        principal = next(iter(lugares_llegada), "")
        nombre = f"Ramal Tigre - {principal}".strip(" -")
        self.notas.append(
            f"Servicio sin número/tipo impreso en el PDF (destino: '{principal}') - "
            f"asignado nombre='{nombre}', tipo='ramal' por defecto. Verificar manualmente."
        )
        return nombre, "ramal"

    # ------------------------------------------------------------------
    # Filas de horario: reconstrucción de dirección / lugar / destino
    # ------------------------------------------------------------------

    def _agrupar_horarios(self, page, filas: list, filas_meta: list) -> list[dict]:
        n = len(filas)
        direccion: list = [None] * n
        salida = [""] * n
        llegada = [""] * n

        for i, fila in enumerate(filas):
            direccion[i] = self._direccion_por_color(page, filas_meta[i])
            salida[i] = self._limpiar(fila[3])
            llegada[i] = self._limpiar(fila[4])

        # Respaldo si el color no alcanzó para clasificar alguna fila (no
        # debería pasar, pero por robustez): usar la etiqueta IDA/VUELTA
        # propia y, si tampoco está, heredar de la fila vecina.
        for i, fila in enumerate(filas):
            if direccion[i] is not None:
                continue
            etiqueta = self._limpiar(fila[2]).upper()
            if etiqueta == "IDA":
                direccion[i] = "ida"
            elif etiqueta == "VUELTA":
                direccion[i] = "vuelta"
        for i in range(1, n):
            if direccion[i] is None:
                direccion[i] = direccion[i - 1]
        for i in range(n - 2, -1, -1):
            if direccion[i] is None:
                direccion[i] = direccion[i + 1]

        # Nombre de lugar cortado por un salto de línea del PDF en una
        # preposición/conjunción colgante (ej. "Arroyo Durazno por" en una
        # fila y "Caraguatá" en la siguiente, cada una con su propia hora:
        # no son horarios distintos, es el mismo lugar con su nombre partido
        # en dos filas). Se reconstruye el texto completo y se lo deja en
        # las dos filas - CORRECCIONES_VIA/CORRECCIONES_VIA_MULTIPLE deciden
        # después si el resultado es un solo lugar limpio o dos lugares
        # reales a preservar por separado, sin perder el que quedó en la
        # fila siguiente.
        for i in range(n - 1):
            if direccion[i] != direccion[i + 1]:
                continue
            if salida[i] and salida[i + 1] and _RE_FRAGMENTO_COLGANTE.search(salida[i]):
                completo = f"{salida[i]} {salida[i + 1]}".strip()
                salida[i] = completo
                salida[i + 1] = completo
            if llegada[i] and llegada[i + 1] and _RE_FRAGMENTO_COLGANTE.search(llegada[i]):
                completo = f"{llegada[i]} {llegada[i + 1]}".strip()
                llegada[i] = completo
                llegada[i + 1] = completo

        # lugar_salida/lugar_llegada: hereda de la fila vecina solo dentro
        # del mismo bloque de dirección (ya resuelto de forma confiable
        # arriba), para no arrastrar el lugar de un bloque al de al lado.
        for i in range(1, n):
            if direccion[i] == direccion[i - 1]:
                if not salida[i]:
                    salida[i] = salida[i - 1]
                if not llegada[i]:
                    llegada[i] = llegada[i - 1]
        for i in range(n - 2, -1, -1):
            if direccion[i] == direccion[i + 1]:
                if not salida[i]:
                    salida[i] = salida[i + 1]
                if not llegada[i]:
                    llegada[i] = llegada[i + 1]

        resultado = []
        for i, fila in enumerate(filas):
            dias = {}
            for col_idx, dia in enumerate(self.DIAS_COLUMNAS):
                indice = 5 + col_idx
                # Algunas tablas (Delta) a veces ni siquiera detectan la
                # columna FERIADOS como celda propia (desaparece del todo,
                # no solo queda vacía) - tratarla como sin dato en vez de
                # reventar con IndexError.
                celda_cruda = fila[indice] if indice < len(fila) else ""
                celda_cruda = celda_cruda or ""
                if "\n" in celda_cruda:
                    # Algunas tablas no subdividen todas las columnas de día
                    # por igual - la mayoría de las filas quedan bien
                    # repartidas, pero alguna columna puntual junta varios
                    # horarios (de filas/direcciones distintas) en una sola
                    # celda. No hay forma confiable de saber a qué fila
                    # pertenece cada línea, así que se toma solo la primera
                    # y se deja registrado para revisión manual.
                    lineas = [self._limpiar(l) for l in celda_cruda.split("\n") if self._limpiar(l)]
                    valor = lineas[0] if lineas else ""
                    if len(lineas) > 1:
                        self.notas.append(
                            f"Fila {i}, columna '{dia}': la celda traía varios horarios "
                            f"apilados ({lineas}) - se tomó solo '{valor}', revisar "
                            "manualmente en el PDF."
                        )
                else:
                    valor = self._limpiar(celda_cruda)
                if valor:
                    # Typo visto en Delta: "13;30" en vez de "13:30".
                    dias[dia] = re.sub(r"(\d);(\d)", r"\1:\2", valor)
            if not dias:
                continue
            if direccion[i] is None:
                raise ParserError(f"no se pudo determinar IDA/VUELTA para la fila {i}")
            resultado.append({
                "fila_idx": i,
                "direccion": direccion[i],
                "lugar_salida": salida[i],
                "lugar_llegada": llegada[i],
                "dias": dias,
            })
        return resultado

    def _construir_horarios(self, filas_agrupadas: list, condiciones_por_fila: dict):
        llegadas_ida = {f["lugar_llegada"] for f in filas_agrupadas if f["direccion"] == "ida"}
        salidas_vuelta = {f["lugar_salida"] for f in filas_agrupadas if f["direccion"] == "vuelta"}

        horarios = []
        for f in filas_agrupadas:
            condicion = condiciones_por_fila.get(f["fila_idx"], "")
            # El "destino" de cada fila es siempre el extremo lejano de Tigre
            # (llegada en ida, salida en vuelta) - se guarda siempre, no solo
            # cuando el servicio se bifurca, para poder ubicar horarios por
            # cualquier lugar puntual del recorrido (ej. un muelle final).
            lugar = f["lugar_llegada"] if f["direccion"] == "ida" else f["lugar_salida"]
            destinos_fila = self.CORRECCIONES_VIA_MULTIPLE.get(lugar) or [self._corregir_via(lugar)]
            for dia, hora in f["dias"].items():
                for destino in destinos_fila:
                    horarios.append({
                        "direccion": f["direccion"],
                        "tipo_dia": dia,
                        "hora": hora,
                        "condicion": condicion,
                        "destino": destino,
                    })

        destinos_finales = llegadas_ida if llegadas_ida else salidas_vuelta
        return horarios, destinos_finales

    # ------------------------------------------------------------------
    # Condiciones (triángulos de color)
    # ------------------------------------------------------------------

    # Las notas al pie arrancan con su triángulo-marcador pegado al margen
    # izquierdo de la página (verificado en Jilguero e Interisleña: x0≈50-60).
    # No se puede filtrar por "color puro": algunos PDFs (Interisleña, bloques
    # con varias notas) usan colores de marcador que no son primarios (ej.
    # verde, casi negro, cian) - lo que sí es constante es la posición, muy
    # a la izquierda, bien afuera de sellos/logos decorativos que algunos
    # PDFs tienen cerca del pie de página (esos quedan pegados a la derecha).
    _MARGEN_IZQUIERDO_MARCADOR = 150

    def _extraer_condiciones(self, page) -> dict:
        """Mapea color de relleno -> texto de nota al pie, para toda la página."""
        tablas = page.find_tables()
        if not tablas:
            return {}
        limite = max(t.bbox[3] for t in tablas)
        condiciones = {}
        for curva in page.curves:
            if not curva.get("fill"):
                continue
            if curva["top"] < limite or curva["x0"] > self._MARGEN_IZQUIERDO_MARCADOR:
                continue
            color = self._color_key(curva)
            if color is None:
                continue
            recorte = page.crop((curva["x0"], curva["top"] - 2, page.width, curva["bottom"] + 2))
            texto = self._limpiar(recorte.extract_text(x_tolerance=1.5))
            if texto:
                condiciones[color] = texto
        return condiciones

    def _condiciones_por_fila(self, page, filas_meta: list, condiciones_pagina: dict) -> dict:
        if not condiciones_pagina:
            return {}
        resultado = {}
        for i, meta in enumerate(filas_meta):
            # Las columnas 0-3 suelen tener celdas altas (fusionadas visualmente
            # con filas vecinas); las columnas de día (5+) sí reflejan la
            # altura real de la fila visual, así que se usan para acotar.
            celda = next((c for c in meta.cells[5:] if c is not None), None)
            if celda is None:
                continue
            top, bottom = celda[1], celda[3]
            for curva in page.curves:
                if not curva.get("fill"):
                    continue
                centro = (curva["top"] + curva["bottom"]) / 2
                if top <= centro <= bottom:
                    color = self._color_key(curva)
                    if color in condiciones_pagina:
                        resultado[i] = condiciones_pagina[color]
                        break
        return resultado

    @staticmethod
    def _bbox_texto_fila(fila_meta, page):
        """Bbox de la celda de texto libre de una fila (columna 4 en adelante,
        evitando arrastrar las columnas de etiqueta 0-3 que suelen tener
        celdas altas fusionadas con filas vecinas). El borde derecho siempre
        se extiende hasta el borde de la página (no el de la celda ni el de
        la tabla, que en algunas tablas (ej. Interisleña, bloques sin
        columna FERIADOS) quedan más angostos que el texto real y cortan
        palabras al final de la línea, ej. "Gaviota" -> "Gav")."""
        celda = next((c for c in fila_meta.cells[4:] if c is not None), None)
        if celda is None:
            celda = next((c for c in fila_meta.cells if c is not None), None)
        if celda is None:
            celda = fila_meta.bbox
        return (celda[0], celda[1], page.width, celda[3])

    @staticmethod
    def _color_key(curva):
        color = curva.get("non_stroking_color")
        if isinstance(color, (list, tuple)):
            return tuple(round(c, 3) for c in color)
        return color

    def _direccion_por_color(self, page, fila_meta):
        """
        Clasifica IDA/VUELTA por el color de fondo (fill) de la fila, no por
        la posición de la etiqueta "IDA"/"VUELTA": esa etiqueta se ancla al
        centro vertical del bloque completo, que no coincide con ninguna
        fila real cuando IDA y VUELTA tienen distinta cantidad de filas
        (ej. Río Espera en Jilguero: IDA=6 filas, VUELTA=8 - la etiqueta
        "IDA" cae en la 4ª fila y contamina por posición las primeras filas
        de VUELTA si se infiere por cercanía). El relleno, en cambio, es
        constante para todas las filas de un mismo bloque y cambia justo en
        el límite real.
        """
        celda = next((c for c in fila_meta.cells[3:] if c is not None), None)
        if celda is None:
            return None
        centro = (celda[1] + celda[3]) / 2
        for r in page.rects:
            if not r.get("fill"):
                continue
            color = self._color_key(r)
            color = color[:3] if isinstance(color, tuple) else None
            if color not in (_COLOR_FONDO_IDA, _COLOR_FONDO_VUELTA):
                continue
            if r["top"] <= centro <= r["top"] + r["height"]:
                return "ida" if color == _COLOR_FONDO_IDA else "vuelta"
        return None

    # ------------------------------------------------------------------
    # Texto de celdas (recorte + re-extracción con tolerancia chica)
    # ------------------------------------------------------------------

    def _extraer_texto_fila(self, page, bbox, patron_etiqueta: str) -> str:
        texto = page.crop(bbox).extract_text(x_tolerance=1.5) or ""
        texto = re.sub(patron_etiqueta, "", texto, flags=re.IGNORECASE)
        return self._limpiar(texto)

    @staticmethod
    def _limpiar(texto) -> str:
        if not texto:
            return ""
        return re.sub(r"\s+", " ", texto.replace("\n", " ")).strip()

    # ------------------------------------------------------------------
    # Vías del recorrido
    # ------------------------------------------------------------------

    @staticmethod
    def _normalizar_destino(texto: str) -> str:
        t = texto.lower()
        t = re.sub(r"\bde\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _parse_vias(self, recorrido_texto: str, lugares_llegada) -> list:
        texto = recorrido_texto.strip().rstrip(".").strip()
        segmentos = [s.strip() for s in _RE_SEPARADOR_TRAMO.split(texto) if s.strip()]
        if not segmentos:
            return []

        destinos_norm = {self._normalizar_destino(d) for d in lugares_llegada if d}
        if destinos_norm:
            partes_ultimo = [
                self._normalizar_destino(p) for p in re.split(r"\s*/\s*", segmentos[-1])
            ]
            if all(
                any(p == d or p in d or d in p for d in destinos_norm)
                for p in partes_ultimo
            ):
                segmentos = segmentos[:-1]

        vias: list = []
        for seg in segmentos:
            match = _RE_PREFIJO_VIA.search(seg)
            if not match:
                continue
            resto = seg[match.start():].strip()
            clave = match.group(1).lower()
            if clave in _VIA_PREFIJO_PLURAL:
                prefijo = _VIA_PREFIJO_PLURAL[clave]
                nombres_texto = resto[len(match.group(1)):].strip()
                nombres = [n.strip() for n in re.split(r"\s*,\s*|\s+y\s+", nombres_texto) if n.strip()]
                vias.extend(f"{prefijo} {n}" for n in nombres)
            else:
                vias.append(resto)

        if len(destinos_norm) == 1:
            # Servicio no bifurcado: el destino final es un lugar real y
            # concreto (muelle, escuela, puerto...) aunque no tenga forma de
            # "Río/Arroyo/Canal" - se agrega como último tramo, con el texto
            # de la columna "Lugar salida/llegada" (más confiable que el
            # texto libre y a veces inconsistente del recorrido).
            vias.append(next(iter(lugares_llegada)))

        resultado = []
        for v in vias:
            resultado.extend(self.CORRECCIONES_VIA_MULTIPLE.get(v) or [self._corregir_via(v)])
        return resultado

    # ------------------------------------------------------------------
    # Tipo / nombre de servicio
    # ------------------------------------------------------------------

    def _clasificar_tipo(self, texto: str) -> str:
        for patron, tipo in TIPO_MAP:
            if patron.match(texto):
                return tipo
        self.notas.append(f"Tipo de servicio no reconocido: '{texto}' - asignado 'ramal' por defecto.")
        return "ramal"

    @staticmethod
    def _formatear_nombre(texto: str) -> str:
        palabras = texto.split()
        resultado = []
        for i, palabra in enumerate(palabras):
            base = palabra.lower()
            if i > 0 and base in _PALABRAS_MINUSCULA:
                resultado.append(base)
            else:
                resultado.append(base.capitalize())
        return " ".join(resultado)
