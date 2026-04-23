import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.db.models import Q, Count, Case, When, Value, IntegerField

from ..models import PATD
from ..forms import AtribuirOficialForm, AceitarAtribuicaoForm
from Secao_pessoal.models import Efetivo
from Secao_pessoal.utils import get_rank_value, RANK_HIERARCHY
from .decorators import (
    ouvidoria_required, oficial_responsavel_required, OuvidoriaAccessMixin, comandante_redirect,
)
from .helpers import format_militar_string, _sync_oficial_signature, get_document_pages, _try_advance_status_from_justificativa

logger = logging.getLogger(__name__)

@login_required
@ouvidoria_required
def atribuir_oficial(request, pk):
    patd = get_object_or_404(PATD, pk=pk)
    if request.method == 'POST':
        # --- INÍCIO DA MODIFICAÇÃO: Validação explícita ---
        if not request.POST.get('oficial_responsavel'):
            messages.error(request, 'Você deve selecionar um oficial para fazer a atribuição.')
            form = AtribuirOficialForm(instance=patd, user=request.user)
            return render(request, 'atribuir_oficial.html', {'form': form, 'patd': patd})
        # --- FIM DA MODIFICAÇÃO ---

        form = AtribuirOficialForm(request.POST, instance=patd, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Oficial {patd.oficial_responsavel.nome_guerra} foi atribuído. Aguardando aceitação.')
            return redirect('Ouvidoria:patd_detail', pk=pk)
    else:
        form = AtribuirOficialForm(instance=patd, user=request.user)
    return render(request, 'atribuir_oficial.html', {'form': form, 'patd': patd})


@login_required
@comandante_redirect
def patd_atribuicoes_pendentes(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.militar:
        messages.warning(request, "Seu usuário não está associado a um militar.")
        return redirect('Ouvidoria:index')
    
    if not request.user.profile.militar.oficial:
        messages.error(request, "Apenas Oficiais podem acessar a área de atribuições.")
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
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        return _aceitar_atribuicao_inner(request, pk, patd, is_ajax)
    except Exception as exc:
        logger.exception(f"Erro inesperado em aceitar_atribuicao PATD {pk}: {exc}")
        if is_ajax:
            return JsonResponse({'ok': False, 'erro': f'Erro interno: {exc}'}, status=500)
        messages.error(request, f"Erro interno: {exc}")
        return redirect('Ouvidoria:patd_atribuicoes_pendentes')


def _aceitar_atribuicao_inner(request, pk, patd, is_ajax):
    try:
        tem_perfil = hasattr(request.user, 'profile') and request.user.profile.militar
    except Exception:
        tem_perfil = False

    if not (tem_perfil and request.user.profile.militar == patd.oficial_responsavel):
        if is_ajax:
            return JsonResponse({'ok': False, 'erro': 'Você não tem permissão para aceitar esta atribuição.'}, status=403)
        messages.error(request, "Você não tem permissão para aceitar esta atribuição.")
        return redirect('Ouvidoria:patd_detail', pk=pk)

    form = AceitarAtribuicaoForm(request.POST)
    if form.is_valid():
        senha = form.cleaned_data['senha']
        user = authenticate(request, username=request.user.username, password=senha)
        if user is not None:
            # --- INÍCIO DA LÓGICA DE STATUS ---
            # Se a PATD já foi finalizada (data_termino preenchido durante finalizar_patd_completa)
            # mas ficou aguardando aceitação do oficial, retorna direto para finalizado.
            if patd.data_termino:
                patd.status = 'finalizado'
                patd.status_anterior = None
            elif patd.status_anterior:
                patd.status = patd.status_anterior
                patd.status_anterior = None
            else:
                patd.status = 'ciencia_militar'
            # --- FIM DA LÓGICA DE STATUS ---

            patd.save() # Salva o status para que a sincronização funcione corretamente

            # --- INÍCIO DA MODIFICAÇÃO: Sincronizar assinatura do oficial ---
            _sync_oficial_signature(patd)
            # --- FIM DA MODIFICAÇÃO ---

            # --- NOVA VERIFICAÇÃO DE ASSINATURAS DE CIÊNCIA ---
            if not patd.data_termino and patd.status == 'ciencia_militar':
                try:
                    document_pages = get_document_pages(patd) # Gera o documento para contar placeholders
                    coringa_doc_text = document_pages[0] if document_pages else ""
                    required_initial_signatures = coringa_doc_text.count('{Assinatura Militar Arrolado}')
                    provided_signatures = sum(1 for s in (patd.assinaturas_militar or []) if s is not None)

                    logger.info(f"PATD {pk} aceita. Status: {patd.status}. Assinaturas requeridas: {required_initial_signatures}, Assinaturas providas: {provided_signatures}")

                    if provided_signatures >= required_initial_signatures:
                        if patd.data_ciencia is None: # Define a data da ciência se ainda não estiver definida
                            patd.data_ciencia = timezone.now()
                        patd.status = 'aguardando_justificativa' # Avança o status
                        logger.info(f"PATD {pk}: Assinaturas de ciência completas. Avançando status para 'aguardando_justificativa'.")
                        # Tenta avançar mais se a defesa já existir (caso raro, mas possível)
                        _try_advance_status_from_justificativa(patd)
                except Exception as e:
                    logger.error(f"Erro ao verificar assinaturas de ciência após aceite para PATD {pk}: {e}")
            # --- FIM DA NOVA VERIFICAÇÃO ---

            patd.save()
            if is_ajax:
                return JsonResponse({'ok': True, 'mensagem': f'Atribuição da PATD Nº {patd.numero_patd} aceite com sucesso.'})
            messages.success(request, f'Atribuição da PATD Nº {patd.numero_patd} aceite com sucesso.')
            return redirect('Ouvidoria:patd_atribuicoes_pendentes')
        else:
            if is_ajax:
                return JsonResponse({'ok': False, 'erro': 'Senha incorreta. Tente novamente.'}, status=400)
            messages.error(request, "Senha incorreta. A atribuição não foi aceite.")
    else:
        if is_ajax:
            return JsonResponse({'ok': False, 'erro': 'Formulário inválido. A senha é obrigatória.'}, status=400)
        messages.error(request, "Formulário inválido.")

    return redirect('Ouvidoria:patd_atribuicoes_pendentes')


class MilitarDetailView(DetailView):
    model = Efetivo # Certifique-se de usar o modelo correto
    template_name = 'militar_detail.html'
    context_object_name = 'militar'


@method_decorator([login_required, ouvidoria_required], name='dispatch')
class MilitarListView(ListView):
    model = Efetivo
    template_name = 'militar_list.html'
    context_object_name = 'militares'
    ordering = ['nome_guerra']
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['militar_list_partial.html']
        return ['militar_list.html']

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


@method_decorator([login_required, ouvidoria_required], name='dispatch')
class MilitarPATDListView(ListView):
    model = PATD
    template_name = 'militar_patd_list.html'
    context_object_name = 'patds'
    paginate_by = 10

    def get_queryset(self):
        self.militar = get_object_or_404(Efetivo, pk=self.kwargs['pk'])
        # Verifique se no seu model PATD o campo é 'militar_envolvido' ou 'militar'
        return PATD.objects.filter(militar=self.militar).select_related('militar', 'oficial_responsavel').order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['militar'] = self.militar
        return context
