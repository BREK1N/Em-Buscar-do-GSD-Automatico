import pandas as pd
import io
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Max, Case, When, Value, IntegerField
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from .models import Militar, PATD
from .forms import MilitarForm, PATDForm
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
import os
import tempfile
from dotenv import load_dotenv
import logging
from datetime import datetime

# Configuração de logging para depuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# --- Classe para Estruturação da Análise de PDF ---
class AnaliseTransgressao(BaseModel):
    nome_militar: str = Field(description="O nome do militar acusado, sem o posto ou graduação.")
    posto_graduacao: str = Field(description="O posto ou graduação (ex: Sargento, Capitão), se mencionado. Se não, retorne uma string vazia.")
    transgressao: str = Field(description="A descrição detalhada da transgressão disciplinar cometida.")
    local: str = Field(description="O local onde a transgressão ocorreu.")
    data_ocorrencia: str = Field(description="A data em que a transgressão ocorreu, no formato AAAA-MM-DD. Se não for mencionada, retorne uma string vazia.")


def get_next_patd_number():
    """Gera o próximo número sequencial para a PATD."""
    max_num = PATD.objects.aggregate(max_num=Max('numero_patd'))['max_num']
    return (max_num or 0) + 1

# --- View Principal do Analisador de PDF ---
def index(request):
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

                patd = PATD.objects.create(
                    militar=new_militar,
                    transgressao=transgressao,
                    numero_patd=get_next_patd_number(),
                    data_ocorrencia=data_ocorrencia
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

                llm = ChatOpenAI(model="gpt-4o", temperature=0)
                structured_llm = llm.with_structured_output(AnaliseTransgressao)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", "Você é um assistente especialista em analisar documentos disciplinares militares. Extraia a data da ocorrência no formato AAAA-MM-DD."),
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

                if militar:
                    # Lógica de verificação de duplicidade
                    if data_ocorrencia:
                        existing_patds = PATD.objects.filter(
                            militar=militar,
                            data_ocorrencia=data_ocorrencia
                        )

                        for patd in existing_patds:
                            nova_transgressao = resultado.transgressao.strip()
                            transgressao_existente = patd.transgressao.strip()
                            
                            if nova_transgressao in transgressao_existente or transgressao_existente in nova_transgressao:
                                patd_url = reverse('Ouvidoria:patd_detail', kwargs={'pk': patd.pk})
                                return JsonResponse({
                                    'status': 'patd_exists',
                                    'message': f'Já existe uma PATD para este militar na mesma data e com transgressão similar (Nº {patd.numero_patd}).',
                                    'url': patd_url
                                })

                    patd = PATD.objects.create(
                        militar=militar,
                        transgressao=resultado.transgressao,
                        numero_patd=get_next_patd_number(),
                        data_ocorrencia=data_ocorrencia
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
                        }
                    })

            except Exception as e:
                logger.error(f"Erro na análise do PDF: {e}")
                return JsonResponse({'status': 'error', 'message': f"Ocorreu um erro ao analisar o ficheiro: {e}"}, status=500)
    
    return render(request, 'indexOuvidoria.html')

# --- View para Importação de Excel ---
def importar_excel(request):
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

    return render(request, 'importar_excel.html')


# --- Views CRUD para Militares ---
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

class MilitarCreateView(CreateView):
    model = Militar
    form_class = MilitarForm
    template_name = 'militar_form.html'
    success_url = reverse_lazy('Ouvidoria:militar_list')

class MilitarUpdateView(UpdateView):
    model = Militar
    form_class = MilitarForm
    template_name = 'militar_form.html'
    success_url = reverse_lazy('Ouvidoria:militar_list')

class MilitarDeleteView(DeleteView):
    model = Militar
    template_name = 'militar_confirm_delete.html'
    success_url = reverse_lazy('Ouvidoria:militar_list')

# --- Views CRUD para PATDs ---
class PATDListView(ListView):
    model = PATD
    template_name = 'patd_list.html'
    context_object_name = 'patds'
    paginate_by = 15
    def get_queryset(self):
        query = self.request.GET.get('q')
        qs = super().get_queryset().select_related('militar', 'oficial_responsavel').order_by('-data_inicio')
        if query:
            qs = qs.filter(
                Q(numero_patd__icontains=query) | 
                Q(militar__nome_completo__icontains=query) | 
                Q(militar__nome_guerra__icontains=query)
            )
        return qs

class PATDDetailView(DetailView):
    model = PATD
    template_name = 'patd_detail.html'
    context_object_name = 'patd'

class PATDUpdateView(UpdateView):
    model = PATD
    form_class = PATDForm
    template_name = 'patd_form.html'
    
    def get_success_url(self):
        return reverse_lazy('Ouvidoria:patd_detail', kwargs={'pk': self.object.pk})

class PATDDeleteView(DeleteView):
    model = PATD
    success_url = reverse_lazy('Ouvidoria:patd_list')

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

# --- View para Salvar Assinatura ---
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


# --- VIEWS PARA CONFIGURAÇÃO DE ASSINATURAS (COM PESQUISA) ---
@require_GET
def lista_oficiais(request):
    """Retorna uma lista de todos os oficiais, com filtro de pesquisa."""
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

@require_POST
def salvar_assinatura_padrao(request, pk):
    """Salva ou atualiza a assinatura padrão de um oficial."""
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
