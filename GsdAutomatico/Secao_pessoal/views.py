import pandas as pd
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from Secao_pessoal.models import Efetivo
from Ouvidoria.forms import MilitarForm 
from django.contrib import messages
from django.db.models import Q


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

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(nome_guerra__icontains=q) |
                Q(nome_completo__icontains=q) |
                Q(posto__icontains=q) |
                Q(om__icontains=q) |
                Q(saram__icontains=q)
            )
        return queryset

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            self.object_list = self.get_queryset()
            context = self.get_context_data()
            return render(request, 'Secao_pessoal/militar_list_partial.html', context)
        return super().get(request, *args, **kwargs)

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
    if request.method == 'POST' and request.FILES.get('arquivo_excel'):
        excel_file = request.FILES['arquivo_excel']
        
        try:
            df = pd.read_excel(excel_file).fillna('')

            df.columns = df.columns.str.strip()
            
            importados = 0
            
            for index, row in df.iterrows():
                posto = row.get('PST.', '')
                quad = row.get('QUAD.', '')
                especializacao = row.get('ESP.', '')
                saram = row.get('SARAM')
                nome_completo = row.get('NOME COMPLETO')
                nome_guerra = row.get('NOME DE GUERRA')
                turma = row.get('TURMA', '')
                situacao = row.get('SITUAÇÃO', '')
                om = row.get('OM', '')
                setor = row.get('SETOR', '')
                subsetor = row.get('SUBSETOR', '')
                
                # Fallbacks para compatibilidade caso as colunas venham com nomes antigos
                if not nome_guerra:
                    nome_guerra = row.get('Nome de Guerra', '')
                if not nome_completo:
                    nome_completo = row.get('Nome Completo', '') or nome_guerra
                
                if saram and not Efetivo.objects.filter(saram=saram).exists():
                    Efetivo.objects.create(
                        posto=posto,
                        quad=quad,
                        especializacao=especializacao,
                        saram=saram,
                        nome_completo=nome_completo,
                        nome_guerra=nome_guerra,
                        turma=turma,
                        situacao=situacao,
                        om=om,
                        setor=setor,
                        subsetor=subsetor,
                    )
                    importados += 1
            
            messages.success(request, f'Importação concluída! {importados} novos militares adicionados.')
            return redirect('Secao_pessoal:militar_list')
            
        except Exception as e:
            messages.error(request, f'Erro ao processar o arquivo: {str(e)}')
            
    return render(request, 'Secao_pessoal/importar_excel.html')