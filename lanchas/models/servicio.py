from django.db import models

TIPO_SERVICIO_CHOICES = [
    ("troncal", "Troncal"),
    ("ramal", "Ramal"),
    ("fraccionado", "Fraccionado"),
    ("desdoblamiento", "Desdoblamiento"),
]


class Servicio(models.Model):
    linea = models.ForeignKey(
        "lanchas.Linea",
        on_delete=models.CASCADE,
        related_name="servicios",
    )
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=15, choices=TIPO_SERVICIO_CHOICES)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)
    vias = models.ManyToManyField(
        "lanchas.Via",
        through="lanchas.RecorridoTramo",
        related_name="servicios",
    )

    class Meta:
        verbose_name_plural = "servicios"
        ordering = ["linea", "orden", "nombre"]

    def __str__(self):
        return f"{self.linea} - {self.nombre}"


class RecorridoTramo(models.Model):
    """Secuencia ordenada de vías (ríos/arroyos) que recorre un servicio."""

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="tramos",
    )
    via = models.ForeignKey(
        "lanchas.Via",
        on_delete=models.CASCADE,
        related_name="tramos",
    )
    orden = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ("servicio", "orden")
        ordering = ["servicio", "orden"]
        verbose_name = "tramo de recorrido"
        verbose_name_plural = "tramos de recorrido"
        indexes = [
            models.Index(fields=["via", "servicio"]),
        ]

    def __str__(self):
        return f"{self.servicio} - tramo {self.orden}: {self.via}"
