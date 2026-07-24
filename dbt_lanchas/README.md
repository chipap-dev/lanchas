# dbt_lanchas

Proyecto dbt para el modelo dimensional (star schema) de Lanchas en
BigQuery (`lanchas_raw.horarios` → staging → dimensiones + fact).
Independiente del venv de la app Django.

La fuente de `lanchas_raw.horarios` es **Postgres**, no los PDFs: el
management command `lanchas_cargar_bigquery` lee `Horario` vía el ORM
de Django (el pipeline existente ya normalizó y validó esos datos) y
sube el dataset completo con `WRITE_TRUNCATE` - a diferencia de Mareas
(`dbt_mareas`, que hace `MERGE` porque le interesa el histórico), acá no
hay versiones anteriores que conservar: el horario vigente es lo único
relevante.

## Setup (venv aislado)

`dbt-bigquery` **no** se instala en el Python global del sistema ni en
el venv de Django. Vive en un venv propio, exclusivo de esta carpeta:

**Git Bash / Linux / Mac:**
```bash
cd dbt_lanchas
python -m venv .venv
source .venv/Scripts/activate   # Git Bash en Windows
# source .venv/bin/activate     # Linux / Mac
pip install dbt-bigquery
```

**Windows (CMD / PowerShell):**
```bat
cd dbt_lanchas
python -m venv .venv
.venv\Scripts\activate
pip install dbt-bigquery
```

`dbt_lanchas/.venv/` está en `.gitignore` (regla `.venv/` ya existente en
el `.gitignore` del repo).

## Credenciales

```bash
cp profiles.yml.example profiles.yml
```

`profiles.yml` ya viene con los valores reales de infra (`project:
chipap`, `dataset: lanchas_raw`, `location: us-central1`, `keyfile:
../secrets/gcp-key.json`) - no hace falta editarlo salvo que cambie la
ubicación de la key. Nunca se commitea (`dbt_lanchas/profiles.yml` está
en `.gitignore`).

## Comandos

Con el venv activado, parado en `dbt_lanchas/`:

```bash
dbt parse             # chequeo de sintaxis, no requiere credenciales validas
dbt compile           # compila el SQL final
dbt run               # materializa staging (views) + dimensiones/fact (tables)
dbt test              # not_null / unique / relationships / accepted_values
dbt source freshness  # freshness de carga sobre lanchas_raw.horarios
dbt docs generate
```

## Modelos

```
models/
├── staging/
│   ├── sources.yml            # declara lanchas_raw.horarios como source, con freshness
│   └── stg_lanchas_horarios.sql  # limpieza minima de formato (trim)
└── marts/
    ├── dim_empresa.sql        # Interisleña, Jilguero, Delta Argentino
    ├── dim_linea.sql          # numero de linea + FK a empresa
    ├── dim_via.sql            # rios/arroyos/destinos puntuales (Via.nombre)
    ├── dim_tipo_dia.sql       # lunes...domingo + feriado (Horario.tipo_dia tal cual)
    ├── fact_horario.sql       # 1 fila por (horario, via)
    └── schema.yml             # tests: not_null / unique / relationships / accepted_values
```

### Decisiones que se apartan del diseño original pedido

Inspeccionando `lanchas/models/` (ver `lanchas/models/horario.py`,
`servicio.py`, `linea.py`, `via.py`) antes de escribir estos modelos,
aparecieron 3 cosas que no coinciden con los supuestos iniciales:

1. **No existe un campo "tipo de día" agregado** (hábil/sábado/domingo/
   feriado). `Horario.tipo_dia` guarda directamente 'lunes'…'domingo' o
   'feriado' (`TIPO_DIA_CHOICES`), y 'feriado' solo se usa en las
   líneas que tienen columna propia en el PDF (Jilguero 450, Delta
   Argentino 453) - Interisleña resuelve sus feriados en tiempo de
   consulta reasignándolos a 'sabado'/'domingo'
   (`services/feriados.resolver_tipo_dia`), sin persistir una fila
   propia. `dim_tipo_dia` refleja el dato crudo tal cual está en la
   base, no una interpretación calculada.

2. **No existe un atributo "río" separado del nombre de la vía.**
   `Via.nombre` ya es el nombre completo del lugar (río, arroyo, o un
   destino puntual como un puerto o muelle - ver
   `lanchas/services/landing.py::_vias_de_empresa`). `dim_via` tiene
   una sola columna descriptiva (`via_nombre`), no dos.

3. **`Linea` no tiene un campo `nombre`** (solo `numero`) - el nombre
   descriptivo real vive un nivel más abajo, en `Servicio.nombre` (ej.
   "Troncal", "Ramal 3"), junto con `Servicio.tipo`. En vez de inventar
   un campo inexistente en `dim_linea`, `servicio_nombre` y
   `servicio_tipo` quedan como atributos degenerados en `fact_horario`
   (no ameritan una quinta dimensión: son de baja cardinalidad por
   línea y muy correlacionados con la fila del hecho).

Además, el grano de `fact_horario` es **(horario, vía)**, no
`(horario)` a secas: un `Horario` no pertenece a una sola vía, sino a
un `Servicio` que recorre N vías (`Servicio.tramos`), y puede además
fijar un destino puntual propio (`Horario.destino`) para servicios
bifurcados. `lanchas/services/bigquery_export.py::_vias_del_horario`
resuelve esto exactamente igual que la lógica ya existente en
`lanchas/services/horarios.py` (`_filtro_via` / `_acotar_a_destino`):
un horario es relevante para cada vía que sea tramo de su servicio, más
su destino puntual si no es ya uno de esos tramos.

Los surrogate keys se generan con `row_number()` sobre valores
distintos (no `dbt_utils.generate_surrogate_key`): el proyecto no tiene
`packages.yml` ni `dbt_utils` instalado, y agregarlo requeriría `dbt
deps` con acceso de red durante `dbt parse`/`dbt run` en CI - se prefirió
no sumar esa dependencia externa para un star schema de este tamaño
(mismo criterio que `dbt_mareas`, que tampoco usa `dbt_utils`).
