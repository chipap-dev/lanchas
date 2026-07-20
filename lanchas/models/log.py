from django.db import models


class ActualizacionLog(models.Model):
    linea = models.ForeignKey(
        "lanchas.Linea",
        on_delete=models.CASCADE,
        related_name="actualizaciones",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    pdf_hash = models.CharField(max_length=64, blank=True)
    pdf_modificado = models.BooleanField(default=False)
    exito = models.BooleanField(default=True)
    horarios_agregados = models.IntegerField(default=0)
    horarios_eliminados = models.IntegerField(default=0)
    errores = models.JSONField(default=list)
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "log de actualización"
        verbose_name_plural = "logs de actualización"

    def __str__(self):
        estado = "OK" if self.exito else "ERROR"
        return f"{self.linea} · {self.fecha:%Y-%m-%d %H:%M} · {estado}"
