import hashlib
import logging
from pathlib import Path

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30

# Configurable vía LANCHAS_PDF_DIR en settings. Default: BASE_DIR/data/lanchas/pdfs/
_PDF_DIR: Path | None = None


def get_pdf_dir() -> Path:
    global _PDF_DIR
    if _PDF_DIR is None:
        _PDF_DIR = Path(
            getattr(settings, "LANCHAS_PDF_DIR", settings.BASE_DIR / "data" / "lanchas" / "pdfs")
        )
    _PDF_DIR.mkdir(parents=True, exist_ok=True)
    return _PDF_DIR


def hash_archivo(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def hash_combinado(paths: list[Path]) -> str:
    """
    Hash único para una línea con más de un PDF fuente (ej. Interisleña
    451+452): cambia si cambia CUALQUIERA de los archivos. Sigue siendo un
    hex de 64 caracteres, compatible con ActualizacionLog.pdf_hash.
    """
    combinado = "".join(hash_archivo(p) for p in paths)
    return hashlib.sha256(combinado.encode()).hexdigest()


def descargar_pdf(url: str, filename: str) -> dict:
    """
    Descarga un PDF y lo guarda localmente.
    Retorna {'path', 'hash', 'modificado', 'bytes'}.
    """
    dest = get_pdf_dir() / filename
    hash_anterior = hash_archivo(dest) if dest.exists() else None

    logger.info("Descargando %s → %s", url, dest)
    try:
        resp = requests.get(url, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Error al descargar {url}: {exc}") from exc

    dest.write_bytes(resp.content)
    hash_nuevo = hash_archivo(dest)
    modificado = hash_anterior != hash_nuevo

    if modificado:
        logger.info("%s: PDF modificado", filename)
    else:
        logger.debug("%s: sin cambios", filename)

    return {
        "path": dest,
        "hash": hash_nuevo,
        "modificado": modificado,
        "bytes": len(resp.content),
    }


def descargar_todos(lineas: list) -> list[dict]:
    """
    Descarga los PDFs para una lista de objetos Linea. Si una línea tiene
    un segundo PDF (pdf_url_2/pdf_filename_2, ej. Interisleña 451+452),
    se descargan ambos y se combinan en un solo resultado: 'modificado' es
    True si cambió cualquiera de los dos, y 'hash' es el hash combinado.
    """
    resultados = []
    for linea in lineas:
        try:
            fuentes = [(linea.pdf_url, linea.pdf_filename)]
            if linea.pdf_url_2:
                fuentes.append((linea.pdf_url_2, linea.pdf_filename_2))

            infos = [descargar_pdf(url, filename) for url, filename in fuentes]
            info = {
                "path": infos[0]["path"],
                "hash": hash_combinado([i["path"] for i in infos]) if len(infos) > 1 else infos[0]["hash"],
                "modificado": any(i["modificado"] for i in infos),
                "bytes": sum(i["bytes"] for i in infos),
            }
            resultados.append({"linea": linea, "ok": True, "error": None, **info})
        except Exception as exc:
            logger.error("Error descargando línea %s: %s", linea.numero, exc)
            resultados.append({
                "linea": linea,
                "ok": False,
                "error": str(exc),
                "path": None,
                "hash": "",
                "modificado": False,
                "bytes": 0,
            })
    return resultados
