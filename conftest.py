import os

# config.settings.lanchas_standalone reads DATABASE_URL eagerly at import
# time. Los tests del parser no tocan la base de datos, pero Django igual
# necesita poder importar settings - se define un default de sqlite en
# memoria acá, antes de que pytest-django dispare django.setup(), para no
# obligar a levantar Postgres solo para correr `pytest`.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
