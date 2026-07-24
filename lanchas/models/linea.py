from django.db import models


class Linea(models.Model):
    empresa = models.ForeignKey(
        "lanchas.Empresa",
        on_delete=models.CASCADE,
        related_name="lineas",
    )
    numero = models.CharField(max_length=10)
    pdf_url = models.URLField()
    pdf_filename = models.CharField(max_length=100)
    # Interisleña publica sus servicios en dos PDF (líneas 451 y 452) que en
    # esta app se tratan como una sola Línea/empresa combinada - estos dos
    # campos opcionales permiten un segundo archivo fuente. Si están vacíos,
    # la línea tiene un solo PDF (caso normal).
    pdf_url_2 = models.URLField(blank=True)
    pdf_filename_2 = models.CharField(max_length=100, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "línea"
        verbose_name_plural = "líneas"
        unique_together = ("empresa", "numero")
        ordering = ["numero"]

    def __str__(self):
        return f"Línea {self.numero} ({self.empresa.nombre})"
