"""
Carga full-refresh de Horario (leído de Postgres vía ORM) a BigQuery
(`lanchas_raw.horarios`), para poder analizar el modelo dimensional en
`dbt_lanchas/`. No corre como parte del flujo que sirve al visitante.

A diferencia de Mareas (`mareas_cargar_bigquery`, que hace MERGE porque
le interesa conservar el histórico de lecturas), acá no hay histórico
que conservar: el horario vigente es lo único relevante, así que cada
corrida reemplaza el dataset completo (WRITE_TRUNCATE).

Forma de ejecutar:
- python manage.py lanchas_cargar_bigquery
"""

import logging
import os
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

from lanchas.services.bigquery_export import TABLE_SCHEMA_FIELDS, flatten_horarios

logger = logging.getLogger(__name__)

TABLE_NAME = "horarios"


def _get_client_and_config():
    from google.cloud import bigquery

    project_id = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ["GCP_DATASET_RAW"]
    location = os.environ["GCP_LOCATION"]

    client = bigquery.Client(project=project_id, location=location)
    table_ref = f"{project_id}.{dataset}.{TABLE_NAME}"
    return client, table_ref, bigquery


def _schema(bigquery):
    return [bigquery.SchemaField(name, field_type) for name, field_type in TABLE_SCHEMA_FIELDS]


def _cargar_full_refresh(client, table_ref, bigquery, rows):
    job_config = bigquery.LoadJobConfig(
        schema=_schema(bigquery),
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()


class Command(BaseCommand):
    help = "Sube Horario (Postgres, vía ORM) a BigQuery (lanchas_raw.horarios, full-refresh)."

    def handle(self, *args, **options):
        try:
            client, table_ref, bigquery = _get_client_and_config()
        except KeyError as exc:
            raise CommandError(f"Falta la variable de entorno {exc}.") from exc

        loaded_at_iso = datetime.now(timezone.utc).isoformat()
        rows = flatten_horarios(loaded_at_iso)

        if not rows:
            self.stdout.write("Sin horarios en la base de datos, no se sube nada.")
            return

        try:
            _cargar_full_refresh(client, table_ref, bigquery, rows)
        except Exception as exc:
            logger.exception("Error subiendo horarios a BigQuery")
            raise CommandError(f"Error subiendo horarios a BigQuery: {exc}") from exc

        self.stdout.write(f"{len(rows)} filas cargadas (WRITE_TRUNCATE) en {table_ref}.")
