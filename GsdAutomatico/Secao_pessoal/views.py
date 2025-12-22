import pandas as pd
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from Secao_pessoal.models import Efetivo
from Ouvidoria.forms import MilitarForm 
from django.contrib import messages


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
            queryset = queryset.filter(nome_guerra__icontains=q)
        return queryset

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
            df = pd.read_excel(excel_file)

            df.columns = df.columns.str.strip()
            
            importados = 0
            
            for index, row in df.iterrows():
                posto = row.get('PST.')
                nome_guerra = row.get('Nome de Guerra')
                saram = row.get('SARAM')
                
                
                if saram and not Efetivo.objects.filter(saram=saram).exists():
                    Efetivo.objects.create(
                        posto=posto,
                        nome_guerra=nome_guerra,
                        saram=saram,
                    )
                    importados += 1
            
            messages.success(request, f'Importação concluída! {importados} novos militares adicionados.')
            return redirect('Secao_pessoal:militar_list')
            
        except Exception as e:
            messages.error(request, f'Erro ao processar o arquivo: {str(e)}')
            
    return render(request, 'Secao_pessoal/importar_excel.html')

def nome_de_guerra(request):
    # Lembre-se de criar o arquivo: templates/Secao_pessoal/nome_de_guerra.html
    return render(request, 'Secao_pessoal/nome_de_guerra.html')

def troca_de_setor(request):
    # Lembre-se de criar o arquivo: templates/Secao_pessoal/troca_de_setor.html
    return render(request, 'Secao_pessoal/troca_de_setor.html')