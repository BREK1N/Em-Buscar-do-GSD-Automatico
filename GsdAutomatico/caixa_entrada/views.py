import json
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.contrib import messages
from django.db.models import Q, Count, OuterRef, Exists
from django.urls import reverse, reverse_lazy
from django.http import HttpResponse, FileResponse, Http404
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model

from Secao_pessoal.models import Efetivo, SolicitacaoTrocaSetor
from .models import Notificacao, Mensagem, LeituraMensagem, Anexo
from .forms import NotificacaoForm, MensagemForm, FiltroInboxForm

User = get_user_model()

# ─── Helpers ──────────────────────────────────────────────────────────────────

_SECAO_TEMPLATES = {
    'ouvidoria': 'base.html',
    'informatica': 'informatica/base.html',
    'operacoes': 'Secao_operacoes/base.html',
    's1': 'Secao_pessoal/base.html',
    'home': 'home/base_for_inbox.html',
}

_GROUP_SECAO = {
    'Ouvidoria': 'ouvidoria',
    'Informatica': 'informatica',
    'seção de operação': 'operacoes',
    'Secao_operacoes': 'operacoes',
    'S1': 's1',
}


def _get_militar_logado(request):
    try:
        if hasattr(request.user, 'profile'):
            return request.user.profile.militar
    except Exception:
        pass
    return None


def _resolve_base_template(request):
    secao = request.session.get('caixa_entrada_secao')
    if secao and secao in _SECAO_TEMPLATES:
        return _SECAO_TEMPLATES[secao]
    if request.user.is_authenticated and not request.user.is_superuser:
        for group in request.user.groups.values_list('name', flat=True):
            if group in _GROUP_SECAO:
                return _SECAO_TEMPLATES[_GROUP_SECAO[group]]
    return 'Secao_pessoal/base.html'


def _sidebar_counts(user):
    """Retorna contagens para a sidebar."""
    base_qs = Mensagem.objects.filter(eh_rascunho=False)

    nao_lidas = base_qs.filter(
        destinatarios=user
    ).exclude(
        excluida_por=user
    ).exclude(
        permanentemente_excluida_por=user
    ).exclude(
        lida_por=user
    ).count()

    chamados_abertos = base_qs.filter(
        tipo='chamado', status_chamado='aberto'
    ).filter(
        Q(remetente=user) | Q(destinatarios=user)
    ).exclude(excluida_por=user).exclude(permanentemente_excluida_por=user).count()

    rascunhos = Mensagem.objects.filter(remetente=user, eh_rascunho=True).count()
    excluidas = Mensagem.objects.filter(
        excluida_por=user
    ).exclude(permanentemente_excluida_por=user).count()
    favoritas = Mensagem.objects.filter(
        favoritos=user
    ).exclude(permanentemente_excluida_por=user).count()

    return {
        'count_nao_lidas': nao_lidas,
        'count_chamados_abertos': chamados_abertos,
        'count_rascunhos': rascunhos,
        'count_excluidas': excluidas,
        'count_favoritas': favoritas,
    }


def _base_context(request):
    ctx = {'base_template': _resolve_base_template(request)}
    ctx.update(_sidebar_counts(request.user))
    return ctx


# ─── Mixin para context comum ─────────────────────────────────────────────────

class InboxMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        secao_param = request.GET.get('secao')
        if secao_param and secao_param in _SECAO_TEMPLATES:
            request.session['caixa_entrada_secao'] = secao_param
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['base_template'] = _resolve_base_template(self.request)
        ctx.update(_sidebar_counts(self.request.user))
        return ctx


# ─── Inbox: mensagens recebidas ───────────────────────────────────────────────

class InboxListView(InboxMixin, ListView):
    template_name = 'caixa_entrada/lista.html'
    context_object_name = 'mensagens'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        qs = Mensagem.objects.filter(
            destinatarios=user, eh_rascunho=False
        ).exclude(excluida_por=user).exclude(permanentemente_excluida_por=user).prefetch_related('anexos', 'lida_por', 'destinatarios', 'favoritos').select_related('remetente')

        filtro = FiltroInboxForm(self.request.GET)
        if filtro.is_valid():
            if filtro.cleaned_data.get('tipo'):
                qs = qs.filter(tipo=filtro.cleaned_data['tipo'])
            if filtro.cleaned_data.get('status_chamado'):
                qs = qs.filter(status_chamado=filtro.cleaned_data['status_chamado'])
            if filtro.cleaned_data.get('data_inicial'):
                qs = qs.filter(data_envio__date__gte=filtro.cleaned_data['data_inicial'])
            if filtro.cleaned_data.get('data_final'):
                qs = qs.filter(data_envio__date__lte=filtro.cleaned_data['data_final'])
            if filtro.cleaned_data.get('q'):
                qs = qs.filter(assunto__icontains=filtro.cleaned_data['q'])
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro'] = FiltroInboxForm(self.request.GET)
        ctx['pasta_ativa'] = 'entrada'
        # Para saber quais mensagens o usuário já leu
        user = self.request.user
        ids_lidas = set(
            LeituraMensagem.objects.filter(
                usuario=user,
                mensagem__in=ctx['mensagens']
            ).values_list('mensagem_id', flat=True)
        )
        ctx['ids_lidas'] = ids_lidas
        ids_favoritas = set(
            Mensagem.objects.filter(
                favoritos=user,
                pk__in=[m.pk for m in ctx['mensagens']]
            ).values_list('pk', flat=True)
        )
        ctx['ids_favoritas'] = ids_favoritas
        return ctx


# ─── Favoritos ────────────────────────────────────────────────────────────────

class FavoritosListView(InboxMixin, ListView):
    template_name = 'caixa_entrada/lista.html'
    context_object_name = 'mensagens'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        return Mensagem.objects.filter(
            favoritos=user, eh_rascunho=False
        ).exclude(permanentemente_excluida_por=user).prefetch_related('anexos', 'lida_por', 'destinatarios', 'favoritos').select_related('remetente')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro'] = FiltroInboxForm(self.request.GET)
        ctx['pasta_ativa'] = 'favoritos'
        user = self.request.user
        ids_lidas = set(
            LeituraMensagem.objects.filter(
                usuario=user, mensagem__in=ctx['mensagens']
            ).values_list('mensagem_id', flat=True)
        )
        ctx['ids_lidas'] = ids_lidas
        ctx['ids_favoritas'] = set(m.pk for m in ctx['mensagens'])
        return ctx


# ─── Enviados ─────────────────────────────────────────────────────────────────

class EnviadosListView(InboxMixin, ListView):
    template_name = 'caixa_entrada/lista.html'
    context_object_name = 'mensagens'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        return Mensagem.objects.filter(
            remetente=user, eh_rascunho=False
        ).exclude(
            excluida_por=user
        ).exclude(permanentemente_excluida_por=user).prefetch_related('anexos', 'lida_por', 'destinatarios', 'favoritos').select_related('remetente')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro'] = FiltroInboxForm(self.request.GET)
        ctx['pasta_ativa'] = 'enviados'
        ctx['ids_lidas'] = set()
        user = self.request.user
        ctx['ids_favoritas'] = set(
            Mensagem.objects.filter(
                favoritos=user, pk__in=[m.pk for m in ctx['mensagens']]
            ).values_list('pk', flat=True)
        )
        return ctx


# ─── Rascunhos ────────────────────────────────────────────────────────────────

class RascunhosListView(InboxMixin, ListView):
    template_name = 'caixa_entrada/lista.html'
    context_object_name = 'mensagens'
    paginate_by = 20

    def get_queryset(self):
        return Mensagem.objects.filter(
            remetente=self.request.user, eh_rascunho=True
        ).prefetch_related('anexos', 'destinatarios').select_related('remetente')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro'] = FiltroInboxForm()
        ctx['pasta_ativa'] = 'rascunhos'
        ctx['ids_lidas'] = set()
        return ctx


# ─── Excluídos ────────────────────────────────────────────────────────────────

class ExcluidosListView(InboxMixin, ListView):
    template_name = 'caixa_entrada/lista.html'
    context_object_name = 'mensagens'
    paginate_by = 20

    def get_queryset(self):
        return Mensagem.objects.filter(
            excluida_por=self.request.user
        ).exclude(permanentemente_excluida_por=self.request.user).prefetch_related('anexos', 'lida_por', 'destinatarios', 'favoritos').select_related('remetente')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filtro'] = FiltroInboxForm()
        ctx['pasta_ativa'] = 'excluidos'
        user = self.request.user
        ids_lidas = set(
            LeituraMensagem.objects.filter(
                usuario=user, mensagem__in=ctx['mensagens']
            ).values_list('mensagem_id', flat=True)
        )
        ctx['ids_lidas'] = ids_lidas
        ctx['ids_favoritas'] = set(
            Mensagem.objects.filter(
                favoritos=user, pk__in=[m.pk for m in ctx['mensagens']]
            ).values_list('pk', flat=True)
        )
        return ctx


# ─── Detalhe / Leitura ────────────────────────────────────────────────────────

class DetalheView(InboxMixin, DetailView):
    template_name = 'caixa_entrada/detalhe.html'
    context_object_name = 'msg'

    def get_object(self):
        user = self.request.user
        allowed_ids = Mensagem.objects.filter(
            Q(remetente=user) | Q(destinatarios=user)
        ).values_list('id', flat=True)
        return get_object_or_404(
            Mensagem.objects.prefetch_related('anexos', 'destinatarios', 'lida_por').select_related('remetente'),
            pk=self.kwargs['pk'],
            id__in=allowed_ids,
        )

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        msg = self.object
        # Marcar como lida
        if request.user in msg.destinatarios.all():
            LeituraMensagem.objects.get_or_create(mensagem=msg, usuario=request.user)
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        msg = self.object
        user = self.request.user
        ctx['pasta_ativa'] = 'enviados' if msg.remetente == user else 'entrada'
        ctx['leituras'] = LeituraMensagem.objects.filter(
            mensagem=msg
        ).select_related('usuario') if msg.remetente == user else []
        ctx['is_favorita'] = msg.favoritos.filter(pk=user.pk).exists()
        return ctx


# ─── Escrever / Editar rascunho ───────────────────────────────────────────────

class EscreveView(InboxMixin, View):
    template_name = 'caixa_entrada/nova.html'

    def _get_instance(self):
        pk = self.kwargs.get('pk')
        if pk:
            return get_object_or_404(
                Mensagem, pk=pk, remetente=self.request.user, eh_rascunho=True
            )
        return None

    def _get_reply_data(self, request):
        """Monta dados iniciais para responder uma mensagem."""
        reply_pk = request.GET.get('reply')
        if not reply_pk:
            return None, {}
        try:
            original = Mensagem.objects.get(
                pk=reply_pk,
                **{'id__in': Mensagem.objects.filter(
                    Q(remetente=request.user) | Q(destinatarios=request.user) | Q(cc=request.user)
                ).values_list('id', flat=True)}
            )
            assunto = original.assunto if original.assunto.startswith('Re:') else f"Re: {original.assunto}"
            corpo = f"\n\n---\nEm {original.data_envio.strftime('%d/%m/%Y %H:%M')}, {original.remetente.get_full_name() or original.remetente.username} escreveu:\n\n{original.corpo}"
            return original, {
                'assunto': assunto,
                'corpo': corpo,
                'reply_to_id': original.remetente.pk,
                'reply_to_label': self._user_label(original.remetente),
            }
        except Mensagem.DoesNotExist:
            return None, {}

    @staticmethod
    def _user_label(user):
        try:
            mil = user.profile.militar
            return f"{mil.posto} {mil.nome_guerra}"
        except Exception:
            return user.get_full_name() or user.username

    def get(self, request, *args, **kwargs):
        instance = self._get_instance()
        form = MensagemForm(instance=instance)
        original, reply_data = self._get_reply_data(request)
        if reply_data and not instance:
            form.initial['assunto'] = reply_data['assunto']
            form.initial['corpo'] = reply_data['corpo']
        ctx = self.get_context_data(form=form, reply_data=reply_data, original=original)
        return render(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        instance = self._get_instance()
        form = MensagemForm(request.POST, instance=instance)
        salvar_como_rascunho = 'rascunho' in request.POST

        if form.is_valid():
            msg = form.save(commit=False)
            msg.remetente = request.user
            msg.eh_rascunho = salvar_como_rascunho
            if msg.tipo == 'chamado' and not msg.status_chamado:
                msg.status_chamado = 'aberto'
            # Vincular reply
            reply_pk = request.POST.get('reply_to_msg')
            if reply_pk:
                try:
                    msg.mensagem_original_id = int(reply_pk)
                except (ValueError, TypeError):
                    pass
            msg.save()
            form.save_m2m()

            # Processar anexos
            for f in request.FILES.getlist('anexos'):
                mime = f.content_type or mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
                Anexo.objects.create(
                    mensagem=msg, arquivo=f,
                    nome_original=f.name, tamanho=f.size, tipo_mime=mime,
                )

            if salvar_como_rascunho:
                messages.success(request, "Rascunho salvo.")
                return redirect('caixa_entrada:rascunhos')
            messages.success(request, "Mensagem enviada com sucesso.")
            return redirect('caixa_entrada:enviados')

        ctx = self.get_context_data(form=form, reply_data={}, original=None)
        return render(request, self.template_name, ctx)

    def get_context_data(self, **kwargs):
        ctx = _base_context(self.request)
        ctx.update(kwargs)
        ctx['pasta_ativa'] = 'nova'
        ctx.update(_sidebar_counts(self.request.user))
        return ctx


# ─── Excluir (soft delete) ────────────────────────────────────────────────────

@login_required
@require_POST
def excluir_mensagem_view(request, pk):
    user = request.user
    msg = get_object_or_404(
        Mensagem,
        pk=pk
    )
    # Só pode excluir se for remetente ou destinatário
    if msg.remetente != user and user not in msg.destinatarios.all():
        messages.error(request, "Sem permissão para excluir esta mensagem.")
        return redirect('caixa_entrada:inbox')

    if msg.eh_rascunho and msg.remetente == user:
        msg.delete()
        messages.success(request, "Rascunho excluído.")
        return redirect('caixa_entrada:rascunhos')

    msg.excluida_por.add(user)
    messages.success(request, "Mensagem movida para excluídos.")
    return redirect(request.META.get('HTTP_REFERER', reverse('caixa_entrada:inbox')))


@login_required
@require_POST
def excluir_definitivo_view(request, pk):
    user = request.user
    msg = get_object_or_404(Mensagem, pk=pk)
    if msg.remetente != user and user not in msg.destinatarios.all():
        messages.error(request, "Sem permissão.")
        return redirect('caixa_entrada:excluidos')
    # Marca como permanentemente excluída para este usuário
    msg.permanentemente_excluida_por.add(user)
    # Verifica se todos os usuários com acesso excluíram permanentemente
    todos = set([msg.remetente.pk]) | set(msg.destinatarios.values_list('pk', flat=True))
    perm_excluidos = set(msg.permanentemente_excluida_por.values_list('pk', flat=True))
    if todos.issubset(perm_excluidos):
        msg.delete()
    messages.success(request, "Mensagem excluída permanentemente.")
    return redirect('caixa_entrada:excluidos')


@login_required
@require_POST
def restaurar_mensagem_view(request, pk):
    user = request.user
    msg = get_object_or_404(Mensagem, pk=pk)
    msg.excluida_por.remove(user)
    messages.success(request, "Mensagem restaurada.")
    return redirect('caixa_entrada:excluidos')


@login_required
@require_POST
def excluir_lote_view(request):
    user = request.user
    ids = request.POST.getlist('ids')
    acao = request.POST.get('acao', 'excluir')
    if not ids:
        messages.warning(request, "Nenhuma mensagem selecionada.")
        return redirect(request.META.get('HTTP_REFERER', reverse('caixa_entrada:inbox')))

    qs = Mensagem.objects.filter(pk__in=ids).filter(
        Q(remetente=user) | Q(destinatarios=user)
    ).distinct()

    count = qs.count()
    if acao == 'excluir':
        for msg in qs:
            msg.excluida_por.add(user)
        messages.success(request, f"{count} mensagem(ns) movida(s) para excluídos.")
    elif acao == 'restaurar':
        for msg in qs:
            msg.excluida_por.remove(user)
        messages.success(request, f"{count} mensagem(ns) restaurada(s).")
    elif acao == 'excluir_definitivo':
        for msg in qs:
            msg.permanentemente_excluida_por.add(user)
            todos = set([msg.remetente.pk]) | set(msg.destinatarios.values_list('pk', flat=True))
            perm_excluidos = set(msg.permanentemente_excluida_por.values_list('pk', flat=True))
            if todos.issubset(perm_excluidos):
                msg.delete()
        messages.success(request, f"{count} mensagem(ns) excluída(s) permanentemente.")
    elif acao == 'marcar_lida':
        for msg in qs:
            if user in msg.destinatarios.all():
                LeituraMensagem.objects.get_or_create(mensagem=msg, usuario=user)
        messages.success(request, f"{count} mensagem(ns) marcada(s) como lida(s).")
    elif acao == 'marcar_nao_lida':
        LeituraMensagem.objects.filter(mensagem__in=qs, usuario=user).delete()
        messages.success(request, f"{count} mensagem(ns) marcada(s) como não lida(s).")

    return redirect(request.META.get('HTTP_REFERER', reverse('caixa_entrada:inbox')))


# ─── Favoritar mensagem (toggle) ─────────────────────────────────────────────

@login_required
@require_POST
def favoritar_mensagem_view(request, pk):
    user = request.user
    msg = get_object_or_404(
        Mensagem,
        pk=pk,
    )
    if msg.remetente != user and user not in msg.destinatarios.all():
        from django.http import JsonResponse
        return JsonResponse({'error': 'Sem permissão.'}, status=403)
    if msg.favoritos.filter(pk=user.pk).exists():
        msg.favoritos.remove(user)
        ativo = False
    else:
        msg.favoritos.add(user)
        ativo = True
    from django.http import JsonResponse
    return JsonResponse({'favorito': ativo})


# ─── Marcar como lida / não lida (individual) ────────────────────────────────

@login_required
@require_POST
def marcar_lida_view(request, pk):
    user = request.user
    msg = get_object_or_404(Mensagem, pk=pk)
    if user not in msg.destinatarios.all():
        from django.http import JsonResponse
        return JsonResponse({'error': 'Sem permissão.'}, status=403)
    acao = request.POST.get('acao', 'lida')
    if acao == 'nao_lida':
        LeituraMensagem.objects.filter(mensagem=msg, usuario=user).delete()
        lida = False
    else:
        LeituraMensagem.objects.get_or_create(mensagem=msg, usuario=user)
        lida = True
    from django.http import JsonResponse
    return JsonResponse({'lida': lida})


# ─── Chamados (painel admin) ──────────────────────────────────────────────────

class ChamadoListView(InboxMixin, UserPassesTestMixin, ListView):
    template_name = 'caixa_entrada/chamados_admin.html'
    context_object_name = 'chamados'
    paginate_by = 30

    def test_func(self):
        return self.request.user.is_staff or self.request.user.has_perm('caixa_entrada.gerenciar_chamados')

    def get_queryset(self):
        qs = Mensagem.objects.filter(tipo='chamado').select_related('remetente').prefetch_related('destinatarios', 'anexos')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status_chamado=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pasta_ativa'] = 'chamados'
        ctx['status_filtro'] = self.request.GET.get('status', '')
        ctx['total_abertos'] = Mensagem.objects.filter(tipo='chamado', status_chamado='aberto').count()
        ctx['total_andamento'] = Mensagem.objects.filter(tipo='chamado', status_chamado='em_andamento').count()
        ctx['total_resolvidos'] = Mensagem.objects.filter(tipo='chamado', status_chamado='resolvido').count()
        return ctx


@login_required
@require_POST
def chamado_update_status(request, pk):
    if not (request.user.is_staff or request.user.has_perm('caixa_entrada.gerenciar_chamados')):
        messages.error(request, "Sem permissão.")
        return redirect('caixa_entrada:chamados')

    chamado = get_object_or_404(Mensagem, pk=pk, tipo='chamado')
    novo_status = request.POST.get('status')
    if novo_status in ('aberto', 'em_andamento', 'resolvido'):
        chamado.status_chamado = novo_status
        chamado.save()
        messages.success(request, f"Status atualizado para '{chamado.get_status_chamado_display()}'.")
    return redirect(request.META.get('HTTP_REFERER', reverse('caixa_entrada:chamados')))


# ─── Download de anexo ────────────────────────────────────────────────────────

@login_required
def download_anexo(request, pk):
    anexo = get_object_or_404(Anexo, pk=pk)
    msg = anexo.mensagem
    user = request.user
    if msg.remetente != user and user not in msg.destinatarios.all():
        raise Http404
    try:
        response = FileResponse(anexo.arquivo.open('rb'), content_type=anexo.tipo_mime)
        response['Content-Disposition'] = f'attachment; filename="{anexo.nome_original}"'
        return response
    except FileNotFoundError:
        raise Http404


# ─── API de notificações (bell no header) ─────────────────────────────────────

@login_required
def api_notificacoes_check(request):
    try:
        user = request.user
        data = []
        total = 0

        if hasattr(user, 'profile') and user.profile.militar:
            militar = user.profile.militar

            # Notificações do sistema (Ouvidoria etc.)
            sys_nao_lidas = Notificacao.objects.filter(
                destinatario=militar, lida=False
            )
            total += sys_nao_lidas.count()

            autorizacoes = SolicitacaoTrocaSetor.objects.filter(
                Q(chefe_atual=militar, status='pendente_atual') |
                Q(chefe_destino=militar, status='pendente_destino')
            )
            total += autorizacoes.count()

            for a in autorizacoes[:3]:
                data.append({
                    'id': a.id,
                    'titulo': f"Autorização Pendente: {a.militar.nome_guerra}",
                    'remetente': "Sistema",
                    'data': a.data_solicitacao.strftime('%d/%m %H:%M'),
                    'is_autorizacao': True,
                    'url': reverse('caixa_entrada:comunicacoes') + '?box=autorizacoes',
                })

            remaining = 5 - len(data)
            for n in sys_nao_lidas[:remaining]:
                data.append({
                    'id': n.id,
                    'titulo': n.titulo,
                    'remetente': n.remetente.nome_guerra if n.remetente else "Sistema",
                    'data': n.data_criacao.strftime('%d/%m %H:%M') if n.data_criacao else "",
                    'is_autorizacao': False,
                    'url': reverse('caixa_entrada:comunicacoes') + f'?ler={n.id}',
                })

        # Mensagens da nova caixa de entrada
        msgs_nao_lidas = Mensagem.objects.filter(
            destinatarios=user, eh_rascunho=False
        ).exclude(lida_por=user).exclude(excluida_por=user).exclude(permanentemente_excluida_por=user)
        total += msgs_nao_lidas.count()

        remaining = 5 - len(data)
        for m in msgs_nao_lidas[:remaining]:
            try:
                nome = m.remetente.profile.militar.nome_guerra
            except Exception:
                nome = m.remetente.get_full_name() or m.remetente.username
            data.append({
                'id': m.id,
                'titulo': m.assunto,
                'remetente': nome,
                'data': m.data_envio.strftime('%d/%m %H:%M'),
                'is_autorizacao': False,
                'url': reverse('caixa_entrada:detalhe', kwargs={'pk': m.pk}),
            })

        return HttpResponse(
            json.dumps({'count': total, 'unread_mensagens': msgs_nao_lidas.count(), 'notifications': data}),
            content_type='application/json'
        )
    except Exception as e:
        print(f"Erro API notificações: {e}")
    return HttpResponse(
        json.dumps({'count': 0, 'notifications': []}),
        content_type='application/json'
    )


# ─── API busca de usuários para o campo destinatários ────────────────────────

@login_required
def api_buscar_usuarios(request):
    term = request.GET.get('term', '').strip()
    if len(term) < 2:
        return HttpResponse(json.dumps({'results': []}), content_type='application/json')

    from django.db.models import Q as Qdb
    users = User.objects.filter(
        is_active=True
    ).filter(
        Qdb(username__icontains=term) |
        Qdb(first_name__icontains=term) |
        Qdb(last_name__icontains=term) |
        Qdb(profile__militar__nome_guerra__icontains=term) |
        Qdb(profile__militar__nome_completo__icontains=term)
    ).exclude(pk=request.user.pk).distinct()[:20]

    results = []
    for u in users:
        try:
            mil = u.profile.militar
            label = f"{mil.posto} {mil.nome_guerra} ({mil.setor or 'sem setor'})"
        except Exception:
            label = u.get_full_name() or u.username
        results.append({'user_id': u.pk, 'label': label})

    return HttpResponse(json.dumps({'results': results}), content_type='application/json')


# ─── View legada: comunicacoes (mantida para compatibilidade) ─────────────────

@login_required
def comunicacoes(request):
    secao_param = request.GET.get('secao')
    if secao_param and secao_param in _SECAO_TEMPLATES:
        request.session['caixa_entrada_secao'] = secao_param
    return redirect('caixa_entrada:inbox')
