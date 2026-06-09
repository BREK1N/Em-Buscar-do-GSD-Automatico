import io, os, re, logging, traceback, tempfile, locale
import json
from datetime import datetime

from django.core.files import File
import fitz  # PyMuPDF

from num2words import num2words

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Max, Case, When, Value, IntegerField, Count
from django.db.models.functions import TruncMonth
from django.db import transaction
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils.decorators import method_decorator
from django.utils import timezone

from ..models import PATD, Configuracao, Anexo
from ..forms import MilitarForm, PATDForm, AtribuirOficialForm, AceitarAtribuicaoForm, ComandanteAprovarForm
from ..permissions import has_ouvidoria_access, can_delete_patd, has_comandante_access, can_edit_patd, is_apurador

def has_patd_detail_access(user):
    return has_ouvidoria_access(user) or has_comandante_access(user)
from Secao_pessoal.models import Efetivo
from Secao_pessoal.utils import get_rank_value, RANK_HIERARCHY
from .decorators import (
    comandante_redirect, ouvidoria_required, OuvidoriaAccessMixin, oficial_responsavel_required,
    finalizar_ouvidoria_required,
)
from .helpers import (
    get_next_patd_number, format_militar_string, buscar_militar_inteligente,
    _get_document_context, _render_document_from_template, get_document_pages,
    _sync_oficial_signature, _try_advance_status_from_justificativa,
)
from .commander import _check_and_finalize_patd, _check_and_advance_reconsideracao_status
from ..analise_transgressao import (
    AnaliseTransgressao, MilitarAcusado, analisar_documento_pdf,
    verifica_similaridade, personalizar_ocorrencia, enquadra_item,
)

logger = logging.getLogger(__name__)


def _fix_pdf_text_encoding(text: str) -> str:
    """
    Corrige problemas de encoding em texto extraído de PDFs brasileiros.

    Cobre três padrões comuns:
    1. Caracteres no Private Use Area (U+F000-U+F0FF) gerados por fontes WinAnsi/
       MacRoman sem mapa ToUnicode — subtrai 0xF000 para recuperar o Latin-1 original.
    2. Sequências de escape literal '\\uXXXX' armazenadas como texto em vez de
       como o caractere Unicode correspondente.
    3. Caractere de substituição U+FFFD seguido de dois dígitos hex — padrão
       produzido quando PyMuPDF não consegue decodificar um byte Latin-1 como UTF-8.
    """
    if not text:
        return text

    # Fix 1: PUA U+F021..U+F0FF → Latin-1 U+0021..U+00FF
    fixed = []
    for ch in text:
        cp = ord(ch)
        if 0xF021 <= cp <= 0xF0FF:
            fixed.append(chr(cp - 0xF000))
        else:
            fixed.append(ch)
    text = ''.join(fixed)

    # Fix 2: sequências literais \uXXXX → caractere Unicode
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)

    # Fix 3: U+FFFD + 2 hex chars → chr(byte) — ex: �e7 → ç
    text = re.sub('�([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), text)

    return text


PHASE_GROUPS = [
    {
        'key': 'confeccao',
        'label': '1 – Confecção / FR e Ficha Individual',
        'statuses': ['confeccao_fr_ficha'],
    },
    {
        'key': 'ciencia_defesa',
        'label': '2 – Ciência do Militar e Defesa',
        'statuses': ['ciencia_militar', 'aguardando_justificativa', 'prazo_expirado', 'preclusao'],
    },
    {
        'key': 'apuracao',
        'label': '3 – Apuração',
        'statuses': [
            'definicao_oficial', 'aguardando_aprovacao_atribuicao',
            'em_apuracao', 'apuracao_preclusao',
            'aguardando_punicao', 'aguardando_punicao_alterar',
        ],
    },
    {
        'key': 'analise_oficial',
        'label': '4 – Análise do Oficial Apurador',
        'statuses': ['analise_oficial_apurador'],
    },
    {
        'key': 'aguardando_comandante',
        'label': '5 – Aguardando Resposta do Comandante',
        'statuses': [
            'analise_comandante',
        ],
    },
    {
        'key': 'condenacao',
        'label': '6 – Ciência da Condenação / NPD',
        'statuses': [
            'aguardando_assinatura_npd', 'aguardando_nova_punicao',
            'periodo_reconsideracao', 'em_reconsideracao',
            'aguardando_publicacao', 'aguardando_preenchimento_npd_reconsideracao',
            'finalizado',
        ],
    },
]

STATUS_GROUPS = {
    "1 – Confecção / FR e Ficha Individual": {
        'confeccao_fr_ficha': 'Confecção / FR e Ficha Individual',
    },
    "2 – Ciência do Militar e Defesa": {
        'ciencia_militar': 'Aguardando ciência do militar',
        'aguardando_justificativa': 'Aguardando Justificativa',
        'prazo_expirado': 'Prazo expirado',
        'preclusao': 'Preclusão - Sem Defesa',
    },
    "3 – Apuração": {
        'definicao_oficial': 'Aguardando atribuição do Oficial',
        'aguardando_aprovacao_atribuicao': 'Aguardando aprovação de atribuição de oficial',
        'em_apuracao': 'Em Apuração',
        'apuracao_preclusao': 'Em Apuração (Preclusão)',
        'aguardando_punicao': 'Aguardando Aplicação da Punição',
        'aguardando_punicao_alterar': 'Aguardando Punição (alterar)',
    },
    "4 – Análise do Oficial Apurador": {
        'analise_oficial_apurador': 'Análise do Oficial Apurador',
    },
    "5 – Aguardando Resposta do Comandante": {
        'analise_comandante': 'Em Análise pelo Comandante',
        'aguardando_assinatura_npd': 'Aguardando Assinatura NPD',
        'aguardando_nova_punicao': 'Aguardando nova punição',
    },
    "6 – Ciência da Condenação / NPD": {
        'periodo_reconsideracao': 'Período de Reconsideração',
        'em_reconsideracao': 'Em Reconsideração',
        'aguardando_preenchimento_npd_reconsideracao': 'Aguardando preenchimento NPD Reconsideração',
        'aguardando_publicacao': 'Aguardando publicação',
        'finalizado': 'Finalizado',
    },
}



@login_required
@comandante_redirect
@ouvidoria_required
def index(request):
    config = Configuracao.load()
    context = {
        'prazo_defesa_dias': config.prazo_defesa_dias,
        'prazo_defesa_minutos': config.prazo_defesa_minutos,
    }
    if request.method == 'POST':
        action = request.POST.get('action', 'analyze')

        # --- NOVO BLOCO 1: Busca Dinâmica (Search Bar) ---
        if action == 'search_militar':
            term = request.POST.get('term', '').strip()
            if not term or len(term) < 2:
                return JsonResponse({'results': []})
            
            # Busca por Nome de Guerra ou Nome Completo ou SARAM
            militares = Efetivo.objects.filter(
                Q(nome_guerra__icontains=term) |
                Q(nome_completo__icontains=term) |
                Q(saram__icontains=term)
            )[:10] # Limita a 10 resultados para não pesar


            results = []
            for m in militares:
                results.append({
                    'id': m.id,
                    'posto': m.posto,
                    'nome_guerra': m.nome_guerra,
                    'nome_completo': m.nome_completo,
                    'saram': m.saram or 'N/A'
                })

            
            return JsonResponse({'results': results})

        # --- NOVO BLOCO 2: Associar Transgressão a Militar Existente ---
        # --- BLOCO 2 ATUALIZADO: Associar Transgressão com Verificação de Duplicidade ---
        elif action == 'associate_patd':
            post_data = request.POST.copy()
            post_data.pop('oficio_lancamento_texto', None)
            militar_id = post_data.get('militar_id')
            if not militar_id:
                return JsonResponse({'status': 'error', 'message': 'ID do militar não fornecido.'}, status=400)

            
            militar = get_object_or_404(Efetivo, pk=militar_id)
            
            # Recupera os dados
            transgressao = post_data.get('transgressao', '')
            protocolo_comaer = post_data.get('protocolo_comaer', '')
            oficio_transgressao = post_data.get('oficio_transgressao', '')

            # --- Tratamento de Datas ---
            data_ocorrencia_str = post_data.get('data_ocorrencia')
            data_oficio_str = post_data.get('data_oficio', '')


            data_ocorrencia = None
            if data_ocorrencia_str:
                try:
                    data_ocorrencia = datetime.strptime(data_ocorrencia_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass

            data_oficio = None
            if data_oficio_str:
                cleaned_data_oficio_str = re.sub(r"^[A-Za-z\s]+,\s*", "", data_oficio_str).strip()
                formats_to_try = ['%d/%m/%Y', '%d de %B de %Y', '%Y-%m-%d', '%d.%m.%Y']
                for fmt in formats_to_try:
                    try:
                        if '%B' in fmt:
                            try:
                                locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
                            except locale.Error:
                                continue
                        data_oficio = datetime.strptime(cleaned_data_oficio_str, fmt).date()
                        break
                    except (ValueError, TypeError):
                        continue
            
            # =================================================================
            # NOVA LOGICA: VERIFICAÇÃO DE DUPLICIDADE
            # =================================================================
            # 1. Busca PATDs desse militar na mesma data (excluindo arquivadas e deletadas)
            existing_patds = PATD.objects.filter(militar=militar, data_ocorrencia=data_ocorrencia, arquivado=False, deleted=False)
            
            # 2. Compara o texto da transgressão
            is_duplicate = False
            duplicated_patd_num = None

            for patd_existente in existing_patds:
                # Usa SequenceMatcher para comparar similaridade (acima de 80%)


                # similarity = SequenceMatcher(None, transgressao.strip().lower(), patd_existente.transgressao.strip().lower()).ratio()
                # if similarity > 0.8:
                #     is_duplicate = True
                is_duplicate = verifica_similaridade(transgressao.strip().lower(), patd_existente.transgressao.strip().lower())
                if is_duplicate:
                    duplicated_patd_num = patd_existente.numero_patd
                    break
            
            if is_duplicate:
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Ação bloqueada: Já existe a PATD Nº {duplicated_patd_num} para o militar {militar.nome_guerra} nesta data com teor similar.'
                })
            # =================================================================

            # Processa itens_enquadrados se enviados
            itens_enquadrados = None
            itens_json_str = post_data.get('itens_enquadrados_json', '')
            if itens_json_str:
                try:
                    itens_enquadrados = json.loads(itens_json_str)
                    if not isinstance(itens_enquadrados, list):
                        itens_enquadrados = None
                except (json.JSONDecodeError, ValueError):
                    pass

            # Se não for duplicada, cria a PATD normalmente
            try:
                patd = PATD.objects.create(
                    militar=militar,
                    transgressao=transgressao,
                    numero_patd=get_next_patd_number(),
                    data_ocorrencia=data_ocorrencia,
                    protocolo_comaer=protocolo_comaer,
                    oficio_transgressao=oficio_transgressao,
                    data_oficio=data_oficio,
                    itens_enquadrados=itens_enquadrados,
                )
                
                # Anexar o ofício de lançamento que foi salvo temporariamente
                oficio_info = request.session.get('oficio_lancamento')
                if oficio_info and 'path' in oficio_info and os.path.exists(oficio_info['path']):
                    filepath = oficio_info['path']
                    with open(filepath, 'rb') as f:
                        django_file = File(f, name=os.path.basename(filepath))
                        Anexo.objects.create(patd=patd, arquivo=django_file, tipo='oficio_lancamento')

                    # Decrementa o contador e verifica se o ficheiro pode ser removido
                    oficio_info['count'] -= 1
                    if oficio_info['count'] <= 0:
                        try:
                            os.remove(filepath)
                            logger.info(f"Ficheiro temporário {filepath} removido após todas as associações.")
                            if 'oficio_lancamento' in request.session:
                                del request.session['oficio_lancamento']
                        except OSError as e:
                            logger.error(f"Erro ao remover ficheiro temporário {filepath}: {e}")
                    else:
                        # Se ainda não terminou, atualiza a sessão com o novo contador
                        request.session['oficio_lancamento'] = oficio_info

                return JsonResponse({
                    'status': 'success', 
                    'militar_nome': militar.nome_guerra,
                    'message': f'PATD Nº {patd.numero_patd} criada com sucesso para {militar.nome_guerra}.'
                })
            except Exception as e:
                logger.error(f"Erro ao associar PATD: {e}")
                return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)
            
        elif action == 'create_manual_patd':
            militar_id = request.POST.get('militar_id')
            transgressao = request.POST.get('transgressao', '')
            data_ocorrencia_str = request.POST.get('data_ocorrencia')
            oficio_transgressao = request.POST.get('oficio_transgressao', '')
            oficio_lancamento_file = request.FILES.get('oficio_lancamento')

            if not all([militar_id, transgressao, data_ocorrencia_str, oficio_lancamento_file]):
                return JsonResponse({'status': 'error', 'message': 'Militar, transgressão, data da ocorrência e ofício de lançamento são obrigatórios.'}, status=400)
            
            militar = get_object_or_404(Efetivo, pk=militar_id)

            data_ocorrencia = None
            try:
                data_ocorrencia = datetime.strptime(data_ocorrencia_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return JsonResponse({'status': 'error', 'message': 'Formato de data da ocorrência inválido.'}, status=400)
            
            # Check for duplicates (excluding archived and deleted)
            existing_patds = PATD.objects.filter(militar=militar, data_ocorrencia=data_ocorrencia, arquivado=False, deleted=False)
            is_duplicate = False
            duplicated_patd_num = None
            for patd_existente in existing_patds:
                if verifica_similaridade(transgressao.strip().lower(), patd_existente.transgressao.strip().lower()):
                    is_duplicate = True
                    duplicated_patd_num = patd_existente.numero_patd
                    break
            
            if is_duplicate:
                return JsonResponse({
                    'status': 'error', 
                    'message': f'Ação bloqueada: Já existe a PATD Nº {duplicated_patd_num} para o militar {militar.nome_guerra} nesta data com teor similar.'
                }, status=409) # 409 Conflict

            try:
                patd = PATD.objects.create(
                    militar=militar,
                    transgressao=transgressao,
                    numero_patd=get_next_patd_number(),
                    data_ocorrencia=data_ocorrencia,
                    oficio_transgressao=oficio_transgressao,
                )

                Anexo.objects.create(
                    patd=patd,
                    arquivo=oficio_lancamento_file,
                    tipo='oficio_lancamento'
                )
                
                return JsonResponse({
                    'status': 'success', 
                    'message': f'PATD Nº {patd.numero_patd} criada com sucesso para {militar.nome_guerra}. Redirecionando...', 
                    'patd_url': reverse('Ouvidoria:patd_detail', kwargs={'pk': patd.pk})
                })
            except Exception as e:
                logger.error(f"Erro ao criar PATD manual: {e}")
                return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)

        # --- Modificação na ação 'analyze' ---
        elif action == 'analyze':
            pdf_file = request.FILES.get('pdf_file')
            if not pdf_file:
                return JsonResponse({'status': 'error', 'message': "Nenhum ficheiro foi enviado."}, status=400)

            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    for chunk in pdf_file.chunks():
                        temp_file.write(chunk)
                    temp_file_path = temp_file.name
                
                # Extração Híbrida: Texto nativo + OCR para escaneamentos
                content = ""
                doc = fitz.open(temp_file_path)
                for page in doc:
                    page_text = page.get_text()
                    if len(page_text.strip()) > 50:
                        content += _fix_pdf_text_encoding(page_text) + "\n\n"
                    else:
                        try:
                            pix = page.get_pixmap(dpi=300)
                            img = Image.open(io.BytesIO(pix.tobytes("png")))
                            if pytesseract:
                                content += pytesseract.image_to_string(img, lang='por') + "\n\n"
                            else:
                                logger.warning("pytesseract não está instalado. OCR ignorado.")
                        except Exception as e:
                            logger.warning(f"Erro ao processar OCR na página: {e}")
                doc.close()
                # Do not remove the temp file here: os.remove(temp_file_path)


                logger.info("Conteúdo do PDF extraído com sucesso. Chamando a IA para análise...")
                resultado_analise: AnaliseTransgressao = analisar_documento_pdf(content)
                if not resultado_analise.acusados:
                    logger.warning("Primeira análise retornou lista de acusados vazia. Retentando...")
                    resultado_analise = analisar_documento_pdf(content)
                logger.info(f"Resultado da análise da IA: {resultado_analise}")

                militares_para_confirmacao = []
                militares_nao_encontrados = []
                duplicatas_encontradas = []

                transgressao_comum = resultado_analise.transgressao
                data_ocorrencia_str = resultado_analise.data_ocorrencia
                protocolo_comaer_comum = resultado_analise.protocolo_comaer
                oficio_transgressao_comum = resultado_analise.oficio_transgressao
                data_oficio_str = resultado_analise.data_oficio
                
                # Armazenar dados comuns na sessão
                request.session['analise_transgressao_data'] = {
                    'transgressao': transgressao_comum,
                    'data_ocorrencia': data_ocorrencia_str,
                    'protocolo_comaer': protocolo_comaer_comum,
                    'oficio_transgressao': oficio_transgressao_comum,
                    'data_oficio': data_oficio_str,
                }

                data_ocorrencia = None
                if data_ocorrencia_str:
                    try:
                        data_ocorrencia = datetime.strptime(data_ocorrencia_str, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        logger.warning(f"Formato inválido para data_ocorrencia: {data_ocorrencia_str}")
                        pass
                
                if not hasattr(resultado_analise, 'acusados') or not isinstance(resultado_analise.acusados, list):
                     logger.error(f"A resposta da IA não continha uma lista válida de 'acusados'. Resposta: {resultado_analise}")
                     raise ValueError("Formato de resposta inválido da IA: lista de acusados ausente ou malformada.")

                for acusado in resultado_analise.acusados:
                    militar = buscar_militar_inteligente(acusado)

                    if militar:
                        logger.info(f"Militar encontrado no BD: {militar}")
                        existing_patds = PATD.objects.filter(militar=militar, data_ocorrencia=data_ocorrencia, arquivado=False, deleted=False)

                        # Sempre personaliza a ocorrência para mencionar apenas este militar
                        try:
                            transgressao_acusado = personalizar_ocorrencia(
                                transgressao_comum,
                                acusado.posto_graduacao or militar.posto or '',
                                acusado.nome_guerra or militar.nome_guerra or '',
                            )
                        except Exception as _e:
                            logger.warning(f"Falha ao personalizar ocorrência para {militar}: {_e}")
                            transgressao_acusado = (acusado.transgressao_individual or '').strip() or transgressao_comum

                        duplicata = False
                        for patd_existente in existing_patds:
                            if verifica_similaridade(transgressao_acusado.strip().lower(), patd_existente.transgressao.strip().lower()):
                                patd_url = reverse('Ouvidoria:patd_detail', kwargs={'pk': patd_existente.pk})
                                duplicatas_encontradas.append({
                                    'nome_militar': str(militar),
                                    'numero_patd': patd_existente.numero_patd,
                                    'url': patd_url
                                })
                                duplicata = True
                                logger.info(f"PATD duplicada encontrada para {militar}: Nº {patd_existente.numero_patd}")
                                break

                        if not duplicata:
                            itens_pre_enquadrados = []
                            try:
                                resultado_itens = enquadra_item(transgressao_acusado)
                                itens_pre_enquadrados = resultado_itens.item if resultado_itens and resultado_itens.item else []
                            except Exception as _e:
                                logger.warning(f"Falha ao pré-enquadrar itens para {militar}: {_e}")

                            militares_para_confirmacao.append({
                                'id': militar.id,
                                'nome_guerra': militar.nome_guerra,
                                'nome_completo': militar.nome_completo,
                                'saram': militar.saram,
                                'posto': militar.posto,
                                'transgressao_individual': transgressao_acusado,
                                'itens_enquadrados': itens_pre_enquadrados,
                            })
                    else:
                        logger.warning(f"Militar '{acusado.nome_completo or acusado.nome_guerra}' não encontrado no banco de dados.")
                        nome_para_cadastro = f"{acusado.posto_graduacao or ''} {acusado.nome_completo or acusado.nome_guerra}".strip()
                        try:
                            transgressao_acusado = personalizar_ocorrencia(
                                transgressao_comum,
                                acusado.posto_graduacao or '',
                                acusado.nome_guerra or acusado.nome_completo or '',
                            )
                        except Exception as _e:
                            logger.warning(f"Falha ao personalizar ocorrência para não encontrado '{nome_para_cadastro}': {_e}")
                            transgressao_acusado = (acusado.transgressao_individual or '').strip() or transgressao_comum
                        itens_pre_enquadrados_nao_enc = []
                        try:
                            resultado_itens_nao_enc = enquadra_item(transgressao_acusado)
                            itens_pre_enquadrados_nao_enc = resultado_itens_nao_enc.item if resultado_itens_nao_enc and resultado_itens_nao_enc.item else []
                        except Exception as _e:
                            logger.warning(f"Falha ao pré-enquadrar itens para não encontrado '{nome_para_cadastro}': {_e}")

                        militares_nao_encontrados.append({
                            'nome_completo_sugerido': nome_para_cadastro,
                            'transgressao': transgressao_acusado,
                            'data_ocorrencia': data_ocorrencia_str,
                            'protocolo_comaer': protocolo_comaer_comum,
                            'oficio_transgressao': oficio_transgressao_comum,
                            'data_oficio': data_oficio_str,
                            'itens_enquadrados': itens_pre_enquadrados_nao_enc,
                        })
                
                total_pendentes = len(militares_para_confirmacao) + len(militares_nao_encontrados)
                if total_pendentes > 0:
                    request.session['oficio_lancamento'] = {
                        'path': temp_file_path,
                        'count': total_pendentes
                    }
                else:
                    try:
                        os.remove(temp_file_path)
                    except OSError as e:
                        logger.error(f"Erro ao remover ficheiro temporário {temp_file_path}: {e}")

                response_data = {
                    'status': 'processed',
                    'militares_para_confirmacao': militares_para_confirmacao,
                    'militares_nao_encontrados': militares_nao_encontrados,
                    'duplicatas_encontradas': duplicatas_encontradas,
                    'transgressao_data': request.session.get('analise_transgressao_data', {})
                }
                logger.info(f"Análise concluída. Resposta: {response_data}")
                return JsonResponse(response_data)

            except Exception as e:
                import openai as _openai
                error_type = type(e).__name__
                error_message = str(e)
                logger.error(
                    "Erro na análise do PDF: %s - %s",
                    error_type, error_message, exc_info=True,
                )

                if isinstance(e, _openai.RateLimitError):
                    if 'insufficient_quota' in error_message:
                        user_message = (
                            "Os créditos da API de IA foram esgotados. "
                            "O administrador do sistema (Informática) precisa recarregar "
                            "os créditos em platform.openai.com para restaurar a funcionalidade."
                        )
                    else:
                        user_message = (
                            "A API de IA está temporariamente sobrecarregada. "
                            "Aguarde 1 minuto e tente novamente."
                        )
                    return JsonResponse(
                        {'status': 'error', 'message': user_message, 'detail': error_message},
                        status=429,
                    )

                if isinstance(e, _openai.AuthenticationError):
                    user_message = (
                        "Chave de API da IA inválida ou expirada. "
                        "Contate o administrador do sistema (Informática)."
                    )
                    return JsonResponse(
                        {'status': 'error', 'message': user_message, 'detail': error_message},
                        status=503,
                    )

                user_message = (
                    f"Ocorreu um erro inesperado durante a análise ({error_type}). "
                    "Verifique os logs do servidor para mais detalhes."
                )
                return JsonResponse(
                    {'status': 'error', 'message': user_message, 'detail': f"{error_type}: {error_message}"},
                    status=500,
                )

    # Lógica para GET request (permanece igual)
    return render(request, 'indexOuvidoria.html', context)


@login_required
@ouvidoria_required
@require_POST
def enquadrar_itens_view(request):
    """Recebe uma transgressão e retorna os itens enquadrados pela IA."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

    transgressao = data.get('transgressao', '').strip()
    if not transgressao:
        return JsonResponse({'status': 'error', 'message': 'Transgressão não fornecida.'}, status=400)

    try:
        resultado = enquadra_item(transgressao)
        itens = resultado.item if resultado and resultado.item else []
        return JsonResponse({'status': 'success', 'itens': itens})
    except Exception as e:
        logger.error(f"Erro ao enquadrar itens: {e}")
        return JsonResponse({'status': 'error', 'message': 'Erro ao processar o enquadramento.'}, status=500)


@method_decorator([login_required, comandante_redirect, ouvidoria_required], name='dispatch')
class PATDListView(ListView):
    model = PATD
    template_name = 'patd_list.html'
    context_object_name = 'patds'
    paginate_by = 15

    def get_queryset(self):
        from django.utils import timezone as _tz
        query = self.request.GET.get('q')
        status_filter = self.request.GET.get('status')
        fase_key = self.request.GET.get('fase')
        ano = self.request.GET.get('ano', str(_tz.now().year))

        # --- Sorting Logic ---
        sort_by = self.request.GET.get('sort', '-numero_patd') # Default sort by PATD number descending
        valid_sort_fields = ['numero_patd', '-numero_patd', 'data_inicio', '-data_inicio']
        if sort_by not in valid_sort_fields:
            sort_by = '-numero_patd' # Fallback to default if invalid sort is provided

        qs = super().get_queryset().exclude(status='finalizado').exclude(arquivado=True).select_related('militar', 'oficial_responsavel').order_by(sort_by)

        # Filtro de ano
        try:
            qs = qs.filter(data_inicio__year=int(ano))
        except (ValueError, TypeError):
            pass


        if query:
            qs = qs.filter(
                Q(numero_patd__icontains=query) |
                Q(militar__nome_completo__icontains=query) |
                Q(militar__nome_guerra__icontains=query) |
                Q(militar__saram__icontains=query)
            )

        if fase_key:
            phase = next((p for p in PHASE_GROUPS if p['key'] == fase_key), None)
            if phase:
                qs = qs.filter(status__in=phase['statuses'])

        if status_filter:
            if status_filter in STATUS_GROUPS:
                statuses_in_group = list(STATUS_GROUPS[status_filter].keys())
                qs = qs.filter(status__in=statuses_in_group)
            else:
                qs = qs.filter(status=status_filter)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = Configuracao.load()
        context['prazo_defesa_dias'] = config.prazo_defesa_dias
        context['prazo_defesa_minutos'] = config.prazo_defesa_minutos
        context['status_groups'] = STATUS_GROUPS

        # Notificação: PATDs aguardando aceitação do oficial logado
        user_militar = getattr(getattr(self.request.user, 'profile', None), 'militar', None)
        if user_militar:
            context['patds_pendentes_aceitacao'] = PATD.objects.filter(
                oficial_responsavel=user_militar,
                oficial_aceitou=None,
                status='finalizado'
            ).count()
        context['current_status'] = self.request.GET.get('status', '')
        context['current_fase'] = self.request.GET.get('fase', '')

        # Phase tab counts (base queryset without phase/status filter)
        from django.utils import timezone as _tz
        _ano = self.request.GET.get('ano', str(_tz.now().year))
        base_qs = PATD.objects.exclude(status='finalizado').exclude(arquivado=True)
        try:
            base_qs = base_qs.filter(data_inicio__year=int(_ano))
        except (ValueError, TypeError):
            pass
        _q = self.request.GET.get('q')
        if _q:
            base_qs = base_qs.filter(
                Q(numero_patd__icontains=_q) |
                Q(militar__nome_completo__icontains=_q) |
                Q(militar__nome_guerra__icontains=_q) |
                Q(militar__saram__icontains=_q)
            )
        phases_with_counts = []
        for phase in PHASE_GROUPS:
            count = base_qs.filter(status__in=phase['statuses']).count()
            phases_with_counts.append({**phase, 'count': count})
        context['phase_groups'] = phases_with_counts

        # Ano selecionado
        from django.utils import timezone as _tz
        context['ano'] = self.request.GET.get('ano', str(_tz.now().year))
        from Ouvidoria.models import PATD as _PATD
        context['anos_disponiveis'] = sorted(set(
            _PATD.objects.dates('data_inicio', 'year').values_list('data_inicio__year', flat=True)
        ), reverse=True)

        # --- Sorting Context ---
        sort = self.request.GET.get('sort', '-numero_patd')
        context['current_sort'] = sort
        
        # Determine the next sort direction for the 'numero_patd' column
        if sort == 'numero_patd':
            context['numero_patd_next_sort'] = '-numero_patd'
        else: # Covers '-numero_patd' and any other default
            context['numero_patd_next_sort'] = 'numero_patd'
            
        return context


@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PatdFinalizadoListView(ListView):
    model = PATD
    template_name = 'patd_finalizado_list.html'
    context_object_name = 'patds'
    paginate_by = 15

    def get_queryset(self):
        return PATD.objects.filter(status='finalizado').select_related('militar', 'oficial_responsavel').order_by('-data_inicio')


@method_decorator([login_required, user_passes_test(lambda u: u.is_superuser)], name='dispatch')
class PATDTrashListView(ListView):
    model = PATD
    template_name = 'patd_trash_list.html'
    context_object_name = 'patds'
    paginate_by = 15

    def get_queryset(self):
        return PATD.all_objects.filter(deleted=True).select_related('militar').order_by('-deleted_at')


@method_decorator([login_required, user_passes_test(has_patd_detail_access)], name='dispatch')
class PATDDetailView(DetailView):
    model = PATD
    template_name = 'patd_detail.html'
    context_object_name = 'patd'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        return response

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        return response

    def get_queryset(self):
        # Mudamos de super().get_queryset() para PATD.all_objects
        return PATD.all_objects.select_related(
            'militar', 'oficial_responsavel', 'testemunha1', 'testemunha2'
        ).prefetch_related('anexos')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patd = self.get_object()

        # --- INÍCIO DA MODIFICAÇÃO: Sincronização de Assinatura ---
        # Garante que a assinatura do oficial seja copiada para a PATD se for adicionada posteriormente.
        if _sync_oficial_signature(patd):
            patd.refresh_from_db() # Recarrega a PATD se a assinatura foi adicionada
        # --- FIM DA MODIFICAÇÃO ---

        # Força o recarregamento do objeto oficial_responsavel para garantir 
        # que quaisquer alterações (como a assinatura) sejam refletidas.
        if patd.oficial_responsavel:
            patd.oficial_responsavel.refresh_from_db()

        config = Configuracao.load()

        # --- INÍCIO DA MODIFICAÇÃO: Verificação Proativa ---
        # Se a PATD está em reconsideração, verifica se já pode avançar.
        # Isso corrige casos em que a página é recarregada após a assinatura
        # e o status ainda não foi atualizado.
        if patd.status == 'em_reconsideracao':
            _check_and_advance_reconsideracao_status(patd.pk)

        document_pages = get_document_pages(patd)
        context['documento_texto_json'] = json.dumps(document_pages)

        context['assinaturas_militar_json'] = json.dumps(patd.assinaturas_militar or [])


        context['now_iso'] = timezone.now().isoformat()
        context['prazo_defesa_dias'] = config.prazo_defesa_dias
        context['prazo_defesa_minutos'] = config.prazo_defesa_minutos

        context['locked_statuses_for_edit'] = []

        doc_context = _get_document_context(patd)
        context['comandante_assinatura'] = doc_context.get('assinatura_comandante_data')

        context['analise_data_json'] = json.dumps({
            'itens': patd.itens_enquadrados,
            'circunstancias': patd.circunstancias,
            'punicao': patd.punicao_sugerida
        }) if patd.punicao_sugerida else 'null'

        militar_acusado = patd.militar
        patds_anteriores = PATD.objects.filter(
            militar=militar_acusado
        ).exclude(pk=patd.pk).order_by('-data_inicio')

        historico_punicoes = []
        for p_antiga in patds_anteriores:
            # Inclui no histórico se houve punição OU se foi justificado
            if p_antiga.punicao or p_antiga.justificado:
                itens_str = ""
                if p_antiga.itens_enquadrados and isinstance(p_antiga.itens_enquadrados, list):
                    itens_str = ", ".join([str(item.get('numero', '')) for item in p_antiga.itens_enquadrados if 'numero' in item])

                # Define a string da punição
                punicao_str = "Transgressão Justificada"
                if not p_antiga.justificado and p_antiga.punicao:
                    punicao_str = f"{p_antiga.dias_punicao} de {p_antiga.punicao}" if p_antiga.dias_punicao else p_antiga.punicao

                historico_punicoes.append({
                    'pk': p_antiga.pk, # Adiciona a PK para o link
                    'numero_patd': p_antiga.numero_patd,
                    'punicao': punicao_str,
                    'itens': itens_str,
                    'data': p_antiga.data_inicio.strftime('%d/%m/%Y'),
                    'circunstancias': p_antiga.circunstancias
                })

        context['historico_punicoes'] = historico_punicoes

        # ── Avisos de assinaturas pendentes por fase ─────────────────────────
        assinaturas_pendentes = []
        s = patd.status

        if s == 'confeccao_fr_ficha':
            if not patd.anexos.filter(tipo='formulario_resumo').exists():
                assinaturas_pendentes.append({
                    'quem': 'Ouvidoria',
                    'descricao': 'Anexar Formulário de Resumo (FR)',
                    'urgente': True,
                })
            if not patd.anexos.filter(tipo='ficha_individual').exists():
                assinaturas_pendentes.append({
                    'quem': 'Ouvidoria',
                    'descricao': 'Anexar Ficha Individual',
                    'urgente': True,
                })

        if s == 'ciencia_militar':
            if not (patd.assinaturas_militar and len(patd.assinaturas_militar) > 0):
                assinaturas_pendentes.append({
                    'quem': 'Militar Arrolado',
                    'descricao': 'Assinatura de Ciência (tomar conhecimento da instauração)',
                    'urgente': True,
                })

        if s in ('aguardando_justificativa',):
            if not patd.assinatura_alegacao_defesa:
                assinaturas_pendentes.append({
                    'quem': 'Militar Arrolado',
                    'descricao': 'Assinatura na Alegação de Defesa',
                    'urgente': True,
                })

        # Em apuração: apenas aviso de oficial (doc ainda não gerado, testemunhas assinam depois)
        if s in ('preclusao', 'em_apuracao', 'apuracao_preclusao'):
            if not patd.assinatura_oficial:
                assinaturas_pendentes.append({
                    'quem': 'Oficial Responsável',
                    'descricao': f'Assinatura do Oficial ({patd.oficial_responsavel or "não atribuído"})',
                    'urgente': False,
                })

        # Aguardando punição: apenas assinatura do oficial pendente (testemunhas e militar assinam após retorno do comandante)
        if s in ('aguardando_punicao', 'aguardando_punicao_alterar'):
            if not patd.assinatura_oficial:
                assinaturas_pendentes.append({
                    'quem': 'Oficial Responsável',
                    'descricao': f'Assinatura do Oficial ({patd.oficial_responsavel or "não atribuído"})',
                    'urgente': False,
                })

        if s == 'aguardando_assinatura_npd':
            if not patd.assinatura_oficial:
                assinaturas_pendentes.append({
                    'quem': f'Oficial Responsável — {patd.oficial_responsavel}' if patd.oficial_responsavel else 'Oficial Responsável',
                    'descricao': 'Assinatura na NPD',
                    'urgente': True,
                })
            num_sig_militar = len(patd.assinaturas_militar or [])
            if num_sig_militar == 0:
                assinaturas_pendentes.append({
                    'quem': f'Militar Arrolado — {patd.militar}',
                    'descricao': 'Assinatura na NPD (ainda nenhuma registrada)',
                    'urgente': True,
                })

        if s == 'em_reconsideracao':
            if not patd.assinatura_reconsideracao:
                assinaturas_pendentes.append({
                    'quem': 'Militar Arrolado',
                    'descricao': 'Assinatura no Pedido de Reconsideração',
                    'urgente': True,
                })

        if s in ('aguardando_preenchimento_npd_reconsideracao',):
            num_npd_recon = len(patd.assinaturas_npd_reconsideracao or [])
            if num_npd_recon == 0:
                assinaturas_pendentes.append({
                    'quem': 'Militar Arrolado',
                    'descricao': 'Assinatura na NPD de Reconsideração (ainda nenhuma registrada)',
                    'urgente': True,
                })
            if not patd.assinatura_oficial:
                assinaturas_pendentes.append({
                    'quem': 'Oficial Responsável',
                    'descricao': 'Assinatura na NPD de Reconsideração',
                    'urgente': False,
                })

        context['assinaturas_pendentes'] = assinaturas_pendentes
        # ── Fim avisos de assinaturas ─────────────────────────────────────────

        # Listas para os dropdowns do modal de finalizar
        from Secao_pessoal.models import Efetivo as _Efetivo
        from django.db.models import Q as _Q
        context['oficiais_lista'] = _Efetivo.objects.filter(oficial=True, deleted=False).order_by('nome_guerra')
        # Testemunhas: militares cujo setor ou subsetor contenha "ouvidoria"
        context['efetivos_ouvidoria'] = _Efetivo.objects.filter(
            _Q(setor__icontains='ouvidoria') | _Q(subsetor__icontains='ouvidoria'),
            deleted=False
        ).order_by('nome_guerra')

        # --- INÍCIO DA MODIFICAÇÃO AQUI ---
        # Não vamos mais extrair o HTML, apenas passar os metadados do arquivo.
        
        def _build_anexo_entry(a):
            """Monta dict de metadados de um anexo. PDFs incluem lista de páginas renderizadas."""
            import base64 as _b64
            ext = os.path.splitext(a.arquivo.name)[1].lower().replace('.', '')
            entry = {
                'id': a.id,
                'nome': os.path.basename(a.arquivo.name),
                'url': a.arquivo.url,
                'tipo_arquivo': ext,
            }
            if ext == 'pdf':
                try:
                    import fitz
                    doc = fitz.open(a.arquivo.path)
                    mat = fitz.Matrix(1.5, 1.5)  # ~108 DPI — boa qualidade sem pesar muito
                    pages = []
                    for page in doc:
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        b64 = _b64.b64encode(pix.tobytes('png')).decode()
                        pages.append(f'data:image/png;base64,{b64}')
                    doc.close()
                    entry['pages'] = pages
                except Exception as _e:
                    logger.warning("Não foi possível renderizar PDF %s: %s", a.arquivo.name, _e)
            return entry

        anexos_defesa = patd.anexos.filter(tipo='defesa')
        context['anexos_defesa_json'] = json.dumps([_build_anexo_entry(a) for a in anexos_defesa])

        anexos_reconsideracao = patd.anexos.filter(tipo='reconsideracao')
        context['anexos_reconsideracao_json'] = json.dumps([_build_anexo_entry(a) for a in anexos_reconsideracao])

        ficha_individual_anexo = patd.anexos.filter(tipo='ficha_individual').first()
        context['ficha_individual_anexo'] = ficha_individual_anexo

        formulario_resumo_anexo = patd.anexos.filter(tipo='formulario_resumo').first()
        context['formulario_resumo_anexo'] = formulario_resumo_anexo
        if formulario_resumo_anexo:
            context['formulario_resumo_json'] = json.dumps(_build_anexo_entry(formulario_resumo_anexo))
        else:
            context['formulario_resumo_json'] = 'null'

        anexos_reconsideracao_oficial = patd.anexos.filter(tipo='reconsideracao_oficial')
        context['anexos_reconsideracao_oficial_json'] = json.dumps([_build_anexo_entry(a) for a in anexos_reconsideracao_oficial])

        # --- FIM DA MODIFICAÇÃO ---

        context['user_is_apurador'] = is_apurador(self.request.user)

        return context


@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PATDUpdateView(UserPassesTestMixin, UpdateView):
    model = PATD
    form_class = PATDForm
    template_name = 'patd_form.html'

    def test_func(self):
        user = self.request.user
        if can_edit_patd(user) or has_comandante_access(user):
            return True
        # O oficial responsável pela PATD também pode editar
        patd = self.get_object()
        return (hasattr(user, 'profile') and user.profile.militar and
                user.profile.militar == patd.oficial_responsavel)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Este método é chamado quando os dados do formulário são válidos."""
        messages.success(self.request, "PATD atualizada com sucesso!")
        return super().form_valid(form)

    # --- FIM DA MODIFICAÇÃO ---


    def handle_no_permission(self):
        # This is now called for users who are not superusers and not comandantes.
        messages.error(self.request, "Você não tem permissão para editar este processo.")
        patd_pk = self.kwargs.get('pk')
        if patd_pk:
            return redirect('Ouvidoria:patd_detail', pk=patd_pk)
        return redirect('Ouvidoria:index')

    def get_success_url(self):
        return reverse_lazy('Ouvidoria:patd_detail', kwargs={'pk': self.object.pk})


@method_decorator(login_required, name='dispatch')
class PATDDeleteView(UserPassesTestMixin, DeleteView):
    model = PATD
    template_name = 'militar_confirm_delete.html'
    success_url = reverse_lazy('Ouvidoria:patd_list')

    def test_func(self):
        return can_delete_patd(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "Você não tem permissão para excluir esta PATD.")
        if self.kwargs.get('pk'):
            return redirect('Ouvidoria:patd_detail', pk=self.kwargs.get('pk'))
        return redirect('Ouvidoria:patd_list')

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        numero_original = self.object.numero_patd
        
        self.object.deleted = True
        self.object.deleted_at = timezone.now()
        
        # Salva o número original antes de apagar
        self.object.numero_patd_anterior = numero_original
        self.object.numero_patd = None 
            
        self.object.save()
        messages.success(request, f"A PATD (antigo Nº {numero_original}) foi movida para a lixeira.")
        return redirect(self.get_success_url())


@login_required
@ouvidoria_required
@require_POST
def prosseguir_sem_alegacao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        if patd.status != 'prazo_expirado':
            return JsonResponse({'status': 'error', 'message': 'Ação permitida apenas para PATDs com prazo expirado.'}, status=400)

        # Avança para 'definicao_oficial' para atribuir o oficial apurador
        # antes de abrir o Termo de Preclusão.
        patd.status = 'definicao_oficial'
        patd.save(update_fields=['status'])
        return JsonResponse({'status': 'success', 'message': 'Prazo encerrado sem defesa. Atribua o oficial apurador para prosseguir.'})
    except Exception as e:
        logger.error(f"Erro ao prosseguir sem alegação para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@ouvidoria_required
@require_POST
def excluir_anexo(request, pk):
    try:
        anexo = get_object_or_404(Anexo, pk=pk)

        if anexo.arquivo and os.path.isfile(anexo.arquivo.path):
            os.remove(anexo.arquivo.path)

        anexo.delete()

        return JsonResponse({'status': 'success', 'message': 'Anexo excluído com sucesso.'})
    except Http404:
        return JsonResponse({'status': 'error', 'message': 'Anexo não encontrado.'}, status=404)
    except Exception as e:
        logger.error(f"Erro ao excluir anexo {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@oficial_responsavel_required # Alterado para oficial_responsavel_required
@require_POST
def finalizar_publicacao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)

        # Apenas quem tem acesso à Ouvidoria pode finalizar
        if not has_ouvidoria_access(request.user):
             messages.error(request, "Você não tem permissão para finalizar este processo.")
             return redirect('Ouvidoria:patd_detail', pk=pk)

        boletim = request.POST.get('boletim_publicacao')

        if not boletim or not boletim.strip():
            messages.error(request, "O número do boletim é obrigatório para finalizar o processo.")
            return redirect('Ouvidoria:patd_detail', pk=pk)

        patd.boletim_publicacao = boletim
        patd.status = 'finalizado'
        patd.data_termino = timezone.now()

        # Se houve reconsideração com nova punição, promove para os campos principais
        if patd.nova_punicao_tipo:
            patd.dias_punicao = patd.nova_punicao_dias or ""
            patd.punicao = patd.nova_punicao_tipo
            patd.punicao_sugerida = f"{patd.dias_punicao} de {patd.punicao}" if patd.dias_punicao else patd.punicao
            patd.definir_natureza_transgressao()
            patd.calcular_e_atualizar_comportamento()

        patd.save()

        messages.success(request, f"PATD Nº {patd.numero_patd} finalizada com sucesso e publicada no boletim {boletim}.")
        return redirect('Ouvidoria:patd_detail', pk=pk)
    except Exception as e:
        logger.error(f"Erro ao finalizar PATD {pk}: {e}")
        messages.error(request, "Ocorreu um erro ao tentar finalizar o processo.")
        return redirect('Ouvidoria:patd_detail', pk=pk)


@login_required
@oficial_responsavel_required
@require_POST
def justificar_patd(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        motivo = data.get('motivo_justificativa')

        if not motivo or not motivo.strip():
             return JsonResponse({'status': 'error', 'message': 'É obrigatório informar o motivo da justificativa.'}, status=400)

        if patd.status not in ['em_apuracao', 'apuracao_preclusao']:
             return JsonResponse({'status': 'error', 'message': 'A PATD não está na fase correta para ser justificada.'}, status=400)

        # Limpar dados de punição
        patd.punicao = ""
        patd.dias_punicao = ""

        patd.justificado = True
        patd.justificativa_texto = motivo  # Salva o motivo personalizado
        patd.status = 'finalizado'
        patd.data_termino = timezone.now()

        patd.punicao_sugerida = "Transgressão Justificada"
        
        # Atualiza o relatório com o motivo digitado pelo usuário
        patd.texto_relatorio = f"""Após análise dos fatos, alegações e circunstâncias, este Oficial Apurador conclui que a transgressão disciplinar imputada ao militar está JUSTIFICADA, nos termos do Art. 13, item 1 do RDAER.
        
        Motivo da Justificativa:
        {motivo}"""

        patd.save()
        return JsonResponse({'status': 'success', 'message': 'A transgressão foi justificada e o processo finalizado com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao justificar a PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@oficial_responsavel_required
@require_POST
def salvar_nova_punicao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

        dias_str = data.get('dias')
        if dias_str is None:
            return JsonResponse({'status': 'error', 'message': 'O número de dias é obrigatório.'}, status=400)

        dias = int(dias_str)
        tipo = data.get('tipo')

        if dias < 0 or not tipo:
            return JsonResponse({'status': 'error', 'message': 'Dados inválidos.'}, status=400)

        # Salva a nova punição nos campos dedicados sem sobrescrever a punição original
        if tipo == 'repreensão':
            patd.nova_punicao_dias = ""
            patd.nova_punicao_tipo = "repreensão"
        else:
            dias_texto = num2words(dias, lang='pt_BR')
            patd.nova_punicao_dias = f"{dias_texto} ({dias:02d}) dias"
            patd.nova_punicao_tipo = tipo

        # Recalcula comportamento com base na nova punição (simulado sobre os campos originais)
        import copy
        patd_simulado = copy.copy(patd)
        patd_simulado._state = copy.copy(patd._state)
        patd_simulado.dias_punicao = patd.nova_punicao_dias
        patd_simulado.punicao = patd.nova_punicao_tipo
        patd_simulado.calcular_e_atualizar_comportamento()
        patd.comportamento = patd_simulado.comportamento

        patd.status = 'aguardando_publicacao'
        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Nova punição salva com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar nova punição para PATD {pk}: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@oficial_responsavel_required
@require_POST
def preview_nova_punicao(request, pk):
    """
    Calcula e retorna o comportamento e natureza resultantes de uma nova punição
    sem salvar no banco — usado para preview em tempo real no formulário.
    """
    try:
        patd = get_object_or_404(PATD, pk=pk)
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

        dias_str = data.get('dias', 0)
        tipo = data.get('tipo', '')

        if not tipo:
            return JsonResponse({'status': 'error', 'message': 'Tipo de punição obrigatório.'}, status=400)

        dias = int(dias_str)

        # Cria uma cópia em memória para simular o cálculo sem salvar
        import copy
        patd_simulado = copy.copy(patd)
        patd_simulado._state = copy.copy(patd._state)

        if tipo == 'repreensão':
            patd_simulado.dias_punicao = ""
            patd_simulado.punicao = "repreensão"
        else:
            dias_texto = num2words(dias, lang='pt_BR')
            patd_simulado.dias_punicao = f"{dias_texto} ({dias:02d}) dias"
            patd_simulado.punicao = tipo

        patd_simulado.definir_natureza_transgressao()
        patd_simulado.calcular_e_atualizar_comportamento()

        return JsonResponse({
            'status': 'success',
            'comportamento': patd_simulado.comportamento,
            'natureza': patd_simulado.natureza_transgressao or 'Não definida',
        })
    except Exception as e:
        logger.error(f"Erro ao calcular preview de nova punição para PATD {pk}: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@method_decorator([login_required, comandante_redirect, ouvidoria_required], name='dispatch')
class PatdArquivadoListView(ListView):
    model = PATD
    template_name = 'patd_arquivado_list.html'
    context_object_name = 'patds'
    paginate_by = 15

    def get_queryset(self):
        # O resto permanece igual...
        return PATD.objects.filter(arquivado=True).select_related('militar').order_by('-data_inicio')


@login_required
@ouvidoria_required
@require_POST
def arquivar_patd(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    motivo = request.POST.get('motivo_arquivamento', '')
    
    if not motivo:
        messages.error(request, 'O motivo do arquivamento é obrigatório.')
        return redirect(request.META.get('HTTP_REFERER', 'Ouvidoria:patd_list'))
    
    if patd.arquivado:
        messages.error(request, 'A PATD já está arquivada.')
        return redirect(request.META.get('HTTP_REFERER', 'Ouvidoria:patd_list'))

    # Salva o número original e remove o número principal (igual na lixeira)
    numero_original = patd.numero_patd
    
    # Tratamento caso haja alguma PATD antiga arquivada com número negativo
    if numero_original and numero_original < 0:
        numero_original = abs(numero_original)
        
    patd.numero_patd_anterior = numero_original
    patd.numero_patd = None 
    
    patd.arquivado = True
    patd.motivo_arquivamento = motivo
    patd.save()
    
    messages.success(request, f'A PATD Nº {numero_original} foi arquivada com sucesso.')

    return redirect('Ouvidoria:patd_arquivado_list')


@login_required
@ouvidoria_required
@require_POST
def desarquivar_patd(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    numero_antigo = patd.numero_patd_anterior

    patd.arquivado = False
    # Gera um novo número limpo e tira o registro do número antigo
    patd.numero_patd = get_next_patd_number()
    patd.numero_patd_anterior = None 
    patd.save()
    
    messages.success(request, f'A PATD (antigo Nº {numero_antigo}) foi desarquivada e recebeu o novo número {patd.numero_patd}.')
    return redirect('Ouvidoria:patd_arquivado_list')


@method_decorator([login_required, user_passes_test(lambda u: u.is_superuser)], name='dispatch')
class PATDTrashView(ListView):
    model = PATD
    template_name = 'patd_trash_list.html'
    context_object_name = 'patds'
    paginate_by = 15

    def get_queryset(self):
        return PATD.all_objects.filter(deleted=True).select_related('militar').order_by('-deleted_at')

    def get_context_data(self, **kwargs):
        from ..models import Configuracao
        ctx = super().get_context_data(**kwargs)
        ctx['config'] = Configuracao.load()
        ctx['total_lixeira'] = PATD.all_objects.filter(deleted=True).count()
        return ctx


@login_required
@user_passes_test(lambda u: u.is_superuser) # Bloqueia para não-admins
@require_POST
def patd_restore(request, pk):
    patd = get_object_or_404(PATD.all_objects, pk=pk)
    numero_antigo = patd.numero_patd_anterior

    patd.deleted = False
    patd.restored_at = timezone.now()
    patd.restored_by = request.user.profile.militar
    
    patd.numero_patd = get_next_patd_number()
    patd.numero_patd_anterior = None
    
    patd.save()
    messages.success(request, f'A PATD (antigo Nº {numero_antigo}) foi restaurada com sucesso e recebeu o novo Nº {patd.numero_patd}.')
    return redirect('Ouvidoria:patd_trash')


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def patd_permanently_delete(request, pk):
    patd = get_object_or_404(PATD.all_objects, pk=pk)
    numero = patd.numero_patd_anterior
    patd.delete()
    messages.success(request, f'A PATD Nº {numero} foi excluída permanentemente.')
    return redirect('Ouvidoria:patd_trash')


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def lixeira_esvaziar(request):
    """Exclui permanentemente todas as PATDs na lixeira."""
    from ..models import Configuracao
    count = PATD.all_objects.filter(deleted=True).count()
    PATD.all_objects.filter(deleted=True).delete()
    messages.success(request, f'{count} PATD(s) excluída(s) permanentemente da lixeira.')
    return redirect('Ouvidoria:patd_trash')


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def lixeira_config(request):
    """Atualiza a configuração de retenção da lixeira."""
    from ..models import Configuracao
    config = Configuracao.load()
    try:
        dias = int(request.POST.get('dias_retencao_lixeira', 30))
        if dias < 1:
            dias = 1
        config.dias_retencao_lixeira = dias
        config.save()
        messages.success(request, f'Prazo de retenção atualizado para {dias} dias.')
    except (ValueError, TypeError):
        messages.error(request, 'Valor inválido para o prazo de retenção.')
    return redirect('Ouvidoria:patd_trash')


@login_required
@finalizar_ouvidoria_required
@require_POST
def finalizar_patd_completa(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        
        # 1. Validação de Senha do usuário logado (Ouvidoria)
        senha = request.POST.get('senha')
        user = authenticate(username=request.user.username, password=senha)
        if user is None:
            messages.error(request, "Senha incorreta. A PATD não foi finalizada.")
            return redirect('Ouvidoria:patd_detail', pk=pk)

        # 2. Resgate de Dados do Formulário
        documento = request.FILES.get('documento_final')
        tipo_punicao = request.POST.get('tipo_punicao')
        dias = request.POST.get('dias_punicao', 0)
        motivo = request.POST.get('motivo_justificativa')
        boletim = request.POST.get('boletim_publicacao')
        oficial_id = request.POST.get('oficial_responsavel_id')
        testemunha1_id = request.POST.get('testemunha1_id')
        testemunha2_id = request.POST.get('testemunha2_id')
        itens_numeros = request.POST.get('itens_enquadrados_numeros', '').strip()

        if not boletim or not tipo_punicao or not documento:
            messages.error(request, "Preencha todos os campos obrigatórios (Boletim, Punição e Documento Final).")
            return redirect('Ouvidoria:patd_detail', pk=pk)

        # 3. Processamento do Resultado e Punição
        if tipo_punicao == 'justificada':
            if not motivo or not motivo.strip():
                messages.error(request, "O motivo da justificativa é obrigatório para transgressões justificadas.")
                return redirect('Ouvidoria:patd_detail', pk=pk)
            
            patd.justificado = True
            patd.justificativa_texto = motivo
            patd.punicao = ""
            patd.dias_punicao = ""
            patd.punicao_sugerida = "Transgressão Justificada"
            patd.texto_relatorio = f"Transgressão JUSTIFICADA. Motivo: {motivo}"
        else:
            patd.justificado = False
            if tipo_punicao in ['repreensão por escrito', 'repreensão verbal']:
                patd.punicao = tipo_punicao
                patd.dias_punicao = ""
            else:
                patd.punicao = tipo_punicao
                try:
                    dias_int = int(dias)
                    dias_texto = num2words(dias_int, lang='pt_BR')
                    patd.dias_punicao = f"{dias_texto} ({dias_int:02d}) dias"
                except ValueError:
                    patd.dias_punicao = "0 dias"
            
            patd.punicao_sugerida = f"{patd.dias_punicao} de {patd.punicao}" if patd.dias_punicao else patd.punicao

        # Salva o número do boletim
        patd.boletim_publicacao = boletim

        # Atribuição de oficial e testemunhas (com rastreamento de aceitação)
        from Secao_pessoal.models import Efetivo as _Efetivo
        if oficial_id:
            try:
                novo_oficial = _Efetivo.objects.get(pk=oficial_id, oficial=True)
                if patd.oficial_responsavel_id != novo_oficial.pk:
                    patd.oficial_responsavel = novo_oficial
                    patd.oficial_aceitou = None  # pendente aceitação
            except _Efetivo.DoesNotExist:
                pass
        from django.db.models import Q as _Q
        _ouvidoria_ids = set(_Efetivo.objects.filter(
            _Q(setor__icontains='ouvidoria') | _Q(subsetor__icontains='ouvidoria'),
            deleted=False
        ).values_list('pk', flat=True))
        if testemunha1_id:
            try:
                t1 = _Efetivo.objects.get(pk=testemunha1_id)
                if int(testemunha1_id) in _ouvidoria_ids:
                    patd.testemunha1 = t1
            except _Efetivo.DoesNotExist:
                pass
        if testemunha2_id:
            try:
                t2 = _Efetivo.objects.get(pk=testemunha2_id)
                if int(testemunha2_id) in _ouvidoria_ids:
                    patd.testemunha2 = t2
            except _Efetivo.DoesNotExist:
                pass

        # 4. Anexar o Documento Final Completo
        Anexo.objects.create(patd=patd, arquivo=documento, tipo='documento_final')

        # 5a. Processar itens enquadrados (só números, ex: "10, 13, 15")
        if itens_numeros:
            itens_list = []
            for parte in itens_numeros.split(','):
                n = parte.strip()
                if n:
                    try:
                        itens_list.append({'numero': int(n), 'descricao': ''})
                    except ValueError:
                        itens_list.append({'numero': n, 'descricao': ''})
            if itens_list:
                patd.itens_enquadrados = itens_list

        # 5b. Fechamento e Atualização de Histórico Militar
        patd.definir_natureza_transgressao()
        patd.calcular_e_atualizar_comportamento() # Altera para "Mau comportamento" se necessário

        patd.status = 'finalizado'
        patd.data_termino = timezone.now()

        patd.save()

        messages.success(request, f"PATD Nº {patd.numero_patd} de {patd.militar.nome_guerra} foi finalizada, documentada e arquivada com sucesso!")
        return redirect('Ouvidoria:patd_detail', pk=pk)

    except Exception as e:
        logger.error(f"Erro ao finalizar PATD Completa {pk}: {e}", exc_info=True)
        messages.error(request, "Ocorreu um erro ao tentar finalizar o processo.")
        return redirect('Ouvidoria:patd_detail', pk=pk)


@login_required
@require_POST
def aceitar_atribuicao_patd(request, pk):
    """Oficial aceita ou recusa a atribuição como responsável pela PATD."""
    patd = get_object_or_404(PATD, pk=pk)

    user_militar = getattr(getattr(request.user, 'profile', None), 'militar', None)
    if not user_militar or patd.oficial_responsavel_id != user_militar.pk:
        return JsonResponse({'status': 'error', 'message': 'Não autorizado.'}, status=403)

    acao = request.POST.get('acao')
    if acao == 'aceitar':
        patd.oficial_aceitou = True
        fields = ['oficial_aceitou']
        # Se a PATD já foi finalizada (data_termino preenchido) mas ficou aguardando
        # aceitação do oficial atribuído durante a finalização, retorna direto para finalizado.
        if patd.data_termino and patd.status == 'aguardando_aprovacao_atribuicao':
            patd.status = 'finalizado'
            fields.append('status')
        patd.save(update_fields=fields)
        return JsonResponse({'status': 'success', 'message': 'Atribuição aceita. A PATD aparece agora no seu histórico.'})
    elif acao == 'recusar':
        patd.oficial_aceitou = False
        patd.save(update_fields=['oficial_aceitou'])
        return JsonResponse({'status': 'success', 'message': 'Atribuição recusada.'})

    return JsonResponse({'status': 'error', 'message': 'Ação inválida.'}, status=400)


