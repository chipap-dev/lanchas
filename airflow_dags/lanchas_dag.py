"""
DAG de orquestacion mensual de la capa de datos de Lanchas.

Este archivo vive versionado en el repo de Lanchas, pero no trae un
stack de Airflow propio: se asume que corre en el Airflow que ya existe
aparte (airflow_repo), copiando o linkeando este archivo a esa carpeta
dags/.

El contenedor de Airflow monta lanchas_repo en /opt/lanchas (solo codigo
y credenciales) y trae sus dependencias (Django, dbt-bigquery,
google-cloud-bigquery) ya instaladas en la imagen - no depende de
ningun venv creado en el host.

Orden: actualizar_pdfs -> cargar_bigquery -> dbt_run -> dbt_test.

`actualizar_pdfs` reusa el management command existente
`lanchas_actualizar` (descarga PDFs + parsea + upsert a Postgres +
sincroniza feriados - ver lanchas/management/commands/lanchas_actualizar.py).
No se reescribe esa logica aca. `cargar_bigquery` lee Postgres via ORM
(no re-parsea los PDFs) y sube el dataset completo con WRITE_TRUNCATE:
no hay historico que conservar, el horario vigente es lo unico
relevante.
"""

import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

LANCHAS_REPO_DIR = "/opt/lanchas"
DBT_PROJECT_DIR = f"{LANCHAS_REPO_DIR}/dbt_lanchas"

LANCHAS_ENV = {
    **os.environ,
    # Lanchas' own app database (docker-compose service `lanchas-db` in
    # airflow_repo) - actualizar_pdfs writes here via the Django ORM,
    # cargar_bigquery reads it back out. Not related to Airflow's own
    # metadata Postgres, and not chipap_net's production database.
    "DATABASE_URL": "postgres://lanchas:lanchas@lanchas-db:5432/lanchas",
    "GCP_PROJECT_ID": "chipap",
    "GCP_DATASET_RAW": "lanchas_raw",
    "GCP_LOCATION": "us-central1",
    "GOOGLE_APPLICATION_CREDENTIALS": f"{LANCHAS_REPO_DIR}/secrets/gcp-key.json",
    # profiles.yml vive junto a dbt_project.yml; dbt no lo busca ahi por
    # defecto (busca en ~/.dbt/), asi que se lo indicamos explicitamente.
    "DBT_PROFILES_DIR": DBT_PROJECT_DIR,
}

default_args = {
    "owner": "lanchas",
    "retries": 0,
}

with DAG(
    dag_id="lanchas_dag",
    description="Actualiza los horarios de Lanchas, los carga a BigQuery y corre dbt.",
    default_args=default_args,
    schedule="@monthly",
    # airflow.utils.dates.days_ago was removed in Airflow 3.x; a fixed
    # past date is the recommended replacement (catchup=False means the
    # exact value doesn't matter beyond "in the past").
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    tags=["lanchas", "bigquery", "dbt"],
) as dag:

    actualizar_pdfs = BashOperator(
        task_id="actualizar_pdfs",
        bash_command=f"cd {LANCHAS_REPO_DIR} && python manage.py lanchas_actualizar",
        env=LANCHAS_ENV,
        # Depende de los sitios de gobierno que publican los PDFs
        # oficiales, que pueden ser inestables.
        retries=2,
        retry_delay=timedelta(minutes=10),
    )

    cargar_bigquery = BashOperator(
        task_id="cargar_bigquery",
        bash_command=f"cd {LANCHAS_REPO_DIR} && python manage.py lanchas_cargar_bigquery",
        env=LANCHAS_ENV,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run",
        env=LANCHAS_ENV,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt test",
        env=LANCHAS_ENV,
    )

    actualizar_pdfs >> cargar_bigquery >> dbt_run >> dbt_test
