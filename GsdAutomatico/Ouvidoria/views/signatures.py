import json
import logging, base64
from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST, require_GET
from django.core.files.base import ContentFile

from ..models import PATD, Configuracao, Anexo
from Secao_pessoal.models import Efetivo
from ..permissions import can_change_patd_date
from .decorators import ouvidoria_required, oficial_responsavel_required
from .helpers import get_document_pages, _try_advance_status_from_justificativa
from .commander import _check_and_finalize_patd, _check_and_advance_reconsideracao_status

logger = logging.getLogger(__name__)

def _check_preclusao_signatures(patd):
    if patd.testemunha1 and not patd.assinatura_testemunha1:
        return False
    if patd.testemunha2 and not patd.assinatura_testemunha2:
        return False

    return True


@login_required
@oficial_responsavel_required
@require_POST
def salvar_assinatura(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        signature_data_base64 = data.get('signature_data')

        if not signature_data_base64:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)

        try:
            format, imgstr = signature_data_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_content = ContentFile(base64.b64decode(imgstr), name=f'sig_oficial_{pk}.{ext}')

            if patd.assinatura_oficial:
                patd.assinatura_oficial.delete(save=False)

            # Garante que a referência do ficheiro seja salva na base de dados explicitamente
            patd.assinatura_oficial.save(file_content.name, file_content, save=False)
            patd.save(update_fields=['assinatura_oficial'])
        except Exception as e:
            logger.error(f"Erro ao converter Base64 para ficheiro para PATD {pk}: {e}")
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar a imagem da assinatura.'}, status=500)

        return JsonResponse({'status': 'success', 'message': 'Assinatura salva com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura do oficial para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_ciencia(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        signature_data_base64 = data.get('signature_data')
        assinatura_index = int(data.get('assinatura_index', -1))

        if not signature_data_base64 or assinatura_index < 0:
            return JsonResponse({'status': 'error', 'message': 'Dados de assinatura inválidos.'}, status=400)

        try:
            format, imgstr = signature_data_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f'sig_ciencia_{assinatura_index}_{pk}_{uuid4().hex[:6]}.{ext}'
            file_content = ContentFile(base64.b64decode(imgstr))

            anexo = Anexo.objects.create(patd=patd, tipo='assinatura_ciencia')
            anexo.arquivo.save(file_name, file_content, save=True)
            signature_url = anexo.arquivo.url

        except Exception as e:
            logger.error(f"Erro ao converter Base64 da assinatura de ciência para ficheiro (PATD {pk}): {e}")
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar a imagem da assinatura.'}, status=500)

        if patd.assinaturas_militar is None:
            patd.assinaturas_militar = []

        while len(patd.assinaturas_militar) <= assinatura_index:
            patd.assinaturas_militar.append(None)

        patd.assinaturas_militar[assinatura_index] = signature_url

        if patd.status == 'ciencia_militar':
            document_pages = get_document_pages(patd)
            coringa_doc_text = document_pages[0] if document_pages else ""
            required_initial_signatures = coringa_doc_text.count('{Assinatura Militar Arrolado}')
            provided_signatures = sum(1 for s in (patd.assinaturas_militar or []) if s is not None)
            if provided_signatures >= required_initial_signatures:
                if patd.data_ciencia is None:
                    patd.data_ciencia = timezone.now()
                patd.status = 'aguardando_justificativa'

        _try_advance_status_from_justificativa(patd)
        _check_and_finalize_patd(patd)

        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Assinatura registrada com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura de ciência da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_defesa(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        signature_data_base64 = data.get('signature_data')

        if not signature_data_base64:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)

        try:
            format, imgstr = signature_data_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_content = ContentFile(base64.b64decode(imgstr), name=f'sig_defesa_{pk}.{ext}')

            if patd.assinatura_alegacao_defesa:
                patd.assinatura_alegacao_defesa.delete(save=False)

            patd.assinatura_alegacao_defesa.save(file_content.name, file_content, save=True)
        except Exception as e:
            logger.error(f"Erro ao converter Base64 para ficheiro para PATD {pk}: {e}")
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar a imagem da assinatura.'}, status=500)

        return JsonResponse({'status': 'success', 'message': 'Assinatura da defesa salva com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura da defesa da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_reconsideracao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)

        if patd.status != 'em_reconsideracao':
            return JsonResponse({'status': 'error', 'message': 'A PATD não está na fase correta para assinar a reconsideração.'}, status=400)

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        signature_data_base64 = data.get('signature_data')

        if not signature_data_base64:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)

        try:
            format, imgstr = signature_data_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_content = ContentFile(base64.b64decode(imgstr), name=f'sig_reconsideracao_{pk}.{ext}')

            if patd.assinatura_reconsideracao:
                patd.assinatura_reconsideracao.delete(save=False)

            patd.assinatura_reconsideracao.save(file_content.name, file_content, save=False)
            patd.save(update_fields=['assinatura_reconsideracao'])
            logger.info(f"Assinatura de reconsideração para PATD {pk} salva em {patd.assinatura_reconsideracao.path}")

        except Exception as e:
            logger.error(f"Erro ao converter Base64 para ficheiro para PATD {pk}: {e}")
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar a imagem da assinatura.'}, status=500)

        # --- CORREÇÃO: Usar transaction.on_commit ---
        # Agenda a verificação para ser executada APÓS o save() ser confirmado na base de dados,
        # evitando condições de corrida onde a verificação ocorre antes do campo da assinatura ser atualizado.
        transaction.on_commit(lambda: _check_and_advance_reconsideracao_status(pk))

        return JsonResponse({'status': 'success', 'message': 'Assinatura salva com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura da reconsideração da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@require_POST
def remover_assinatura(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Apenas administradores podem remover assinaturas.'}, status=403)

    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        signature_type = data.get('signature_type')
        signature_index = data.get('signature_index')

        if not signature_type:
            return JsonResponse({'status': 'error', 'message': 'O tipo de assinatura não foi especificado.'}, status=400)

        if signature_type == 'oficial':
            return JsonResponse({'status': 'error', 'message': 'A assinatura do oficial não pode ser removida.'}, status=403)
        elif signature_type == 'defesa':
            if patd.assinatura_alegacao_defesa:
                patd.assinatura_alegacao_defesa.delete(save=True)
        elif signature_type == 'reconsideracao':
            if patd.assinatura_reconsideracao:
                patd.assinatura_reconsideracao.delete(save=True)
        elif signature_type == 'testemunha1':
            if patd.assinatura_testemunha1:
                patd.assinatura_testemunha1.delete(save=True)
        elif signature_type == 'testemunha2':
            if patd.assinatura_testemunha2:
                patd.assinatura_testemunha2.delete(save=True)
        elif signature_type == 'ciencia':
            if signature_index is not None and patd.assinaturas_militar and len(patd.assinaturas_militar) > signature_index:
                signature_url = patd.assinaturas_militar[signature_index]
                if signature_url:
                    try:
                        anexo = Anexo.objects.get(patd=patd, arquivo=signature_url.replace('/media/', ''))
                        anexo.delete() 
                    except Anexo.DoesNotExist:
                        logger.warning(f"Anexo for signature URL {signature_url} not found for PATD {pk}. Removing URL from list.")
                        pass
                patd.assinaturas_militar[signature_index] = None
                patd.save(update_fields=['assinaturas_militar'])
        else:
            return JsonResponse({'status': 'error', 'message': 'Tipo de assinatura desconhecido.'}, status=400)

        return JsonResponse({'status': 'success', 'message': 'Assinatura removida com sucesso.'})

    except Exception as e:
        logger.error(f"Erro ao remover assinatura da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_GET
def lista_oficiais(request):
    query = request.GET.get('q', '')
    oficiais = Efetivo.objects.filter(oficial=True)
    if query:
        oficiais = oficiais.filter(
            Q(nome_completo__icontains=query) |
            Q(nome_guerra__icontains=query)
        )
    oficiais = oficiais.order_by('posto', 'nome_guerra')
    data = list(oficiais.values('id', 'posto', 'nome_guerra', 'assinatura'))
    response = JsonResponse(data, safe=False)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return response


@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_padrao(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Apenas administradores podem alterar assinaturas.'}, status=403)
    try:
        oficial = get_object_or_404(Efetivo, pk=pk, oficial=True)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        signature_data = data.get('signature_data', '')
        oficial.assinatura = signature_data
        oficial.save()
        return JsonResponse({'status': 'success', 'message': 'Assinatura padrão salva com sucesso.'})
    except Efetivo.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Oficial não encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def gerenciar_configuracoes_padrao(request):
    config = Configuracao.load()
    if request.method == 'POST':
        if not request.user.is_superuser:
            return JsonResponse({'status': 'error', 'message': 'Apenas administradores podem alterar as configurações.'}, status=403)
        try:
            try:
                data = json.loads(request.body)
            except (json.JSONDecodeError, ValueError):
                return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
            comandante_gsd_id = data.get('comandante_gsd_id')
            comandante_bagl_id = data.get('comandante_bagl_id')
            prazo_dias = data.get('prazo_defesa_dias')
            prazo_minutos = data.get('prazo_defesa_minutos')

            if comandante_gsd_id:
                comandante = get_object_or_404(Efetivo, pk=comandante_gsd_id, oficial=True)
                config.comandante_gsd = comandante
            else:
                config.comandante_gsd = None

            if comandante_bagl_id:
                comandante_bagl = get_object_or_404(Efetivo, pk=comandante_bagl_id, oficial=True)
                config.comandante_bagl = comandante_bagl
            else:
                config.comandante_bagl = None

            if prazo_dias is not None:
                config.prazo_defesa_dias = int(prazo_dias)
            if prazo_minutos is not None:
                config.prazo_defesa_minutos = int(prazo_minutos)

            config.save()
            return JsonResponse({'status': 'success', 'message': 'Configurações salvas com sucesso.'})
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Prazo de defesa inválido.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)

    oficiais = Efetivo.objects.filter(oficial=True).order_by('posto', 'nome_guerra')
    oficiais_data = [{'id': o.id, 'texto': f"{o.posto} {o.nome_guerra}"} for o in oficiais]
    data = {
        'comandante_gsd_id': config.comandante_gsd.id if config.comandante_gsd else None,
        'comandante_bagl_id': config.comandante_bagl.id if config.comandante_bagl else None,
        'oficiais': oficiais_data,
        'prazo_defesa_dias': config.prazo_defesa_dias,
        'prazo_defesa_minutos': config.prazo_defesa_minutos
    }
    return JsonResponse(data)


@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_testemunha(request, pk, testemunha_num):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        signature_data_base64 = data.get('signature_data')

        if not signature_data_base64:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)

        try:
            format, imgstr = signature_data_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_content = ContentFile(base64.b64decode(imgstr), name=f'sig_testemunha_{testemunha_num}_{pk}.{ext}')

            if testemunha_num == 1:
                if patd.assinatura_testemunha1:
                    patd.assinatura_testemunha1.delete(save=False)
                patd.assinatura_testemunha1.save(file_content.name, file_content, save=False) # Não salva o modelo PATD ainda
                patd.save(update_fields=['assinatura_testemunha1']) # Salva explicitamente a referência do ficheiro
            elif testemunha_num == 2:
                if patd.assinatura_testemunha2:
                    patd.assinatura_testemunha2.delete(save=False)
                patd.assinatura_testemunha2.save(file_content.name, file_content, save=False) # Não salva o modelo PATD ainda
                patd.save(update_fields=['assinatura_testemunha2']) # Salva explicitamente a referência do ficheiro
            else:
                return JsonResponse({'status': 'error', 'message': 'Número de testemunha inválido.'}, status=400)

            patd.save()

        except Exception as e:
            logger.error(f"Erro ao converter Base64 para ficheiro para PATD {pk}: {e}")
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar a imagem da assinatura.'}, status=500)

        if _check_and_finalize_patd(patd):
             patd.save()

        return JsonResponse({'status': 'success', 'message': f'Assinatura da {testemunha_num}ª testemunha salva.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura da testemunha {testemunha_num} para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)
