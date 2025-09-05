import pandas as pd
import io
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Max, Case, When, Value, IntegerField, Count
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from .models import Militar, PATD, Configuracao
from .forms import MilitarForm, PATDForm
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
from .analise_transgressao import enquadra_item, verifica_agravante_atenuante, sugere_punicao, model, analisar_e_resumir_defesa, reescrever_ocorrencia
from difflib import SequenceMatcher # Importado para a verificação de similaridade
from django.utils.decorators import method_decorator
from num2words import num2words # Importação para converter números em texto


# --- Funções e Mixins de Permissão ---
def has_ouvidoria_access(user):
    """Verifica se o utilizador pertence ao grupo 'Ouvidoria' ou é um superutilizador."""
    return user.groups.filter(name='Ouvidoria').exists() or user.is_superuser

def has_comandante_access(user):
    """Verifica se o utilizador pertence ao grupo 'Comandante' ou é um superutilizador."""
    return user.groups.filter(name='Comandante').exists() or user.is_superuser

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


# --- Classe para Estruturação da Análise de PDF ---
class AnaliseTransgressao(BaseModel):
    nome_militar: str = Field(description="O nome do militar acusado, sem o posto ou graduação.")
    posto_graduacao: str = Field(description="O posto ou graduação (ex: Sargento, Capitão), se mencionado. Se não, retorne uma string vazia.")
    transgressao: str = Field(description="A descrição detalhada da transgressão disciplinar cometida.")
    local: str = Field(description="O local onde a transgressão ocorreu.")
    data_ocorrencia: str = Field(description="A data em que a transgressão ocorreu, no formato AAAA-MM-DD. Se não for mencionada, retorne uma string vazia.")
    
    # NOVOS CAMPOS ADICIONADOS
    protocolo_comaer: str = Field(description="O número de protocolo COMAER. Ex: 67112.004914/2025-10. Se não for mencionado, retorne uma string vazia.")
    oficio_transgrecao: str = Field(description="O número do Ofício de Transgressão. Ex: 189/DSEG/5127. Se não for mencionado, retorne uma string vazia.")
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

def _get_document_context(patd):
    """
    Função centralizada para coletar e formatar todos os dados 
    necessários para qualquer documento.
    """
    config = Configuracao.load()
    comandante_gsd = config.comandante_gsd
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

    return {
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
        '{Oficial Apurador}': format_militar_string(patd.oficial_responsavel) if patd.oficial_responsavel else '[Oficial não definido]',
        '{Posto/Especialização Oficial Apurador}': format_militar_string(patd.oficial_responsavel, with_spec=True) if patd.oficial_responsavel else "[Oficial apurador não definido]",
        '{Saram Oficial Apurador}': str(getattr(patd.oficial_responsavel, 'saram', '[Não informado]')) if patd.oficial_responsavel else "[Oficial apurador não definido]",
        '{Setor Oficial Apurador}': getattr(patd.oficial_responsavel, 'setor', '[Não informado]') if patd.oficial_responsavel else "[Oficial apurador não definido]",

        # Dados do Comandante
        '{Comandante /Posto/Especialização}': format_militar_string(comandante_gsd, with_spec=True) if comandante_gsd else "[Comandante GSD não definido]",
        
        # Dados da Transgressão
        '{data da Ocorrencia}': data_ocorrencia_fmt,
        '{Ocorrencia reescrita}': patd.ocorrencia_reescrita or patd.transgressao,
        '{protocolo comaer}': patd.protocolo_comaer,
        '{Oficio Transgrecao}': patd.oficio_transgrecao,
        '{data_oficio}': data_oficio_fmt,
        '{comprovante}': patd.comprovante or "[Não informado]",

        # Dados da Apuração
        '{Itens enquadrados}': itens_enquadrados_str,
        '{Atenuante}': atenuantes_str,
        '{agravantes}': agravantes_str,
        '{transgreção_afirmativa}': patd.transgressao_afirmativa or "[Análise não realizada]",
        '{natureza_transgreção}': patd.natureza_transgressao or "[Análise não realizada]",
        
        # Dados da Defesa
        '{data ciência}': data_ciencia_fmt,
        '{Data da alegação}': data_alegacao_fmt,
        '{Alegação de defesa}': patd.alegacao_defesa or "[Defesa não apresentada]",
        '{Alegação_defesa_resumo}': patd.alegacao_defesa_resumo or "[Resumo não gerado]",
        
        # --- PLACEHOLDERS DE PUNIÇÃO ATUALIZADOS ---
        '{punicao_completa}': punicao_final_str,
        '{punicao}': punicao_final_str, # Agora contém a string completa e formatada
        '{dias_punicao}': "", # Esvaziado para evitar duplicação no template
        '{comportamento}': patd.comportamento or "[Não avaliado]",
        
        # Assinaturas
        '{Assinatura Comandante do GSD}': getattr(comandante_gsd, 'assinatura', '[Sem assinatura]') if comandante_gsd else "[Comandante GSD não definido]",
        '{Assinatura Militar Arrolado}': patd.assinatura_militar_ciencia or '[Assinatura não registrada]',
        '{Assinatura Oficial Apurador}': getattr(patd.oficial_responsavel, 'assinatura', '[Sem assinatura]') if patd.oficial_responsavel else '[Oficial não definido]',
        '{Assinatura Testemunha 1}': patd.assinatura_testemunha1 or '[Sem assinatura]',
        '{Assinatura Testemunha 2}': patd.assinatura_testemunha2 or '[Sem assinatura]',
        
        # Testemunhas
        '{Testemunha 1}': format_militar_string(patd.testemunha1) if patd.testemunha1 else '[Testemunha não definida]',
        '{Testemunha 2}': format_militar_string(patd.testemunha2) if patd.testemunha2 else '[Testemunha não definida]',

        # Específico para Preclusão
        '{Data Final Prazo}': deadline_str,
    }

def _render_document_from_template(template_name, context):
    """
    Função genérica para renderizar um documento .docx a partir de um template e um contexto.
    """
    try:
        doc_path = os.path.join(settings.BASE_DIR, 'pdf', template_name)
        document = docx.Document(doc_path)
        template_content = '\n'.join([p.text for p in document.paragraphs])

        for placeholder, value in context.items():
            template_content = template_content.replace(placeholder, str(value))
        
        return template_content
    except FileNotFoundError:
        error_msg = f"\n\n--- ERRO: Template '{template_name}' não encontrado. ---"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"\n\n--- ERRO ao processar o template '{template_name}': {e} ---"
        logger.error(error_msg)
        return error_msg

# =============================================================================
# Views e Lógica da Aplicação
# =============================================================================

@login_required
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
                
                # NOVOS CAMPOS OBTIDOS DO REQUEST
                protocolo_comaer = request.POST.get('protocolo_comaer', '')
                oficio_transgrecao = request.POST.get('oficio_transgrecao', '')
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
                    # NOVOS CAMPOS ADICIONADOS À CRIAÇÃO
                    protocolo_comaer=protocolo_comaer,
                    oficio_transgrecao=oficio_transgrecao,
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
                        # NOVOS CAMPOS ADICIONADOS À CRIAÇÃO
                        protocolo_comaer=resultado.protocolo_comaer,
                        oficio_transgrecao=resultado.oficio_transgrecao,
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
                            # NOVOS CAMPOS ADICIONADOS AO RETORNO
                            'protocolo_comaer': resultado.protocolo_comaer,
                            'oficio_transgrecao': resultado.oficio_transgrecao,
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

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PATDListView(ListView):
    model = PATD
    template_name = 'patd_list.html'
    context_object_name = 'patds'
    paginate_by = 15
    def get_queryset(self):
        query = self.request.GET.get('q')
        # ALTERAÇÃO AQUI: Exclui PATDs com status 'finalizado'
        qs = super().get_queryset().exclude(status='finalizado').select_related('militar', 'oficial_responsavel').order_by('-data_inicio')
        if query:
            qs = qs.filter(
                Q(numero_patd__icontains=query) | 
                Q(militar__nome_completo__icontains=query) | 
                Q(militar__nome_guerra__icontains=query)
            )
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = Configuracao.load()
        context['prazo_defesa_dias'] = config.prazo_defesa_dias
        context['prazo_defesa_minutos'] = config.prazo_defesa_minutos
        return context

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PatdFinalizadoListView(ListView):
    model = PATD
    template_name = 'patd_finalizado_list.html'
    context_object_name = 'patds'
    paginate_by = 15

    def get_queryset(self):
        return PATD.objects.filter(status='finalizado').order_by('-data_inicio')

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PATDDetailView(DetailView):
    model = PATD
    template_name = 'patd_detail.html'
    context_object_name = 'patd'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patd = self.get_object()
        config = Configuracao.load()
        
        # Coleta todos os parâmetros necessários de uma vez
        doc_context = _get_document_context(patd)

        # Monta o documento completo
        document_content = _render_document_from_template('PATD_Coringa.docx', doc_context)

        if patd.alegacao_defesa:
            document_content += "\n\n" + _render_document_from_template('PATD_Alegacao_DF.docx', doc_context)
        
        if not patd.alegacao_defesa and patd.status in ['preclusao', 'apuracao_preclusao', 'aguardando_punicao', 'aguardando_assinatura_npd', 'finalizado', 'aguardando_punicao_alterar']:
            document_content += "\n\n" + _render_document_from_template('PRECLUSAO.docx', doc_context)
        
        if patd.punicao_sugerida:
            document_content += "\n\n" + _render_document_from_template('RELATORIO_DELTA.docx', doc_context)

        if patd.status == 'finalizado':
            document_content += "\n\n" + _render_document_from_template('MODELO_NPD.docx', doc_context)

        patd.documento_texto = document_content

        context['now_iso'] = timezone.now().isoformat()
        context['prazo_defesa_dias'] = config.prazo_defesa_dias
        context['prazo_defesa_minutos'] = config.prazo_defesa_minutos
        context['patd'] = patd
        
        context['analise_data_json'] = json.dumps({
            'itens': patd.itens_enquadrados,
            'circunstancias': patd.circunstancias,
            'punicao': patd.punicao_sugerida
        }) if patd.punicao_sugerida else 'null'
        
        return context

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PATDUpdateView(UpdateView):
    model = PATD
    form_class = PATDForm
    template_name = 'patd_form.html'
    
    def get_success_url(self):
        return reverse_lazy('Ouvidoria:patd_detail', kwargs={'pk': self.object.pk})

@method_decorator([login_required, ouvidoria_required], name='dispatch')
class PATDDeleteView(DeleteView):
    model = PATD
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
@ouvidoria_required
@require_POST
def salvar_assinatura(request, pk):
    try:
        patd = PATD.objects.get(pk=pk)
        data = json.loads(request.body)
        signature_data = data.get('signature_data')

        if not signature_data:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)

        patd.assinatura_oficial = signature_data
        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Assinatura salva com sucesso.'})
    except PATD.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'PATD não encontrada.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def salvar_assinatura_ciencia(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
        signature_data = data.get('signature_data')

        if not signature_data:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)

        patd.assinatura_militar_ciencia = signature_data
        patd.data_ciencia = timezone.now()
        patd.status = 'aguardando_justificativa'
        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Ciência registrada com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura de ciência da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def salvar_alegacao_defesa(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
        alegacao_texto = data.get('alegacao_defesa')

        if alegacao_texto is None:
             return JsonResponse({'status': 'error', 'message': 'Nenhum texto de alegação recebido.'}, status=400)

        patd.alegacao_defesa = alegacao_texto
        patd.status = 'em_apuracao' 
        patd.data_alegacao = timezone.now()

        try:
            # Chama os agentes de IA para processar os textos
            resumo_tecnico = analisar_e_resumir_defesa(patd.alegacao_defesa)
            ocorrencia_formatada = reescrever_ocorrencia(patd.transgressao)
            
            # Atualiza o objeto PATD com os novos textos
            patd.alegacao_defesa_resumo = resumo_tecnico
            patd.ocorrencia_reescrita = ocorrencia_formatada
            
        except Exception as e:
            # Se a IA falhar, o processo continua, mas registamos o erro.
            logger.error(f"Erro ao chamar a IA para processar textos da PATD {pk}: {e}")
            patd.alegacao_defesa_resumo = "Erro ao gerar resumo."
            patd.ocorrencia_reescrita = patd.transgressao # Usa a original como fallback

        # Salva todos os campos atualizados de uma vez
        patd.save(update_fields=[
            'alegacao_defesa', 
            'status', 
            'data_alegacao',
            'ocorrencia_reescrita',
            'alegacao_defesa_resumo'
        ])

        return JsonResponse({'status': 'success', 'message': 'Alegação de defesa salva com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar alegação de defesa da PATD {pk}: {e}")
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
            comandante_id = data.get('comandante_gsd_id')
            prazo_dias = data.get('prazo_defesa_dias')
            prazo_minutos = data.get('prazo_defesa_minutos')
            if comandante_id:
                comandante = get_object_or_404(Militar, pk=comandante_id, oficial=True)
                config.comandante_gsd = comandante
            else:
                config.comandante_gsd = None
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
    now = timezone.localtime(timezone.now())
    if not (now.hour == 0 and 0 <= now.minute <= 5):
        return JsonResponse({'status': 'not_in_time_window', 'updated_count': 0})
    try:
        patds_pendentes = PATD.objects.filter(status='aguardando_justificativa')
        config = Configuracao.load()
        prazos_atualizados = 0
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
        return JsonResponse({'status': 'success', 'updated_count': prazos_atualizados})
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
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)
        signature_data = data.get('signature_data')
        if not signature_data:
            return JsonResponse({'status': 'error', 'message': 'Nenhum dado de assinatura recebido.'}, status=400)
        if testemunha_num == 1:
            patd.assinatura_testemunha1 = signature_data
        elif testemunha_num == 2:
            patd.assinatura_testemunha2 = signature_data
        else:
            return JsonResponse({'status': 'error', 'message': 'Número de testemunha inválido.'}, status=400)
        patd.save()
        return JsonResponse({'status': 'success', 'message': f'Assinatura da {testemunha_num}ª testemunha salva.'})
    except Exception as e:
        logger.error(f"Erro ao salvar assinatura da testemunha {testemunha_num} para PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@ouvidoria_required
@require_POST
def analisar_punicao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)

        # 1. Enquadrar os itens
        itens_obj = enquadra_item(patd.transgressao)
        
        # 2. Histórico
        historico_punicoes = PATD.objects.filter(militar=patd.militar).exclude(pk=patd.pk).count()
        historico_str = f"O militar possui {historico_punicoes} transgressões anteriores."
        
        # 3. Agravantes e Atenuantes
        justificativa = patd.alegacao_defesa or "O militar não apresentou alegação de defesa (preclusão)."
        circunstancias_obj = verifica_agravante_atenuante(historico_str, patd.transgressao, justificativa, itens_obj.item)
        
        # 4. Punição
        punicao_obj = sugere_punicao(
            patd.transgressao, 
            circunstancias_obj.item[0].get('agravantes', []), 
            circunstancias_obj.item[0].get('atenuantes', []), 
            itens_obj.item, 
            "N/A"
        )
        
        # 5. Retornar os dados para o frontend
        return JsonResponse({
            'status': 'success',
            'data': {
                'itens_enquadrados': itens_obj.item,
                'circunstancias': circunstancias_obj.item[0],
                'punicao_sugerida': punicao_obj.punicao.get('punicao', 'Erro na sugestão')
            }
        })

    except Exception as e:
        logger.error(f"Erro ao analisar punição da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@ouvidoria_required
@require_POST
def salvar_apuracao(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        data = json.loads(request.body)

        # Atualiza os campos da PATD com os dados recebidos
        patd.itens_enquadrados = data.get('itens_enquadrados')
        patd.circunstancias = data.get('circunstancias')
        punicao_sugerida_str = data.get('punicao_sugerida', '')
        patd.punicao_sugerida = punicao_sugerida_str

        # Processa a string da punição para extrair dias e tipo
        match = re.search(r'(\d+)\s+dias\s+de\s+(.+)', punicao_sugerida_str, re.IGNORECASE)
        if match:
            dias_num = int(match.group(1))
            punicao_tipo = match.group(2).strip()
            # Converte o número para extenso
            dias_texto = num2words(dias_num, lang='pt_BR')
            patd.dias_punicao = f"{dias_texto} ({dias_num:02d}) dias"
            patd.punicao = punicao_tipo
        else:
            patd.dias_punicao = ""
            patd.punicao = punicao_sugerida_str

        # Define valores placeholder para outros campos
        patd.natureza_transgressao = "Média"
        patd.transgressao_afirmativa = f"foi verificado que o militar realmente cometeu a transgressão de '{patd.transgressao}'."
        
        # Atualiza o status
        patd.status = 'aguardando_punicao'
        
        # Salva o objeto
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
        return PATD.objects.filter(status='aguardando_assinatura_npd').order_by('-data_inicio')

@login_required
@comandante_required
@require_POST
def patd_aprovar(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    patd.status = 'finalizado'
    patd.save()
    messages.success(request, f"PATD Nº {patd.numero_patd} aprovada e finalizada com sucesso.")
    return redirect('Ouvidoria:comandante_dashboard')

@login_required
@comandante_required
@require_POST
def patd_retornar(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    patd.status = 'aguardando_punicao_alterar'
    patd.save()
    messages.warning(request, f"PATD Nº {patd.numero_patd} retornada para alteração.")
    return redirect('Ouvidoria:comandante_dashboard')

@login_required
@ouvidoria_required
@require_POST
def avancar_para_comandante(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    patd.status = 'aguardando_assinatura_npd'
    patd.save()
    messages.success(request, f"PATD Nº {patd.numero_patd} enviada para análise do Comandante.")
    return redirect('Ouvidoria:patd_detail', pk=pk)
