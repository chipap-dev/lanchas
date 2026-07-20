from django.db import models

_EMPRESA_COLORES = {
    "interislena":     "#B4472C",
    "jilguero":        "#CB8A4C",
    "delta-argentino": "#7C8B44",
}


class Empresa(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    razon_social = models.CharField(max_length=150, blank=True)

    @property
    def color(self):
        return _EMPRESA_COLORES.get(self.slug, "#8A5A2E")

    class Meta:
        verbose_name_plural = "empresas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
