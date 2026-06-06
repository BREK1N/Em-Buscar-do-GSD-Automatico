import json
import logging
import re

from num2words import num2words
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from ..models import PATD
from ..tasks import (
    regenerar_ocorrencia_task,
    regenerar_resumo_defesa_task,
    regenerar_texto_relatorio_task,
    regenerar_punicao_task,
    analisar_punicao_task,
)
from .decorators import ouvidoria_required, oficial_responsavel_required
from .signatures import _check_preclusao_signatures

logger = logging.getLogger(__name__)


def _is_primeira_prisao_disciplinar(patd):
    if 'prisão' not in (patd.punicao or '').lower():
        return False
    ja_teve_prisao = PATD.objects.filter(
        militar=patd.militar,
        punicao__icontains='prisão',
        justificado=False,
        status__in=[
            'aguardando_punicao', 'aguardando_punicao_alterar',
            'aplicacao_punicao_cmd_base', 'analise_comandante',
            'aguardando_assinatura_npd', 'periodo_reconsideracao',
            'em_reconsideracao', 'aguardando_comandante_base',
            'aguardando_nova_punicao', 'aguardando_publicacao', 'finalizado',
        ],
    ).exclude(pk=patd.pk).exists()
    return not ja_teve_prisao


@login_required
@oficial_responsavel_required
@require_POST
def regenerar_ocorrencia(request, pk):
    get_object_or_404(PATD, pk=pk)
    task = regenerar_ocorrencia_task.delay(pk)
    return JsonResponse({'status': 'pending', 'task_id': task.id}, status=202)


@login_required
@oficial_responsavel_required
@require_POST
def regenerar_resumo_defesa(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    if not patd.alegacao_defesa:
        return JsonResponse({'status': 'error', 'message': 'Não há texto de defesa para resumir.'}, status=400)
    task = regenerar_resumo_defesa_task.delay(pk)
    return JsonResponse({'status': 'pending', 'task_id': task.id}, status=202)


@login_required
@oficial_responsavel_required
@require_POST
def regenerar_texto_relatorio(request, pk):
    get_object_or_404(PATD, pk=pk)
    task = regenerar_texto_relatorio_task.delay(pk)
    return JsonResponse({'status': 'pending', 'task_id': task.id}, status=202)


@login_required
@oficial_responsavel_required
@require_POST
def regenerar_punicao(request, pk):
    get_object_or_404(PATD, pk=pk)
    task = regenerar_punicao_task.delay(pk)
    return JsonResponse({'status': 'pending', 'task_id': task.id}, status=202)


@login_required
@oficial_responsavel_required
@require_POST
def analisar_punicao(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    force_reanalyze = False

    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            force_reanalyze = data.get('force_reanalyze', False)
        except json.JSONDecodeError:
            pass

    # Caminho rápido: resultado já existe e não foi pedido re-análise
    if patd.punicao_sugerida and not force_reanalyze:
        return JsonResponse({
            'status': 'success',
            'analise_data': {
                'itens': patd.itens_enquadrados,
                'circunstancias': patd.circunstancias,
                'punicao': patd.punicao_sugerida,
            }
        })

    task = analisar_punicao_task.delay(pk, force_reanalyze)
    return JsonResponse({'status': 'pending', 'task_id': task.id}, status=202)


@login_required
@oficial_responsavel_required
@require_POST
def salvar_apuracao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

        if patd.status == 'apuracao_preclusao':
            if not _check_preclusao_signatures(patd):
                return JsonResponse({
                    'status': 'error',
                    'message': 'A apuração não pode ser concluída. Faltam assinaturas das testemunhas no termo de preclusão.'
                }, status=400)

        patd.itens_enquadrados = data.get('itens_enquadrados')
        patd.circunstancias = data.get('circunstancias')

        dias_num_int = data.get('punicao_dias')
        punicao_tipo_str = data.get('punicao_tipo')

        if dias_num_int is None or not punicao_tipo_str:
            logger.warning("PATD %s: usando fallback (punicao_sugerida) para salvar apuração.", pk)
            punicao_sugerida_str = data.get('punicao_sugerida', '')
            patd.punicao_sugerida = punicao_sugerida_str

            match = re.search(r'(\d+)\s+dias\s+de\s+(.+)', punicao_sugerida_str, re.IGNORECASE)
            if match:
                dias_num_int = int(match.group(1))
                punicao_tipo_str = match.group(2).strip().lower()
            elif 'repreensão' in punicao_sugerida_str.lower():
                dias_num_int = 0
                punicao_tipo_str = punicao_sugerida_str.strip().lower()
            else:
                dias_num_int = 0
                punicao_tipo_str = punicao_sugerida_str

        if dias_num_int is None:
            dias_num_int = 0
        if not punicao_tipo_str:
            punicao_tipo_str = "Não definida"

        if punicao_tipo_str in ['repreensão por escrito', 'repreensão verbal']:
            patd.punicao_sugerida = punicao_tipo_str
        else:
            patd.punicao_sugerida = f"{dias_num_int} dias de {punicao_tipo_str}"

        if punicao_tipo_str in ['repreensão por escrito', 'repreensão verbal']:
            patd.dias_punicao = ""
            patd.punicao = punicao_tipo_str
            patd.justificado = False
        elif dias_num_int > 0:
            dias_texto = num2words(dias_num_int, lang='pt_BR')
            patd.dias_punicao = f"{dias_texto} ({dias_num_int:02d}) dias"
            patd.punicao = punicao_tipo_str
            patd.justificado = False
        else:
            patd.dias_punicao = ""
            patd.punicao = punicao_tipo_str
            patd.justificado = False

        patd.transgressao_afirmativa = f"foi verificado que o militar realmente cometeu a transgressão de '{patd.transgressao}'."

        if not patd.texto_relatorio:
            from ..analise_transgressao import texto_relatorio as _texto_relatorio
            patd.texto_relatorio = _texto_relatorio(patd.transgressao, patd.alegacao_defesa)

        patd.definir_natureza_transgressao()
        patd.calcular_e_atualizar_comportamento()

        primeira_prisao = _is_primeira_prisao_disciplinar(patd)

        if primeira_prisao:
            patd.save(update_fields=[
                'itens_enquadrados', 'circunstancias', 'punicao_sugerida',
                'dias_punicao', 'punicao', 'justificado', 'transgressao_afirmativa',
                'texto_relatorio', 'natureza_transgressao', 'comportamento',
            ])
            return JsonResponse({
                'status': 'success',
                'primeira_prisao': True,
                'message': 'Apuração salva. Confirme o destino do processo.',
            })
        else:
            patd.status = 'aguardando_punicao'
            patd.save(update_fields=[
                'itens_enquadrados', 'circunstancias', 'punicao_sugerida',
                'dias_punicao', 'punicao', 'justificado', 'transgressao_afirmativa',
                'texto_relatorio', 'natureza_transgressao', 'comportamento', 'status',
            ])
            return JsonResponse({'status': 'success', 'primeira_prisao': False, 'message': 'Apuração salva com sucesso!'})

    except Exception as e:
        logger.error("Erro ao salvar apuração da PATD %s: %s", pk, e)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)
