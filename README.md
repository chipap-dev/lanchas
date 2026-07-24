# Lanchas - Horarios del Delta del Tigre

[![CI](https://github.com/chipap-dev/lanchas/actions/workflows/ci.yml/badge.svg)](https://github.com/chipap-dev/lanchas/actions/workflows/ci.yml)

A Django app that scrapes and parses the official PDF schedules of the three
passenger-boat companies operating in the Tigre Delta (Argentina) and serves
them as a searchable, mobile-friendly timetable.

**Dockerized. Comes with real, pre-loaded data. `docker compose up` and go.**

---

## What it does

- Downloads and parses the official government PDF schedules of 3 lines
  (Interisleña 451/452, Jilguero 450, Delta Argentino 453) with `pdfplumber`
  - table extraction, color-coded direction detection, footnote-condition
  matching, not plain-text scraping
- Normalizes everything into a relational model: companies → lines →
  services → stops (rivers/streams) → timetable rows
- Resolves holiday schedules against Argentina's official calendar
  (`holidays` package)
- "Today" view, weekly schedule per direction, and a sidebar with every
  line's route as a native (JS-free) accordion
- Local (device-only) favorites via `localStorage`, no accounts

---

## Stack

Python 3.11 · Django 4.2 · PostgreSQL 16 · pdfplumber · holidays · Docker ·
Whitenoise · Vanilla JS · CSS custom properties · pytest + GitHub Actions

Data layer (optional, parallel): BigQuery · dbt · Airflow (shared engine,
sibling repo)

---

## Architecture

Real ORM, real migrations, real Postgres - unlike the sibling
[luthier](https://github.com/chipap-dev/luthier) and
[mareas](https://github.com/chipap-dev/mareas) repos, this app's whole
purpose is normalizing messy source data, so a database is the point.

```
lanchas/
├── models/         # Empresa → Linea → Servicio → Horario, Via, Feriado, ActualizacionLog
├── pipeline/
│   ├── downloader.py   # fetches PDFs, detects changes via SHA-256
│   └── loader.py       # loads parsed services/schedules into the DB
├── services/
│   ├── parsers/         # BaseGobiernoParser + one subclass per company
│   ├── feriados.py      # holiday → weekday-type resolution per company
│   ├── horarios.py      # query helpers for the landing page
│   ├── landing.py       # view context
│   └── bigquery_export.py  # flattens Horario (via ORM) into rows for the raw BigQuery table
├── views/          # main landing view
├── forms/
└── management/commands/  # lanchas_inicializar, lanchas_descargar_pdfs,
                            # lanchas_parsear_pdfs, lanchas_actualizar,
                            # lanchas_sincronizar_feriados, lanchas_validar,
                            # lanchas_listar, lanchas_cargar_bigquery

tests/                  # pytest suite, focused on services/parsers/
├── fixtures/            # synthetic PDFs (reportlab) + generator script
└── test_*.py

.github/workflows/
├── ci.yml               # push/PR to main: docker compose up + pytest + coverage
└── smoke-test.yml       # weekly cron: parses the live PDFs from the 3 companies

dbt_lanchas/             # star schema on top of lanchas_raw.horarios (see below)
airflow_dags/            # lanchas_dag.py: actualizar_pdfs -> cargar_bigquery -> dbt run/test
```

---

## Data pipeline

The app itself never talks to BigQuery. `lanchas_cargar_bigquery`,
`dbt_lanchas`, and `airflow_dags` are a **parallel, optional layer** for
dimensional modeling. They don't change what the visitor sees or how the
existing PDF → Postgres pipeline works.

**Why the source is Postgres, not the PDFs.** `pipeline/downloader.py` +
`pipeline/loader.py` + `services/parsers/` already normalize and validate
the schedule data into a real 3NF schema. Re-parsing the PDFs for the
analytics layer would mean maintaining two paths to the same truth;
instead, `lanchas_cargar_bigquery` reads `Horario` through the Django ORM
and flattens it.

**Why full-refresh, not incremental.** Unlike the sibling
[mareas](https://github.com/chipap-dev/mareas) repo (`dbt_mareas`, which
does `MERGE` because it cares about the historical time series), the
current schedule is the only thing that matters here - there's no
"yesterday's timetable" worth keeping. Every run replaces
`lanchas_raw.horarios` wholesale (`WRITE_TRUNCATE`).

**Grain: one row per (horario, vía), not per horario.** A `Horario` isn't
tied to a single stop - it belongs to a `Servicio` that runs through N
vías (`Servicio.tramos`), and can additionally pin a one-off destination
for branched services (`Horario.destino`). `bigquery_export.py` fans
each `Horario` out to every vía it's actually relevant to, mirroring the
same rule the app's own query layer already uses
(`services/horarios.py::_filtro_via` / `_acotar_a_destino`).

**Diagram:**
```
Government PDFs (3 companies)
       |
  downloader.py / loader.py / parsers/
       |
   Postgres (Empresa -> Linea -> Servicio -> Horario)
       |
       ├──> Django app (end user)
       |
       └──> lanchas_cargar_bigquery ──> BigQuery (lanchas_raw.horarios, full-refresh)
                   |
                dbt_lanchas
                   |
        staging (view) -> dim_empresa / dim_linea / dim_via / dim_tipo_dia -> fact_horario
```

![Successful run of the lanchas_dag DAG in Airflow: actualizar_pdfs, cargar_bigquery, dbt_run, and dbt_test all green](static/img/pipeline/airflow_dag_exitoso.png)

**A real run, in numbers.** The `dbt run` behind the screenshots below
(BigQuery job stats, not estimates) rebuilt the full star schema from the
current schedule: `dim_empresa` 3 rows, `dim_linea` 3 rows, `dim_tipo_dia`
8 rows (7 weekdays + `feriado`), `dim_via` 72 rows, and `fact_horario`
7.1k rows - a full-refresh `CREATE TABLE`, not an incremental append, so
that count is the entire current schedule fanned out by (horario, vía),
not a running total.

![dbt lineage graph: lanchas_raw.horarios into stg_lanchas_horarios, into dim_empresa/dim_linea/dim_tipo_dia/dim_via, into fact_horario](static/img/pipeline/dbt_lineage.png)

![dbt docs detail view of the fact_horario model: grain, columns, and tests](static/img/pipeline/dbt_database.png)

`airflow_dags/lanchas_dag.py` runs monthly: `actualizar_pdfs` (the
existing `lanchas_actualizar` command, retried up to twice since the
government PDF sites can be unstable) → `cargar_bigquery` → `dbt run` →
`dbt test`. See [dbt modeling](#dbt-modeling) and
[Orchestration with Airflow](#orchestration-with-airflow) below.

---

## dbt modeling

Four dimensions, one fact - built from `lanchas_raw.horarios`, the flat
table `lanchas_cargar_bigquery` uploads from Postgres:

- **Staging** (`stg_lanchas_horarios`, `view`): minimal formatting cleanup
  only (`trim`), no business logic - the source is already normalized on
  the Postgres side.
- **Dimensions** (`table`): `dim_empresa`, `dim_linea` (FK to
  `dim_empresa`), `dim_via`, `dim_tipo_dia`. Surrogate keys are generated
  with `row_number()` over distinct values, not `dbt_utils.generate_surrogate_key`
  - the project has no `packages.yml`, and installing `dbt_utils` would need
  `dbt deps` with network access during `dbt parse`/`dbt run` in CI (same
  call `dbt_mareas` makes, for the same reason).
- **Fact** (`fact_horario`, `table`): grain is **(horario, vía)**, not
  `horario` alone - see "Grain" above. No surrogate key of its own; the
  FKs + `hora` + `direccion` define the row.

Building these models meant checking the assumptions against the real
Django models first (`lanchas/models/horario.py`, `servicio.py`,
`linea.py`, `via.py`), and three didn't hold:

1. **No aggregated "day type" field exists.** `Horario.tipo_dia` stores
   `'lunes'`…`'domingo'` or `'feriado'` directly, and `'feriado'` only
   appears for the two companies with their own holiday column in the PDF
   (Jilguero, Delta Argentino) - Interisleña resolves holidays at query
   time by reassigning them to `'sabado'`/`'domingo'`
   (`services/feriados.resolver_tipo_dia`), without persisting a row of
   its own. `dim_tipo_dia` reflects the raw stored value, not a computed
   category.
2. **No separate "river" attribute exists.** `Via.nombre` is already the
   full place name (river, stream, or a specific stop like a port or
   dock). `dim_via` has one descriptive column, not two.
3. **`Linea` has no `nombre` field** (only `numero`) - the descriptive
   name lives one level down, on `Servicio.nombre` (e.g. "Troncal", "Ramal
   3"), together with `Servicio.tipo`. Rather than inventing a field
   `dim_linea` doesn't have, `servicio_nombre` and `servicio_tipo` stay as
   degenerate dimensions on `fact_horario` directly - too low-cardinality
   and too tied to the fact row to earn a fifth dimension table.

**Tests.** All 31 are generic (`not_null`, `unique`, `accepted_values`,
`relationships`) - there's no singular SQL test like `dbt_mareas`'s
freshness check, because full-refresh has no history to protect against
duplicating. `accepted_values` does the content-level guarding instead:
`dim_tipo_dia.tipo_dia` is locked to the 8 real values, and
`fact_horario.servicio_tipo` / `direccion` are locked to
`troncal/ramal/fraccionado/desdoblamiento` and `ida/vuelta`.

`dbt source freshness` on `lanchas_raw.horarios` uses generous thresholds
on purpose (`warn_after` 35 days, `error_after` 45 days) - the DAG runs
`@monthly`, so a threshold tuned for a daily job would false-alarm between
runs by design, not by bug.

See `dbt_lanchas/README.md` for the full setup (isolated `.venv`, since
`dbt-bigquery` doesn't share Django's environment) and command reference.

---

## Orchestration with Airflow

The Airflow engine doesn't live in this repo. It lives in a sibling repo,
`airflow_repo`, shared with [mareas](https://github.com/chipap-dev/mareas)
- the same reusable-engine design mareas' README describes ("Lanchas next,
after Mareas") is now real: both projects' DAGs run off the same image and
the same `scripts/sync_dags.sh`.

How the two repos connect:

- `airflow_repo` mounts this repo as a volume at `/opt/lanchas` inside the
  container (code and credentials only). The image already has Django,
  `dbt-bigquery`, and `google-cloud-bigquery` installed - no dependency on
  any venv created on the host.
- The DAG (`airflow_dags/lanchas_dag.py`) is versioned **here**, in
  `lanchas_repo`, not in `airflow_repo`. `airflow_repo/scripts/sync_dags.sh`
  puts it where the DAG processor looks for it (`airflow_repo/dags/`),
  preferring a symlink and falling back to a plain copy on environments
  without symlink privileges (common on Windows without dev-mode/admin
  rights) - re-run it after editing the DAG if the fallback path was used.
- The DAG orchestrates `actualizar_pdfs → cargar_bigquery → dbt_run →
  dbt_test`, runs `@monthly` with `catchup=False`, and connects to
  Lanchas' own app database in that environment
  (`lanchas-db`, a separate Postgres service from Airflow's own metadata
  DB and from chipap_net's production database) plus the same
  `GCP_PROJECT_ID` / `GCP_DATASET_RAW` / `GCP_LOCATION` /
  `GOOGLE_APPLICATION_CREDENTIALS` variables used by `dbt_lanchas`.

A real scheduled run of this DAG completed all four tasks successfully
(see the screenshot above) - `actualizar_pdfs` needed one retry before
the government PDF sites responded, exactly the scenario `retries=2` /
`retry_delay=10min` on that task exists for; `cargar_bigquery`,
`dbt_run`, and `dbt_test` each passed on the first attempt, with
`dbt_test` finishing 31/31 tests green (see [dbt modeling](#dbt-modeling)
above for what those tests check).

---

## Run locally (Docker)

```bash
git clone https://github.com/chipap-dev/lanchas.git
cd lanchas
cp .env.example .env
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). The first boot runs
migrations and loads `fixtures/lanchas_seed.json` - real schedule data
already parsed from the official PDFs, so there are no extra steps.

Django admin is available at `/admin/` (create a user first):

```bash
docker compose exec web python manage.py createsuperuser
```

To wipe the database and start over:

```bash
docker compose down -v
```

### Seeing the real pipeline run

The fixture ships with parsed data so the app works immediately, but the
full scrape-and-parse pipeline that produced it is in the repo too and can
be run against the live official PDFs:

```bash
docker compose exec web python manage.py lanchas_inicializar
docker compose exec web python manage.py lanchas_actualizar
```

This downloads the current PDFs from `minfra.gba.gob.ar`, parses them, and
upserts the schedule (idempotent - re-running only applies real diffs).

### Running the data layer (BigQuery + dbt)

Optional, and separate from the steps above - see
[Data pipeline](#data-pipeline) for why it's parallel to the app.

Environment variables (already defined in `.env.example` / `.env`):

```
GCP_PROJECT_ID=chipap
GCP_DATASET_RAW=lanchas_raw
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=secrets/gcp-key.json
```

`secrets/gcp-key.json` is a service account key with `BigQuery Data
Editor` + `BigQuery Job User` on the `chipap` project. It's git-ignored,
so it never ships with the repo: spin up your own GCP project (BigQuery's
free tier is enough) and point `GOOGLE_APPLICATION_CREDENTIALS` at your
own key.

```bash
docker compose exec web python manage.py lanchas_cargar_bigquery
```

`dbt-bigquery` lives in its own venv, isolated from the Django one (see
`dbt_lanchas/README.md` for the full rationale and setup):

```bash
cd dbt_lanchas
python -m venv .venv
source .venv/Scripts/activate   # Git Bash on Windows; .venv/bin/activate on Linux/Mac
pip install dbt-bigquery
cp profiles.yml.example profiles.yml   # edit the keyfile path if needed, never commit this file
dbt run
dbt test
dbt docs generate
```

`dbt parse` works without real credentials (useful for a quick syntax
check in CI).

The Airflow DAG (`airflow_dags/lanchas_dag.py`) isn't run from this repo.
See [Orchestration with Airflow](#orchestration-with-airflow) above for
where it actually runs and how the two repos connect.

---

## Testing

The most fragile part of this project is the PDF parser (color-based
direction detection, table-layout quirks per company), so that's what the
test suite focuses on: real synthetic PDFs (built with `reportlab`,
committed under `tests/fixtures/`) exercising a well-formed schedule for
each of the 3 companies, corrupt/unexpected-format PDFs (must raise
`ParserError`, never fail silently), and edge cases (missing data,
overlapping schedules, malformed hours).

Run the full suite locally with coverage on the parser module:

```bash
pip install -r requirements_lanchas_dev.txt
pytest -v -m "not smoke" --cov=lanchas.services.parsers --cov-report=term-missing
```

(`-m "not smoke"` skips `tests/test_smoke_real_sources.py`, which downloads
the real PDFs from `minfra.gba.gob.ar` - that one only runs on the weekly
cron, see below.)

**CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) builds and
boots the project with the existing `docker-compose.yml` and runs the same
`pytest` command on every push/PR to `main`; the job fails if any test
fails. A separate scheduled workflow
([`.github/workflows/smoke-test.yml`](.github/workflows/smoke-test.yml))
runs weekly, parses the live PDFs from the 3 companies, and fails if any of
them changed format in a way the parser can't handle.

---

Built by [Claudia Cáceres](https://chipap.net) · [LinkedIn](https://linkedin.com/in/claudiacaceresv) · Buenos Aires, Argentina
