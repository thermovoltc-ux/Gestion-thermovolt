from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .models import Notificacion


@login_required
@never_cache
def lista_notificaciones(request):
    tipo = request.GET.get('tipo', '').strip()
    tipos_validos = {valor for valor, _ in Notificacion.TIPO_CHOICES}
    if tipo and tipo not in tipos_validos:
        return HttpResponseBadRequest('El tipo de notificación no es válido.')

    notificaciones = Notificacion.objects.filter(usuario=request.user)
    if tipo:
        notificaciones = notificaciones.filter(tipo=tipo)
    return render(request, 'notificaciones/lista.html', {
        'notificaciones': notificaciones,
        'tipos': Notificacion.TIPO_CHOICES,
        'tipo_seleccionado': tipo,
        'no_leidas': Notificacion.objects.filter(
            usuario=request.user,
            leida=False,
        ).count(),
        'webpush_enabled': all(
            settings.WEBPUSH_SETTINGS.get(key)
            for key in (
                'VAPID_PUBLIC_KEY',
                'VAPID_PRIVATE_KEY',
                'VAPID_ADMIN_EMAIL',
            )
        ),
    })


@login_required
@require_POST
def marcar_todas_leidas(request):
    Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
    ).update(leida=True)
    return redirect('notificaciones:lista')


@login_required
@require_GET
@never_cache
def contador_no_leidas(request):
    total = Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
    ).count()
    response = JsonResponse({'count': total})
    response['Cache-Control'] = 'no-store'
    return response
