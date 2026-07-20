from django.contrib import admin

from lanchas.models import (
    Empresa,
    Linea,
    Via,
    Servicio,
    RecorridoTramo,
    Horario,
    Feriado,
    ActualizacionLog,
)


class RecorridoTramoInline(admin.TabularInline):
    model = RecorridoTramo
    extra = 0
    ordering = ["orden"]


class HorarioInline(admin.TabularInline):
    model = Horario
    extra = 0
    ordering = ["tipo_dia", "direccion", "hora"]
    fields = ["direccion", "tipo_dia", "hora", "condicion"]


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "slug", "razon_social"]
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(Linea)
class LineaAdmin(admin.ModelAdmin):
    list_display = ["numero", "empresa", "activa", "pdf_filename"]
    list_filter = ["empresa", "activa"]


@admin.register(Via)
class ViaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "slug"]
    prepopulated_fields = {"slug": ("nombre",)}
    search_fields = ["nombre"]


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "linea", "tipo", "orden", "activo"]
    list_filter = ["linea__empresa", "tipo", "activo"]
    search_fields = ["nombre"]
    inlines = [RecorridoTramoInline, HorarioInline]
    ordering = ["linea", "orden"]


@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ["fecha", "nombre"]
    ordering = ["fecha"]


@admin.register(ActualizacionLog)
class ActualizacionLogAdmin(admin.ModelAdmin):
    list_display = [
        "linea", "fecha", "exito", "pdf_modificado",
        "horarios_agregados", "horarios_eliminados",
    ]
    list_filter = ["linea", "exito"]
    readonly_fields = ["fecha", "pdf_hash", "pdf_modificado", "errores"]
    ordering = ["-fecha"]
