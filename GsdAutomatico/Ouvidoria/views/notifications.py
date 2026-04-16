import json
import logging
from datetime import timedelta

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q

from ..models import PATD, Configuracao
from ..permissions import has_comandante_access
from Secao_pessoal.models import Efetivo
from .decorators import ouvidoria_required, comandante_required

logger = logging.getLogger(__name__)

@login_required
@require_GET
def patd_atribuicoes_pendentes_json(request):
    count = 0
    if hasattr(request.user, 'profile') and request.user.profile.militar:
        militar_logado = request.user.profile.militar

        count_aprovar = PATD.objects.filter(
            oficial_responsavel=militar_logado,
            status='aguardando_aprovacao_atribuicao'
        ).count()

        status_list_apuracao = ['em_apuracao', 'apuracao_preclusao', 'aguardando_punicao', 'aguardando_punicao_alterar']
        count_apuracao = PATD.objects.filter(
            oficial_responsavel=militar_logado,
            status__in=status_list_apuracao
        ).count()

        count = count_aprovar + count_apuracao

    return JsonResponse({'count': count})


@login_required
@ouvidoria_required
@require_GET
def patds_expirados_json(request):
    patds_expiradas = PATD.objects.filter(status='prazo_expirado').select_related('militar')
    data = [{'id': p.id, 'numero_patd': p.numero_patd, 'militar_nome': str(p.militar)} for p in patds_expiradas]
    return JsonResponse(data, safe=False)


@login_required
@ouvidoria_required
@require_POST
def extender_prazo_massa(request):
    try:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        dias_extensao = int(data.get('dias', 5))
        minutos_extensao = int(data.get('minutos', 0))
        if dias_extensao < 0 or minutos_extensao < 0:
            return JsonResponse({'status': 'error', 'message': 'Valores de extensão inválidos.'}, status=400)
        patds_expiradas = PATD.objects.filter(status='prazo_expirado')
        if not patds_expiradas.exists():
            return JsonResponse({'status': 'no_action', 'message': 'Nenhuma PATD com prazo expirado para atualizar.'})
        count = 0
        for patd in patds_expiradas:
            config = Configuracao.load()
            delta_dias = config.prazo_defesa_dias - dias_extensao
            delta_minutos = config.prazo_defesa_minutos - minutos_extensao
            patd.data_ciencia = timezone.now() - timedelta(days=delta_dias, minutes=delta_minutos)
            patd.status = 'aguardando_justificativa'
            patd.save()
            count += 1
        return JsonResponse({'status': 'success', 'message': f'{count} prazos foram estendidos com sucesso.'})
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Dados de entrada inválidos.'}, status=400)
    except Exception as e:
        logger.error(f"Erro ao estender prazos em massa: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@ouvidoria_required
@require_POST
def verificar_e_atualizar_prazos(request):
    try:
        prazos_atualizados = 0
        patds_pendentes = PATD.objects.filter(status='aguardando_justificativa')
        config = Configuracao.load()

        for patd in patds_pendentes:
            if patd.data_ciencia:
                dias_uteis_a_adicionar = config.prazo_defesa_dias
                data_final = patd.data_ciencia
                dias_adicionados = 0
                while dias_adicionados < dias_uteis_a_adicionar:
                    data_final += timedelta(days=1)
                    if data_final.weekday() < 5: # 0-4 são dias úteis
                        dias_adicionados += 1

                deadline = (data_final + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

                if timezone.now() > deadline:
                    patd.status = 'prazo_expirado'
                    patd.save(update_fields=['status'])
                    prazos_atualizados += 1

        patds_em_reconsideracao = PATD.objects.filter(status='periodo_reconsideracao')
        reconsideracoes_finalizadas = 0
        for patd in patds_em_reconsideracao:
            if patd.data_publicacao_punicao:
                deadline = patd.data_publicacao_punicao + timedelta(days=15)
                if timezone.now() > deadline:
                    patd.status = 'aguardando_publicacao'
                    patd.save(update_fields=['status'])
                    reconsideracoes_finalizadas += 1

        total_updated = prazos_atualizados + reconsideracoes_finalizadas
        return JsonResponse({'status': 'success', 'updated_count': total_updated})

    except Exception as e:
        logger.error(f"Erro ao verificar e atualizar prazos: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@require_GET
def search_militares_json(request):
    """Retorna uma lista de militares para a pesquisa no modal."""
    query = request.GET.get('q', '')
    militares = Efetivo.objects.all()

    if query:
        militares = militares.filter(
            Q(nome_completo__icontains=query) |
            Q(nome_guerra__icontains=query) |
            Q(posto__icontains=query)
        )

    militares = militares.order_by('posto', 'nome_guerra')[:50]
    data = list(militares.values('id', 'posto', 'nome_guerra', 'nome_completo'))
    return JsonResponse(data, safe=False)


@login_required
@require_GET
def comandante_pendencias_json(request):
    if not has_comandante_access(request.user):
        return JsonResponse({'count': 0})

    count = PATD.objects.filter(status='analise_comandante').count()
    return JsonResponse({'count': count})
