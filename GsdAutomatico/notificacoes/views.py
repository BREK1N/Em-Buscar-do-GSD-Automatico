from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .models import Notificacao

MAX_LIST = 20


@login_required
@require_GET
def api_notificacoes(request):
    qs = Notificacao.objects.filter(usuario=request.user, lida=False)
    total = qs.count()
    items = []
    for n in qs[:MAX_LIST]:
        items.append({
            'id':          n.pk,
            'tipo':        n.tipo,
            'titulo':      n.titulo,
            'corpo':       n.corpo[:120] if n.corpo else '',
            'url':         n.url,
            'criado_em':   n.criado_em.strftime('%d/%m %H:%M'),
            'origem_id':   n.origem_id,
            'origem_tipo': n.origem_tipo,
        })
    return JsonResponse({'count': total, 'notifications': items})


@login_required
@require_POST
def api_limpar(request):
    notif_id = request.POST.get('id', '').strip()
    if notif_id:
        Notificacao.objects.filter(pk=notif_id, usuario=request.user).update(lida=True)
    else:
        Notificacao.objects.filter(usuario=request.user, lida=False).update(lida=True)
    return JsonResponse({'ok': True})
