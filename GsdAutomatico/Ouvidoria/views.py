import pandas as pd
import io
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Max, Case, When, Value, IntegerField, Count
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from .models import Militar, PATD, Configuracao, Anexo
from .forms import MilitarForm, PATDForm, AtribuirOficialForm, AceitarAtribuicaoForm
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import os
import tempfile
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
from django.conf import settings
import locale
import docx
import re
from django.templatetags.static import static
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from .analise_transgressao import enquadra_item, verifica_agravante_atenuante, sugere_punicao, model, analisar_e_resumir_defesa, reescrever_ocorrencia, texto_relatorio
from difflib import SequenceMatcher # Importado para a verificação de similaridade
from django.utils.decorators import method_decorator
from num2words import num2words # Importação para converter números em texto
from django.contrib.auth import authenticate
from functools import wraps # Importado para criar o decorator
import threading # Importado para tarefas em background
from .permissions import has_comandante_access, has_ouvidoria_access
import base64
from django.core.files.base import ContentFile
from uuid import uuid4


# --- Funções e Mixins de Permissão ---
def comandante_redirect(view_func):
    """
    Decorator for views that checks that the user is NOT a comandante,
    redirecting to the comandante dashboard if they are.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if has_comandante_access(request.user) and not request.user.is_superuser:
            return redirect('Ouvidoria:comandante_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

# --- NOVO DECORATOR ---
def oficial_responsavel_required(view_func):
    """
    Decorator que verifica se o usuário logado é o oficial responsável pela PATD.
    """
    @wraps(view_func)
    def _wrapped_view(request, pk, *args, **kwargs):
        patd = get_object_or_404(PATD, pk=pk)
        
        # Verifica se o usuário tem um perfil militar e se ele é o oficial responsável
        if (hasattr(request.user, 'profile') and 
            request.user.profile.militar and 
            request.user.profile.militar == patd.oficial_responsavel):
            return view_func(request, pk, *args, **kwargs)
        else:
            messages.error(request, "Acesso negado. Apenas o oficial apurador designado pode executar esta ação.")
            return redirect('Ouvidoria:patd_detail', pk=pk)
    return _wrapped_view

class OuvidoriaAccessMixin(UserPassesTestMixin):
    """Mixin para Class-Based Views para verificar a permissão de acesso à Ouvidoria."""
    def test_func(self):
        return has_ouvidoria_access(self.request.user)

class ComandanteAccessMixin(UserPassesTestMixin):
    """Mixin para Class-Based Views para verificar a permissão de acesso do Comandante."""
    def test_func(self):
        return has_comandante_access(self.request.user)

ouvidoria_required = user_passes_test(has_ouvidoria_access)
comandante_required = user_passes_test(has_comandante_access)


# Configuração de logging para depuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Define o locale para português do Brasil para formatar as datas
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    logger.warning("Locale pt_BR.UTF-8 não encontrado. A data pode não ser formatada corretamente.")

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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

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

            has_content = bool(patd.texto_reconsideracao or patd.anexos.filter(tipo='reconsideracao').exists())
            has_signature = bool(patd.assinatura_reconsideracao)

            logger.info(f"PATD {patd.pk}: Current status: {patd.status}, Has Content? {has_content}, Has Signature? {has_signature}")

            if patd.status == 'em_reconsideracao' and has_content:
                patd.status = 'aguardando_comandante_base'
                patd.save(update_fields=['status'])
                logger.info(f"PATD {patd.pk} status advanced to 'aguardando_comandante_base'.")
            else:
                logger.info(f"PATD {patd.pk}: Conditions not met to advance status.")
    except PATD.DoesNotExist:
        logger.error(f"PATD {patd_pk} not found during status check.")
    except Exception as e:
        logger.error(f"Error in _check_and_advance_reconsideracao_status for PATD {patd_pk}: {e}")


# --- Classe para Estruturação da Análise de PDF ---
class AnaliseTransgressao(BaseModel):
    nome_militar: str = Field(description="O nome do militar acusado, sem o posto ou graduação.")
    posto_graduacao: str = Field(description="O posto ou graduação (ex: Sargento, Capitão), se mencionado. Se não, retorne uma string vazia.")
    transgressao: str = Field(description="A descrição detalhada da transgressão disciplinar cometida.")
    local: str = Field(description="O local onde a transgressão ocorreu.")
    data_ocorrencia: str = Field(description="A data em que a transgressão ocorreu, no formato AAAA-MM-DD. Se não for mencionada, retorne uma string vazia.")
    
    # NOVOS CAMPOS ADICIONADOS
    protocolo_comaer: str = Field(description="O número de protocolo COMAER. Ex: 67112.004914/2025-10. Se não for mencionado, retorne uma string vazia.")
    oficio_transgressao: str = Field(description="O número do Ofício de Transgressão. Ex: 189/DSEG/5127. Se não for mencionado, retorne uma string vazia.")
    data_oficio: str = Field(description="A data de emissão do ofício. Ex: Rio de Janeiro, 8 de julho de 2025. Se não for mencionada, retorne uma string vazia.")


def get_next_patd_number():
    """Gera o próximo número sequencial para a PATD."""
    max_num = PATD.objects.aggregate(max_num=Max('numero_patd'))['max_num']
    return (max_num or 0) + 1

# =============================================================================
# FUNÇÕES AUXILIARES MOVIMDAS PARA CIMA PARA CORRIGIR O ERRO
# =============================================================================
def format_militar_string(militar, with_spec=False):
    """
    Formata o nome do militar, colocando o nome de guerra em negrito (com **).
    Lida com casos complexos como 'D. PAULA'.
    """
    if not militar:
        return ""

    nome_completo = militar.nome_completo
    nome_guerra = militar.nome_guerra
    
    # Limpa o nome de guerra de pontuações e divide em partes
    guerra_parts = re.sub(r'[^\w\s]', '', nome_guerra).upper().split()
    
    # Divide o nome completo em palavras para manipulação
    nome_completo_words = nome_completo.split()
    
    # Itera sobre cada parte do nome de guerra
    for part in guerra_parts:
        if len(part) == 1:  # Se for uma inicial (ex: 'D')
            last_match_index = -1
            # Encontra o índice da ÚLTIMA palavra no nome completo que começa com essa inicial
            for i, word in enumerate(nome_completo_words):
                if word.upper().startswith(part):
                    last_match_index = i
            
            # Se encontrou uma correspondência, aplica o negrito apenas na inicial
            if last_match_index != -1:
                word_to_format = nome_completo_words[last_match_index]
                # Coloca em negrito apenas a primeira letra
                formatted_word = f"**{word_to_format[0]}**{word_to_format[1:]}"
                nome_completo_words[last_match_index] = formatted_word
        
        else:  # Se for uma palavra completa (ex: 'PAULA')
            # Procura a palavra exata no nome completo e aplica o negrito
            for i, word in enumerate(nome_completo_words):
                # Remove pontuação da palavra do nome completo para comparação
                clean_word = re.sub(r'[^\w\s]', '', word)
                if clean_word.upper() == part:
                    nome_completo_words[i] = f"**{word}**"
                    break # Para de procurar após encontrar a primeira correspondência

    formatted_name = ' '.join(nome_completo_words)
    posto = getattr(militar, 'posto', '')
    
    if with_spec:
        especializacao = getattr(militar, 'especializacao', '')
        return f"{posto} {especializacao} {formatted_name}".strip()
    else:
        return f"{posto} {formatted_name}".strip()

# =============================================================================
# Otimização da Geração de Documentos
# =============================================================================

def get_anexo_content_as_html(anexo):
    """
    Lê um ficheiro Anexo e retorna o seu conteúdo como uma string HTML.
    Suporta imagens, PDFs, e ficheiros DOCX.
    """
    try:
        file_path = anexo.arquivo.path
        file_url = anexo.arquivo.url
        file_name = os.path.basename(file_path)

        if not os.path.exists(file_path):
            return f"<p><strong>{file_name}</strong>: Erro - Ficheiro não encontrado no servidor.</p>"

        ext = os.path.splitext(file_name)[1].lower()

        if ext in ['.png', '.jpg', '.jpeg', '.gif']:
            with open(file_path, 'rb') as f:
                encoded_string = base64.b64encode(f.read()).decode('utf-8')
                return f'<h4>Anexo: {file_name}</h4><img src="data:image/{ext[1:]};base64,{encoded_string}" style="max-width: 100%; height: auto;" alt="{file_name}"><hr>'
        
        elif ext == '.pdf':
            try:
                loader = PyPDFLoader(file_path)
                pages = loader.load_and_split()
                content = "\n".join([page.page_content for page in pages])
                return f'<h4>Anexo: {file_name}</h4><pre style="white-space: pre-wrap; word-wrap: break-word;">{content}</pre><hr>'
            except Exception as e:
                logger.error(f"Erro ao ler PDF {file_name}: {e}")
                return f'<p><strong>{file_name}</strong>: Não foi possível extrair o texto do PDF. <a href="{file_url}" target="_blank">Fazer download</a></p><hr>'

        elif ext == '.docx':
            try:
                doc = docx.Document(file_path)
                content = "\n".join([para.text for para in doc.paragraphs])
                return f'<h4>Anexo: {file_name}</h4><pre style="white-space: pre-wrap; word-wrap: break-word;">{content}</pre><hr>'
            except Exception as e:
                logger.error(f"Erro ao ler DOCX {file_name}: {e}")
                return f'<p><strong>{file_name}</strong>: Não foi possível ler o conteúdo do DOCX. <a href="{file_url}" target="_blank">Fazer download</a></p><hr>'
        
        elif ext == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return f'<h4>Anexo: {file_name}</h4><pre style="white-space: pre-wrap; word-wrap: break-word;">{content}</pre><hr>'

        else:
            # Para outros tipos de ficheiro, apenas fornece um link
            return f'<p><strong>Anexo: {file_name}</strong> (Tipo de ficheiro não suportado para visualização) - <a href="{file_url}" target="_blank">Fazer download</a></p><hr>'

    except Exception as e:
        logger.error(f"Erro ao processar anexo {anexo.id}: {e}")
        return f"<p>Erro ao carregar o anexo {os.path.basename(anexo.arquivo.name)}.</p>"


def _get_document_context(patd):
    """
    Função centralizada para coletar e formatar todos os dados 
    necessários para qualquer documento.
    """
    config = Configuracao.load()
    comandante_gsd = config.comandante_gsd
    comandante_bagl = config.comandante_bagl
    now = timezone.now()

    # Formatações de Data
    data_inicio = patd.data_inicio
    data_patd_fmt = data_inicio.strftime('%d%m%Y')
    data_ocorrencia_fmt = patd.data_ocorrencia.strftime('%d/%m/%Y') if patd.data_ocorrencia else "[Data não informada]"
    data_oficio_fmt = patd.data_oficio.strftime('%d/%m/%Y') if patd.data_oficio else "[Data do ofício não informada]"
    data_ciencia_fmt = patd.data_ciencia.strftime('%d/%m/%Y') if patd.data_ciencia else "[Data não informada]"
    data_alegacao_fmt = patd.data_alegacao.strftime('%d/%m/%Y') if patd.data_alegacao else "[Data não informada]"

    # Formatação de Itens Enquadrados e Circunstâncias
    itens_enquadrados_str = ", ".join([str(item.get('numero', '')) for item in patd.itens_enquadrados]) if patd.itens_enquadrados else ""
    atenuantes_str = ", ".join(patd.circunstancias.get('atenuantes', [])) if patd.circunstancias else "Nenhuma"
    agravantes_str = ", ".join(patd.circunstancias.get('agravantes', [])) if patd.circunstancias else "Nenhuma"
    
    # --- LÓGICA DE FORMATAÇÃO DA PUNIÇÃO ATUALIZADA ---
    # Formatação da Punição Completa
    punicao_final_str = patd.punicao or "[Punição não definida]"
    if patd.dias_punicao and patd.punicao:
        # A lógica agora constrói a string completa, ex: "Seis (06) de detenção"
        punicao_final_str = f"{patd.dias_punicao} de {patd.punicao}"

    # Cálculo do Prazo Final (Deadline) para Preclusão
    deadline_str = "[Prazo não iniciado]"
    if patd.data_ciencia:
        dias_uteis_a_adicionar = config.prazo_defesa_dias
        data_final = patd.data_ciencia
        dias_adicionados = 0
        while dias_adicionados < dias_uteis_a_adicionar:
            data_final += timedelta(days=1)
            if data_final.weekday() < 5:
                dias_adicionados += 1
        deadline = data_final + timedelta(minutes=config.prazo_defesa_minutos)
        deadline_str = deadline.strftime('%d/%m/%Y às %H:%M')

    data_publicacao_fmt = patd.data_publicacao_punicao.strftime('%d/%m/%Y às %H:%M') if patd.data_publicacao_punicao else "[Data não informada]"
    data_reconsideracao_fmt = patd.data_reconsideracao.strftime('%d/%m/%Y') if patd.data_reconsideracao else "[Data não informada]"

    # Lógica para Oficial Apurador
    oficial_definido = patd.status not in ['definicao_oficial', 'aguardando_aprovacao_atribuicao']
    
    context = {
        # Placeholders Comuns
        '{Brasao da Republica}': f'<img src="{static("img/brasao.png")}" alt="Brasão da República" style="width: 100px; height: auto;">',
        '{N PATD}': str(patd.numero_patd),
        '{DataPatd}': data_patd_fmt,
        '{dia}': now.strftime('%d'),
        '{Mês}': now.strftime('%B').capitalize(),
        '{Ano}': now.strftime('%Y'),
        
        # Dados do Militar Arrolado
        '{Militar Arrolado}': format_militar_string(patd.militar),
        '{Saram Militar Arrolado}': str(getattr(patd.militar, 'saram', '[Não informado]')),
        '{Setor Militar Arrolado}': getattr(patd.militar, 'setor', '[Não informado]'),
        
        # Dados do Oficial Apurador
        '{Oficial Apurador}': format_militar_string(patd.oficial_responsavel) if oficial_definido else '[Aguardando Oficial confirmar]',
        '{Posto/Especialização Oficial Apurador}': format_militar_string(patd.oficial_responsavel, with_spec=True) if oficial_definido else "[Aguardando Oficial confirmar]",
        '{Saram Oficial Apurador}': str(getattr(patd.oficial_responsavel, 'saram', 'N/A')) if oficial_definido else "[Aguardando Oficial confirmar]",
        '{Setor Oficial Apurador}': getattr(patd.oficial_responsavel, 'setor', 'N/A') if oficial_definido else "[Aguardando Oficial confirmar]",
        '{Assinatura Oficial Apurador}': '{Assinatura_Imagem_Oficial_Apurador}' if oficial_definido and patd.assinatura_oficial else ('[Aguardando Oficial confirmar]' if not oficial_definido else '{Botao Assinar Oficial}'),

        # Dados do Comandante
        '{Comandante /Posto/Especialização}': format_militar_string(comandante_gsd, with_spec=True) if comandante_gsd else "[Comandante GSD não definido]",
        '{Comandante_bagl_botao}': format_militar_string(comandante_bagl, with_spec=True) if comandante_bagl else "[Comandante BAGL não definido]",
    
        
        # Dados da Transgressão
        '{data da Ocorrencia}': data_ocorrencia_fmt,
        '{Ocorrencia reescrita}': patd.ocorrencia_reescrita or patd.transgressao,
        '{protocolo comaer}': patd.protocolo_comaer,
        '{Oficio Transgressao}': patd.oficio_transgressao,
        '{data_oficio}': data_oficio_fmt,
        '{comprovante}': patd.comprovante or '',

        # Dados da Apuração
        '{Itens enquadrados}': itens_enquadrados_str,
        '{Atenuante}': atenuantes_str,
        '{agravantes}': agravantes_str,
        '{transgressao_afirmativa}': patd.transgressao_afirmativa or '',
        '{natureza_transgressao}': patd.natureza_transgressao or '',
        
        # Dados da Defesa
        '{data ciência}': data_ciencia_fmt,
        '{Data da alegação}': data_alegacao_fmt,
        '{Alegação_defesa_resumo}': patd.alegacao_defesa_resumo or '',
        
        # Placeholders de Punição
        '{punicao_completa}': punicao_final_str,
        '{punicao}': punicao_final_str,
        '{punição_botao}': f"{patd.nova_punicao_dias} de {patd.nova_punicao_tipo}" if patd.nova_punicao_dias else '{Botao Definir Nova Punicao}',
        '{dias_punicao}': "", 
        '{comportamento}': patd.comportamento or "[Não avaliado]",
        '{data_publicacao_punicao}': data_publicacao_fmt,
        
        # Placeholders de Assinatura
        '{Assinatura Comandante do GSD}': '{Assinatura_Imagem_Comandante_GSD}' if comandante_gsd and comandante_gsd.assinatura else '[Sem assinatura]',
        '{Assinatura Alegacao Defesa}': '{Assinatura Alegacao Defesa}' if patd.assinatura_alegacao_defesa else '{Botao Assinar Defesa}',
        '{Assinatura Reconsideracao}': '{Assinatura Reconsideracao}' if patd.assinatura_reconsideracao else '{Botao Assinar Reconsideracao}',

        # Testemunhas
        '{Testemunha 1}': format_militar_string(patd.testemunha1) if patd.testemunha1 else '[Testemunha não definida]',
        '{Testemunha 2}': format_militar_string(patd.testemunha2) if patd.testemunha2 else '[Testemunha não definida]',
        '{Assinatura Testemunha 1}': '{Assinatura_Imagem_Testemunha_1}' if patd.assinatura_testemunha1 else ('{Botao Assinar Testemunha 1}' if patd.testemunha1 else '[Sem assinatura]'),
        '{Assinatura Testemunha 2}': '{Assinatura_Imagem_Testemunha_2}' if patd.assinatura_testemunha2 else ('{Botao Assinar Testemunha 2}' if patd.testemunha2 else '[Sem assinatura]'),

        # Específicos
        '{Data Final Prazo}': deadline_str,
        '{texto_relatorio}': patd.texto_relatorio or '',
        '{Texto_reconsideracao}': patd.texto_reconsideracao or '',
        '{Data_reconsideracao}': data_reconsideracao_fmt,
    }

    # Adiciona os dados das assinaturas ao contexto para o frontend
    if oficial_definido and patd.assinatura_oficial:
        context['assinatura_oficial_data'] = patd.assinatura_oficial
    if comandante_gsd and comandante_gsd.assinatura:
        context['assinatura_comandante_data'] = comandante_gsd.assinatura
    
    return context


def _render_document_from_template(template_name, context):
    """
    Função genérica para renderizar um documento .docx a partir de um template e um contexto.
    """
    try:
        doc_path = os.path.join(settings.BASE_DIR, 'pdf', template_name)
        document = docx.Document(doc_path)
        template_content = '\n'.join([p.text for p in document.paragraphs])

        for placeholder, value in context.items():
            template_content = template_content.replace(str(placeholder), str(value))
        
        return template_content
    except FileNotFoundError:
        error_msg = f"\n\n--- ERRO: Template '{template_name}' não encontrado. ---"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"\n\n--- ERRO ao processar o template '{template_name}': {e} ---"
        logger.error(error_msg)
        return error_msg


def get_raw_document_text(patd):
    """
    Gera o texto completo do documento a partir dos templates,
    preservando os placeholders que serão substituídos no frontend.
    """
    doc_context = _get_document_context(patd)
    
    # 1. Conteúdo inicial (Capa, Despacho, etc.)
    document_content = _render_document_from_template('PATD_Coringa.docx', doc_context)

    # 2. Adiciona a alegação de defesa, se existir
    if patd.alegacao_defesa or patd.anexos.filter(tipo='defesa').exists():
        alegacao_context = doc_context.copy()
        alegacao_context['{Alegação de defesa}'] = patd.alegacao_defesa if patd.alegacao_defesa else "[Ver documentos anexos]"
        document_content += "\n\n" + _render_document_from_template('PATD_Alegacao_DF.docx', alegacao_context)
        document_content += "\n\n{ANEXOS_DEFESA_PLACEHOLDER}"
    
    # 3. Adiciona Termo de Preclusão, se aplicável (sem defesa e em status avançado)
    status_preclusao_e_posteriores = [
        'preclusao', 'apuracao_preclusao', 'aguardando_punicao', 
        'aguardando_assinatura_npd', 'finalizado', 'aguardando_punicao_alterar', 
        'analise_comandante', 'periodo_reconsideracao', 'em_reconsideracao', 
        'aguardando_publicacao', 'aguardando_preenchimento_npd_reconsideracao', 
        'aguardando_comandante_base'
    ]
    if not patd.alegacao_defesa and not patd.anexos.filter(tipo='defesa').exists() and patd.status in status_preclusao_e_posteriores:
        document_content += "\n\n" + _render_document_from_template('PRECLUSAO.docx', doc_context)

    # 4. Adiciona Relatório de Apuração (Justificado ou Punição Sugerida)
    if patd.justificado:
        document_content += "\n\n" + _render_document_from_template('RELATORIO_JUSTIFICADO.docx', doc_context)
    elif patd.punicao_sugerida:
        document_content += "\n\n" + _render_document_from_template('RELATORIO_DELTA.docx', doc_context)

    # 5. Adiciona a Nota de Punição Disciplinar (NPD)
    status_npd_e_posteriores = [
        'aguardando_assinatura_npd', 'finalizado', 'periodo_reconsideracao', 
        'em_reconsideracao', 'aguardando_publicacao', 
        'aguardando_preenchimento_npd_reconsideracao', 'aguardando_comandante_base'
    ]
    if patd.status in status_npd_e_posteriores:
        document_content += "\n\n" + _render_document_from_template('MODELO_NPD.docx', doc_context)
    
    # 6. Adiciona a Reconsideração
    status_reconsideracao_e_posteriores = [
        'em_reconsideracao', 'aguardando_publicacao', 'finalizado', 
        'aguardando_preenchimento_npd_reconsideracao', 'aguardando_comandante_base'
    ]
    if patd.status in status_reconsideracao_e_posteriores:
         reconsideracao_context = doc_context.copy()
         if not patd.texto_reconsideracao and not patd.anexos.filter(tipo='reconsideracao').exists():
             reconsideracao_context['{Texto_reconsideracao}'] = '{Botao Adicionar Reconsideracao}'
         else:
             reconsideracao_context['{Texto_reconsideracao}'] = patd.texto_reconsideracao or "[Ver documentos anexos]"
         document_content += "\n\n" + _render_document_from_template('MODELO_RECONSIDERACAO.docx', reconsideracao_context)
         document_content += "\n\n{ANEXOS_RECONSIDERACAO_PLACEHOLDER}"
    
    # 7. Adiciona anexos e NPD da reconsideração
    status_npd_reconsideracao_e_posteriores = [
        'aguardando_preenchimento_npd_reconsideracao', 'aguardando_publicacao', 'finalizado'
    ]
    if patd.status in status_npd_reconsideracao_e_posteriores:
         document_content += "\n\n{ANEXO_OFICIAL_RECONSIDERACAO_PLACEHOLDER}"
         document_content += "\n\n" + _render_document_from_template('MODELO_NPD_RECONSIDERACAO.docx', doc_context)

    return document_content


def _check_preclusao_signatures(patd):
    """
    Verifica se as assinaturas das testemunhas para o documento de preclusão
    foram coletadas, APENAS se as testemunhas tiverem sido designadas.
    Retorna True se as assinaturas estiverem completas, False caso contrário.
    """
    if patd.testemunha1 and not patd.assinatura_testemunha1:
        return False
    if patd.testemunha2 and not patd.assinatura_testemunha2:
        return False
    
    return True

def _check_and_finalize_patd(patd):
    """
    Verifica se todas as assinaturas necessárias para a NPD foram coletadas
    e, em caso afirmativo, avança o PATD para o período de reconsideração.
    """
    if patd.status != 'aguardando_assinatura_npd':
        return False

    raw_document_text = get_raw_document_text(patd)
    
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

def _try_advance_status_from_justificativa(patd):
    """
    Verifica se a PATD no status 'aguardando_justificativa' pode avançar
    para 'em_apuracao'. Isso só deve ocorrer se tanto a alegação de defesa
    quanto todas as assinaturas necessárias estiverem presentes.
    """
    if patd.status != 'aguardando_justificativa':
        return False

    if not patd.alegacao_defesa and not patd.anexos.filter(tipo='defesa').exists():
        return False

    raw_document_text = get_raw_document_text(patd)
    required_signatures = raw_document_text.count('{Assinatura Militar Arrolado}')
    provided_signatures = sum(1 for s in (patd.assinaturas_militar or []) if s)
    
    if provided_signatures < required_signatures:
        return False

    patd.status = 'em_apuracao'
    return True


# =============================================================================
# Views e Lógica da Aplicação
# =============================================================================

@login_required
@ouvidoria_required
def atribuir_oficial(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    if request.method == 'POST':
        form = AtribuirOficialForm(request.POST, instance=patd)
        if form.is_valid():
            form.save()
            messages.success(request, f'Oficial {patd.oficial_responsavel.nome_guerra} foi atribuído. Aguardando aceitação.')
            return redirect('Ouvidoria:patd_detail', pk=pk)
    else:
        form = AtribuirOficialForm(instance=patd)
    return render(request, 'atribuir_oficial.html', {'form': form, 'patd': patd})

@login_required
def patd_atribuicoes_pendentes(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.militar:
        messages.warning(request, "Seu usuário não está associado a um militar.")
        return redirect('Ouvidoria:index')
    
    militar_logado = request.user.profile.militar
    active_tab = request.GET.get('tab', 'aprovar') # 'aprovar' is the default tab

    count_aprovar = PATD.objects.filter(
        oficial_responsavel=militar_logado,
        status='aguardando_aprovacao_atribuicao'
    ).count()
    
    status_list_apuracao = ['em_apuracao', 'apuracao_preclusao', 'aguardando_punicao', 'aguardando_punicao_alterar']
    count_apuracao = PATD.objects.filter(
        oficial_responsavel=militar_logado,
        status__in=status_list_apuracao
    ).count()

    if active_tab == 'apuracao':
        patds = PATD.objects.filter(
            oficial_responsavel=militar_logado,
            status__in=status_list_apuracao
        ).select_related('militar').order_by('-data_inicio')
    elif active_tab == 'todas':
        patds = PATD.objects.filter(
            oficial_responsavel=militar_logado
        ).select_related('militar').order_by('-data_inicio')
    else: # default is 'aprovar'
        patds = PATD.objects.filter(
            oficial_responsavel=militar_logado,
            status='aguardando_aprovacao_atribuicao'
        ).select_related('militar').order_by('-data_inicio')

    context = {
        'patds': patds,
        'active_tab': active_tab,
        'count_aprovar': count_aprovar,
        'count_apuracao': count_apuracao
    }
    
    return render(request, 'patd_atribuicoes_pendentes.html', context)

@login_required
@require_POST
def aceitar_atribuicao(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    
    if not (hasattr(request.user, 'profile') and request.user.profile.militar and request.user.profile.militar == patd.oficial_responsavel):
        messages.error(request, "Você não tem permissão para aceitar esta atribuição.")
        return redirect('Ouvidoria:patd_detail', pk=pk)

    form = AceitarAtribuicaoForm(request.POST)
    if form.is_valid():
        senha = form.cleaned_data['senha']
        user = authenticate(username=request.user.username, password=senha)
        if user is not None:
            if patd.status_anterior:
                patd.status = patd.status_anterior
                patd.status_anterior = None 
            else:
                patd.status = 'ciencia_militar'
            

            if patd.oficial_responsavel and patd.oficial_responsavel.assinatura:
                # --- INÍCIO DA CORREÇÃO ---
                # A assinatura do oficial é um Base64. Precisamos convertê-la para um ficheiro.
                signature_data_base64 = patd.oficial_responsavel.assinatura
                try:
                    # Divide a string Base64 para obter o formato e os dados
                    format, imgstr = signature_data_base64.split(';base64,') 
                    ext = format.split('/')[-1] 
                    # Cria um ficheiro em memória a partir dos dados Base64
                    file_content = ContentFile(base64.b64decode(imgstr), name=f'sig_oficial_{patd.pk}.{ext}')
                    
                    # Apaga a assinatura antiga se existir para evitar lixo
                    if patd.assinatura_oficial:
                        patd.assinatura_oficial.delete(save=False)

                    # Guarda o novo ficheiro no campo FileField. O `save=False` é para evitar uma query extra.
                    patd.assinatura_oficial.save(file_content.name, file_content, save=False)
                except Exception as e:
                    logger.error(f"Erro ao converter assinatura padrão do oficial para a PATD {pk}: {e}")
                    messages.error(request, "Erro ao processar a assinatura padrão do oficial.")
                    return redirect('Ouvidoria:patd_atribuicoes_pendentes')
                # --- FIM DA CORREÇÃO ---
            
            patd.save()
            messages.success(request, f'Atribuição da PATD Nº {patd.numero_patd} aceite com sucesso.')
            return redirect('Ouvidoria:patd_atribuicoes_pendentes')
        else:
            messages.error(request, "Senha incorreta. A atribuição não foi aceite.")
    else:
        messages.error(request, "Formulário inválido.")
    
    return redirect('Ouvidoria:patd_atribuicoes_pendentes')


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

        if action == 'create_militar_and_patd':
            form = MilitarForm(request.POST)
            if form.is_valid():
                new_militar = form.save()
                transgressao = request.POST.get('transgressao')
                data_ocorrencia_str = request.POST.get('data_ocorrencia')
                
                data_ocorrencia = None
                if data_ocorrencia_str:
                    try:
                        data_ocorrencia = datetime.strptime(data_ocorrencia_str, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        pass
                
                protocolo_comaer = request.POST.get('protocolo_comaer', '')
                oficio_transgressao = request.POST.get('oficio_transgressao', '')
                data_oficio_str = request.POST.get('data_oficio', '')

                data_oficio = None
                if data_oficio_str:
                    try:
                        data_oficio = datetime.strptime(data_oficio_str, '%d/%m/%Y').date()
                    except (ValueError, TypeError):
                        pass

                patd = PATD.objects.create(
                    militar=new_militar,
                    transgressao=transgressao,
                    numero_patd=get_next_patd_number(),
                    data_ocorrencia=data_ocorrencia,
                    protocolo_comaer=protocolo_comaer,
                    oficio_transgressao=oficio_transgressao,
                    data_oficio=data_oficio
                )
                return JsonResponse({
                    'status': 'success',
                    'message': f'Militar cadastrado e PATD Nº {patd.numero_patd} criada com sucesso!'
                })
            else:
                return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)


        elif action == 'analyze':
            pdf_file = request.FILES.get('pdf_file')
            if not pdf_file:
                return JsonResponse({'status': 'error', 'message': "Nenhum ficheiro foi enviado."}, status=400)

            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    for chunk in pdf_file.chunks():
                        temp_file.write(chunk)
                    temp_file_path = temp_file.name

                loader = PyPDFLoader(temp_file_path)
                content = " ".join(page.page_content for page in loader.load_and_split())
                os.remove(temp_file_path)


                structured_llm = model.with_structured_output(AnaliseTransgressao)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "Você é um assistente especialista em analisar documentos disciplinares militares. Extraia a data em que a transgressão ocorreu, no formato AAAA-MM-DD. Ignore a data de emissão do documento. Extraia também o número de protocolo COMAER e o número do ofício de transgressão, se existirem. Extraia a data do ofício no formato 'Dia/Mês/Ano'."),
                    ("human", "Analise o seguinte documento e extraia os dados: \n\n{documento}")
                ])
                chain = prompt | structured_llm
                resultado = chain.invoke({"documento": content})

                nome_extraido = resultado.nome_militar
                militar = Militar.objects.filter(
                    Q(nome_completo__icontains=nome_extraido) | 
                    Q(nome_guerra__icontains=nome_extraido)
                ).first()

                data_ocorrencia = None
                if resultado.data_ocorrencia:
                    try:
                        data_ocorrencia = datetime.strptime(resultado.data_ocorrencia, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        pass

                data_oficio = None
                if resultado.data_oficio:
                    try:
                        # Para converter a data do ofício "8 de julho de 2025" para "2025-07-08"
                        data_oficio = datetime.strptime(resultado.data_oficio, '%d de %B de %Y').date()
                    except (ValueError, TypeError):
                        pass

                if militar:
                    existing_patds = PATD.objects.filter(militar=militar)
                    
                    def similar(a, b):
                        return SequenceMatcher(None, a, b).ratio()

                    for patd in existing_patds:
                        if patd.data_ocorrencia != data_ocorrencia:
                            continue

                        nova_transgressao = resultado.transgressao.strip()
                        transgressao_existente = patd.transgressao.strip()
                        
                        if similar(nova_transgressao, transgressao_existente) > 0.8:
                            patd_url = reverse('Ouvidoria:patd_detail', kwargs={'pk': patd.pk})
                            return JsonResponse({
                                'status': 'patd_exists',
                                'message': f'Já existe uma PATD para este militar com data e transgressão similares (Nº {patd.numero_patd}).',
                                'url': patd_url
                            })
                    
                    patd = PATD.objects.create(
                        militar=militar,
                        transgressao=resultado.transgressao,
                        numero_patd=get_next_patd_number(),
                        data_ocorrencia=data_ocorrencia,
                        protocolo_comaer=resultado.protocolo_comaer,
                        oficio_transgressao=resultado.oficio_transgressao,
                        data_oficio=data_oficio
                    )
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Militar encontrado. PATD Nº {patd.numero_patd} criada com sucesso para {militar}.'
                    })
                else:
                    nome_para_cadastro = f"{resultado.posto_graduacao} {resultado.nome_militar}".strip()
                    return JsonResponse({
                        'status': 'militar_not_found',
                        'resultado': {
                            'nome_completo': nome_para_cadastro,
                            'transgressao': resultado.transgressao,
                            'local': resultado.local,
                            'data_ocorrencia': resultado.data_ocorrencia,
                            'protocolo_comaer': resultado.protocolo_comaer,
                            'oficio_transgressao': resultado.oficio_transgressao,
                            'data_oficio': resultado.data_oficio,
                        }
                    })
            except Exception as e:
                logger.error(f"Erro na análise do PDF: {e}")
                return JsonResponse({'status': 'error', 'message': f"Ocorreu um erro ao analisar o ficheiro: {e}"}, status=500)
    
    return render(request, 'indexOuvidoria.html', context)

@login_required
@ouvidoria_required
def importar_excel(request):
    config = Configuracao.load()
    context = {
        'prazo_defesa_dias': config.prazo_defesa_dias,
        'prazo_defesa_minutos': config.prazo_defesa_minutos,
    }
    if request.method == 'POST':
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Nenhum ficheiro foi enviado.")
            return redirect('Ouvidoria:importar_excel')

        try:
            df = pd.read_excel(excel_file).fillna('')
            column_mapping = {
                'pst.': 'posto', 'quad.': 'quad', 'esp.': 'especializacao', 'saram': 'saram',
                'nome completo': 'nome_completo', 'nome de guerra': 'nome_guerra', 'turma': 'turma',
                'situação': 'situacao', 'om': 'om', 'setor': 'setor', 'subsetor': 'subsetor'
            }
            df.columns = df.columns.str.lower().str.strip()
            militares_criados = 0
            militares_atualizados = 0
            linhas_com_erro = 0
            for index, row in df.iterrows():
                data_dict = {}
                for excel_col, model_field in column_mapping.items():
                    if excel_col in df.columns:
                        data_dict[model_field] = row[excel_col]
                postos_oficiais = ['TC', 'MJ', 'CP', '1T', '2T']
                is_recruta = str(data_dict.get('posto', '')).upper() == 'REC'
                if 'posto' in data_dict:
                    data_dict['oficial'] = str(data_dict.get('posto', '')).upper() in postos_oficiais
                identifier = {}
                if is_recruta:
                    if 'nome_completo' in data_dict and data_dict['nome_completo']:
                        identifier['nome_completo'] = data_dict['nome_completo']
                        data_dict.pop('saram', None) 
                    else:
                        linhas_com_erro += 1
                        continue
                else:
                    if 'saram' in data_dict and str(data_dict['saram']).strip():
                        try:
                            identifier['saram'] = int(data_dict['saram'])
                        except (ValueError, TypeError):
                            linhas_com_erro += 1
                            continue
                    else:
                        linhas_com_erro += 1
                        continue
                try:
                    for field in Militar._meta.get_fields():
                        if not field.is_relation and field.name not in data_dict and not field.blank and field.name not in identifier:
                            if is_recruta and field.name == 'saram':
                                continue
                            data_dict[field.name] = ''
                    obj, created = Militar.objects.update_or_create(**identifier, defaults=data_dict)
                    if created:
                        militares_criados += 1
                    else:
                        militares_atualizados += 1
                except Exception as e:
                    logger.warning(f"Não foi possível processar a linha {index+2}: {e}. Dados: {row}")
                    linhas_com_erro += 1
                    continue
            msg = f"Importação concluída! {militares_criados} militares criados e {militares_atualizados} atualizados."
            if linhas_com_erro > 0:
                msg += f" {linhas_com_erro} linhas foram ignoradas por dados inválidos ou ausência de identificador."
            messages.success(request, msg)
        except Exception as e:
            logger.error(f"Erro na importação do Excel: {e}")
            messages.error(request, f"Ocorreu um erro ao processar o ficheiro: {e}")
        return redirect('Ouvidoria:importar_excel')
    return render(request, 'importar_excel.html', context)

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class MilitarListView(ListView):
    model = Militar
    template_name = 'militar_list.html'
    context_object_name = 'militares'
    paginate_by = 25

    def get_queryset(self):
        query = self.request.GET.get('q')
        rank_order = Case(
            When(posto='TC', then=Value(0)), When(posto='MJ', then=Value(1)), When(posto='CP', then=Value(2)),
            When(posto='1T', then=Value(3)), When(posto='2T', then=Value(4)), When(posto='SO', then=Value(5)),
            When(posto='1S', then=Value(6)), When(posto='2S', then=Value(7)), When(posto='3S', then=Value(8)),
            When(posto='CB', then=Value(9)), When(posto='S1', then=Value(10)), When(posto='S2', then=Value(11)),
            default=Value(99), output_field=IntegerField(),
        )
        qs = super().get_queryset().annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
        if query:
            qs = qs.filter(
                Q(nome_completo__icontains=query) | 
                Q(nome_guerra__icontains=query) | 
                Q(saram__icontains=query)
            )
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = Configuracao.load()
        context['prazo_defesa_dias'] = config.prazo_defesa_dias
        context['prazo_defesa_minutos'] = config.prazo_defesa_minutos
        return context

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class MilitarCreateView(CreateView):
    model = Militar
    form_class = MilitarForm
    template_name = 'militar_form.html'
    success_url = reverse_lazy('Ouvidoria:militar_list')

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class MilitarUpdateView(UpdateView):
    model = Militar
    form_class = MilitarForm
    template_name = 'militar_form.html'
    success_url = reverse_lazy('Ouvidoria:militar_list')

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class MilitarDeleteView(DeleteView):
    model = Militar
    template_name = 'militar_confirm_delete.html'
    success_url = reverse_lazy('Ouvidoria:militar_list')

# Dicionário com os grupos de status
STATUS_GROUPS = {
    "Aguardando Oficial": {
        'definicao_oficial': 'Aguardando definição do Oficial',
        'aguardando_aprovacao_atribuicao': 'Aguardando aprovação de atribuição de oficial',
    },
    "Fase de Defesa": {
        'ciencia_militar': 'Aguardando ciência do militar',
        'aguardando_justificativa': 'Aguardando Justificativa',
        'prazo_expirado': 'Prazo expirado',
        'preclusao': 'Preclusão - Sem Defesa',
    },
    "Fase de Apuração": {
        'em_apuracao': 'Em Apuração',
        'apuracao_preclusao': 'Em Apuração (Preclusão)',
        'aguardando_punicao': 'Aguardando Aplicação da Punição',
        'aguardando_punicao_alterar': 'Aguardando Punição (alterar)',
    },
    "Decisão do Comandante": {
        'analise_comandante': 'Em Análise pelo Comandante',
        'aguardando_assinatura_npd': 'Aguardando Assinatura NPD',
    },
    "Fase de Reconsideração": {
        'periodo_reconsideracao': 'Período de Reconsideração',
        'em_reconsideracao': 'Em Reconsideração',
        'aguardando_comandante_base': 'Aguardando Comandante da Base',
        'aguardando_preenchimento_npd_reconsideracao': 'Aguardando preenchimento NPD Reconsideração',
    },
    "Aguardando Publicação": {
        'aguardando_publicacao': 'Aguardando publicação',
    }
}

@method_decorator([login_required, comandante_redirect, ouvidoria_required], name='dispatch')
class PATDListView(ListView):
    model = PATD
    template_name = 'patd_list.html'
    context_object_name = 'patds'
    paginate_by = 15

    def get_queryset(self):
        query = self.request.GET.get('q')
        status_filter = self.request.GET.get('status')

        qs = super().get_queryset().exclude(status='finalizado').select_related('militar', 'oficial_responsavel').order_by('-data_inicio')

        if query:
            qs = qs.filter(
                Q(numero_patd__icontains=query) |
                Q(militar__nome_completo__icontains=query) |
                Q(militar__nome_guerra__icontains=query)
            )

        if status_filter:
            # Verifica se o filtro é um nome de grupo
            if status_filter in STATUS_GROUPS:
                statuses_in_group = list(STATUS_GROUPS[status_filter].keys())
                qs = qs.filter(status__in=statuses_in_group)
            else: # É um status individual
                qs = qs.filter(status=status_filter)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = Configuracao.load()
        context['prazo_defesa_dias'] = config.prazo_defesa_dias
        context['prazo_defesa_minutos'] = config.prazo_defesa_minutos
        context['status_groups'] = STATUS_GROUPS  # Passa os grupos para o template
        context['current_status'] = self.request.GET.get('status', '')  # Passa o filtro atual para o template
        return context

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PatdFinalizadoListView(ListView):
    model = PATD
    template_name = 'patd_finalizado_list.html'
    context_object_name = 'patds'
    paginate_by = 15

    def get_queryset(self):
        return PATD.objects.filter(status='finalizado').select_related('militar').order_by('-data_inicio')

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PATDDetailView(DetailView):
    model = PATD
    template_name = 'patd_detail.html'
    context_object_name = 'patd'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'militar', 'oficial_responsavel', 'testemunha1', 'testemunha2'
        ).prefetch_related('anexos')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patd = self.get_object()
        config = Configuracao.load()
        
        document_content = get_raw_document_text(patd)
        context['documento_texto_json'] = json.dumps(document_content)
        context['assinaturas_militar_json'] = json.dumps(patd.assinaturas_militar or [])
        


        context['now_iso'] = timezone.now().isoformat()
        context['prazo_defesa_dias'] = config.prazo_defesa_dias
        context['prazo_defesa_minutos'] = config.prazo_defesa_minutos
        
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
            if p_antiga.punicao:
                itens_str = ""
                if p_antiga.itens_enquadrados and isinstance(p_antiga.itens_enquadrados, list):
                    itens_str = ", ".join([str(item.get('numero', '')) for item in p_antiga.itens_enquadrados if 'numero' in item])
                
                historico_punicoes.append({
                    'numero_patd': p_antiga.numero_patd,
                    'punicao': f"{p_antiga.dias_punicao} de {p_antiga.punicao}" if p_antiga.dias_punicao else p_antiga.punicao,
                    'itens': itens_str,
                    'data': p_antiga.data_inicio.strftime('%d/%m/%Y')
                })
                
        context['historico_punicoes'] = historico_punicoes
        
        anexos_defesa = patd.anexos.filter(tipo='defesa')
        anexos_defesa_data = []
        for a in anexos_defesa:
            anexos_defesa_data.append({
                'id': a.id, 
                'nome': os.path.basename(a.arquivo.name), 
                'url': a.arquivo.url,
                'content_html': get_anexo_content_as_html(a)
            })
        context['anexos_defesa_json'] = json.dumps(anexos_defesa_data)

        anexos_reconsideracao = patd.anexos.filter(tipo='reconsideracao')
        anexos_reconsideracao_data = []
        for a in anexos_reconsideracao:
            anexos_reconsideracao_data.append({
                'id': a.id, 
                'nome': os.path.basename(a.arquivo.name), 
                'url': a.arquivo.url,
                'content_html': get_anexo_content_as_html(a)
            })
        context['anexos_reconsideracao_json'] = json.dumps(anexos_reconsideracao_data)
        
        # Adiciona a lógica para buscar os anexos de reconsideração do oficial
        anexos_reconsideracao_oficial = patd.anexos.filter(tipo='reconsideracao_oficial')
        anexos_reconsideracao_oficial_data = []
        for a in anexos_reconsideracao_oficial:
            anexos_reconsideracao_oficial_data.append({
                'id': a.id,
                'nome': os.path.basename(a.arquivo.name),
                'url': a.arquivo.url,
                'content_html': get_anexo_content_as_html(a)
            })
        context['anexos_reconsideracao_oficial_json'] = json.dumps(anexos_reconsideracao_oficial_data)

        return context

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PATDUpdateView(UserPassesTestMixin, UpdateView):
    model = PATD
    form_class = PATDForm
    template_name = 'patd_form.html'

    def test_func(self):
        # Nega o acesso se o usuário for do grupo 'comandante'
        return not has_comandante_access(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, "Acesso negado. Comandantes não podem editar o processo.")
        patd_pk = self.kwargs.get('pk')
        if patd_pk:
            return redirect('Ouvidoria:patd_detail', pk=patd_pk)
        return redirect('Ouvidoria:index')
    
    def get_success_url(self):
        return reverse_lazy('Ouvidoria:patd_detail', kwargs={'pk': self.object.pk})

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PATDDeleteView(DeleteView):
    model = PATD
    template_name = 'militar_confirm_delete.html'
    success_url = reverse_lazy('Ouvidoria:patd_list')

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class MilitarPATDListView(ListView):
    model = PATD
    template_name = 'militar_patd_list.html'
    context_object_name = 'patds'
    paginate_by = 10

    def get_queryset(self):
        self.militar = get_object_or_404(Militar, pk=self.kwargs['pk'])
        return PATD.objects.filter(militar=self.militar).order_by('-data_inicio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['militar'] = self.militar
        return context

@login_required
@oficial_responsavel_required
@require_POST
def salvar_assinatura(request, pk):
    # CORRIGIDO: Esta função agora converte a assinatura Base64 em um ficheiro e guarda-o.
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
        signature_data_base64 = data.get('signature_data')

        if not signature_data_base64:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)
        
        # Converte a string base64 num ficheiro que o Django pode guardar
        try:
            format, imgstr = signature_data_base64.split(';base64,') 
            ext = format.split('/')[-1] 
            file_content = ContentFile(base64.b64decode(imgstr), name=f'sig_oficial_{pk}.{ext}')
            
            # Apaga a assinatura antiga se existir, para não acumular lixo
            if patd.assinatura_oficial:
                patd.assinatura_oficial.delete(save=False)

            patd.assinatura_oficial.save(file_content.name, file_content, save=True)
        except Exception as e:
            logger.error(f"Erro ao converter Base64 para ficheiro para PATD {pk}: {e}")
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar a imagem da assinatura.'}, status=500)

        return JsonResponse({'status': 'success', 'message': 'Assinatura salva com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura do oficial para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_ciencia(request, pk):
    # CORRIGIDO: Esta função agora converte a assinatura Base64 em um ficheiro e guarda a URL.
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
        signature_data_base64 = data.get('signature_data')
        assinatura_index = int(data.get('assinatura_index', -1))

        if not signature_data_base64 or assinatura_index < 0:
            return JsonResponse({'status': 'error', 'message': 'Dados de assinatura inválidos.'}, status=400)

        # --- INÍCIO DA CORREÇÃO ---
        # Converte a assinatura em ficheiro e obtém a URL
        try:
            format, imgstr = signature_data_base64.split(';base64,')
            ext = format.split('/')[-1]
            file_name = f'sig_ciencia_{assinatura_index}_{pk}_{uuid4().hex[:6]}.{ext}'
            file_content = ContentFile(base64.b64decode(imgstr))

            # Cria um Anexo para guardar a assinatura
            anexo = Anexo.objects.create(patd=patd, tipo='assinatura_ciencia')
            anexo.arquivo.save(file_name, file_content, save=True)
            signature_url = anexo.arquivo.url

        except Exception as e:
            logger.error(f"Erro ao converter Base64 da assinatura de ciência para ficheiro (PATD {pk}): {e}")
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar a imagem da assinatura.'}, status=500)
        # --- FIM DA CORREÇÃO ---

        if patd.assinaturas_militar is None:
            patd.assinaturas_militar = []
        
        while len(patd.assinaturas_militar) <= assinatura_index:
            patd.assinaturas_militar.append(None)

        # Guarda a URL do ficheiro em vez do Base64
        patd.assinaturas_militar[assinatura_index] = signature_url
        
        if patd.status == 'ciencia_militar':
            coringa_doc_text = _render_document_from_template('PATD_Coringa.docx', _get_document_context(patd))
            required_initial_signatures = coringa_doc_text.count('{Assinatura Militar Arrolado}')
            provided_signatures = sum(1 for s in patd.assinaturas_militar if s is not None)
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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def salvar_alegacao_defesa(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        
        if patd.alegacao_defesa or patd.anexos.filter(tipo='defesa').exists():
            return JsonResponse({
                'status': 'error',
                'message': 'A alegação de defesa já foi enviada e não pode ser alterada.'
            }, status=403)
        
        alegacao_texto = request.POST.get('alegacao_defesa', '')
        arquivos = request.FILES.getlist('anexos_defesa')

        if not alegacao_texto and not arquivos:
            return JsonResponse({'status': 'error', 'message': 'É necessário fornecer um texto ou anexar pelo menos um ficheiro.'}, status=400)

        patd.alegacao_defesa = alegacao_texto
        patd.data_alegacao = timezone.now()

        for arquivo in arquivos:
            Anexo.objects.create(patd=patd, arquivo=arquivo, tipo='defesa')

        try:
            # Check if fields are empty before calling AI
            if not patd.alegacao_defesa_resumo:
                patd.alegacao_defesa_resumo = analisar_e_resumir_defesa(patd.alegacao_defesa)
            if not patd.ocorrencia_reescrita:
                ocorrencia_formatada = reescrever_ocorrencia(patd.transgressao)
                patd.ocorrencia_reescrita = ocorrencia_formatada
                patd.comprovante = ocorrencia_formatada
        except Exception as e:
            logger.error(f"Erro ao chamar a IA para processar textos da PATD {pk}: {e}")
            # Set default error messages only if fields are still empty
            if not patd.alegacao_defesa_resumo:
                patd.alegacao_defesa_resumo = "Erro ao gerar resumo."
            if not patd.ocorrencia_reescrita:
                patd.ocorrencia_reescrita = patd.transgressao
                patd.comprovante = patd.transgressao

        # Save immediately after generation
        patd.save() 
        _try_advance_status_from_justificativa(patd)
        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Alegação de defesa e anexos salvos com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar alegação de defesa da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_defesa(request, pk):
    # CORRIGIDO: Esta função agora converte a assinatura Base64 em um ficheiro e guarda-o.
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_reconsideracao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        
        if patd.status != 'em_reconsideracao':
            return JsonResponse({'status': 'error', 'message': 'A PATD não está na fase correta para assinar a reconsideração.'}, status=400)

        data = json.loads(request.body)
        signature_data_base64 = data.get('signature_data')

        if not signature_data_base64:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)

        try:
            format, imgstr = signature_data_base64.split(';base64,') 
            ext = format.split('/')[-1] 
            file_content = ContentFile(base64.b64decode(imgstr), name=f'sig_reconsideracao_{pk}.{ext}')
            
            if patd.assinatura_reconsideracao:
                patd.assinatura_reconsideracao.delete(save=False)

            patd.assinatura_reconsideracao.save(file_content.name, file_content, save=True)
            logger.info(f"Assinatura de reconsideração para PATD {pk} salva em {patd.assinatura_reconsideracao.path}")

        except Exception as e:
            logger.error(f"Erro ao converter Base64 para ficheiro para PATD {pk}: {e}")
            return JsonResponse({'status': 'error', 'message': 'Erro ao processar a imagem da assinatura.'}, status=500)

        _check_and_advance_reconsideracao_status(pk)

        return JsonResponse({'status': 'success', 'message': 'Assinatura salva com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura da reconsideração da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def extender_prazo(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        if patd.status != 'prazo_expirado':
            return JsonResponse({'status': 'error', 'message': 'O prazo só pode ser estendido se estiver expirado.'}, status=400)

        data = json.loads(request.body)
        dias_extensao = int(data.get('dias', 0))
        minutos_extensao = int(data.get('minutos', 0))
        
        if not request.user.is_superuser and minutos_extensao != 0:
            return JsonResponse({'status': 'error', 'message': 'Apenas administradores podem alterar os minutos.'}, status=403)


        if dias_extensao < 0 or minutos_extensao < 0:
            return JsonResponse({'status': 'error', 'message': 'Valores de extensão de prazo inválidos.'}, status=400)

        config = Configuracao.load()
        
        delta_dias = config.prazo_defesa_dias - dias_extensao
        delta_minutos = config.prazo_defesa_minutos - minutos_extensao

        patd.data_ciencia = timezone.now() - timedelta(days=delta_dias, minutes=delta_minutos)
        patd.status = 'aguardando_justificativa'
        patd.save()
        
        return JsonResponse({'status': 'success', 'message': 'Prazo estendido com sucesso.'})

    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Dados de entrada inválidos.'}, status=400)
    except Exception as e:
        logger.error(f"Erro ao estender prazo da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def salvar_documento_patd(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
        texto_documento = data.get('texto_documento')

        if texto_documento is None:
            return JsonResponse({'status': 'error', 'message': 'Nenhum texto recebido.'}, status=400)

        patd.documento_texto = texto_documento
        patd.save()
        
        return JsonResponse({'status': 'success', 'message': 'Documento salvo com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar documento da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_GET
def lista_oficiais(request):
    query = request.GET.get('q', '')
    oficiais = Militar.objects.filter(oficial=True)
    if query:
        oficiais = oficiais.filter(
            Q(nome_completo__icontains=query) | 
            Q(nome_guerra__icontains=query)
        )
    oficiais = oficiais.order_by('posto', 'nome_guerra')
    data = list(oficiais.values('id', 'posto', 'nome_guerra', 'assinatura'))
    return JsonResponse(data, safe=False)

@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_padrao(request, pk):
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Apenas administradores podem alterar assinaturas.'}, status=403)
    try:
        oficial = get_object_or_404(Militar, pk=pk, oficial=True)
        data = json.loads(request.body)
        signature_data = data.get('signature_data', '')
        oficial.assinatura = signature_data
        oficial.save()
        return JsonResponse({'status': 'success', 'message': 'Assinatura padrão salva com sucesso.'})
    except Militar.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Oficial não encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
def gerenciar_configuracoes_padrao(request):
    config = Configuracao.load()
    if request.method == 'POST':
        if not request.user.is_superuser:
            return JsonResponse({'status': 'error', 'message': 'Apenas administradores podem alterar as configurações.'}, status=403)
        try:
            data = json.loads(request.body)
            comandante_gsd_id = data.get('comandante_gsd_id')
            comandante_bagl_id = data.get('comandante_bagl_id')
            prazo_dias = data.get('prazo_defesa_dias')
            prazo_minutos = data.get('prazo_defesa_minutos')
            
            if comandante_gsd_id:
                comandante = get_object_or_404(Militar, pk=comandante_gsd_id, oficial=True)
                config.comandante_gsd = comandante
            else:
                config.comandante_gsd = None

            if comandante_bagl_id:
                comandante_bagl = get_object_or_404(Militar, pk=comandante_bagl_id, oficial=True)
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
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    oficiais = Militar.objects.filter(oficial=True).order_by('posto', 'nome_guerra')
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
        data = json.loads(request.body)
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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def prosseguir_sem_alegacao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        if patd.status != 'prazo_expirado':
            return JsonResponse({'status': 'error', 'message': 'Ação permitida apenas para PATDs com prazo expirado.'}, status=400)
        patd.status = 'apuracao_preclusao'
        patd.save(update_fields=['status'])
        return JsonResponse({'status': 'success', 'message': 'PATD atualizada para Apuração (Preclusão).'})
    except Exception as e:
        logger.error(f"Erro ao prosseguir sem alegação para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_testemunha(request, pk, testemunha_num):
    # CORRIGIDO: Esta função agora converte a assinatura Base64 em um ficheiro e guarda-o.
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
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
                patd.assinatura_testemunha1.save(file_content.name, file_content, save=False)
            elif testemunha_num == 2:
                if patd.assinatura_testemunha2:
                    patd.assinatura_testemunha2.delete(save=False)
                patd.assinatura_testemunha2.save(file_content.name, file_content, save=False)
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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

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
        ).exclude(pk=patd.pk)

        historico_list = []
        if patds_anteriores.exists():
            for p_antiga in patds_anteriores:
                if p_antiga.itens_enquadrados and isinstance(p_antiga.itens_enquadrados, list):
                    itens_str = ", ".join([f"Item {item.get('numero')}" for item in p_antiga.itens_enquadrados if 'numero' in item])
                    if itens_str:
                         historico_list.append(f"PATD anterior (Nº {p_antiga.numero_patd}) foi enquadrada em: {itens_str}.")

        historico_militar = "\n".join(historico_list) if historico_list else "Nenhuma punição anterior registrada."
        justificativa = patd.alegacao_defesa or "Nenhuma alegação de defesa foi apresentada."
        
        circunstancias_obj = verifica_agravante_atenuante(historico_militar, patd.transgressao, justificativa, patd.itens_enquadrados)
        
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
        data = json.loads(request.body)

        if patd.status == 'apuracao_preclusao':
            if not _check_preclusao_signatures(patd):
                return JsonResponse({
                    'status': 'error',
                    'message': 'A apuração não pode ser concluída. Faltam assinaturas das testemunhas no termo de preclusão.'
                }, status=400)

        patd.itens_enquadrados = data.get('itens_enquadrados')
        patd.circunstancias = data.get('circunstancias')
        punicao_sugerida_str = data.get('punicao_sugerida', '')
        patd.punicao_sugerida = punicao_sugerida_str

        match = re.search(r'(\d+)\s+dias\s+de\s+(.+)', punicao_sugerida_str, re.IGNORECASE)
        if match:
            dias_num = int(match.group(1))
            punicao_tipo = match.group(2).strip()
            dias_texto = num2words(dias_num, lang='pt_BR')
            patd.dias_punicao = f"{dias_texto} ({dias_num:02d}) dias"
            patd.punicao = punicao_tipo
        else:
            patd.dias_punicao = ""
            patd.punicao = punicao_sugerida_str

        patd.transgressao_afirmativa = f"foi verificado que o militar realmente cometeu a transgressão de '{patd.transgressao}'."
        
        if not patd.texto_relatorio:
            patd.texto_relatorio = texto_relatorio(patd.transgressao, patd.alegacao_defesa)
        
        # --- LÓGICA ATUALIZADA ---
        patd.definir_natureza_transgressao()
        patd.calcular_e_atualizar_comportamento()
        
        patd.status = 'aguardando_punicao'
        
        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Apuração salva com sucesso!'})

    except Exception as e:
        logger.error(f"Erro ao salvar apuração da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_GET
def search_militares_json(request):
    """Retorna uma lista de militares para a pesquisa no modal."""
    query = request.GET.get('q', '')
    militares = Militar.objects.all()
    
    if query:
        militares = militares.filter(
            Q(nome_completo__icontains=query) | 
            Q(nome_guerra__icontains=query) |
            Q(posto__icontains=query)
        )
        
    militares = militares.order_by('posto', 'nome_guerra')[:50]
    data = list(militares.values('id', 'posto', 'nome_guerra', 'nome_completo'))
    return JsonResponse(data, safe=False)

@method_decorator([login_required, comandante_required], name='dispatch')
class ComandanteDashboardView(ListView):
    model = PATD
    template_name = 'comandante_dashboard.html'
    context_object_name = 'patds'

    def get_queryset(self):
        return PATD.objects.filter(status='analise_comandante').select_related('militar').order_by('-data_inicio')

@login_required
@comandante_required
@require_POST
def patd_aprovar(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    
    errors = []
    # Verificação 1: Garante que as duas testemunhas foram definidas.
    if not patd.testemunha1 or not patd.testemunha2:
        errors.append("É necessário definir as duas testemunhas no processo.")
    
    # As verificações de assinatura foram movidas para _check_and_finalize_patd.
    # Esta função agora foca apenas na aprovação do comandante.

    if errors:
        error_message = f"PATD Nº {patd.numero_patd}: Não foi possível aprovar. " + " ".join(errors)
        messages.error(request, error_message)
        # Redireciona de volta para a página de onde o usuário veio.
        return redirect(request.META.get('HTTP_REFERER', 'Ouvidoria:comandante_dashboard'))
        
    patd.status = 'aguardando_assinatura_npd'
    patd.save()
    messages.success(request, f"PATD Nº {patd.numero_patd} aprovada. Aguardando assinatura da NPD.")
    return redirect('Ouvidoria:comandante_dashboard')

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
    return redirect(request.META.get('HTTP_REFERER', 'Ouvidoria:comandante_dashboard'))

@login_required
@oficial_responsavel_required
@require_POST
def avancar_para_comandante(request, pk):
    patd = get_object_or_404(PATD, pk=pk)

    # NEW: Check for witnesses before advancing
    if not patd.testemunha1 or not patd.testemunha2:
        messages.error(request, "Não é possível avançar a PATD. É necessário definir as duas testemunhas no processo antes de enviar para o comandante.")
        return redirect('Ouvidoria:patd_detail', pk=pk)

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
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

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
        
        _check_and_advance_reconsideracao_status(pk)
        
        return JsonResponse({'status': 'success', 'message': 'Pedido de reconsideração e anexos salvos com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar texto de reconsideração para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_GET
def comandante_pendencias_json(request):
    if not has_comandante_access(request.user):
        return JsonResponse({'count': 0})
        
    count = PATD.objects.filter(status='analise_comandante').count()
    return JsonResponse({'count': count})

@login_required
@ouvidoria_required
@require_POST
def excluir_anexo(request, pk):
    try:
        anexo = get_object_or_404(Anexo, pk=pk)
        
        patd = anexo.patd
        user_militar = request.user.profile.militar if hasattr(request.user, 'profile') else None
        
        if not (request.user.is_superuser or user_militar == patd.oficial_responsavel):
             return JsonResponse({'status': 'error', 'message': 'Você não tem permissão para excluir este anexo.'}, status=403)

        if anexo.arquivo and os.path.isfile(anexo.arquivo.path):
            os.remove(anexo.arquivo.path)
        
        anexo.delete()
        
        return JsonResponse({'status': 'success', 'message': 'Anexo excluído com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao excluir anexo {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@oficial_responsavel_required
@require_POST
def finalizar_publicacao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        boletim = request.POST.get('boletim_publicacao')

        if not boletim or not boletim.strip():
            messages.error(request, "O número do boletim é obrigatório para finalizar o processo.")
            return redirect('Ouvidoria:patd_detail', pk=pk)
        
        patd.boletim_publicacao = boletim
        patd.status = 'finalizado'
        patd.data_termino = timezone.now()
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
        
        if patd.status not in ['em_apuracao', 'apuracao_preclusao']:
             return JsonResponse({'status': 'error', 'message': 'A PATD não está na fase correta para ser justificada.'}, status=400)

        patd.justificado = True
        patd.status = 'aguardando_publicacao'
        
        patd.punicao_sugerida = "Transgressão Justificada"
        patd.punicao = ""
        patd.dias_punicao = ""

        patd.texto_relatorio = """Após análise dos fatos, alegações e circunstâncias, este Oficial Apurador conclui que a transgressão disciplinar imputada ao militar está JUSTIFICADA, nos termos do Art. 13, item 1 do RDAER."""
        
        patd.save()
        return JsonResponse({'status': 'success', 'message': 'A transgressão foi justificada com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao justificar a PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@oficial_responsavel_required
@require_POST
def anexar_documento_reconsideracao_oficial(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    if patd.status != 'aguardando_comandante_base':
        messages.error(request, "Ação não permitida no status atual.")
        return redirect('Ouvidoria:patd_detail', pk=pk)

    anexo_file = request.FILES.get('anexo_oficial')
    if not anexo_file:
        messages.error(request, "Nenhum ficheiro foi enviado.")
        return redirect('Ouvidoria:patd_detail', pk=pk)

    Anexo.objects.create(patd=patd, arquivo=anexo_file, tipo='reconsideracao_oficial')
    
    patd.status = 'aguardando_preenchimento_npd_reconsideracao'
    patd.save()

    messages.success(request, "Documento anexado com sucesso. O processo aguarda o preenchimento da NPD de Reconsideração.")
    return redirect('Ouvidoria:patd_detail', pk=pk)

@login_required
@oficial_responsavel_required
@require_POST
def salvar_nova_punicao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
        dias = int(data.get('dias'))
        tipo = data.get('tipo')

        if dias < 0 or not tipo:
            return JsonResponse({'status': 'error', 'message': 'Dados inválidos.'}, status=400)

        dias_texto = num2words(dias, lang='pt_BR')
        
        # Salva nos campos de nova punição
        patd.nova_punicao_dias = f"{dias_texto} ({dias:02d}) dias"
        patd.nova_punicao_tipo = tipo
        
        # Atualiza os campos da punição principal também
        patd.dias_punicao = f"{dias_texto} ({dias:02d}) dias"
        patd.punicao = tipo
        
        # Recalcula o comportamento com a nova punição
        patd.definir_natureza_transgressao()
        patd.calcular_e_atualizar_comportamento()
        
        patd.status = 'aguardando_publicacao'
        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Nova punição salva com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar nova punição para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)