from django.db import models


class Feriado(models.Model):
    fecha = models.DateField(unique=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        ordering = ["fecha"]
        verbose_name_plural = "feriados"

    def __str__(self):
        return f"{self.fecha} - {self.nombre}"
