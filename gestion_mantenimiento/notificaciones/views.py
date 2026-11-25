from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .utils import destino_seguro_para_usuario
from .models import Notificacion


@login_required
@never_cache
def lista_notificaciones(request):
    tipo = request.GET.get('tipo', '').strip()
    tipos_validos = {valor for valor, _ in Notificacion.TIPO_CHOICES}
    if tipo and tipo not in tipos_validos:
        return HttpResponseBadRequest('El tipo de notificación no es válido.')

    Notificacion.objects.filter(
        usuario=request.user,
        leida=False,
    ).update(leida=True)

    notificaciones = Notificacion.objects.filter(usuario=request.user)
    if tipo:
        notificaciones = notificaciones.filter(tipo=tipo)
    return render(request, 'notificaciones/lista.html', {
        'notificaciones': notificaciones,
        'tipos': Notificacion.TIPO_CHOICES,
        'tipo_seleccionado': tipo,
        'no_leidas': 0,
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
def eliminar_y_redirigir(request, notificacion_id):
    notificacion = get_object_or_404(
        Notificacion,
        pk=notificacion_id,
        usuario=request.user,
    )
    destino = destino_seguro_para_usuario(request.user, notificacion.url_destino)
    notificacion.delete()

    if not url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        destino = ''
    return redirect(destino or 'notificaciones:lista')


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
