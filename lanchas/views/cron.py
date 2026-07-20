import hmac
import io

from django.conf import settings
from django.core.management import call_command
from django.http import HttpResponse, HttpResponseForbidden


def cron_actualizar(request):
    secreto = settings.CRON_SECRET_LANCHAS
    token = request.GET.get("token", "")
    if not secreto or not hmac.compare_digest(token, secreto):
        return HttpResponseForbidden("Token inválido.")

    salida = io.StringIO()
    try:
        call_command("lanchas_actualizar", stdout=salida, stderr=salida)
    except Exception as exc:
        salida.write(f"\nERROR: {exc}")
        return HttpResponse(salida.getvalue(), content_type="text/plain; charset=utf-8", status=500)

    return HttpResponse(salida.getvalue(), content_type="text/plain; charset=utf-8")
