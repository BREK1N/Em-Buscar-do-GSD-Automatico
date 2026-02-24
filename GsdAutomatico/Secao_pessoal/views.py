import pandas as pd
import os
import tempfile
import httpx
import random
import fitz  # PyMuPDF
import base64
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from Secao_pessoal.models import Efetivo, Posto, Quad, Especializacao, OM, Setor, Subsetor
from .forms import MilitarForm 
from django.contrib import messages
from django.db.models import Q, Max, Case, When, Value, IntegerField, Count
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

def is_s1_member(user):
    """Check if the user is a member of the 'S1' group."""
    return user.groups.filter(name='S1').exists()

s1_required = user_passes_test(is_s1_member)



@s1_required
def index(request):
    return render(request, 'Secao_pessoal/index.html')

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
            When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),
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
    
@method_decorator(s1_required, name='dispatch')
class MilitarCreateView(CreateView):
    model = Efetivo
    form_class = MilitarForm
    template_name = 'Secao_pessoal/militar_form.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

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
                # Pega o SARAM e remove espaços extras
                saram_valor = str(row.get('SARAM', '')).strip()
                
                # Se não tiver SARAM, pula a linha
                if not saram_valor:
                    continue

                # Dicionário com os dados a serem salvos/atualizados
                # AJUSTE AQUI: O lado esquerdo é o campo do seu Modelo, o direito é a coluna do Excel
                dados_militar = {
                    'posto': row.get('PST.', '').strip(),
                    'quad': row.get('QUAD.', '').strip(),
                    'especializacao': row.get('ESP.', '').strip(),
                    'saram': row.get('SARAM', '').strip(),
                    'nome_completo': row.get('NOME COMPLETO', '').strip(),
                    'nome_guerra': row.get('NOME DE GUERRA', '').strip(),
                    'turma': row.get('TURMA', '').strip(),
                    'situacao': row.get('SITUAÇÃO', '').strip(),
                    'om': row.get('OM', '').strip(),
                    'setor': row.get('SETOR', '').strip(),
                    'subsetor': row.get('SUBSETOR', '').strip()                    

                }

                # update_or_create busca pelo SARAM. Se achar, atualiza. Se não, cria.
                obj, created = Efetivo.objects.update_or_create(
                    saram=saram_valor,
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

class CandidatoExtraction(BaseModel):
    numero: str = Field(description="Número do candidato (ex: 01, 02)")
    nome_completo: str = Field(description="Nome completo do candidato")
    saram: str = Field(description="SARAM do candidato")

class ListaCandidatosExtraction(BaseModel):
    candidatos: list[CandidatoExtraction] = Field(description="Lista de candidatos extraídos")

def get_llm_model():
    """Configura o modelo LLM com as mesmas configurações de proxy da Ouvidoria."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    proxy_url = os.getenv("http_proxy") or os.getenv("HTTP_PROXY") or os.getenv("https_proxy") or os.getenv("HTTPS_PROXY")
    
    if proxy_url:
        http_client = httpx.Client(proxy=proxy_url, verify=False, timeout=600.0)
    else:
        http_client = httpx.Client(verify=False, timeout=600.0)
        
    return ChatOpenAI(model="gpt-4o", temperature=0, api_key=openai_api_key, http_client=http_client)

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

    # 4. Primeiro + Último
    add_unique(f"{partes[0]} {partes[-1]}")
    
    # 5. Inicial + Último
    add_unique(f"{partes[0][0]}. {partes[-1]}")
    
    # 6. Outras combinações
    if len(partes) > 2:
        add_unique(f"{partes[0]} {partes[-2]}")
        add_unique(f"{partes[0][0]}. {partes[-2]}")

    for i in range(1, len(partes)-1):
        add_unique(partes[i])
        add_unique(f"{partes[0]} {partes[i]}")

    return sugestoes

@s1_required
def nome_de_guerra(request):
    if request.method == 'POST' and request.FILES.get('pdf_file'):
        try:
            pdf_file = request.FILES['pdf_file']
            
            # 1. Salvar PDF temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                for chunk in pdf_file.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name
            
            # 2. Processar PDF como Imagens (Vision) para lidar com planilhas digitalizadas/imagens
            doc = fitz.open(temp_path)
            content_parts = []
            
            # Instrução para o modelo
            content_parts.append({
                "type": "text", 
                "text": "Analise as imagens deste documento. Ele contém uma lista ou planilha de militares. Extraia os dados de cada candidato: Número (ex: 01, 02), Nome Completo e SARAM. Ignore cabeçalhos, rodapés e assinaturas."
            })

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                # Renderiza a página como imagem (PNG) com DPI suficiente para leitura
                pix = page.get_pixmap(dpi=150) 
                img_data = pix.tobytes("png")
                base64_image = base64.b64encode(img_data).decode('utf-8')
                
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                })
            
            doc.close()
            os.remove(temp_path) # Limpeza
            
            # 3. Usar IA com capacidade de Visão (GPT-4o)
            llm = get_llm_model()
            structured_llm = llm.with_structured_output(ListaCandidatosExtraction)
            
            # Cria a mensagem humana com o conteúdo misto (texto + imagens)
            message = HumanMessage(content=content_parts)
            
            # Invoca o modelo
            resultado = structured_llm.invoke([message])
            
            # 4. Gerar Nomes de Guerra e Criar Excel
            data_rows = []
            nomes_usados_sessao = set() # Rastreia nomes gerados nesta importação para evitar duplicatas no lote

            for cand in resultado.candidatos:
                sugestoes = gerar_sugestoes_guerra(cand.nome_completo)
                nome_final = None
                
                # Verifica disponibilidade no banco de dados (prioridade da lista)
                for sugestao in sugestoes:
                    # Verifica no banco E na lista atual de nomes gerados
                    if not Efetivo.objects.filter(nome_guerra=sugestao).exists() and sugestao not in nomes_usados_sessao:
                        nome_final = sugestao
                        break
                
                # Se todas as sugestões estiverem ocupadas, cria uma variação numérica
                if not nome_final:
                    base = sugestoes[0] if sugestoes else "MILITAR"
                    contador = 2
                    while True:
                        teste = f"{base} {contador}"
                        if not Efetivo.objects.filter(nome_guerra=teste).exists() and teste not in nomes_usados_sessao:
                            nome_final = teste
                            break
                        contador += 1

                nomes_usados_sessao.add(nome_final) # Adiciona ao conjunto de usados nesta sessão

                row = {
                    'Numero': cand.numero,
                    'SARAM': cand.saram,
                    'NOME COMPLETO': cand.nome_completo,
                    'NOME DE GUERRA': nome_final
                }
                
                data_rows.append(row)
            
            df = pd.DataFrame(data_rows)
            
            # 5. Retornar o arquivo Excel
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=sugestoes_nome_guerra.xlsx'
            df.to_excel(response, index=False)
            return response
            
        except Exception as e:
            messages.error(request, f"Erro ao processar o arquivo: {str(e)}")
            return redirect('Secao_pessoal:nome_de_guerra')

    return render(request, 'Secao_pessoal/nome_de_guerra.html')

@s1_required
def comunicacoes(request):
    # View para a nova aba de Comunicações
    return render(request, 'Secao_pessoal/comunicacoes.html')

@s1_required
def troca_de_setor(request):
    # Lembre-se de criar o arquivo: templates/Secao_pessoal/troca_de_setor.html
    return render(request, 'Secao_pessoal/troca_de_setor.html')

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