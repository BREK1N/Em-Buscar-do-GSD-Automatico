import logging
import pandas as pd
import openpyxl
import os
import tempfile
import httpx, json
import random
import unicodedata
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from django.contrib.auth.models import Group
from Secao_pessoal.models import (
    Efetivo, Posto, Quad, Especializacao, OM, Setor, Subsetor, SolicitacaoTrocaSetor,
    HistoricoInspsau, MovimentacaoEfetivo, LotacaoPessoal,
)
from django.contrib.auth import get_user_model as _get_user_model
from caixa_entrada.models import Notificacao, Mensagem as _Mensagem

_User = _get_user_model()


def _enviar_mensagem_sistema(remetente_militar, destinatario_militar, assunto, corpo):
    """Envia uma Mensagem da nova caixa de entrada entre dois militares."""
    try:
        rem  = _User.objects.filter(profile__militar=remetente_militar).first()
        dest = _User.objects.filter(profile__militar=destinatario_militar).first()
        if rem and dest:
            msg = _Mensagem.objects.create(remetente=rem, assunto=assunto, corpo=corpo)
            msg.destinatarios.add(dest)
    except Exception:
        pass
from .forms import MilitarForm, LotacaoPessoalForm
import docx
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from django.contrib import messages
from django.db.models import Q, Max, Case, When, Value, IntegerField, Count
from difflib import SequenceMatcher
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from datetime import datetime, date, timedelta
try:
    import pytesseract
except ImportError:
    pytesseract = None
from PIL import Image
import fitz 
import io
import re
# Se estiver no Windows e der erro, descomente e ajuste o caminho do seu tesseract:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
from .analise_inspsau import analisar_inspsau_pdf
from .analise_fq import analisar_fq_documento
from chamada.models import RegistroChamada as ChamadaRegistro

logger = logging.getLogger(__name__)

def is_s1_member(user):
    return user.groups.filter(name='Seção de Pessoal (S1)').exists()

s1_required = user_passes_test(is_s1_member)

def get_chefe_por_grupo(nome_setor):
    if not nome_setor:
        return None
    nome_grupo = f"Chefe - {nome_setor}"
    try:
        grupo = Group.objects.get(name__iexact=nome_grupo)
        user_chefe = grupo.user_set.filter(is_active=True, profile__militar__isnull=False).first()
        if user_chefe:
            return user_chefe.profile.militar
    except Group.DoesNotExist:
        pass
    
    setor_obj = Setor.objects.filter(nome=nome_setor).first()
    return setor_obj.chefe if setor_obj and hasattr(setor_obj, 'chefe') else None


def obter_situacao_inspsau(letra):
    """Mapeia a finalidade da INSPSAU para o campo Situação (limite de 50 caracteres)."""
    if not letra:
        return 'Inspeção de Saúde'
    letra = letra.upper().strip()
    if letra.startswith('G'): return 'De Junta'
    elif letra.startswith('L'): return 'Licença Pessoal Navegação Aérea - LPNA'
    elif letra.startswith('A'): return 'Incorporação ou Desincorporação'
    elif letra.startswith('B'): return 'Matrícula em Escolas de Formação'
    elif letra.startswith('C'): return 'Concurso Cargos Civis no COMAER'
    elif letra.startswith('D'): return 'Verificação Periódica - Temporários'
    elif letra.startswith('E'): return 'Manutenção de Tratamento de Saúde'
    elif letra.startswith('F1'): return 'Missão no Exterior'
    elif letra.startswith('F2'): return 'Localidade Especial'
    elif letra.startswith('H'): return 'Verificação Periódica de Carreira'
    elif letra.startswith('I'): return 'Cursos Operacionais ou Ativ. Aérea'
    elif letra.startswith('J'): return 'Designação PTTC'
    elif letra.startswith('N'): return 'Ordem Judicial/Reversão/DSA'
    elif letra.startswith('O'): return 'Benefícios e Licenças'
    elif letra.startswith('P'): return 'Acidentes/Incidentes Aeronáuticos'
    elif letra.startswith('R1'): return 'Estado de Saúde Desertor/Insubmisso'
    elif letra.startswith('R2'): return 'Verificação de Capacidade Cognitiva'
    else: return f'Inspeção Finalidade {letra}'[:50]

@s1_required
def index(request):
    # Efetivo total ativo/não baixado
    efetivo = Efetivo.objects.exclude(situacao__iexact='Baixado')
    
    total_efetivo = efetivo.count()
    total_oficiais = efetivo.filter(oficial=True).count()
    total_pracas = efetivo.filter(oficial=False).count()
    total_junta = efetivo.filter(situacao__iexact='De Junta').count()

    # Efetivo por posto (Garantindo que a hierarquia completa apareça no gráfico)
    hierarquia = ['CL', 'TC', 'MJ', 'CP', '1T', '2T', 'ASP', 'SO', '1S', '2S', '3S', 'CB', 'S1', 'S2', 'REC']
    
    postos_count = efetivo.values('posto').annotate(count=Count('id'))
    contagem_dict = {item['posto']: item['count'] for item in postos_count if item['posto']}
    
    postos_labels = []
    postos_data = []
    
    # Preenche a lista com todos os postos base, colocando 0 nos que não tiverem militares
    for posto in hierarquia:
        postos_labels.append(posto)
        postos_data.append(contagem_dict.get(posto, 0))
        
    # Adiciona outros postos que não estejam na lista base (ex: Civis ou outras especialidades)
    outros_postos = set(contagem_dict.keys()) - set(hierarquia)
    for posto in sorted(list(outros_postos)):
        postos_labels.append(posto)
        postos_data.append(contagem_dict[posto])

    # Efetivo por setor
    setores_count = efetivo.values('setor').annotate(count=Count('id')).order_by('-count')
    setores_labels = [item['setor'] if item['setor'] else 'Não definido' for item in setores_count]
    setores_data = [item['count'] for item in setores_count]

    context = {
        'total_efetivo': total_efetivo,
        'total_oficiais': total_oficiais,
        'total_pracas': total_pracas,
        'total_junta': total_junta,
        'postos_labels': json.dumps(postos_labels),
        'postos_data': json.dumps(postos_data),
        'setores_labels': json.dumps(setores_labels),
        'setores_data': json.dumps(setores_data),
    }

    return render(request, 'Secao_pessoal/index.html', context)

@s1_required
def painel_chefe(request):
    efetivo = Efetivo.objects.exclude(situacao__iexact='Baixado')
    
    # EFETIVO GERAL
    total_efetivo = efetivo.count()
    total_indisponiveis = efetivo.exclude(Q(situacao__iexact='Ativo') | Q(situacao__exact='') | Q(situacao__isnull=True)).count()
    
    # SAÚDE (INSPSAU)
    hoje = timezone.now().date()
    daqui_30_dias = hoje + timedelta(days=30)
    inspsau_vencidas = efetivo.filter(inspsau_validade__lt=hoje).count()
    inspsau_a_vencer = efetivo.filter(inspsau_validade__gte=hoje, inspsau_validade__lte=daqui_30_dias).count()
    total_junta = efetivo.filter(situacao__iexact='De Junta').count()

    # CONTROLE
    trocas_pendentes = SolicitacaoTrocaSetor.objects.filter(status__in=['pendente_atual', 'pendente_destino']).count()
    total_baixados = Efetivo.objects.filter(situacao__iexact='Baixado').count()

    context = {
        'total_efetivo': total_efetivo,
        'total_indisponiveis': total_indisponiveis,
        'inspsau_vencidas': inspsau_vencidas,
        'inspsau_a_vencer': inspsau_a_vencer,
        'total_junta': total_junta,
        'trocas_pendentes': trocas_pendentes,
        'total_baixados': total_baixados,
    }

    return render(request, 'Secao_pessoal/painel_chefe.html', context)

@s1_required
def inspsau(request):
    if request.method == 'POST':
        # --- Lógica para lidar com a confirmação do usuário ---
        if 'militar_id_confirmado' in request.POST:
            militar_id = request.POST.get('militar_id_confirmado')
            finalidade_ia = request.POST.get('finalidade')
            validade_ia_str = request.POST.get('validade')
            parecer_ia = request.POST.get('parecer')
            pdf_file = request.FILES.get('pdf_file')

            if not all([militar_id, finalidade_ia, pdf_file]):
                return JsonResponse({'status': 'error', 'message': 'Dados de confirmação incompletos.'}, status=400)

            try:
                militar = Efetivo.objects.get(id=militar_id)

                significado = obter_situacao_inspsau(finalidade_ia)
                validade_obj = None
                if validade_ia_str and str(validade_ia_str).lower() != 'none':
                    try:
                        validade_obj = datetime.strptime(validade_ia_str, '%d/%m/%Y').date()
                    except (ValueError, TypeError):
                        pass

                # VERIFICA DUPLICIDADE NO HISTÓRICO
                if HistoricoInspsau.objects.filter(militar=militar, finalidade=finalidade_ia, validade=validade_obj).exists():
                    message = f"Já existe um registro de inspeção com finalidade '{finalidade_ia}' e validade '{validade_ia_str or 'N/A'}' para o militar {militar.posto} {militar.nome_guerra} no histórico."
                    return JsonResponse({'status': 'error', 'message': message}, status=409)

                militar.documento_inspsau = pdf_file
                if finalidade_ia and finalidade_ia.upper().startswith('G'):
                    militar.situacao = 'De Junta'
                elif militar.situacao == significado or militar.situacao == 'De Junta':
                    militar.situacao = 'Ativo'

                observacao_final = f"INSPSAU Finalidade: {finalidade_ia}."
                if validade_ia_str and str(validade_ia_str).lower() != 'none':
                    observacao_final += f" Validade: {validade_ia_str}"
                militar.observacao = observacao_final
                militar.inspsau_finalidade = finalidade_ia
                militar.inspsau_validade = validade_obj
                militar.inspsau_parecer = parecer_ia
                militar.save(update_fields=['observacao', 'situacao', 'documento_inspsau', 'inspsau_finalidade', 'inspsau_validade', 'inspsau_parecer'])
                messages.success(request, f"Inspeção do militar {militar.posto} {militar.nome_guerra} atualizada com sucesso. Finalidade: {finalidade_ia}.")
                return JsonResponse({'status': 'success'})
            except Efetivo.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Militar confirmado não foi encontrado.'}, status=404)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    if request.method == 'POST' and request.FILES.get('pdf_file'):
        pdf_file = request.FILES['pdf_file']
        
        try:
            # Salva o PDF num ficheiro temporário
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                for chunk in pdf_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name

            # Extração Híbrida: Tenta texto nativo, se falhar ou tiver pouco texto, faz OCR
            content = ""
            doc = fitz.open(temp_file_path)
            for page in doc:
                page_text = page.get_text()
                if len(page_text.strip()) > 50:
                    content += page_text + "\n\n"
                else:
                    try:
                        pix = page.get_pixmap(dpi=300)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        if pytesseract:
                            content += pytesseract.image_to_string(img, lang='por') + "\n\n"
                        else:
                            logger.warning("pytesseract não instalado — OCR ignorado.")
                    except Exception as e:
                        logger.warning("Erro ao realizar OCR na página: %s", e)
            doc.close()
            os.remove(temp_file_path) # Remove o ficheiro temporário

            # Analisa o conteúdo com a IA
            resultado_analise = analisar_inspsau_pdf(content)

            # Busca o militar no banco de dados
            nome_completo_ia = resultado_analise.nome_completo
            posto_ia = resultado_analise.posto
            finalidade_ia = resultado_analise.finalidade
            validade_ia_str = getattr(resultado_analise, 'validade', None)
            parecer_ia = getattr(resultado_analise, 'parecer', '')

            significado = obter_situacao_inspsau(finalidade_ia)
            
            observacao_final = f"INSPSAU Finalidade: {finalidade_ia}."
            validade_obj = None
            if validade_ia_str and str(validade_ia_str).lower() != 'none':
                observacao_final += f" Validade: {validade_ia_str}"
                try:
                    validade_obj = datetime.strptime(validade_ia_str, '%d/%m/%Y').date()
                except (ValueError, TypeError):
                    pass
            
            militar = None
            if nome_completo_ia:
                # Tenta encontrar pelo nome completo e posto para maior precisão
                candidatos = Efetivo.all_objects.filter(
                    nome_completo__icontains=nome_completo_ia,
                    posto__iexact=posto_ia
                )
                if candidatos.count() == 1:
                    militar = candidatos.first()
                else:
                    # Se não encontrar ou houver ambiguidade, tenta só pelo nome
                    candidatos = Efetivo.all_objects.filter(nome_completo__icontains=nome_completo_ia)
                    if candidatos.count() == 1:
                        militar = candidatos.first()

            if militar:
                # VERIFICA DUPLICIDADE NO HISTÓRICO
                if HistoricoInspsau.objects.filter(militar=militar, finalidade=finalidade_ia, validade=validade_obj).exists():
                    message = f"Já existe um registro de inspeção com finalidade '{finalidade_ia}' e validade '{validade_ia_str or 'N/A'}' para o militar {militar.posto} {militar.nome_guerra} no histórico."
                    return JsonResponse({'status': 'error', 'message': message}, status=409)

                # Atualiza a observação do militar com a finalidade
                militar.documento_inspsau = pdf_file # Salva o arquivo PDF
                if finalidade_ia and finalidade_ia.upper().startswith('G'):
                    militar.situacao = 'De Junta'
                elif militar.situacao == significado or militar.situacao == 'De Junta':
                    militar.situacao = 'Ativo'
                militar.observacao = observacao_final
                militar.inspsau_finalidade = finalidade_ia
                militar.inspsau_validade = validade_obj
                militar.inspsau_parecer = parecer_ia
                militar.save(update_fields=['observacao', 'situacao', 'documento_inspsau', 'inspsau_finalidade', 'inspsau_validade', 'inspsau_parecer'])

                messages.success(request, f"Inspeção do militar {militar.posto} {militar.nome_guerra} atualizada com sucesso. Finalidade: {finalidade_ia}.")
                return JsonResponse({'status': 'success'})
            else:
                # --- INÍCIO DA LÓGICA DE BUSCA POR SIMILARIDADE ---
                best_match = None
                highest_ratio = 0.7  # Limiar de similaridade de 70%

                if nome_completo_ia:
                    nome_normalizado_ia = normalize_name(nome_completo_ia)
                    todos_militares = Efetivo.all_objects.all()

                    for m in todos_militares:
                        nome_normalizado_db = normalize_name(m.nome_completo)
                        ratio = SequenceMatcher(None, nome_normalizado_ia, nome_normalizado_db).ratio()
                        
                        if ratio > highest_ratio:
                            highest_ratio = ratio
                            best_match = m
                
                if best_match:
                    # Encontrou um militar parecido. Pede confirmação ao usuário.
                    return JsonResponse({
                        'status': 'confirm',
                        'message': f"O militar '{nome_completo_ia}' não foi encontrado. Você quis dizer '{best_match.posto} {best_match.nome_completo}'?",
                        'militar_encontrado': {
                            'id': best_match.id,
                        },
                        'dados_inspsau': {
                            'finalidade': finalidade_ia,
                            'validade': validade_ia_str,
                            'parecer': parecer_ia,
                        }
                    })
                else:
                    # Não encontrou nenhum militar, nem parecido. Retorna um erro.
                    # --- ALTERAÇÃO: Retorna status 'not_found' para acionar a busca manual no frontend ---
                    return JsonResponse({
                        'status': 'not_found',
                        'message': f"O militar '{nome_completo_ia}' não foi encontrado. Deseja procurar manualmente?",
                        'dados_inspsau': {
                            'finalidade': finalidade_ia,
                            'validade': validade_ia_str,
                            'parecer': parecer_ia,
                        }
                    })


        except Exception as e:
            messages.error(request, f"Erro ao processar o PDF: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    # Dashboard básico: Lista militares que estão "De Junta" ou possuem um resultado de INSPSAU a exibir
    query = request.GET.get('q')
    militares_baixados = Efetivo.all_objects.filter(
        Q(situacao__iexact='De Junta') | Q(observacao__icontains='INSPSAU Finalidade')
    )

    if query:
        militares_baixados = militares_baixados.filter(
            Q(posto__icontains=query) |
            Q(nome_guerra__icontains=query) |
            Q(nome_completo__icontains=query) |
            Q(observacao__icontains=query)
        )

    militares_baixados = militares_baixados.order_by('nome_guerra')
    context = {'militares_baixados': militares_baixados, 'current_query': query or ''}
    return render(request, 'Secao_pessoal/inspsau.html', context)

#Efetivo

@method_decorator(s1_required, name='dispatch')
class MilitarListView(ListView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_list.html'
    context_object_name = 'militares'
    ordering = ['nome_guerra']
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['Secao_pessoal/militar_list_partial.html']
        return ['Secao_pessoal/militar_list.html']

    def get_queryset(self):
        query = self.request.GET.get('q')
        rank_order = Case(
            When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
            When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
            When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
            When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
            default=Value(99), output_field=IntegerField(),
        )
        qs = super().get_queryset().annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
        if query:
            q_objects = Q(nome_completo__icontains=query) | \
                        Q(nome_guerra__icontains=query) | \
                        Q(posto__icontains=query)
            
            if query.isdigit():
                q_objects |= Q(saram__icontains=query)
                
            qs = qs.filter(q_objects)
        return qs
    
@method_decorator(s1_required, name='dispatch')
class MilitarCreateView(CreateView):
    model = Efetivo
    form_class = MilitarForm
    template_name = 'Secao_pessoal/militar_form.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

    def get_initial(self):
        initial = super().get_initial()
        initial['nome_completo'] = self.request.GET.get('nome_completo', '')
        initial['posto'] = self.request.GET.get('posto', '')
        initial['situacao'] = self.request.GET.get('situacao', 'Ativo')
        initial['observacao'] = self.request.GET.get('observacao', '')
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Adicionar Militar'
        return context

@method_decorator(s1_required, name='dispatch')
class MilitarUpdateView(UpdateView):
    model = Efetivo
    form_class = MilitarForm
    template_name = 'Secao_pessoal/militar_form.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Militar'
        return context

@method_decorator(s1_required, name='dispatch')
class MilitarDeleteView(DeleteView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_confirm_delete.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

    def get_queryset(self):
        return Efetivo.all_objects.all()

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        nome_guerra = self.object.nome_guerra
        self.object.delete()
        messages.success(request, f"Militar {nome_guerra} excluído permanentemente.")
        return redirect(self.get_success_url())

@method_decorator(s1_required, name='dispatch')
class MilitarTrashListView(ListView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_trash_list.html'
    context_object_name = 'militares'
    paginate_by = 20

    def get_queryset(self):
        return Efetivo.all_objects.filter(deleted=True).order_by('-deleted_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_lixeira'] = Efetivo.all_objects.filter(deleted=True).count()
        return ctx

@s1_required
@require_POST
def militar_restore(request, pk):
    militar = get_object_or_404(Efetivo.all_objects, pk=pk, deleted=True)
    militar.deleted = False
    militar.deleted_at = None
    militar.save(update_fields=['deleted', 'deleted_at'])
    messages.success(request, f"Militar {militar.nome_guerra or militar.nome_completo} foi restaurado com sucesso.")
    return redirect('Secao_pessoal:militar_trash_list')

@s1_required
@require_POST
def militar_permanently_delete(request, pk):
    militar = get_object_or_404(Efetivo.all_objects, pk=pk, deleted=True)
    nome = militar.nome_guerra or militar.nome_completo
    militar.delete()
    messages.success(request, f"Militar {nome} foi excluído permanentemente.")
    return redirect('Secao_pessoal:militar_trash_list')

@s1_required
@require_POST
def militar_lixeira_esvaziar(request):
    count = Efetivo.all_objects.filter(deleted=True).count()
    Efetivo.all_objects.filter(deleted=True).delete()
    messages.success(request, f'{count} militar(es) excluído(s) permanentemente da lixeira.')
    return redirect('Secao_pessoal:militar_trash_list')

@method_decorator(s1_required, name='dispatch')
class MilitarBaixadoListView(ListView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_baixado_list.html'
    context_object_name = 'militares'
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['Secao_pessoal/militar_list_partial.html']
        return ['Secao_pessoal/militar_baixado_list.html']

    def get_queryset(self):
        query = self.request.GET.get('q')
        rank_order = Case(
            When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
            When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
            When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
            When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
            default=Value(99), output_field=IntegerField(),
        ) 
        qs = super().get_queryset().filter(situacao__iexact='De Junta').annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
        if query:
            q_objects = Q(nome_completo__icontains=query) | \
                        Q(nome_guerra__icontains=query) | \
                        Q(posto__icontains=query)
            
            if query.isdigit():
                q_objects |= Q(saram__icontains=query)
                
            qs = qs.filter(q_objects)
        return qs

@s1_required
def movimentar_militar(request):
    rank_order = Case(
        When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
        When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
        When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
        When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
        default=Value(99), output_field=IntegerField(),
    )
    militares = Efetivo.objects.exclude(situacao__iexact='Baixado').annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')

    if request.method == 'POST':
        militar_id = request.POST.get('militar_movimentacao')
        data_movimentacao = request.POST.get('data_movimentacao')
        om_destino = request.POST.get('om_destino')
        sigad_movimentacao = request.POST.get('sigad_movimentacao')
        boletim_movimentacao = request.POST.get('boletim_movimentacao')
        observacao = request.POST.get('observacao')

        if militar_id and data_movimentacao:
            try:
                militar = Efetivo.objects.get(id=militar_id)
                try:
                    data_mov = datetime.strptime(data_movimentacao, '%Y-%m-%d').date()
                except ValueError:
                    messages.error(request, 'Data da movimentação inválida.')
                    return redirect('Secao_pessoal:movimentar_militar')

                MovimentacaoEfetivo.objects.create(
                    militar=militar,
                    data_movimentacao=data_mov,
                    om_destino=om_destino or '',
                    sigad_movimentacao=sigad_movimentacao or '',
                    boletim_movimentacao=boletim_movimentacao or '',
                    observacao=observacao or '',
                )
                militar.situacao = 'Movimentado'
                militar.save()
                messages.success(request, f'Militar {militar.posto} {militar.nome_guerra} movimentado com sucesso.')
            except Efetivo.DoesNotExist:
                messages.error(request, 'Erro: Militar não encontrado.')
        else:
            messages.error(request, 'Selecione o militar e informe a data da movimentação.')

        return redirect('Secao_pessoal:movimentar_militar')

    context = {
        'militares': militares
    }
    return render(request, 'Secao_pessoal/movimentar_militar.html', context)

@method_decorator(s1_required, name='dispatch')
class MilitarMovimentadoListView(ListView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_movimentado_list.html'
    context_object_name = 'militares'
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['Secao_pessoal/militar_movimentado_list_partial.html']
        return ['Secao_pessoal/militar_movimentado_list.html']

    def get_queryset(self):
        query = self.request.GET.get('q')
        rank_order = Case(
            When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
            When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
            When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
            When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
            default=Value(99), output_field=IntegerField(),
        )
        qs = super().get_queryset().filter(situacao__iexact='Movimentado').annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
        if query:
            q_objects = Q(nome_completo__icontains=query) | \
                        Q(nome_guerra__icontains=query) | \
                        Q(posto__icontains=query)
            if query.isdigit():
                q_objects |= Q(saram__icontains=query)
            qs = qs.filter(q_objects)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        militares = ctx.get('militares') or []
        militares_ids = [m.pk for m in militares]
        ultimas = {}
        for mov in MovimentacaoEfetivo.objects.filter(militar_id__in=militares_ids).order_by('militar_id', '-data_movimentacao'):
            ultimas.setdefault(mov.militar_id, mov)
        for militar in militares:
            militar.ultima_movimentacao = ultimas.get(militar.pk)
        return ctx

@s1_required
def gerar_ficha_desimpedimento(request, pk):
    militar = get_object_or_404(Efetivo.all_objects, pk=pk)

    document = docx.Document()
    section = document.sections[0]

    def add_centered(text, bold=False, size=12):
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = bold
        run.font.size = Pt(size)
        return p

    add_centered('MINISTÉRIO DA DEFESA', bold=True)
    add_centered('COMANDO DA AERONÁUTICA', bold=True)
    add_centered(militar.om or '', bold=True)
    add_centered('ESQUADRÃO DE PESSOAL', bold=True)
    add_centered('FICHA DE DESIMPEDIMENTO', bold=True, size=14)
    document.add_paragraph('')

    def add_field(label, valor):
        p = document.add_paragraph()
        run_label = p.add_run(f'{label}: ')
        run_label.bold = True
        p.add_run(str(valor) if valor else '—')

    add_field('Nome do Militar', militar.nome_completo)
    add_field('Posto/Grad', militar.posto)
    add_field('Documento de Publicação', militar.documento_desligamento)
    add_field('OM', militar.om)
    add_field('Motivo do Desligamento', militar.motivo_desligamento)
    add_field('SARAM', militar.saram)
    add_field('Função (conforme publicado)', militar.funcao_desligamento)
    add_field('Setor', militar.setor)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    nome_arquivo = f"ficha_desimpedimento_{militar.nome_guerra or militar.pk}.docx".replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    document.save(response)
    return response

#EFETIVO IMPORT EXCEL
@s1_required
def importar_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        sincronizar = request.POST.get('sincronizar') == '1'

        try:
            # Lê o arquivo Excel e converte tudo para string para evitar erros de tipo
            df = pd.read_excel(excel_file, dtype=str)

            # Remove espaços em branco dos nomes das colunas
            df.columns = df.columns.str.strip()

            # Renomeia as colunas para os nomes canônicos esperados abaixo, aceitando
            # variações de acentuação/maiúsculas/abreviação/pontuação no cabeçalho da
            # planilha (ex.: "Posto", "PST", "Pst." todos casam com "PST."). Sem isso,
            # um cabeçalho ligeiramente diferente faz todas as linhas serem ignoradas.
            ALIASES_COLUNAS_EFETIVO = {
                'SARAM': ['SARAM'],
                'NOME COMPLETO': ['NOME COMPLETO', 'NOME'],
                'PST.': ['PST', 'POSTO', 'POSTOGRAD', 'POSTO GRAD'],
                'QUAD.': ['QUAD', 'QUADRO'],
                'ESP.': ['ESP', 'ESPECIALIZACAO', 'ESPECIALIDADE'],
                'NOME DE GUERRA': ['NOME DE GUERRA', 'NOME GUERRA', 'GUERRA'],
                'TURMA': ['TURMA'],
                'SITUAÇÃO': ['SITUACAO'],
                'OM': ['OM'],
                'SETOR': ['SETOR'],
                'SUBSETOR': ['SUBSETOR'],
            }
            colunas_normalizadas = {
                re.sub(r'\s+', ' ', re.sub(r'[.\/]', '', normalize_name(str(c)))).strip(): c
                for c in df.columns
            }
            renomear = {}
            for canonico, aliases in ALIASES_COLUNAS_EFETIVO.items():
                for alias in aliases:
                    col_real = colunas_normalizadas.get(alias)
                    if col_real:
                        renomear[col_real] = canonico
                        break
            df.rename(columns=renomear, inplace=True)

            # Substitui valores 'nan' (vazios) do pandas por string vazia
            df.fillna('', inplace=True)

            criados = 0
            atualizados = 0

            # Coleta valores únicos para criar no controle geral ao final
            postos_excel = set()
            quads_excel = set()
            especs_excel = set()
            oms_excel = set()
            setores_excel = set()
            subsetores_excel = set()

            # Mapa de militares já existentes sem SARAM confiável, indexado pelo nome
            # normalizado (sem acentos, maiúsculas, espaços colapsados), para evitar
            # criar registros duplicados quando o nome da planilha não é idêntico
            # byte-a-byte ao nome já salvo no banco.
            existentes_por_nome = {}
            for efetivo_existente in Efetivo.all_objects.all():
                chave = normalize_name(efetivo_existente.nome_completo).strip()
                if chave:
                    existentes_por_nome[chave] = efetivo_existente

            # IDs dos militares encontrados/criados nesta planilha, usados pelo modo
            # "importar e sincronizar" para saber quem NÃO está na planilha.
            pks_na_planilha = set()

            for index, row in df.iterrows():
                # Pega valores essenciais
                saram_valor = str(row.get('SARAM', '')).strip()
                nome_completo_valor = row.get('NOME COMPLETO', '').strip()

                # Se não tem SARAM E não tem nome, aí sim a linha é inútil e pulamos
                if not saram_valor and not nome_completo_valor:
                    continue

                # Tratamento do SARAM para salvar no banco (IntegerField exige número ou None)
                saram_db = None
                if saram_valor:
                    try:
                        # Converte de "12345.0" para 12345 caso o pandas tenha lido como float
                        saram_db = int(float(saram_valor))
                    except ValueError:
                        saram_db = None

                # Dicionário com os dados a serem salvos/atualizados
                dados_militar = {
                    'posto': row.get('PST.', '').strip(),
                    'quad': row.get('QUAD.', '').strip(),
                    'especializacao': row.get('ESP.', '').strip(),
                    'saram': saram_db, # Usando a variável tratada
                    'nome_completo': nome_completo_valor,
                    'nome_guerra': row.get('NOME DE GUERRA', '').strip(),
                    'turma': row.get('TURMA', '').strip(),
                    'situacao': row.get('SITUAÇÃO', '').strip(),
                    'om': row.get('OM', '').strip(),
                    'setor': row.get('SETOR', '').strip(),
                    'subsetor': row.get('SUBSETOR', '').strip(),
                    # Se o militar estava na lixeira, reimportá-lo via planilha deve
                    # restaurá-lo para o efetivo ativo — caso contrário ele continua
                    # "atualizado" mas invisível na lista geral.
                    'deleted': False,
                    'deleted_at': None,
                        }

                # Acumula valores não-vazios para criar no controle geral
                if dados_militar['posto']:
                    postos_excel.add(dados_militar['posto'])
                if dados_militar['quad']:
                    quads_excel.add(dados_militar['quad'])
                if dados_militar['especializacao']:
                    especs_excel.add(dados_militar['especializacao'])
                if dados_militar['om']:
                    oms_excel.add(dados_militar['om'])
                if dados_militar['setor']:
                    setores_excel.add(dados_militar['setor'])
                if dados_militar['subsetor']:
                    subsetores_excel.add(dados_militar['subsetor'])

                # LÓGICA DE SALVAMENTO INTELIGENTE:
                if saram_db:
                    # Se tem SARAM, a chave principal é o SARAM
                    obj, created = Efetivo.all_objects.update_or_create(
                        saram=saram_db,
                        defaults=dados_militar
                    )
                else:
                    # Se é um recruta sem SARAM, casa pelo nome normalizado (ignora
                    # acentos/maiúsculas/espaços) para não criar duplicado quando o
                    # nome da planilha não é idêntico ao já salvo no banco.
                    chave_nome = normalize_name(nome_completo_valor).strip()
                    existente = existentes_por_nome.get(chave_nome)
                    if existente:
                        for campo, valor in dados_militar.items():
                            setattr(existente, campo, valor)
                        existente.save()
                        obj, created = existente, False
                    else:
                        obj = Efetivo.all_objects.create(**dados_militar)
                        created = True
                        existentes_por_nome[chave_nome] = obj

                if created:
                    criados += 1
                else:
                    atualizados += 1

                pks_na_planilha.add(obj.pk)

            removidos = 0
            sincronizar_abortada = False
            if sincronizar:
                if criados == 0 and atualizados == 0:
                    # Nenhuma linha da planilha foi reconhecida (provável incompatibilidade
                    # de colunas) — não sincroniza para não apagar todo o efetivo existente.
                    sincronizar_abortada = True
                else:
                    agora = timezone.now()
                    nao_encontrados = Efetivo.objects.exclude(pk__in=pks_na_planilha)
                    removidos = nao_encontrados.update(deleted=True, deleted_at=agora)

            # Cria opções do controle geral sem duplicar (get_or_create é idempotente)
            for v in postos_excel:
                Posto.objects.get_or_create(nome=v)
            for v in quads_excel:
                Quad.objects.get_or_create(nome=v)
            for v in especs_excel:
                Especializacao.objects.get_or_create(nome=v)
            for v in oms_excel:
                OM.objects.get_or_create(nome=v)
            for v in setores_excel:
                Setor.objects.get_or_create(nome=v)
            for v in subsetores_excel:
                Subsetor.objects.get_or_create(nome=v)

            if sincronizar_abortada:
                messages.error(request, 'Nenhum militar foi reconhecido na planilha (verifique se as colunas "SARAM" e "NOME COMPLETO" estão corretas). A sincronização foi cancelada para evitar apagar o efetivo existente.')
            elif sincronizar:
                messages.success(request, f'Sucesso! {criados} militares criados, {atualizados} atualizados e {removidos} removidos (enviados para a lixeira) por não constarem na planilha.')
            else:
                messages.success(request, f'Sucesso! {criados} militares criados e {atualizados} atualizados.')
            return redirect('Secao_pessoal:militar_list') # Verifique o nome da sua rota de listagem

        except Exception as e:
            messages.error(request, f'Erro na importação: {str(e)}')
            return redirect('Secao_pessoal:importar_excel')

    return render(request, 'Secao_pessoal/importar_excel.html')
    
# --- Lógica para Nome de Guerra ---

def normalize_name(name):
    """Remove acentos e caracteres especiais para comparação (ex: 'Corrêa' -> 'CORREA')."""
    if not name:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn').upper()

def gerar_sugestoes_guerra(nome_completo):
    """Gera uma lista de possíveis nomes de guerra baseados no nome completo, em ordem de prioridade."""
    ignore = ['de', 'da', 'do', 'dos', 'das', 'e']
    partes = [p for p in nome_completo.split() if p.lower() not in ignore]
    
    if not partes:
        return []
    
    sugestoes = []
    
    def add_unique(nome):
        nome = nome.upper()
        if nome not in sugestoes:
            sugestoes.append(nome)
    
    # 1. Último nome (Padrão)
    add_unique(partes[-1])
    
    # 2. Penúltimo (se houver e não for o primeiro)
    if len(partes) > 2:
        add_unique(partes[-2])

    # 3. Nomes Compostos (ex: Del Puerto, Villas Boas)
    if len(partes) >= 2:
        add_unique(f"{partes[-2]} {partes[-1]}")

    # 4. Primeiro + Último (Prioriza abreviação se o nome for longo)
    primeiro_ultimo = f"{partes[0]} {partes[-1]}"
    inicial_ultimo = f"{partes[0][0]}. {partes[-1]}"
    
    if len(partes[0]) > 5: # Ex: Leonardo (8) -> L. MARTINS
        add_unique(inicial_ultimo)
        add_unique(primeiro_ultimo)
    else:
        add_unique(primeiro_ultimo)
        add_unique(inicial_ultimo)
    
    # 5. Outras combinações
    if len(partes) > 2:
        primeiro_penultimo = f"{partes[0]} {partes[-2]}"
        inicial_penultimo = f"{partes[0][0]}. {partes[-2]}"
        
        if len(partes[0]) > 5:
            add_unique(inicial_penultimo)
            add_unique(primeiro_penultimo)
        else:
            add_unique(primeiro_penultimo)
            add_unique(inicial_penultimo)

    for i in range(1, len(partes)-1):
        add_unique(partes[i])
        # Adiciona combinações com nomes do meio, também verificando tamanho
        comb_nome = f"{partes[0]} {partes[i]}"
        comb_inicial = f"{partes[0][0]}. {partes[i]}"
        
        if len(partes[0]) > 5:
            add_unique(comb_inicial)
            add_unique(comb_nome)
        else:
            add_unique(comb_nome)
            add_unique(comb_inicial)

    return sugestoes

@s1_required
def nome_de_guerra(request):
    if request.method == 'POST':
        try:
            # 1. Buscar Recrutas no Banco de Dados
            recrutas = Efetivo.objects.filter(posto='REC').exclude(situacao__iexact='Baixado')
            
            if not recrutas.exists():
                messages.warning(request, "Nenhum militar com posto 'REC' encontrado no efetivo.")
                return redirect('Secao_pessoal:nome_de_guerra')

            # Carrega todos os nomes existentes e normaliza para comparação rápida e sem acentos
            existing_names_map = {}
            all_efetivo = Efetivo.objects.exclude(nome_guerra__isnull=True).exclude(nome_guerra='').values('id', 'nome_guerra')
            
            for item in all_efetivo:
                norm = normalize_name(item['nome_guerra'])
                if norm not in existing_names_map:
                    existing_names_map[norm] = set()
                existing_names_map[norm].add(item['id'])

            nomes_usados_sessao_norm = set() # Rastreia nomes gerados nesta sessão (normalizados)
            count_atualizados = 0

            for recruta in recrutas:
                sugestoes = gerar_sugestoes_guerra(recruta.nome_completo)
                nome_final = None
                
                for sugestao in sugestoes:
                    sugestao_norm = normalize_name(sugestao)
                    
                    # Verifica conflito no DB (se existe e não é o próprio recruta)
                    ids_com_esse_nome = existing_names_map.get(sugestao_norm, set())
                    conflito_db = bool(ids_com_esse_nome - {recruta.pk})
                    
                    # Verifica conflito na sessão atual
                    conflito_sessao = sugestao_norm in nomes_usados_sessao_norm

                    if not conflito_db and not conflito_sessao:
                        nome_final = sugestao
                        break
                
                if not nome_final:
                    base = sugestoes[0] if sugestoes else "MILITAR"
                    contador = 2
                    while True:
                        teste = f"{base} {contador}"
                        teste_norm = normalize_name(teste)
                        
                        ids_com_esse_nome = existing_names_map.get(teste_norm, set())
                        conflito_db = bool(ids_com_esse_nome - {recruta.pk})
                        conflito_sessao = teste_norm in nomes_usados_sessao_norm

                        if not conflito_db and not conflito_sessao:
                            nome_final = teste
                            break
                        contador += 1

                nomes_usados_sessao_norm.add(normalize_name(nome_final))

                # Atualiza diretamente no banco de dados
                recruta.nome_guerra = nome_final
                recruta.save()
                count_atualizados += 1
            
            messages.success(request, f"Sucesso! Nomes de guerra atualizados para {count_atualizados} recrutas.")
            return redirect('Secao_pessoal:nome_de_guerra')
            
        except Exception as e:
            messages.error(request, f"Erro ao gerar nomes: {str(e)}")
            return redirect('Secao_pessoal:nome_de_guerra')

    return render(request, 'Secao_pessoal/nome_de_guerra.html')

def comunicacoes(request):
    """Redirecionamento de compatibilidade — caixa de entrada movida para caixa_entrada app."""
    from django.shortcuts import redirect
    return redirect('caixa_entrada:comunicacoes')

@s1_required
def troca_de_setor(request):
    militares = Efetivo.objects.exclude(situacao__iexact='Baixado').order_by('nome_guerra')
    setores = Setor.objects.all().order_by('nome')

    if request.method == 'POST':
        militar_id = request.POST.get('militar_id')
        setor_destino = request.POST.get('setor_destino')

        if militar_id and setor_destino:
            militar = get_object_or_404(Efetivo, id=militar_id)
            setor_atual_str = militar.setor or ''
            
            def get_chefe_por_grupo(nome_setor):
                if not nome_setor:
                    return None
                nome_grupo = f"Chefe - {nome_setor}"
                try:
                    grupo = Group.objects.get(name__iexact=nome_grupo)
                    user_chefe = grupo.user_set.filter(is_active=True, profile__militar__isnull=False).first()
                    if user_chefe:
                        return user_chefe.profile.militar
                except Group.DoesNotExist:
                    pass
                return None
            
            chefe_atual = get_chefe_por_grupo(setor_atual_str)
            if not chefe_atual:
                setor_atual_obj = Setor.objects.filter(nome=setor_atual_str).first()
                chefe_atual = setor_atual_obj.chefe if setor_atual_obj else None
            
            chefe_destino = get_chefe_por_grupo(setor_destino)
            if not chefe_destino:
                setor_destino_obj = Setor.objects.filter(nome=setor_destino).first()
                chefe_destino = setor_destino_obj.chefe if setor_destino_obj else None
            
            if not chefe_destino:
                messages.error(request, f'O setor de destino ({setor_destino}) não possui um chefe configurado no sistema (Grupo "Chefe - {setor_destino}"). Por favor, defina um chefe para este setor na página de Administração.')
                return redirect('Secao_pessoal:troca_de_setor')
                
            status_inicial = 'pendente_atual' if chefe_atual else 'pendente_destino'
            
            solicitacao = SolicitacaoTrocaSetor.objects.create(
                militar=militar,
                setor_atual=setor_atual_str or 'Não definido',
                setor_destino=setor_destino,
                chefe_atual=chefe_atual,
                chefe_destino=chefe_destino,
                status=status_inicial
            )
            
            try:
                S1_militar = request.user.profile.militar
                if not S1_militar:
                    S1_militar = chefe_destino
            except:
                S1_militar = chefe_destino

            if chefe_atual:
                messages.success(request, f'Solicitação criada. Aguardando autorização do chefe atual ({chefe_atual.posto} {chefe_atual.nome_guerra}).')
            else:
                messages.success(request, f'Militar sem chefe atual. Solicitação enviada diretamente para autorização do chefe de destino ({chefe_destino.posto} {chefe_destino.nome_guerra}).')
                
            return redirect('Secao_pessoal:troca_de_setor')
        else:
            messages.error(request, 'Preencha todos os campos corretamente.')

    solicitacoes = SolicitacaoTrocaSetor.objects.all()

    context = {
        'militares': militares,
        'setores': setores,
        'solicitacoes': solicitacoes
    }
    return render(request, 'Secao_pessoal/troca_de_setor.html', context)

@login_required
@xframe_options_sameorigin
def responder_troca_setor(request, solicitacao_id, acao):
    solicitacao = get_object_or_404(SolicitacaoTrocaSetor, id=solicitacao_id)
    militar_logado = None
    try:
        if hasattr(request.user, 'profile'):
            militar_logado = request.user.profile.militar
    except:
        pass
        
    if not militar_logado and not request.user.is_superuser:
        messages.error(request, "Seu usuário não está vinculado a um militar.")
        return redirect('caixa_entrada:comunicacoes')
    
    if solicitacao.status == 'pendente_atual':
        if solicitacao.chefe_atual != militar_logado and not is_s1_member(request.user) and not request.user.is_superuser:
            messages.error(request, 'Você não tem permissão para responder a esta solicitação.')
            return redirect('caixa_entrada:comunicacoes')
            
        if acao == 'aprovar':
            solicitacao.status = 'pendente_destino'
            solicitacao.save()
            if solicitacao.chefe_destino:
                _enviar_mensagem_sistema(
                    militar_logado, solicitacao.chefe_destino,
                    f"Autorização pendente: troca de setor de {solicitacao.militar.nome_guerra}",
                    f"A saída do {solicitacao.militar.posto} {solicitacao.militar.nome_guerra} do setor {solicitacao.setor_atual} foi autorizada. Aguarda sua autorização de entrada no setor {solicitacao.setor_destino}.",
                )
            messages.success(request, 'Saída autorizada com sucesso. Aguardando autorização do setor de destino.')
        elif acao == 'rejeitar':
            solicitacao.status = 'rejeitado'
            solicitacao.save()
            _enviar_mensagem_sistema(
                militar_logado, solicitacao.militar,
                f"Solicitação de troca de setor rejeitada",
                f"Sua solicitação de troca do setor {solicitacao.setor_atual} para {solicitacao.setor_destino} foi rejeitada pelo {militar_logado.posto} {militar_logado.nome_guerra}.",
            )
            messages.success(request, 'Solicitação de troca rejeitada.')

    elif solicitacao.status == 'pendente_destino':
        if solicitacao.chefe_destino != militar_logado and not is_s1_member(request.user) and not request.user.is_superuser:
            messages.error(request, 'Você não tem permissão para responder a esta solicitação.')
            return redirect('caixa_entrada:comunicacoes')

        if acao == 'aprovar':
            solicitacao.status = 'aprovado'
            solicitacao.save()

            militar = solicitacao.militar
            militar.setor = solicitacao.setor_destino
            militar.save()
            _enviar_mensagem_sistema(
                militar_logado, solicitacao.militar,
                f"Troca de setor aprovada",
                f"Sua transferência para o setor {solicitacao.setor_destino} foi aprovada pelo {militar_logado.posto} {militar_logado.nome_guerra}. Você já foi movido para o novo setor.",
            )
            messages.success(request, 'Entrada autorizada com sucesso. O militar foi transferido de setor.')
        elif acao == 'rejeitar':
            solicitacao.status = 'rejeitado'
            solicitacao.save()
            _enviar_mensagem_sistema(
                militar_logado, solicitacao.militar,
                f"Solicitação de troca de setor rejeitada",
                f"Sua solicitação de entrada no setor {solicitacao.setor_destino} foi rejeitada pelo {militar_logado.posto} {militar_logado.nome_guerra}.",
            )
            messages.success(request, 'Solicitação de troca rejeitada.')
            
    return redirect(request.META.get('HTTP_REFERER', 'caixa_entrada:comunicacoes'))

POSTOS_DESIMPEDIMENTO_PRACA = ['CB', 'S1', 'S2']
POSTOS_DESIMPEDIMENTO_GRADUADO_OF = ['TC', 'MJ', 'CP', '1T', '2T', 'ASP', 'SO', '1S', '2S', '3S']


@s1_required
def desimpedimento_busca(request):
    rank_order = Case(
        When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
        When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
        When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
        When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
        default=Value(99), output_field=IntegerField(),
    )
    query = request.GET.get('q')
    tab = request.GET.get('tab') if request.GET.get('tab') in ('praca', 'graduado') else 'praca'
    postos = POSTOS_DESIMPEDIMENTO_GRADUADO_OF if tab == 'graduado' else POSTOS_DESIMPEDIMENTO_PRACA

    militares = Efetivo.objects.filter(posto__in=postos).annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
    if query:
        q_objects = Q(nome_completo__icontains=query) | Q(nome_guerra__icontains=query) | Q(posto__icontains=query)
        if query.isdigit():
            q_objects |= Q(saram__icontains=query)
        militares = militares.filter(q_objects)

    paginator = Paginator(militares, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    template_name = 'Secao_pessoal/desimpedimento_busca_partial.html' if request.headers.get('x-requested-with') == 'XMLHttpRequest' else 'Secao_pessoal/desimpedimento_busca.html'
    return render(request, template_name, {
        'militares': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'tab': tab,
    })


@s1_required
def desimpedimento_form(request, pk):
    militar = get_object_or_404(Efetivo, pk=pk)
    return render(request, 'Secao_pessoal/desimpedimento_form.html', {'militar': militar})


@s1_required
@require_POST
def desimpedimento_gerar_pdf(request, pk):
    from django.contrib.staticfiles import finders
    import shutil
    import subprocess

    militar = get_object_or_404(Efetivo, pk=pk)

    documento_desligamento = request.POST.get('documento_desligamento', '')
    motivo_desligamento = request.POST.get('motivo_desligamento', '')
    data_desligamento_str = request.POST.get('data_desligamento', '')
    salvar_no_cadastro = request.POST.get('salvar_no_cadastro') == '1'

    data_desligamento = None
    if data_desligamento_str:
        try:
            data_desligamento = datetime.strptime(data_desligamento_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    if salvar_no_cadastro:
        militar.documento_desligamento = documento_desligamento
        militar.motivo_desligamento = motivo_desligamento
        militar.data_desligamento = data_desligamento
        militar.save()

    if militar.posto in POSTOS_DESIMPEDIMENTO_GRADUADO_OF:
        template_filename = 'ficha_desimpedimento_graduado_of_template.xlsx'
        print_area_last_row = 35
        image_offset_emu = 26543
    else:
        template_filename = 'ficha_desimpedimento_template.xlsx'
        print_area_last_row = 31
        image_offset_emu = 156210

    template_path = finders.find(f'Secao_pessoal/templates_pdf/{template_filename}')
    if not template_path:
        messages.error(request, 'Modelo de Ficha de Desimpedimento não encontrado.')
        return redirect('Secao_pessoal:desimpedimento_form', pk=pk)

    tmp_dir = tempfile.mkdtemp()
    xlsx_path = os.path.join(tmp_dir, 'ficha_preenchida.xlsx')
    pdf_path = os.path.join(tmp_dir, 'ficha_preenchida.pdf')
    shutil.copyfile(template_path, xlsx_path)

    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.worksheets[0]
    ws['C11'] = militar.nome_completo or ''
    ws['F11'] = f"{militar.posto or ''} {militar.quad or ''}".strip()
    ws['C12'] = documento_desligamento
    ws['F12'] = militar.om or ''
    ws['C13'] = motivo_desligamento
    ws['F13'] = militar.saram or ''
    ws['C14'] = militar.setor or ''
    ws['F14'] = militar.setor or ''
    ws['F15'] = data_desligamento.strftime('%d/%m/%Y') if data_desligamento else ''

    # Limita a área de impressão à tabela real (até a coluna F, alinhada com a logo
    # BINFAE-GL) e desliga a impressão das linhas de grade, já que a planilha tem
    # preenchimento branco em células vazias até a coluna R que expandia a página
    # impressa muito além da tabela.
    ws.print_area = f'A1:F{print_area_last_row}'
    ws.print_options.gridLines = False
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1

    # Sobe o documento na folha: reduz a margem superior (a logo fica rente à borda
    # de impressão) e soma a diferença na margem inferior, mantendo a altura
    # impressa igual e deixando a sobra de espaço no fim da página.
    ws.page_margins.top = 0.15
    ws.page_margins.bottom = 1.35

    # Move a logo do brasão um pouco para a direita para centralizá-la com a
    # frase "MINISTÉRIO DA DEFESA".
    if ws._images:
        ws._images[0].anchor._from.colOff += image_offset_emu

    wb.save(xlsx_path)

    try:
        subprocess.run(
            ['soffice', '--headless', '--norestore', '--convert-to', 'pdf', '--outdir', tmp_dir, xlsx_path],
            check=True, timeout=60, capture_output=True,
        )
        with open(pdf_path, 'rb') as f:
            pdf_bytes = f.read()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    nome_arquivo = f"ficha_desimpedimento_{militar.nome_guerra or militar.pk}.pdf".replace(' ', '_')
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nome_arquivo}"'
    return response

@s1_required
def baixa(request):
    rank_order = Case(
        When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
        When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
        When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
        When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
        default=Value(99), output_field=IntegerField(),
    )
    militares = Efetivo.objects.exclude(situacao__iexact='Baixado').annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
    
    if request.method == 'POST':
        militar_id = request.POST.get('militar_baixa')
        data_baixa = request.POST.get('data_baixa')
        motivo_baixa = request.POST.get('motivo_baixa')
        
        if militar_id:
            try:
                militar = Efetivo.objects.get(id=militar_id) # type: ignore
                militar.situacao = 'De Junta' # Ao invés de deletar, apenas altera a situação
                militar.observacao = motivo_baixa # Salva o motivo da baixa
                militar.motivo_desligamento = motivo_baixa
                if data_baixa:
                    try:
                        militar.data_desligamento = datetime.strptime(data_baixa, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                militar.save()
                messages.success(request, f'Militar {militar.posto} {militar.nome_guerra} desligado do efetivo com sucesso.')
            except Efetivo.DoesNotExist:
                messages.error(request, 'Erro: Militar não encontrado.')
                
        return redirect('Secao_pessoal:baixa')

    context = {
        'militares': militares
    }
    return render(request, 'Secao_pessoal/baixa.html', context)

@s1_required
def indisponiveis(request):
    rank_order = Case(
        When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
        When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
        When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
        When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
        default=Value(99), output_field=IntegerField(),
    )
    # Traz todos os militares onde a situação não seja "Ativo" e não seja vazia
    militares = Efetivo.objects.exclude(
        Q(situacao__iexact='Ativo') | Q(situacao__exact='') | Q(situacao__isnull=True)
    ).annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
    
    context = {
        'militares': militares
    }
    return render(request, 'Secao_pessoal/indisponiveis.html', context)

@s1_required
def reintegrar_militar(request, pk):
    if request.method == 'POST':
        try:
            militar = get_object_or_404(Efetivo.all_objects, id=pk)
            
            # Se o militar tem dados de inspeção, arquiva-os no histórico e limpa os campos
            if militar.inspsau_finalidade or militar.documento_inspsau:
                HistoricoInspsau.objects.create(
                    militar=militar,
                    finalidade=militar.inspsau_finalidade,
                    validade=militar.inspsau_validade,
                    documento=militar.documento_inspsau,
                    parecer=militar.inspsau_parecer
                )
                militar.documento_inspsau = None
                militar.inspsau_finalidade = None
                militar.inspsau_validade = None
                militar.inspsau_parecer = None

            militar.situacao = 'Ativo' # Retorna a situação para Ativo
            militar.observacao = '' # Limpa o histórico de período/motivo
            militar.save()
            
            messages.success(request, f'Militar {militar.posto} {militar.nome_guerra} reintegrado ao efetivo ativo com sucesso.')
        except Efetivo.DoesNotExist:
            messages.error(request, 'Erro: Militar não encontrado.')
            
    return redirect(request.META.get('HTTP_REFERER', 'Secao_pessoal:militar_list'))

@method_decorator(s1_required, name='dispatch')
class LotacaoPessoalListView(ListView):
    model = LotacaoPessoal
    template_name = 'Secao_pessoal/lotacao_list.html'
    context_object_name = 'lotacoes'
    paginate_by = 50

@method_decorator(s1_required, name='dispatch')
class LotacaoPessoalCreateView(CreateView):
    model = LotacaoPessoal
    form_class = LotacaoPessoalForm
    template_name = 'Secao_pessoal/lotacao_form.html'
    success_url = reverse_lazy('Secao_pessoal:lotacao_list')

@method_decorator(s1_required, name='dispatch')
class LotacaoPessoalUpdateView(UpdateView):
    model = LotacaoPessoal
    form_class = LotacaoPessoalForm
    template_name = 'Secao_pessoal/lotacao_form.html'
    success_url = reverse_lazy('Secao_pessoal:lotacao_list')

@method_decorator(s1_required, name='dispatch')
class LotacaoPessoalDeleteView(DeleteView):
    model = LotacaoPessoal
    template_name = 'Secao_pessoal/lotacao_confirm_delete.html'
    success_url = reverse_lazy('Secao_pessoal:lotacao_list')

@s1_required
def relatorio_tlp(request):
    existente_qs = Efetivo.objects.exclude(situacao__iexact='Baixado') \
        .values('posto', 'quad', 'especializacao', 'om').annotate(existente=Count('id'))
    existente_map = {
        (r['posto'], r['quad'], r['especializacao'], r['om']): r['existente']
        for r in existente_qs
    }

    linhas = []
    vistos = set()
    for lot in LotacaoPessoal.objects.all():
        chave = (lot.posto, lot.quad, lot.especializacao, lot.om)
        existente = existente_map.get(chave, 0)
        linhas.append({
            'posto': lot.posto, 'quad': lot.quad, 'especializacao': lot.especializacao,
            'om': lot.om, 'vagas_previstas': lot.vagas_previstas,
            'existente': existente, 'saldo': existente - lot.vagas_previstas,
        })
        vistos.add(chave)

    for chave, existente in existente_map.items():
        if chave not in vistos and any(chave):
            linhas.append({
                'posto': chave[0], 'quad': chave[1], 'especializacao': chave[2],
                'om': chave[3], 'vagas_previstas': 0, 'existente': existente, 'saldo': existente,
            })

    return render(request, 'Secao_pessoal/relatorio_tlp.html', {'linhas': linhas})

@s1_required
def gerenciar_opcoes(request):
    # Dicionário que mapeia o 'tipo' do formulário para a Model correspondente
    MAPA_OPCOES = {
        'posto': Posto,
        'quad': Quad,
        'especializacao': Especializacao,
        'om': OM,
        'setor': Setor,
        'subsetor': Subsetor,
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        tipo_opcao = request.POST.get('tipo_opcao') # Pega o tipo de opção para o redirect
        
        # Ação para ADICIONAR um novo item
        if action == 'add':
            nome = request.POST.get('nome', '').strip()
            
            if tipo_opcao in MAPA_OPCOES and nome:
                model = MAPA_OPCOES[tipo_opcao]
                # 'get_or_create' evita duplicatas
                obj, created = model.objects.get_or_create(nome=nome)
                if created:
                    messages.success(request, f'Opção "{nome}" adicionada com sucesso.')
                else:
                    messages.warning(request, f'Opção "{nome}" já existia.')
            else:
                messages.error(request, 'Erro ao adicionar a opção. Verifique os dados.')

        # Ação para DELETAR um item
        elif action == 'delete':
            item_id = request.POST.get('item_id')

            if tipo_opcao in MAPA_OPCOES and item_id:
                model = MAPA_OPCOES[tipo_opcao]
                try:
                    item = model.objects.get(id=item_id)
                    item_nome = item.nome
                    item.delete()
                    messages.success(request, f'Opção "{item_nome}" removida com sucesso.')
                except model.DoesNotExist:
                    messages.error(request, 'Erro: A opção que você tentou remover não existe.')

        # Redireciona para a mesma página, mantendo o tipo selecionado na URL
        redirect_url = reverse_lazy('Secao_pessoal:gerenciar_opcoes')
        if tipo_opcao:
            return redirect(f'{redirect_url}?tipo={tipo_opcao}')
        return redirect(redirect_url)

    # Contexto para o método GET (carregamento da página)
    context = {
        'postos': Posto.objects.all(),
        'quads': Quad.objects.all(),
        'especializacoes': Especializacao.objects.all(),
        'oms': OM.objects.all(),
        'setores': Setor.objects.all(),
        'subsetores': Subsetor.objects.all(),
        'selected_tipo': request.GET.get('tipo', 'posto'), # Pega da URL ou define um padrão
    }
    return render(request, 'Secao_pessoal/gerenciar_opcoes.html', context)

@s1_required
def exportar_efetivo(request):
    if request.method == 'POST':
        filtro = request.POST.get('filtro')
        
        # Cria o Workbook e a planilha ativa
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Efetivo Exportado"

        # Estilos
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        alignment_center = Alignment(horizontal="center", vertical="center")
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

        # Define os cabeçalhos solicitados
        headers = ["POSTO", "NOME DE GUERRA", "NOME COMPLETO", "SARAM"]
        ws.append(headers)

        # Aplica estilo ao cabeçalho
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = alignment_center

        # Base da query com ordenação hierárquica (Mesma lógica da MilitarListView)
        rank_order = Case(
            When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
            When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
            When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
            When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
            default=Value(99), output_field=IntegerField(),
        )
        queryset = Efetivo.objects.exclude(situacao__iexact='Baixado').annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_guerra')

        # Aplica os filtros
        if filtro == 'todos':
            pass # Pega tudo
        elif filtro == 'oficiais':
            queryset = queryset.filter(oficial=True)
        elif filtro == 'pracas':
            queryset = queryset.filter(oficial=False)
        elif filtro:
            # Assume que é um posto específico (ex: 'CB', 'REC', '3S')
            queryset = queryset.filter(posto=filtro)

        # Preenche os dados
        for militar in queryset:
            ws.append([
                str(militar.posto),
                militar.nome_guerra,
                militar.nome_completo,
                militar.saram if militar.saram else ""
            ])

        # Aplica bordas e alinhamento em todas as células de dados
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=4):
            for cell in row:
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")
        
        # Ajuste automático de largura das colunas
        for column_cells in ws.columns:
            length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
            ws.column_dimensions[get_column_letter(column_cells[0].column)].width = length + 2

        # Configura a resposta HTTP para download do arquivo
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=efetivo_exportado.xlsx'
        wb.save(response)
        return response

    # GET: Renderiza a página de seleção
    postos_db = Efetivo.objects.values_list('posto', flat=True).distinct()
    
    hierarquia = {
        'CL': 0, 'TC': 1, 'MJ': 2, 'CP': 3,
        '1T': 4, '2T': 5, 'ASP': 6, 'SO': 7,
        '1S': 8, '2S': 9, '3S': 10,
        'CB': 11, 'S1': 12, 'S2': 13, 'REC': 14
    }
    
    postos_existentes = sorted(postos_db, key=lambda x: hierarquia.get(x, 99))
    
    return render(request, 'Secao_pessoal/exportar_excel.html', {
        'postos': postos_existentes
    })

@method_decorator(s1_required, name='dispatch')
class HistoricoInspsauListView(ListView):
    model = HistoricoInspsau
    template_name = 'Secao_pessoal/historico_inspsau.html'
    context_object_name = 'historico_list'
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get('q')
        qs = super().get_queryset().select_related('militar').order_by('-data_registro')

        if query:
            qs = qs.filter(
                Q(militar__nome_completo__icontains=query) |
                Q(militar__nome_guerra__icontains=query) |
                Q(militar__posto__icontains=query) |
                Q(militar__saram__icontains=query) |
                Q(finalidade__icontains=query) |
                Q(parecer__icontains=query)
            )
        return qs

@method_decorator(s1_required, name='dispatch')
class PrestacaoServicoListView(ListView):
    model = Efetivo
    template_name = 'Secao_pessoal/prestacao_servico_list.html'
    context_object_name = 'militares'
    paginate_by = 20

    def get_queryset(self):
        query = self.request.GET.get('q')
        rank_order = Case(
            When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
            When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
            When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
            When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
            default=Value(99), output_field=IntegerField(),
        ) 
        qs = super().get_queryset().filter(unidade_prestacao_servico__isnull=False).exclude(unidade_prestacao_servico='').annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
        if query:
            q_objects = Q(nome_completo__icontains=query) | \
                        Q(nome_guerra__icontains=query) | \
                        Q(unidade_prestacao_servico__icontains=query) | \
                        Q(portaria_prestacao__icontains=query)
            qs = qs.filter(q_objects)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_query'] = self.request.GET.get('q', '')
        return context

@s1_required
@require_POST
def historico_inspsau_delete(request, pk):
    if not request.user.is_superuser:
        messages.error(request, "Você não tem permissão para executar esta ação.")
        return redirect('Secao_pessoal:historico_inspsau_list')
    
    historico_item = get_object_or_404(HistoricoInspsau, pk=pk)
    try:
        militar_nome = historico_item.militar.nome_guerra
        historico_item.delete()
        messages.success(request, f"Registro do histórico de {militar_nome} excluído com sucesso.")
    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao excluir o registro: {e}")
        
    return redirect('Secao_pessoal:historico_inspsau_list')
@s1_required
@require_GET
def api_search_militares(request):
    """
    Endpoint de API para a busca manual de militares no modal de INSPSAU.
    """
    query = request.GET.get('q', '')
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)

    militares = Efetivo.objects.filter(
        Q(nome_completo__icontains=query) |
        Q(nome_guerra__icontains=query) |
        Q(saram__icontains=query)
    ).order_by('posto', 'nome_guerra')[:15]

    data = [{'id': m.id, 'posto': m.posto, 'nome_guerra': m.nome_guerra, 'nome_completo': m.nome_completo} for m in militares]
    
    return JsonResponse(data, safe=False)

@s1_required
def importar_fq(request):
    if request.method == 'POST':
        data_str = request.POST.get('data')
        arquivo = request.FILES.get('documento_fq')

        if not data_str or not arquivo:
            messages.error(request, "Por favor, forneça a data e o documento da FQ.")
            return redirect('Secao_pessoal:importar_fq')
            
        try:
            data_chamada = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            data_chamada = date.today()

        try:
            # Salva o arquivo num ficheiro temporário para processar
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(arquivo.name)[1]) as temp_file:
                for chunk in arquivo.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name

            content = ""
            if temp_file_path.lower().endswith('.pdf'):
                doc = fitz.open(temp_file_path)
                for page in doc:
                    page_text = page.get_text()
                    if len(page_text.strip()) > 50:
                        content += page_text + "\n\n"
                    else:
                        try:
                            pix = page.get_pixmap(dpi=300)
                            img = Image.open(io.BytesIO(pix.tobytes("png")))
                            if pytesseract:
                                content += pytesseract.image_to_string(img, lang='por') + "\n\n"
                        except Exception:
                            pass
                doc.close()
            else:
                # Se for imagem
                try:
                    img = Image.open(temp_file_path)
                    if pytesseract:
                        content = pytesseract.image_to_string(img, lang='por')
                except Exception:
                    pass

            os.remove(temp_file_path)

            if not content.strip():
                messages.error(request, "Não foi possível extrair texto legível do documento.")
                return redirect('Secao_pessoal:importar_fq')

            resultado_ia = analisar_fq_documento(content)
            faltosos_marcados = 0
            nao_encontrados = []

            for militar_ia in resultado_ia.faltosos:
                militar = None
                if militar_ia.saram:
                    saram_limpo = re.sub(r'\D', '', str(militar_ia.saram))
                    if saram_limpo:
                        militar = Efetivo.objects.filter(saram=int(saram_limpo)).first()
                
                if not militar and militar_ia.nome_guerra:
                    candidatos = Efetivo.objects.filter(nome_guerra__icontains=militar_ia.nome_guerra)
                    if candidatos.count() == 1:
                        militar = candidatos.first()
                    elif candidatos.count() > 1 and militar_ia.posto:
                        candidatos_posto = candidatos.filter(posto__icontains=militar_ia.posto)
                        if candidatos_posto.count() == 1:
                            militar = candidatos_posto.first()
                        else:
                            militar = candidatos.first()

                if militar:
                    ChamadaRegistro.objects.update_or_create(
                        data=data_chamada,
                        militar=militar,
                        defaults={'status': 'F'}
                    )
                    faltosos_marcados += 1
                else:
                    nao_encontrados.append(f"{militar_ia.posto} {militar_ia.nome_guerra}")

            if faltosos_marcados > 0:
                msg = f"Sucesso! {faltosos_marcados} falta(s) registrada(s) na chamada do dia {data_chamada.strftime('%d/%m/%Y')}."
                if nao_encontrados:
                    msg += f" (Militares não encontrados: {', '.join(nao_encontrados)})"
                messages.success(request, msg)
            else:
                if nao_encontrados:
                    messages.warning(request, f"Faltas identificadas pela IA, mas nenhum militar correspondente foi encontrado no sistema: {', '.join(nao_encontrados)}")
                else:
                    messages.info(request, "A Inteligência Artificial analisou o documento e não encontrou nenhum militar com falta.")
                    
        except Exception as e:
            messages.error(request, f"Erro ao analisar o documento FQ: {e}")

        return redirect('Secao_pessoal:importar_fq')

    # Busca as últimas 50 faltas registradas no sistema para exibir no histórico
    historico_faltas = ChamadaRegistro.objects.filter(status='F').select_related('militar').order_by('-data', 'militar__nome_guerra')[:50]
    return render(request, 'Secao_pessoal/importar_fq.html', {'historico_faltas': historico_faltas})


@s1_required
def desercao(request):
    if request.method == 'POST':
        militar_id = request.POST.get('militar_id')
        data_inicio_str = request.POST.get('data_inicio')
        
        if militar_id and data_inicio_str:
            try:
                militar = Efetivo.objects.get(id=militar_id)
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                
                # Criar 8 faltas consecutivas para tornar o militar um desertor
                for i in range(8):
                    data_falta = data_inicio + timedelta(days=i)
                    ChamadaRegistro.objects.update_or_create(
                        data=data_falta,
                        militar=militar,
                        defaults={'status': 'F'}
                    )
                messages.success(request, f"O militar {militar.posto} {militar.nome_guerra} foi marcado como desertor manualmente (8 faltas lançadas a partir de {data_inicio.strftime('%d/%m/%Y')}).")
            except Exception as e:
                messages.error(request, f"Erro ao adicionar desertor: {e}")
        return redirect('Secao_pessoal:desercao')

    militares = Efetivo.objects.exclude(situacao__iexact='Baixado')
    
    desertores = []
    alertas = []

    for militar in militares:
        # Busca as últimas 30 chamadas para otimização
        chamadas = ChamadaRegistro.objects.filter(militar=militar).order_by('-data')[:30]
        
        faltas_consecutivas = 0
        ultima_data_falta = None
        
        for chamada in chamadas:
            if chamada.status == 'F':
                faltas_consecutivas += 1
                if faltas_consecutivas == 1:
                    ultima_data_falta = chamada.data
            else:
                # Quebra a sequência se tiver presença (P), Missão (M), etc.
                break
                
        if faltas_consecutivas >= 8:
            desertores.append({
                'militar': militar,
                'faltas': faltas_consecutivas,
                'data': ultima_data_falta
            })
        elif faltas_consecutivas >= 4:
            alertas.append({
                'militar': militar,
                'faltas': faltas_consecutivas,
                'data': ultima_data_falta
            })

    # Ordenar por mais faltas
    alertas.sort(key=lambda x: x['faltas'], reverse=True)
    desertores.sort(key=lambda x: x['faltas'], reverse=True)

    context = {
        'desertores': desertores,
        'alertas': alertas,
        'militares': militares,
    }
    return render(request, 'Secao_pessoal/desercao.html', context)