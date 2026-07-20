# Lanchas — Horarios del Delta del Tigre

[![CI](https://github.com/chipap-dev/lanchas/actions/workflows/ci.yml/badge.svg)](https://github.com/chipap-dev/lanchas/actions/workflows/ci.yml)

A Django app that scrapes and parses the official PDF schedules of the three
passenger-boat companies operating in the Tigre Delta (Argentina) and serves
them as a searchable, mobile-friendly timetable.

**Dockerized. Comes with real, pre-loaded data. `docker compose up` and go.**

---

## What it does

- Downloads and parses the official government PDF schedules of 3 lines
  (Interisleña 451/452, Jilguero 450, Delta Argentino 453) with `pdfplumber`
  — table extraction, color-coded direction detection, footnote-condition
  matching, not plain-text scraping
- Normalizes everything into a relational model: companies → lines →
  services → stops (rivers/streams) → timetable rows
- Resolves holiday schedules against Argentina's official calendar
  (`holidays` package)
- "Today" view, weekly schedule per direction, and a sidebar with every
  line's route as a native (JS-free) accordion
- Local (device-only) favorites via `localStorage`, no accounts

---

## Run locally (Docker)

```bash
git clone https://github.com/chipap-dev/lanchas.git
cd lanchas
cp .env.example .env
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). The first boot runs
migrations and loads `fixtures/lanchas_seed.json` — real schedule data
already parsed from the official PDFs, so there are no extra steps.

Django admin is available at `/admin/` (create a user first):

```bash
docker compose exec web python manage_lanchas.py createsuperuser
```

To wipe the database and start over:

```bash
docker compose down -v
```

---

## Seeing the real pipeline run

The fixture ships with parsed data so the app works immediately, but the
full scrape-and-parse pipeline that produced it is in the repo too and can
be run against the live official PDFs:

```bash
docker compose exec web python manage_lanchas.py lanchas_inicializar
docker compose exec web python manage_lanchas.py lanchas_actualizar
```

This downloads the current PDFs from `minfra.gba.gob.ar`, parses them, and
upserts the schedule (idempotent — re-running only applies real diffs).

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

## Architecture

Real ORM, real migrations, real Postgres — unlike the sibling
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
│   └── landing.py       # view context
├── views/          # main landing view
├── forms/
└── management/commands/  # lanchas_inicializar, lanchas_descargar_pdfs,
                            # lanchas_parsear_pdfs, lanchas_actualizar,
                            # lanchas_sincronizar_feriados, lanchas_validar

tests/                  # pytest suite, focused on services/parsers/
├── fixtures/            # synthetic PDFs (reportlab) + generator script
└── test_*.py

.github/workflows/
├── ci.yml               # push/PR to main: docker compose up + pytest + coverage
└── smoke-test.yml       # weekly cron: parses the live PDFs from the 3 companies
```

---

## Stack

Python 3.11 · Django 4.2 · PostgreSQL 16 · pdfplumber · holidays · Docker ·
Whitenoise · Vanilla JS · CSS custom properties · pytest + GitHub Actions

---

Built by [Claudia Cáceres](https://chipap.net) · [LinkedIn](https://linkedin.com/in/claudiacaceresv) · Buenos Aires, Argentina
