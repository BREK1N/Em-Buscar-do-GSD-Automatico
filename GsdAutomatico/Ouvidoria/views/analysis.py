import json
import logging
import re

from num2words import num2words
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from ..models import PATD
from ..analise_transgressao import (
    enquadra_item,
    verifica_agravante_atenuante,
    sugere_punicao,
    model,
    analisar_e_resumir_defesa,
    reescrever_ocorrencia,
    texto_relatorio,
    AnaliseTransgressao,
    MilitarAcusado,
    analisar_documento_pdf,
    verifica_similaridade,
)
from .decorators import ouvidoria_required, oficial_responsavel_required
from .signatures import _check_preclusao_signatures

logger = logging.getLogger(__name__)

@login_required
@oficial_responsavel_required
@require_POST
def regenerar_ocorrencia(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    try:
        nova_ocorrencia = reescrever_ocorrencia(patd.transgressao)
        patd.ocorrencia_reescrita = nova_ocorrencia
        patd.comprovante = nova_ocorrencia  # Atualiza o comprovante também
        patd.save(update_fields=['ocorrencia_reescrita', 'comprovante'])
        return JsonResponse({'status': 'success', 'novo_texto': nova_ocorrencia})
    except Exception as e:
        logger.error("Erro em regenerar_ocorrencia (pk=%s): %s", pk, e, exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@oficial_responsavel_required
@require_POST
def regenerar_resumo_defesa(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    if not patd.alegacao_defesa:
        return JsonResponse({'status': 'error', 'message': 'Não há texto de defesa para resumir.'}, status=400)
    try:
        novo_resumo = analisar_e_resumir_defesa(patd.alegacao_defesa)
        patd.alegacao_defesa_resumo = novo_resumo
        patd.save(update_fields=['alegacao_defesa_resumo'])
        return JsonResponse({'status': 'success', 'novo_texto': novo_resumo})
    except Exception as e:
        logger.error("Erro em regenerar_resumo_defesa (pk=%s): %s", pk, e, exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@oficial_responsavel_required
@require_POST
def regenerar_texto_relatorio(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    try:
        novo_relatorio = texto_relatorio(patd.transgressao, patd.alegacao_defesa)
        patd.texto_relatorio = novo_relatorio
        patd.save(update_fields=['texto_relatorio'])
        return JsonResponse({'status': 'success', 'novo_texto': novo_relatorio})
    except Exception as e:
        logger.error("Erro em regenerar_texto_relatorio (pk=%s): %s", pk, e, exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@oficial_responsavel_required
@require_POST
def regenerar_punicao(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    try:
        punicao_obj = sugere_punicao(
            transgressao=patd.transgressao,
            agravantes=patd.circunstancias.get('agravantes', []),
            atenuantes=patd.circunstancias.get('atenuantes', []),
            itens=patd.itens_enquadrados,
            observacao="Regeneração de punição"
        )
        nova_punicao_sugerida = punicao_obj.punicao.get('punicao', 'Erro na sugestão.')
        patd.punicao_sugerida = nova_punicao_sugerida
        patd.save(update_fields=['punicao_sugerida'])
        return JsonResponse({'status': 'success', 'novo_texto': nova_punicao_sugerida})
    except Exception as e:
        logger.error("Erro em regenerar_punicao (pk=%s): %s", pk, e, exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


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

    if patd.punicao_sugerida and not force_reanalyze:
        return JsonResponse({
            'status': 'success',
            'analise_data': {
                'itens': patd.itens_enquadrados,
                'circunstancias': patd.circunstancias,
                'punicao': patd.punicao_sugerida
            }
        })

    try:
        itens_obj = enquadra_item(patd.transgressao)
        itens_list = [item for item in itens_obj.item]
        patd.itens_enquadrados = itens_list

        militar_acusado = patd.militar
        patds_anteriores = PATD.objects.filter(
            militar=militar_acusado
        ).exclude(pk=patd.pk).order_by('-data_inicio') # Adiciona order_by para pegar o mais recente

        historico_list = []

        # --- CORREÇÃO: Busca o comportamento anterior de forma mais robusta ---
        # Verifica se o militar já teve "Mau comportamento" em qualquer PATD anterior (excluindo a atual)
        if patd.pk: # Se for uma PATD existente sendo re-analisada
            has_previous_mau_comportamento = PATD.objects.filter(
                militar=militar_acusado, 
                comportamento="Mau comportamento"
            ).exclude(pk=patd.pk).exists()
        else: # Se for uma nova PATD sendo analisada pela primeira vez
            has_previous_mau_comportamento = PATD.objects.filter(
                militar=militar_acusado, 
                comportamento="Mau comportamento"
            ).exists()

        comportamento_anterior = "Permanece no \"Bom comportamento\"" # Valor padrão
        if has_previous_mau_comportamento:
            comportamento_anterior = "Mau comportamento"
        # --- FIM DA CORREÇÃO ---

        if patds_anteriores.exists():
            for p_antiga in patds_anteriores:
                if p_antiga.itens_enquadrados and isinstance(p_antiga.itens_enquadrados, list):
                    itens_str = ", ".join([f"Item {item.get('numero')}" for item in p_antiga.itens_enquadrados if 'numero' in item])
                    if itens_str:
                         historico_list.append(f"PATD anterior (Nº {p_antiga.numero_patd}) foi enquadrada em: {itens_str}.")

        historico_militar = "\n".join(historico_list) if historico_list else "Nenhuma punição anterior registrada."
        justificativa = patd.alegacao_defesa or "Nenhuma alegação de defesa foi apresentada."

        # --- CORREÇÃO NA CHAMADA DA FUNÇÃO ---
        circunstancias_obj = verifica_agravante_atenuante(
            historico_militar, 
            patd.transgressao, 
            justificativa, 
            patd.itens_enquadrados,
            comportamento_anterior # Argumento adicionado
        )
        # --- FIM DA CORREÇÃO NA CHAMADA ---

        circunstancias_dict = circunstancias_obj.item[0]
        patd.circunstancias = {
            'atenuantes': circunstancias_dict.get('atenuantes', []),
            'agravantes': circunstancias_dict.get('agravantes', [])
        }

        punicao_obj = sugere_punicao(
            transgressao=patd.transgressao,
            agravantes=patd.circunstancias.get('agravantes', []),
            atenuantes=patd.circunstancias.get('atenuantes', []),
            itens=patd.itens_enquadrados,
            observacao="Análise inicial"
        )
        patd.punicao_sugerida = punicao_obj.punicao.get('punicao', 'Erro na sugestão.')

        patd.save()

        final_response_data = {
            'status': 'success',
            'analise_data': {
                'itens': patd.itens_enquadrados,
                'circunstancias': patd.circunstancias,
                'punicao': patd.punicao_sugerida
            }
        }

        return JsonResponse(final_response_data)

    except Exception as e:
        logger.error(f"Erro na análise da IA para PATD {pk}: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'Ocorreu um erro durante a análise da IA: {e}'
        }, status=500)


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

        # *** INÍCIO DA MODIFICAÇÃO ***
        # Prioriza os novos campos estruturados, se existirem
        dias_num_int = data.get('punicao_dias') # Já vem como INT do JS
        punicao_tipo_str = data.get('punicao_tipo')

        # Fallback para o campo de string antigo, se os novos não vierem
        if dias_num_int is None or not punicao_tipo_str:
            logger.warning(f"PATD {pk}: Usando fallback (punicao_sugerida) para salvar apuração.")
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
                punicao_tipo_str = punicao_sugerida_str # Salva o que veio (ex: "Erro...")
        
        # Garante que dias_num_int é um número
        if dias_num_int is None:
             dias_num_int = 0
             
        # Garante que o tipo não é nulo
        if not punicao_tipo_str:
             punicao_tipo_str = "Não definida"

        # Salva a string de punição sugerida (para consistência)
        if punicao_tipo_str in ['repreensão por escrito', 'repreensão verbal']:
            patd.punicao_sugerida = punicao_tipo_str
        else:
            patd.punicao_sugerida = f"{dias_num_int} dias de {punicao_tipo_str}"
        
        # Define os campos de punição final
        if punicao_tipo_str in ['repreensão por escrito', 'repreensão verbal']:
            patd.dias_punicao = "" # Repreensão não tem dias
            patd.punicao = punicao_tipo_str
            patd.justificado = False # Garante que não está justificado
        elif dias_num_int > 0:
            dias_texto = num2words(dias_num_int, lang='pt_BR')
            patd.dias_punicao = f"{dias_texto} ({dias_num_int:02d}) dias"
            patd.punicao = punicao_tipo_str
            patd.justificado = False # Garante que não está justificado
        else:
             # Caso de 0 dias de prisão/detenção (não deve ocorrer, mas é um fallback)
            patd.dias_punicao = ""
            patd.punicao = punicao_tipo_str
            patd.justificado = False
            
        # *** FIM DA MODIFICAÇÃO ***

        patd.transgressao_afirmativa = f"foi verificado que o militar realmente cometeu a transgressão de '{patd.transgressao}'."

        if not patd.texto_relatorio:
            patd.texto_relatorio = texto_relatorio(patd.transgressao, patd.alegacao_defesa)

        patd.definir_natureza_transgressao()
        patd.calcular_e_atualizar_comportamento()

        patd.status = 'aguardando_punicao'

        patd.save(update_fields=['itens_enquadrados', 'circunstancias', 'punicao_sugerida', 'dias_punicao', 'punicao', 'justificado', 'transgressao_afirmativa', 'texto_relatorio', 'natureza_transgressao', 'comportamento', 'status'])

        return JsonResponse({'status': 'success', 'message': 'Apuração salva com sucesso!'})

    except Exception as e:
        logger.error(f"Erro ao salvar apuração da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)
