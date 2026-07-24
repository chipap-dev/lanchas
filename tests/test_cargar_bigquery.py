"""
Tests de `lanchas_cargar_bigquery` y `services.bigquery_export`.

El cliente de BigQuery se mockea (`sys.modules`, mismo patrón que
`mareas_cargar_bigquery` en el repo hermano): estos tests no pegan a la
red ni requieren `google-cloud-bigquery` instalado.
"""

import sys
from datetime import time
from unittest import mock

import pytest
from django.core.management import call_command

from lanchas.models import Empresa, Horario, Linea, RecorridoTramo, Servicio, Via
from lanchas.services.bigquery_export import TABLE_SCHEMA_FIELDS, flatten_horarios


@pytest.fixture
def escenario_dos_vias(db):
    """
    Un servicio "Troncal" que recorre 2 vías (Río Luján, Arroyo
    Angostura) y bifurca un horario puntual hacia un destino que no es
    tramo del recorrido (ej. un muelle final) - cubre el caso que
    justifica el grano (horario, vía) en vez de (horario) a secas.
    """
    empresa = Empresa.objects.create(nombre="Jilguero", slug="jilguero")
    linea = Linea.objects.create(
        empresa=empresa, numero="450", pdf_url="https://example.com/450.pdf", pdf_filename="450.pdf"
    )
    servicio = Servicio.objects.create(linea=linea, nombre="Troncal", tipo="troncal")

    rio_lujan = Via.objects.create(nombre="Río Luján", slug="rio-lujan")
    arroyo_angostura = Via.objects.create(nombre="Arroyo Angostura", slug="arroyo-angostura")
    muelle_final = Via.objects.create(nombre="Muelle Final", slug="muelle-final")

    RecorridoTramo.objects.create(servicio=servicio, via=rio_lujan, orden=1)
    RecorridoTramo.objects.create(servicio=servicio, via=arroyo_angostura, orden=2)

    horario_normal = Horario.objects.create(
        servicio=servicio, direccion="ida", tipo_dia="lunes", hora=time(8, 0)
    )
    horario_bifurcado = Horario.objects.create(
        servicio=servicio,
        direccion="ida",
        tipo_dia="lunes",
        hora=time(9, 0),
        destino=muelle_final,
    )
    return {
        "empresa": empresa,
        "linea": linea,
        "servicio": servicio,
        "horario_normal": horario_normal,
        "horario_bifurcado": horario_bifurcado,
    }


def test_flatten_genera_una_fila_por_horario_y_via_de_tramo(escenario_dos_vias):
    rows = flatten_horarios("2026-07-23T00:00:00+00:00")

    filas_horario_normal = [r for r in rows if r["hora"] == "08:00:00"]
    assert {r["via_nombre"] for r in filas_horario_normal} == {"Río Luján", "Arroyo Angostura"}
    assert all(r["tipo_dia"] == "lunes" for r in filas_horario_normal)
    assert all(r["direccion"] == "ida" for r in filas_horario_normal)
    assert all(r["empresa_nombre"] == "Jilguero" for r in filas_horario_normal)
    assert all(r["linea_numero"] == "450" for r in filas_horario_normal)
    assert all(r["servicio_nombre"] == "Troncal" for r in filas_horario_normal)
    assert all(r["fecha_carga"] == "2026-07-23T00:00:00+00:00" for r in filas_horario_normal)
    assert {frozenset(r.keys()) for r in rows} == {frozenset(name for name, _ in TABLE_SCHEMA_FIELDS)}


def test_flatten_agrega_el_destino_puntual_sin_duplicar_tramos(escenario_dos_vias):
    rows = flatten_horarios("2026-07-23T00:00:00+00:00")

    filas_horario_bifurcado = [r for r in rows if r["hora"] == "09:00:00"]
    # 2 tramos + 1 destino puntual, sin duplicados.
    assert {r["via_nombre"] for r in filas_horario_bifurcado} == {
        "Río Luján", "Arroyo Angostura", "Muelle Final",
    }
    assert len(filas_horario_bifurcado) == 3


def test_flatten_sin_horarios_devuelve_lista_vacia(db):
    assert flatten_horarios("2026-07-23T00:00:00+00:00") == []


def test_command_hace_write_truncate(escenario_dos_vias):
    fake_bigquery = mock.MagicMock()
    fake_bigquery.WriteDisposition.WRITE_TRUNCATE = "WRITE_TRUNCATE"
    fake_client = mock.MagicMock()
    fake_bigquery.Client.return_value = fake_client
    fake_google_cloud = mock.MagicMock(bigquery=fake_bigquery)

    env = {
        "GCP_PROJECT_ID": "chipap",
        "GCP_DATASET_RAW": "lanchas_raw",
        "GCP_LOCATION": "us-central1",
    }

    with mock.patch.dict(
        sys.modules, {"google.cloud": fake_google_cloud, "google.cloud.bigquery": fake_bigquery}
    ):
        with mock.patch.dict("os.environ", env):
            call_command("lanchas_cargar_bigquery")

    fake_client.load_table_from_json.assert_called_once()
    load_args, load_kwargs = fake_client.load_table_from_json.call_args
    rows, table_ref = load_args
    assert table_ref == "chipap.lanchas_raw.horarios"
    assert len(rows) == 5  # 2 tramos x horario_normal + 3 vias x horario_bifurcado

    _, load_job_config_kwargs = fake_bigquery.LoadJobConfig.call_args
    assert load_job_config_kwargs["write_disposition"] == "WRITE_TRUNCATE"
    assert len(load_job_config_kwargs["schema"]) == len(TABLE_SCHEMA_FIELDS)


def test_command_sin_horarios_no_llama_a_bigquery(db):
    fake_bigquery = mock.MagicMock()
    fake_client = mock.MagicMock()
    fake_bigquery.Client.return_value = fake_client
    fake_google_cloud = mock.MagicMock(bigquery=fake_bigquery)

    env = {
        "GCP_PROJECT_ID": "chipap",
        "GCP_DATASET_RAW": "lanchas_raw",
        "GCP_LOCATION": "us-central1",
    }

    with mock.patch.dict(
        sys.modules, {"google.cloud": fake_google_cloud, "google.cloud.bigquery": fake_bigquery}
    ):
        with mock.patch.dict("os.environ", env):
            call_command("lanchas_cargar_bigquery")

    fake_client.load_table_from_json.assert_not_called()


def test_command_sin_variable_de_entorno_falla_con_mensaje_claro(db):
    from django.core.management.base import CommandError

    fake_bigquery = mock.MagicMock()
    fake_google_cloud = mock.MagicMock(bigquery=fake_bigquery)

    with mock.patch.dict(
        sys.modules, {"google.cloud": fake_google_cloud, "google.cloud.bigquery": fake_bigquery}
    ):
        with mock.patch.dict("os.environ", {}, clear=True):
            with pytest.raises(CommandError, match="GCP_PROJECT_ID"):
                call_command("lanchas_cargar_bigquery")
