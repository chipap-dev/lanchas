from django.urls import path

from lanchas.views.cron import cron_actualizar
from lanchas.views.index import lanchas_view

app_name = "lanchas"

urlpatterns = [
    path("", lanchas_view, name="index"),
    path("cron/actualizar/", cron_actualizar, name="cron_actualizar"),
]
