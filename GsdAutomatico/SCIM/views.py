from datetime import date
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, DetailView
from django.urls import reverse_lazy
from django.db.models import Count, Q, Prefetch, Case, When, Value, IntegerField
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from Secao_pessoal.models import Efetivo

RANK_ORDER = Case(
    When(posto='CL',  then=Value(0)),  When(posto='TC',  then=Value(1)),
    When(posto='MJ',  then=Value(2)),  When(posto='CP',  then=Value(3)),
    When(posto='1T',  then=Value(4)),  When(posto='2T',  then=Value(5)),
    When(posto='ASP', then=Value(6)),  When(posto='SO',  then=Value(7)),
    When(posto='1S',  then=Value(8)),  When(posto='2S',  then=Value(9)),
    When(posto='3S',  then=Value(10)), When(posto='CB',  then=Value(11)),
    When(posto='S1',  then=Value(12)), When(posto='S2',  then=Value(13)),
    When(posto='REC', then=Value(14)),
    default=Value(99), output_field=IntegerField(),
)
from Secao_operacoes.models import Missao
from .models import TipoCurso, CursoEfetivo
from .forms import TipoCursoForm, CursoEfetivoForm


@login_required
def buscar_efetivos(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse([], safe=False)
    efetivos = Efetivo.objects.filter(
        Q(nome_completo__icontains=q) | Q(nome_guerra__icontains=q) | Q(posto__icontains=q)
    ).values('id', 'posto', 'nome_guerra', 'nome_completo')[:20]
    return JsonResponse(list(efetivos), safe=False)


@method_decorator(login_required, name='dispatch')
class IndexSCIM(TemplateView):
    template_name = 'SCIM/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_cursos'] = CursoEfetivo.objects.count()
        ctx['total_tipos'] = TipoCurso.objects.filter(ativo=True).count()
        ctx['cursos_por_tipo'] = (
            TipoCurso.objects
            .filter(ativo=True)
            .annotate(total=Count('cursoefetivo'))
            .order_by('-total')
        )
        ctx['ultimos_cursos'] = CursoEfetivo.objects.select_related('efetivo', 'tipo_curso').order_by('-criado_em')[:10]
        return ctx


@method_decorator(login_required, name='dispatch')
class EfetivoComCursosListView(ListView):
    model = Efetivo
    template_name = 'SCIM/efetivo_list.html'
    context_object_name = 'efetivos'
    paginate_by = 30

    def get_queryset(self):
        qs = Efetivo.objects.annotate(
            total_cursos=Count('cursos'),
            rank_order=RANK_ORDER,
        ).order_by('rank_order', 'turma', 'nome_completo')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nome_completo__icontains=q) | Q(nome_guerra__icontains=q) | Q(posto__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro_q'] = self.request.GET.get('q', '')
        return ctx


@method_decorator(login_required, name='dispatch')
class CursosPorEfetivoView(DetailView):
    model = Efetivo
    template_name = 'SCIM/efetivo_cursos.html'
    context_object_name = 'efetivo'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cursos'] = CursoEfetivo.objects.filter(efetivo=self.object).select_related('tipo_curso').order_by('-data_realizacao')
        return ctx


@method_decorator(login_required, name='dispatch')
class CursoEfetivoListView(ListView):
    model = CursoEfetivo
    template_name = 'SCIM/curso_efetivo_list.html'
    context_object_name = 'cursos'
    paginate_by = 20

    def get_queryset(self):
        qs = CursoEfetivo.objects.select_related('efetivo', 'tipo_curso')
        efetivo_id = self.request.GET.get('efetivo')
        tipo_id = self.request.GET.get('tipo')
        q = self.request.GET.get('q')
        if efetivo_id:
            qs = qs.filter(efetivo_id=efetivo_id)
        if tipo_id:
            qs = qs.filter(tipo_curso_id=tipo_id)
        if q:
            qs = qs.filter(
                Q(efetivo__nome_completo__icontains=q) |
                Q(efetivo__nome_guerra__icontains=q) |
                Q(tipo_curso__nome__icontains=q) |
                Q(instituicao__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tipos'] = TipoCurso.objects.filter(ativo=True)
        ctx['filtro_tipo'] = self.request.GET.get('tipo', '')
        ctx['filtro_q'] = self.request.GET.get('q', '')
        return ctx


@method_decorator(login_required, name='dispatch')
class CursoEfetivoCreateView(CreateView):
    model = CursoEfetivo
    form_class = CursoEfetivoForm
    template_name = 'SCIM/curso_efetivo_form.html'
    success_url = reverse_lazy('SCIM:efetivo_list')

    def get_initial(self):
        initial = super().get_initial()
        efetivo_id = self.request.GET.get('efetivo')
        if efetivo_id:
            initial['efetivo'] = efetivo_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Curso'
        efetivo_id = self.request.GET.get('efetivo')
        if efetivo_id:
            try:
                ctx['efetivo_presel'] = Efetivo.objects.get(pk=efetivo_id)
            except Efetivo.DoesNotExist:
                pass
        return ctx


@method_decorator(login_required, name='dispatch')
class CursoEfetivoUpdateView(UpdateView):
    model = CursoEfetivo
    form_class = CursoEfetivoForm
    template_name = 'SCIM/curso_efetivo_form.html'
    success_url = reverse_lazy('SCIM:efetivo_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Curso'
        return ctx


@method_decorator(login_required, name='dispatch')
class CursoEfetivoDeleteView(DeleteView):
    model = CursoEfetivo
    template_name = 'SCIM/curso_efetivo_confirm_delete.html'
    success_url = reverse_lazy('SCIM:efetivo_list')


@method_decorator(login_required, name='dispatch')
class TipoCursoListView(ListView):
    model = TipoCurso
    template_name = 'SCIM/tipo_curso_list.html'
    context_object_name = 'tipos'
    queryset = TipoCurso.objects.annotate(total=Count('cursoefetivo')).order_by('nome')


@method_decorator(login_required, name='dispatch')
class TipoCursoCreateView(CreateView):
    model = TipoCurso
    form_class = TipoCursoForm
    template_name = 'SCIM/tipo_curso_form.html'
    success_url = reverse_lazy('SCIM:tipo_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Novo Tipo de Curso'
        return ctx


@method_decorator(login_required, name='dispatch')
class TipoCursoUpdateView(UpdateView):
    model = TipoCurso
    form_class = TipoCursoForm
    template_name = 'SCIM/tipo_curso_form.html'
    success_url = reverse_lazy('SCIM:tipo_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Tipo de Curso'
        return ctx
