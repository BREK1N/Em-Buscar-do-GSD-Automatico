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
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from django.contrib.auth.models import Group
from Secao_pessoal.models import Efetivo, Posto, Quad, Especializacao, OM, Setor, Subsetor, Notificacao, SolicitacaoTrocaSetor, HistoricoInspsau
from .forms import MilitarForm, NotificacaoForm
from django.contrib import messages
from django.db.models import Q, Max, Case, When, Value, IntegerField, Count
from difflib import SequenceMatcher
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from datetime import datetime
try:
    import pytesseract
except ImportError:
    pytesseract = None
from PIL import Image
import fitz 
import io
# Se estiver no Windows e der erro, descomente e ajuste o caminho do seu tesseract:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
from .analise_inspsau import analisar_inspsau_pdf

def is_s1_member(user):
    """Check if the user is a member of the 'S1' group."""
    return user.groups.filter(name='S1').exists()

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
    return render(request, 'Secao_pessoal/index.html')

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
                            print("Aviso: pytesseract não instalado. OCR ignorado.")
                    except Exception as e:
                        print(f"Aviso: Erro ao realizar OCR na página: {e}")
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
            qs = qs.filter(
                Q(nome_completo__icontains=query) |
                Q(nome_guerra__icontains=query) |
                Q(saram__icontains=query) |
                Q(posto__icontains=query)
            )
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
        self.object.deleted = True
        self.object.deleted_at = timezone.now()
        self.object.save()
        messages.success(request, f"Militar {self.object.nome_guerra} movido para a lixeira.")
        return redirect(self.get_success_url())

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
            qs = qs.filter(
                Q(nome_completo__icontains=query) |
                Q(nome_guerra__icontains=query) |
                Q(saram__icontains=query) |
                Q(posto__icontains=query)
            )
        return qs

#EFETIVO IMPORT EXCEL
@s1_required
def importar_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            # Lê o arquivo Excel e converte tudo para string para evitar erros de tipo
            df = pd.read_excel(excel_file, dtype=str)
            
            # Remove espaços em branco dos nomes das colunas
            df.columns = df.columns.str.strip()
            
            # Substitui valores 'nan' (vazios) do pandas por string vazia
            df.fillna('', inplace=True)

            criados = 0
            atualizados = 0

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
                        }

                # LÓGICA DE SALVAMENTO INTELIGENTE:
                if saram_db:
                    # Se tem SARAM, a chave principal é o SARAM
                    obj, created = Efetivo.all_objects.update_or_create(
                        saram=saram_db,
                        defaults=dados_militar
                    )
                else:
                    # Se é um recruta sem SARAM, a chave principal para não duplicar é o Nome Completo
                    obj, created = Efetivo.all_objects.update_or_create(
                        nome_completo=nome_completo_valor,
                        defaults=dados_militar
                    )

                if created:
                    criados += 1
                else:
                    atualizados += 1

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

@login_required
def comunicacoes(request):
    """
    View para listar notificações recebidas e, se for S1, enviar novas.
    """
    militar_logado = None
    try:
        if hasattr(request.user, 'profile'):
            militar_logado = request.user.profile.militar
    except:
        pass
        
    if not militar_logado and not request.user.is_superuser:
        messages.error(request, "Seu usuário não está vinculado a um militar.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    if not militar_logado and request.user.is_superuser:
        militar_logado, _ = Efetivo.objects.get_or_create(
            nome_guerra="ADMINISTRADOR",
            defaults={'nome_completo': "Administrador do Sistema", 'posto': "SYS"}
        )
        try:
            request.user.profile.militar = militar_logado
            request.user.profile.save()
        except Exception:
            try:
                from login.models import UserProfile
                UserProfile.objects.create(user=request.user, militar=militar_logado)
            except Exception:
                pass

    # Processar envio de notificação (Agora liberado para todas as seções)
    form = None
    is_s1 = True # Forçando True para o botão "Nova Mensagem" aparecer no template para todos
    
    if request.method == 'POST':
        if not militar_logado:
            messages.error(request, "Apenas usuários vinculados a um militar podem enviar mensagens.")
            return redirect('comunicacoes_global')

        form = NotificacaoForm(request.POST, request.FILES)
        if form.is_valid():
            notificacao = form.save(commit=False)
            notificacao.remetente = militar_logado

            if 'anexo' in request.FILES:
                notificacao.anexo = request.FILES['anexo']

            notificacao.save()
            messages.success(request, f"Notificação enviada para {notificacao.destinatario.nome_guerra}.")
            return redirect('comunicacoes_global')
    else:
        form = NotificacaoForm()

    # Listar notificações (Caixa de Entrada ou Enviados)
    box = request.GET.get('box', 'inbox')
    
    # --- Contadores Globais (aparecem em todas as abas) ---
    if militar_logado:
        unread_count = Notificacao.objects.filter(destinatario=militar_logado, lida=False, arquivada=False).count()
        trash_count = Notificacao.all_objects.filter(
            (Q(destinatario=militar_logado) | Q(remetente=militar_logado)),
            deleted=True
        ).distinct().count()
        
        autorizacoes_count = SolicitacaoTrocaSetor.objects.filter(
            Q(chefe_atual=militar_logado, status='pendente_atual') |
            Q(chefe_destino=militar_logado, status='pendente_destino')
        ).count()
    else:
        unread_count = 0
        trash_count = 0
        autorizacoes_count = 0

    autorizacoes_pendentes_troca = []
    if militar_logado and box == 'sent':
        notificacoes = Notificacao.objects.filter(remetente=militar_logado, arquivada=False).order_by('-data_criacao')
    elif militar_logado and box == 'autorizacoes':
        autorizacoes_pendentes_troca = SolicitacaoTrocaSetor.objects.filter(
            Q(chefe_atual=militar_logado, status='pendente_atual') |
            Q(chefe_destino=militar_logado, status='pendente_destino')
        ).order_by('-data_solicitacao')
        notificacoes = []
    elif militar_logado and box == 'arquivadas':
        notificacoes = Notificacao.objects.filter(
            (Q(destinatario=militar_logado) | Q(remetente=militar_logado)),
            arquivada=True
        ).distinct().order_by('-data_criacao')
    elif militar_logado and box == 'trash':
        notificacoes = Notificacao.all_objects.filter(
            (Q(destinatario=militar_logado) | Q(remetente=militar_logado)),
            deleted=True
        ).distinct().order_by('-deleted_at')
    elif militar_logado:
        notificacoes = Notificacao.objects.filter(destinatario=militar_logado, arquivada=False).order_by('-data_criacao')
    else:
        notificacoes = []
    
    # Marcar como lida se solicitado via GET (simples) ou via AJAX (idealmente)
    if request.GET.get('ler') and box == 'inbox' and militar_logado:
        try:
            notif_id = int(request.GET.get('ler'))
            notif = Notificacao.objects.get(id=notif_id, destinatario=militar_logado)
            notif.lida = True
            notif.save()
            return redirect('comunicacoes_global')
        except:
            pass

    base_template = 'Secao_pessoal/base.html'
    if request.user.is_authenticated and not request.user.is_superuser:
        user_groups = request.user.groups.values_list('name', flat=True)
        if 'Ouvidoria' in user_groups:
            base_template = 'base.html'
        elif 'Informatica' in user_groups:
            base_template = 'informatica/base.html'
        elif 'seção de operação' in user_groups or 'Secao_operacoes' in user_groups:
            base_template = 'Secao_operacoes/base.html'

    context = {
        'notificacoes': notificacoes,
        'autorizacoes_pendentes_troca': autorizacoes_pendentes_troca,
        'form': form,
        'is_s1': is_s1,
        'current_box': box,
        'unread_count': unread_count,
        'trash_count': trash_count,
        'autorizacoes_count': autorizacoes_count,
        'base_template': base_template,
        'militar_logado': militar_logado
    }
    return render(request, 'Secao_pessoal/comunicacoes.html', context)

@login_required
@require_POST
def acoes_em_massa_comunicacoes(request):
    militar_logado = getattr(request.user.profile, 'militar', None)
    if not militar_logado:
        messages.error(request, "Ação não permitida.")
        return redirect(request.META.get('HTTP_REFERER', 'comunicacoes_global'))

    action = request.POST.get('action')
    message_ids = request.POST.getlist('message_ids')

    if not action or not message_ids:
        messages.warning(request, "Nenhuma ação ou mensagem selecionada.")
        return redirect(request.META.get('HTTP_REFERER', 'comunicacoes_global'))

    # Garante que o usuário só modifique suas próprias mensagens
    queryset = Notificacao.all_objects.filter(
        Q(destinatario=militar_logado) | Q(remetente=militar_logado),
        pk__in=message_ids
    )

    if action == 'delete':
        count, _ = queryset.delete()
        messages.success(request, f"{count} mensagem(ns) excluída(s) permanentemente.")
    elif action == 'archive':
        count = queryset.update(arquivada=True)
        messages.success(request, f"{count} mensagem(ns) arquivada(s) com sucesso.")
    elif action == 'unarchive':
        count = queryset.update(arquivada=False)
        messages.success(request, f"{count} mensagem(ns) desarquivada(s) com sucesso.")
    elif action == 'trash':
        count = queryset.update(deleted=True, deleted_at=timezone.now())
        messages.success(request, f"{count} mensagem(ns) movida(s) para a lixeira.")
    elif action == 'restore':
        count = queryset.update(deleted=False, deleted_at=None, arquivada=False)
        messages.success(request, f"{count} mensagem(ns) restaurada(s) com sucesso.")
    else:
        messages.error(request, "Ação desconhecida.")

    return redirect(request.META.get('HTTP_REFERER', 'comunicacoes_global'))

@login_required
@require_POST
def arquivar_mensagem(request, notificacao_id):
    militar_logado = getattr(request.user.profile, 'militar', None)
    notificacao = get_object_or_404(Notificacao, pk=notificacao_id)
    if militar_logado != notificacao.destinatario and militar_logado != notificacao.remetente:
        messages.error(request, "Você não tem permissão para arquivar esta mensagem.")
    else:
        notificacao.arquivada = not notificacao.arquivada
        notificacao.save()
        messages.success(request, f"Mensagem {'arquivada' if notificacao.arquivada else 'desarquivada'} com sucesso.")
    return redirect(request.META.get('HTTP_REFERER', 'comunicacoes_global'))

@login_required
@xframe_options_sameorigin
def excluir_mensagem(request, notificacao_id):
    if request.method == 'POST':
        try:
            militar_logado = getattr(request.user.profile, 'militar', None) if hasattr(request.user, 'profile') else None
            notificacao = get_object_or_404(Notificacao.all_objects, id=notificacao_id)
            
            if request.user.is_superuser or notificacao.destinatario == militar_logado or notificacao.remetente == militar_logado:
                notificacao.deleted = True
                notificacao.deleted_at = timezone.now()
                notificacao.save()
                messages.success(request, "Mensagem movida para a lixeira.")
            else:
                messages.error(request, "Você não tem permissão para mover esta mensagem para a lixeira.")
        except Exception as e:
            messages.error(request, "Erro ao mover a mensagem para a lixeira.")
    return redirect(request.META.get('HTTP_REFERER', 'comunicacoes_global'))

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
        return redirect('comunicacoes_global')
    
    if solicitacao.status == 'pendente_atual':
        if solicitacao.chefe_atual != militar_logado and not is_s1_member(request.user) and not request.user.is_superuser:
            messages.error(request, 'Você não tem permissão para responder a esta solicitação.')
            return redirect('comunicacoes_global')
            
        if acao == 'aprovar':
            solicitacao.status = 'pendente_destino'
            solicitacao.save()
            
            messages.success(request, 'Saída autorizada com sucesso. Aguardando autorização do setor de destino.')
        elif acao == 'rejeitar':
            solicitacao.status = 'rejeitado'
            solicitacao.save()
            messages.success(request, 'Solicitação de troca rejeitada.')
            
    elif solicitacao.status == 'pendente_destino':
        if solicitacao.chefe_destino != militar_logado and not is_s1_member(request.user) and not request.user.is_superuser:
            messages.error(request, 'Você não tem permissão para responder a esta solicitação.')
            return redirect('comunicacoes_global')
            
        if acao == 'aprovar':
            solicitacao.status = 'aprovado'
            solicitacao.save()
            
            militar = solicitacao.militar
            militar.setor = solicitacao.setor_destino
            militar.save()
            
            messages.success(request, 'Entrada autorizada com sucesso. O militar foi transferido de setor.')
        elif acao == 'rejeitar':
            solicitacao.status = 'rejeitado'
            solicitacao.save()
            messages.success(request, 'Solicitação de troca rejeitada.')
            
    return redirect(request.META.get('HTTP_REFERER', 'comunicacoes_global'))

@s1_required
def ata(request):
    rank_order = Case(
        When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
        When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
        When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
        When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
        default=Value(99), output_field=IntegerField(),
    )
    militares = Efetivo.objects.exclude(situacao__iexact='Baixado').annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
    
    if request.method == 'POST':
        militar_substituido_id = request.POST.get('militar_substituido')
        militar_substituto_id = request.POST.get('militar_substituto')
        
        # Aqui você pode implementar a lógica de geração de arquivo no futuro (ex: reportlab, docx)
        messages.success(request, 'ATA gerada com sucesso! (Geração de arquivo a implementar)')
        return redirect('Secao_pessoal:ata')

    context = {
        'militares': militares
    }
    return render(request, 'Secao_pessoal/ata.html', context)

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

@login_required
def api_notificacoes_check(request):
    """Retorna JSON com contagem de notificações não lidas para o header"""
    try:
        if hasattr(request.user, 'profile') and request.user.profile.militar:
            militar = request.user.profile.militar
            nao_lidas = Notificacao.objects.filter(destinatario=militar, lida=False)
            count_notificacoes = nao_lidas.count()
            
            autorizacoes_pendentes_troca = SolicitacaoTrocaSetor.objects.filter(
                Q(chefe_atual=militar, status='pendente_atual') |
                Q(chefe_destino=militar, status='pendente_destino')
            )
            count_autorizacoes_troca = autorizacoes_pendentes_troca.count()

            total_count = count_notificacoes + count_autorizacoes_troca
            
            data = []
            for a in autorizacoes_pendentes_troca[:5]:
                data.append({
                    'id': a.id,
                    'titulo': f"Autorização Pendente: {a.militar.nome_guerra}",
                    'remetente': "Sistema",
                    'data': a.data_solicitacao.strftime('%d/%m %H:%M'),
                    'is_autorizacao': True,
                    'url': reverse('comunicacoes_global') + '?box=autorizacoes'
                })
                
            remaining_slots = 5 - len(data)
            if remaining_slots > 0:
                for n in nao_lidas[:remaining_slots]:
                    data.append({
                        'id': n.id,
                        'titulo': n.titulo,
                        'remetente': n.remetente.nome_guerra if n.remetente else "Sistema",
                        'data': n.data_criacao.strftime('%d/%m %H:%M') if n.data_criacao else "",
                        'is_autorizacao': False,
                        'url': reverse('comunicacoes_global') + f'?ler={n.id}'
                    })
            
            return HttpResponse(json.dumps({'count': total_count, 'notifications': data}), content_type="application/json")
    except Exception as e:
        print(f"Erro ao carregar API de Notificacoes: {e}")
    
    return HttpResponse(json.dumps({'count': 0, 'notifications': []}), content_type="application/json")

# Nota: Você precisará adicionar 'import json' no topo do arquivo views.py se ainda não existir.

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_query'] = self.request.GET.get('q', '')
        return context

@method_decorator(s1_required, name='dispatch')
class MilitarTrashListView(ListView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_trash_list.html'
    context_object_name = 'militares'
    paginate_by = 20

    def get_queryset(self):
        return Efetivo.all_objects.filter(deleted=True).order_by('-deleted_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for militar in context.get('militares', []):
            if militar.deleted_at:
                delta = timezone.now() - militar.deleted_at
                dias_restantes = 30 - delta.days
                militar.dias_para_exclusao = dias_restantes if dias_restantes > 0 else 0
            else:
                militar.dias_para_exclusao = None
        return context

@s1_required
@require_POST
def militar_restore(request, pk):
    militar = get_object_or_404(Efetivo.all_objects, pk=pk)
    militar.deleted = False
    militar.deleted_at = None
    militar.save()
    messages.success(request, f"Militar {militar.nome_guerra} restaurado com sucesso.")
    return redirect('Secao_pessoal:militar_trash_list')

@s1_required
@require_POST
def militar_permanently_delete(request, pk):
    militar = get_object_or_404(Efetivo.all_objects, pk=pk)
    nome_guerra = militar.nome_guerra
    militar.delete()
    messages.success(request, f"Militar {nome_guerra} excluído permanentemente.")
    return redirect('Secao_pessoal:militar_trash_list')

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