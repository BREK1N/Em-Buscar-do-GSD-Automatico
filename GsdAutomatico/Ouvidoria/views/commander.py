import json
import logging
import os
from datetime import timedelta

from django.conf import settings

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.core.files import File
from django.db import transaction
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth

from ..models import PATD, Configuracao, Anexo
from ..forms import ComandanteAprovarForm
from .decorators import (
    comandante_redirect, ouvidoria_required, comandante_required,
    oficial_responsavel_required, ComandanteAccessMixin,
)
from .helpers import _sync_oficial_signature, get_document_pages

logger = logging.getLogger(__name__)

def _check_and_advance_reconsideracao_status(patd_pk):
    """
    Função centralizada que verifica, dentro de uma transação para garantir a consistência dos dados,
    se a reconsideração tem conteúdo e assinatura. Se ambas as condições forem verdadeiras,
    o status é avançado.
    """
    try:
        with transaction.atomic():
            # Bloqueia a linha da PATD para evitar condições de corrida
            patd = PATD.objects.select_for_update().get(pk=patd_pk)

            # --- CORREÇÃO: Forçar a releitura do objeto do banco de dados ---
            # Garante que estamos a verificar o estado mais recente, incluindo
            # a atualização da assinatura que acabou de ser salva.
            patd.refresh_from_db()

            # Detailed logging for debugging
            logger.info(f"PATD {patd.pk} (Reconsideration Check):")
            logger.info(f"  - Current status: {patd.status}")
            logger.info(f"  - Has texto_reconsideracao: {bool(patd.texto_reconsideracao)}")
            logger.info(f"  - Anexos (tipo='reconsideracao') count: {patd.anexos.filter(tipo='reconsideracao').count()}")
            logger.info(f"  - Has assinatura_reconsideracao: {bool(patd.assinatura_reconsideracao)}")

            has_content = bool(patd.texto_reconsideracao or patd.anexos.filter(tipo='reconsideracao').exists())
            
            # Primeiro, tenta verificar pelo campo do modelo (que deveria estar atualizado)
            has_signature_db_field = bool(patd.assinatura_reconsideracao)
            logger.info(f"  - Has assinatura_reconsideracao (DB field): {has_signature_db_field}")

            # Se o campo do DB ainda for False, verifica diretamente no sistema de ficheiros como fallback
            has_signature_filesystem = False
            if not has_signature_db_field and patd.assinatura_reconsideracao and patd.assinatura_reconsideracao.name:
                try:
                    # Constrói o caminho absoluto esperado para o ficheiro da assinatura
                    expected_file_path = os.path.join(settings.MEDIA_ROOT, patd.assinatura_reconsideracao.name)
                    has_signature_filesystem = os.path.exists(expected_file_path)
                    logger.info(f"  - Has assinatura_reconsideracao (Filesystem check at {expected_file_path}): {has_signature_filesystem}")
                except Exception as e:
                    logger.warning(f"Erro ao verificar o sistema de ficheiros para a assinatura da PATD {patd.pk} no caminho '{patd.assinatura_reconsideracao.name}': {e}")

            # A assinatura é considerada válida se estiver no DB OU no sistema de ficheiros
            final_has_signature = has_signature_db_field or has_signature_filesystem

            if patd.status == 'em_reconsideracao' and has_content and final_has_signature:
                patd.status = 'aguardando_comandante_base'
                patd.save(update_fields=['status'])
                logger.info(f"PATD {patd.pk} status advanced to 'aguardando_comandante_base'.")
            else:
                logger.info(f"PATD {patd.pk}: Conditions not met to advance status (still 'em_reconsideracao').")
    except PATD.DoesNotExist:
        logger.error(f"PATD {patd_pk} not found during status check.")
    except Exception as e:
        logger.error(f"Error in _check_and_advance_reconsideracao_status for PATD {patd_pk}: {e}")


def _check_and_finalize_patd(patd):
 
    if patd.status != 'aguardando_assinatura_npd':
        return False

    document_pages = get_document_pages(patd)
    raw_document_text = "".join(document_pages)

    required_mil_signatures = raw_document_text.count('{Assinatura Militar Arrolado}')
    provided_mil_signatures = sum(1 for s in (patd.assinaturas_militar or []) if s)
    if provided_mil_signatures < required_mil_signatures:
        return False

    if not patd.testemunha1 or not patd.assinatura_testemunha1:
        return False

    if not patd.testemunha2 or not patd.assinatura_testemunha2:
        return False

    patd.status = 'periodo_reconsideracao'
    patd.data_publicacao_punicao = timezone.now()
    patd.save()
    return True


@method_decorator([login_required, comandante_required], name='dispatch')
class ComandanteDashboardView(ListView):
    model = PATD
    template_name = 'comandante_dashboard.html'
    context_object_name = 'patds'

    def get_queryset(self):
        # Este queryset é para a lista principal de PATDs "Aguardando Decisão"
        return PATD.objects.filter(status='analise_comandante').select_related('militar').order_by('-data_inicio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)

        # Métricas de contagem simples
        context['patd_em_andamento'] = PATD.objects.exclude(Q(status='finalizado') | Q(justificado=True)).count()
        context['patd_finalizadas_total'] = PATD.objects.filter(status='finalizado').count()
        context['patd_justificadas_total'] = PATD.objects.filter(justificado=True).count()
        
        # Criadas na semana/mês
        context['patd_criadas_semana'] = PATD.objects.filter(data_inicio__date__gte=start_of_week).count()
        context['patd_criadas_mes'] = PATD.objects.filter(data_inicio__date__gte=start_of_month).count()

        # Finalizadas na semana/mês
        context['patd_finalizadas_semana'] = PATD.objects.filter(status='finalizado', data_termino__date__gte=start_of_week).count()
        context['patd_finalizadas_mes'] = PATD.objects.filter(status='finalizado', data_termino__date__gte=start_of_month).count()

        # Dados para gráficos
        # Garante que todos os meses nos últimos 12 tenham um valor
        labels = []
        criadas_counts = []
        finalizadas_counts = []
        
        criadas_por_mes_dict = {
            item['month'].strftime('%Y-%m'): item['count']
            for item in PATD.objects
            .annotate(month=TruncMonth('data_inicio'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        }
        
        finalizadas_por_mes_dict = {
            item['month'].strftime('%Y-%m'): item['count']
            for item in PATD.objects
            .filter(status='finalizado')
            .annotate(month=TruncMonth('data_termino'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        }

        for i in range(11, -1, -1):
            current_month = today - timedelta(days=i*30)
            month_key = current_month.strftime('%Y-%m')
            labels.append(current_month.strftime('%b/%y'))
            
            criadas_counts.append(criadas_por_mes_dict.get(month_key, 0))
            finalizadas_counts.append(finalizadas_por_mes_dict.get(month_key, 0))

        context['chart_labels'] = json.dumps(labels)
        context['chart_data_criadas'] = json.dumps(criadas_counts)
        context['chart_data_finalizadas'] = json.dumps(finalizadas_counts)
        
        return context


@login_required
@comandante_required
@require_POST # Garante que só aceita POST
def patd_aprovar(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    form = ComandanteAprovarForm(request.POST)

    # Verifica se as testemunhas estão definidas (lógica existente)
    errors = []
    if not patd.testemunha1 or not patd.testemunha2:
        errors.append("É necessário definir as duas testemunhas no processo.")

    if errors:
        error_message = f"PATD Nº {patd.numero_patd}: Não foi possível aprovar. " + " ".join(errors)
        messages.error(request, error_message)
        return redirect(request.META.get('HTTP_REFERER', 'Ouvidoria:comandante_dashboard'))

    # Verifica o formulário e a senha
    if form.is_valid():
        senha = form.cleaned_data['senha_comandante']
        # Autentica o usuário logado (que deve ser o comandante) com a senha fornecida
        user = authenticate(username=request.user.username, password=senha)

        if user is not None:
            # Senha correta, prossegue com a aprovação
            patd.status = 'aguardando_assinatura_npd'
            patd.save()
            messages.success(request, f"PATD Nº {patd.numero_patd} aprovada com sucesso. Aguardando assinatura da NPD.")
            return redirect('Ouvidoria:comandante_dashboard')
        else:
            # Senha incorreta
            messages.error(request, "Senha do Comandante incorreta. Aprovação não realizada.")
    else:
        # Formulário inválido (deve ter faltado a senha)
        messages.error(request, "Erro no formulário. A senha é obrigatória.")

    # Redireciona de volta em caso de erro de senha ou formulário
    return redirect(request.META.get('HTTP_REFERER', 'Ouvidoria:comandante_dashboard'))


@login_required
@comandante_required
@require_POST
def patd_retornar(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    comentario = request.POST.get('comentario')

    if not comentario:
        messages.error(request, "O comentário é obrigatório para retornar a PATD.")
        return redirect(request.META.get('HTTP_REFERER', 'Ouvidoria:comandante_dashboard'))

    patd.status = 'aguardando_punicao_alterar'
    patd.comentario_comandante = comentario
    patd.save()
    messages.warning(request, f"PATD Nº {patd.numero_patd} retornada para alteração com observações.")
    # Não precisa de senha aqui
    return redirect(request.META.get('HTTP_REFERER', 'Ouvidoria:comandante_dashboard'))


@login_required
@oficial_responsavel_required
@require_POST
def avancar_para_comandante(request, pk):
    patd = get_object_or_404(PATD, pk=pk)

    if not patd.testemunha1 or not patd.testemunha2:
        detail_url = reverse('Ouvidoria:patd_detail', kwargs={'pk': pk})
        return redirect(f'{detail_url}?erro=testemunhas')

    patd.status = 'analise_comandante'
    patd.save()
    messages.success(request, f"PATD Nº {patd.numero_patd} enviada para análise do Comandante.")
    return redirect('Ouvidoria:patd_detail', pk=pk)


@login_required
@ouvidoria_required
@require_POST
def solicitar_reconsideracao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        if patd.status != 'periodo_reconsideracao':
            return JsonResponse({'status': 'error', 'message': 'A PATD não está no período de reconsideração.'}, status=400)

        patd.status = 'em_reconsideracao'
        patd.save(update_fields=['status'])
        messages.success(request, f'PATD Nº {patd.numero_patd} movida para "Em Reconsideração".')
        return JsonResponse({'status': 'success', 'message': 'Status atualizado com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao solicitar reconsideração para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@ouvidoria_required
@require_POST
def salvar_reconsideracao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        if patd.status != 'em_reconsideracao':
            return JsonResponse({'status': 'error', 'message': 'A PATD não está em fase de reconsideração.'}, status=400)

        texto = request.POST.get('texto_reconsideracao', '')
        arquivos = request.FILES.getlist('anexos_reconsideracao')

        if not texto and not arquivos:
            return JsonResponse({'status': 'error', 'message': 'É necessário fornecer um texto ou anexar pelo menos um ficheiro.'}, status=400)

        patd.texto_reconsideracao = texto
        if not patd.data_reconsideracao:
            patd.data_reconsideracao = timezone.now()
        patd.save(update_fields=['texto_reconsideracao', 'data_reconsideracao'])

        for arquivo in arquivos:
            Anexo.objects.create(patd=patd, arquivo=arquivo, tipo='reconsideracao')

        # --- CORREÇÃO: Usar transaction.on_commit para consistência ---
        # Garante que a verificação só ocorra após o salvamento do texto/anexos
        # ser confirmado na base de dados.
        transaction.on_commit(lambda: _check_and_advance_reconsideracao_status(pk))

        return JsonResponse({'status': 'success', 'message': 'Pedido de reconsideração e anexos salvos com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar texto de reconsideração para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@oficial_responsavel_required
@require_POST
def anexar_documento_reconsideracao_oficial(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        if patd.status != 'aguardando_comandante_base':
            messages.error(request, "Ação não permitida no status atual.")
            return redirect('Ouvidoria:patd_detail', pk=pk)

        anexo_file = request.FILES.get('anexo_oficial')
        if not anexo_file:
            messages.error(request, "Nenhum ficheiro foi enviado.")
            return redirect('Ouvidoria:patd_detail', pk=pk)

        Anexo.objects.create(patd=patd, arquivo=anexo_file, tipo='reconsideracao_oficial')

        # --- INÍCIO DA MODIFICAÇÃO ---
        # Atualiza o status para aguardar a definição da nova punição
        patd.status = 'aguardando_nova_punicao'
        patd.save(update_fields=['status'])

        messages.success(request, "Documento anexado com sucesso! O processo agora aguarda a definição da nova punição.")
        return redirect('Ouvidoria:patd_detail', pk=pk)
        # --- FIM DA MODIFICAÇÃO ---
    except Exception as e:
        logger.error(f"Erro ao anexar documento de reconsideração oficial para PATD {pk}: {e}")
        messages.error(request, f"Ocorreu um erro ao anexar o documento: {e}")
        return redirect('Ouvidoria:patd_detail', pk=pk)
