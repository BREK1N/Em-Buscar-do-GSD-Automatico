import pandas as pd
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from Secao_pessoal.models import Efetivo
from .forms import MilitarForm 
from django.contrib import messages
from django.db.models import Q, Max, Case, When, Value, IntegerField, Count


@login_required
def index(request):
    return render(request, 'Secao_pessoal/index.html')

#Efetivo

@method_decorator(login_required, name='dispatch')
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
    
@method_decorator(login_required, name='dispatch')
class MilitarCreateView(CreateView):
    model = Efetivo
    form_class = MilitarForm
    template_name = 'Secao_pessoal/militar_form.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Adicionar Militar'
        return context

@method_decorator(login_required, name='dispatch')
class MilitarUpdateView(UpdateView):
    model = Efetivo
    form_class = MilitarForm
    template_name = 'Secao_pessoal/militar_form.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Militar'
        return context

@method_decorator(login_required, name='dispatch')
class MilitarDeleteView(DeleteView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_confirm_delete.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')
#EFETIVO IMPORT EXCEL
@login_required
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
    
def nome_de_guerra(request):
    # Lembre-se de criar o arquivo: templates/Secao_pessoal/nome_de_guerra.html
    return render(request, 'Secao_pessoal/nome_de_guerra.html')

def troca_de_setor(request):
    # Lembre-se de criar o arquivo: templates/Secao_pessoal/troca_de_setor.html
    return render(request, 'Secao_pessoal/troca_de_setor.html')