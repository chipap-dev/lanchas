from django.db import models

TIPO_DIA_CHOICES = [
    ("lunes", "Lunes"),
    ("martes", "Martes"),
    ("miercoles", "Miércoles"),
    ("jueves", "Jueves"),
    ("viernes", "Viernes"),
    ("sabado", "Sábado"),
    ("domingo", "Domingo"),
    # Solo para líneas con columna propia de feriados (Jilguero 450, Delta 453).
    # Interisleña resuelve feriados en la capa de servicio, mapeando a días existentes.
    ("feriado", "Feriado"),
]

DIRECCION_CHOICES = [
    ("ida", "Ida (desde Tigre)"),
    ("vuelta", "Vuelta (hacia Tigre)"),
]


class Horario(models.Model):
    """
    Horario de salida o llegada a Tigre para un servicio en un tipo de día.

    Solo se registra la hora de salida desde Tigre (ida) o de llegada a Tigre
    (vuelta). No hay horarios intermedios por parada - eso no aparece en los PDFs.

    Para consultas con feriados, usar services.feriados.resolver_tipo_dia()
    antes de filtrar por tipo_dia: esa función aplica la lógica por empresa.
    """

    servicio = models.ForeignKey(
        "lanchas.Servicio",
        on_delete=models.CASCADE,
        related_name="horarios",
    )
    direccion = models.CharField(max_length=6, choices=DIRECCION_CHOICES)
    tipo_dia = models.CharField(max_length=10, choices=TIPO_DIA_CHOICES)
    hora = models.TimeField()
    condicion = models.CharField(
        max_length=300,
        blank=True,
        help_text='Nota de los PDFs, ej: "los martes y jueves no ingresa a Arroyo Grande"',
    )
    destino = models.ForeignKey(
        "lanchas.Via",
        on_delete=models.PROTECT,
        related_name="horarios_destino",
        null=True,
        blank=True,
        help_text="Extremo lejano de Tigre de esta fila puntual: lugar de "
                   "llegada si es ida, lugar de salida si es vuelta. Permite "
                   "ubicar horarios por un lugar que no es tramo de recorrido "
                   "(ej. un muelle final), y es imprescindible cuando el "
                   "servicio se bifurca en más de un destino dentro del mismo "
                   "IDA o VUELTA (ej: Fraccionado 1 -> Sala 1º Auxilios / Escuela 13).",
    )

    class Meta:
        verbose_name_plural = "horarios"
        ordering = ["tipo_dia", "direccion", "hora"]
        indexes = [
            models.Index(fields=["tipo_dia", "hora"]),
            models.Index(fields=["servicio", "tipo_dia", "direccion"]),
        ]

    def __str__(self):
        cond = f" [{self.condicion}]" if self.condicion else ""
        return (
            f"{self.servicio} · {self.get_tipo_dia_display()} · "
            f"{self.get_direccion_display()} · {self.hora:%H:%M}{cond}"
        )
