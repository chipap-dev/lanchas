from django.shortcuts import render

from lanchas.services import get_lanchas_context


def lanchas_view(request):
    via_slug = request.GET.get("via")
    vista = request.GET.get("vista", "hoy")
    empresa_slug = request.GET.get("empresa")
    contexto = get_lanchas_context(via_slug, vista, empresa_slug)
    # Puramente de UI (filtra el recorrido del sidebar en JS): se reinyecta
    # en los links de resultado al tipear, para que un click en un resultado
    # filtrado no pierda el filtro al recargar la página.
    contexto["busqueda"] = request.GET.get("buscar", "")
    return render(request, "lanchas/index.html", contexto)
