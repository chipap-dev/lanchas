#!/bin/sh
set -e

python manage_lanchas.py migrate --noinput

HAS_DATA=$(python manage_lanchas.py shell -c "from lanchas.models import Empresa; print(Empresa.objects.exists())")
if [ "$HAS_DATA" != "True" ]; then
    echo "Base vacia, cargando fixtures/lanchas_seed.json..."
    python manage_lanchas.py loaddata fixtures/lanchas_seed.json
else
    echo "Ya hay datos cargados, salteo el seed."
fi

if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage_lanchas.py createsuperuser --noinput --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" || true
fi

python manage_lanchas.py runserver 0.0.0.0:8000
