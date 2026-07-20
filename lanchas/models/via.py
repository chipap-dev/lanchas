from django.db import models


class Via(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    descripcion = models.CharField(max_length=250, blank=True)

    class Meta:
        verbose_name = "vía"
        verbose_name_plural = "vías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
