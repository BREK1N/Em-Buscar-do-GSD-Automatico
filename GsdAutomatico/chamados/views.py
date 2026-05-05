"""
Views do módulo de Chamados de Suporte.

Regras de acesso:
  - Grupo 'Militar da Informática' (ou superuser): vê fila global, pode atender/mudar status
  - Demais usuários: veem somente seus próprios chamados

Notificações na Caixa de Entrada:
  - Apenas eventos de sistema chegam na inbox: abertura, atribuição, mudança de status
  - Mensagens do chat NÃO geram item na inbox (comunicação via WebSocket)
"""
import json
import mimetypes
import os

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView

from caixa_entrada.views import InboxMixin, _sidebar_counts

from .models import AnexoChamado, Chamado, MensagemChamado


# ── Helpers de permissão ──────────────────────────────────────────────────────

def _is_informatica(user):
    """Verifica se o usuário pertence ao grupo de suporte ou é superuser."""
    return user.is_superuser or user.groups.filter(name='Militar da Informática').exists()


# ── Mixin para injetar contexto da inbox no chamado ──────────────────────────

class _ChamadoMixin(InboxMixin):
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pasta_ativa'] = 'chamados_suporte'
        ctx['is_informatica'] = _is_informatica(self.request.user)
        user = self.request.user
        if _is_informatica(user):
            ctx['count_chamados_suporte'] = Chamado.objects.filter(
                atribuido_a__isnull=True, status='aberto'
            ).count()
        else:
            ctx['count_chamados_suporte'] = Chamado.objects.filter(
                solicitante=user
            ).exclude(status='fechado').count()
        return ctx


# ── Notificações de sistema (somente eventos relevantes vão para a inbox) ────

def _notificar_sistema(remetente, destinatario, assunto, corpo):
    """Cria Notificacao no novo sistema unificado para eventos de chamado."""
    try:
        from notificacoes.utils import notificar
        notificar(destinatario, assunto, corpo=corpo, tipo='sistema')
    except Exception:
        pass


def _msg_sistema(chamado, texto):
    """Cria mensagem de auditoria no thread do chamado (não vai para inbox)."""
    return MensagemChamado.objects.create(
        chamado=chamado,
        autor=None,
        texto=texto,
        eh_sistema=True,
    )


def _broadcast_ws(chamado_pk, payload):
    """Envia evento via WebSocket para todos os participantes do chamado."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chamado_{chamado_pk}",
        {"type": "broadcast_message", "payload": payload},
    )


def _broadcast_status_ws(chamado):
    """Notifica via WebSocket a mudança de status do chamado."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chamado_{chamado.pk}",
        {
            "type": "broadcast_status",
            "payload": {
                "tipo": "status_change",
                "novo_status": chamado.status,
                "novo_status_display": chamado.get_status_display(),
                "atribuido_a": (
                    chamado.atribuido_a.get_full_name() or chamado.atribuido_a.username
                ) if chamado.atribuido_a else None,
            },
        },
    )


# ── Views CBV ─────────────────────────────────────────────────────────────────

class ChamadoListView(_ChamadoMixin, ListView):
    template_name = 'chamados/lista.html'
    context_object_name = 'chamados'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = Chamado.objects.select_related('solicitante', 'atribuido_a')

        if _is_informatica(user):
            filtro = self.request.GET.get('filtro', 'fila')
            if filtro == 'meus':
                qs = qs.filter(atribuido_a=user)
            elif filtro == 'fila':
                qs = qs.filter(atribuido_a__isnull=True).exclude(
                    status__in=['resolvido', 'fechado']
                )
            # filtro='todos' → sem restrição adicional
        else:
            qs = qs.filter(solicitante=user)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['filtro_ativo'] = self.request.GET.get('filtro', 'fila')
        ctx['status_ativo'] = self.request.GET.get('status', '')
        ctx['status_choices'] = Chamado._meta.get_field('status').choices
        if _is_informatica(user):
            ctx['count_fila'] = Chamado.objects.filter(
                atribuido_a__isnull=True
            ).exclude(status__in=['resolvido', 'fechado']).count()
            ctx['count_meus'] = Chamado.objects.filter(
                atribuido_a=user
            ).exclude(status='fechado').count()
        return ctx


class ChamadoCreateView(_ChamadoMixin, CreateView):
    template_name = 'chamados/novo.html'
    model = Chamado
    fields = ['titulo', 'descricao', 'prioridade']

    def form_valid(self, form):
        chamado = form.save(commit=False)
        chamado.solicitante = self.request.user
        chamado.save()

        nome = self.request.user.get_full_name() or self.request.user.username
        _msg_sistema(chamado, f"Chamado aberto por {nome}.")

        # Salva anexos enviados junto com o formulário
        anexos = self.request.FILES.getlist('anexos')
        if anexos:
            msg_anexos = MensagemChamado.objects.create(
                chamado=chamado,
                autor=self.request.user,
                texto='',
            )
            for f in anexos:
                AnexoChamado.objects.create(
                    mensagem=msg_anexos, arquivo=f, nome=f.name, tamanho=f.size
                )

        # Notifica o grupo Informática na caixa de entrada (evento de sistema)
        for u in User.objects.filter(groups__name='Militar da Informática'):
            _notificar_sistema(
                self.request.user, u,
                f"[Chamado #{chamado.protocolo}] {chamado.titulo}",
                f"{nome} abriu um novo chamado.\n\nPrioridade: {chamado.get_prioridade_display()}\n\n{chamado.descricao}"
            )

        messages.success(self.request, f"Chamado #{chamado.protocolo} aberto com sucesso.")
        return redirect('chamados:detalhe', pk=chamado.pk)


class ChamadoDetailView(_ChamadoMixin, DetailView):
    template_name = 'chamados/detalhe.html'
    model = Chamado

    def get_object(self, queryset=None):
        chamado = get_object_or_404(Chamado, pk=self.kwargs['pk'])
        user = self.request.user
        if not _is_informatica(user) and chamado.solicitante != user:
            raise Http404
        return chamado

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['thread'] = self.object.mensagens.select_related('autor').prefetch_related('anexos')
        ctx['status_choices'] = Chamado._meta.get_field('status').choices
        return ctx


# ── Views de ação ────────────────────────────────────────────────────────────

@login_required
def atender_chamado_view(request, pk):
    """Atribui o chamado ao militar logado e muda status para Em Atendimento."""
    if not _is_informatica(request.user):
        messages.error(request, "Sem permissão.")
        return redirect('chamados:lista')

    chamado = get_object_or_404(Chamado, pk=pk)
    if chamado.atribuido_a:
        messages.warning(
            request,
            f"Chamado já atribuído a "
            f"{chamado.atribuido_a.get_full_name() or chamado.atribuido_a.username}."
        )
        return redirect('chamados:detalhe', pk=pk)

    chamado.atribuido_a = request.user
    chamado.status = 'em_atendimento'
    chamado.save()

    nome = request.user.get_full_name() or request.user.username
    _msg_sistema(chamado, f"{nome} assumiu este chamado.")

    # Notificação de sistema na inbox do solicitante
    _notificar_sistema(
        request.user, chamado.solicitante,
        f"[Chamado #{chamado.protocolo}] Em Atendimento",
        f"Seu chamado '{chamado.titulo}' foi assumido por {nome} e está em atendimento."
    )

    # Broadcast WebSocket para participantes já conectados
    _broadcast_status_ws(chamado)

    messages.success(request, f"Você assumiu o chamado #{chamado.protocolo}.")
    return redirect('chamados:detalhe', pk=pk)


@login_required
def reply_chamado_view(request, pk):
    """
    Fallback HTTP para enviar mensagem no chat quando WebSocket não está disponível
    (ex: upload de arquivo). Mensagens de chat NÃO vão para a caixa de entrada.
    """
    if request.method != 'POST':
        return redirect('chamados:detalhe', pk=pk)

    chamado = get_object_or_404(Chamado, pk=pk)
    user = request.user

    if not _is_informatica(user) and chamado.solicitante != user:
        raise Http404

    texto = request.POST.get('texto', '').strip()
    if not texto and not request.FILES:
        messages.error(request, "Mensagem não pode ser vazia.")
        return redirect('chamados:detalhe', pk=pk)

    msg = MensagemChamado.objects.create(
        chamado=chamado, autor=user, texto=texto
    )

    for f in request.FILES.getlist('anexos'):
        AnexoChamado.objects.create(
            mensagem=msg, arquivo=f, nome=f.name, tamanho=f.size
        )

    # Envia via WebSocket (mensagem aparece em tempo real para quem está na tela)
    if texto:
        _broadcast_ws(chamado.pk, {
            "tipo": "chat_message",
            "id": msg.id,
            "autor_id": user.id,
            "autor_nome": user.get_full_name() or user.username,
            "autor_foto": user.profile.foto.url if hasattr(user, 'profile') and user.profile.foto else None,
            "texto": texto,
            "timestamp": msg.created_at.strftime("%d/%m/%Y %H:%M"),
            "eh_ti": _is_informatica(user),
        })

    # NÃO envia notificação na inbox — o chat é em tempo real via WebSocket
    return redirect('chamados:detalhe', pk=pk)


@login_required
def update_status_view(request, pk):
    """Muda o status do chamado. Gera notificação de sistema na inbox."""
    if request.method != 'POST':
        return redirect('chamados:detalhe', pk=pk)

    if not _is_informatica(request.user):
        messages.error(request, "Sem permissão.")
        return redirect('chamados:lista')

    chamado = get_object_or_404(Chamado, pk=pk)
    novo_status = request.POST.get('status')
    validos = [s[0] for s in Chamado._meta.get_field('status').choices]

    if novo_status not in validos:
        messages.error(request, "Status inválido.")
        return redirect('chamados:detalhe', pk=pk)

    status_anterior = chamado.get_status_display()
    chamado.status = novo_status
    if novo_status in ('resolvido', 'fechado'):
        chamado.fechado_em = timezone.now()
    chamado.save()

    nome = request.user.get_full_name() or request.user.username
    _msg_sistema(
        chamado,
        f"{nome} alterou o status de '{status_anterior}' para '{chamado.get_status_display()}'."
    )

    # Notificação de sistema na inbox (mudança de status é relevante)
    _notificar_sistema(
        request.user, chamado.solicitante,
        f"[Chamado #{chamado.protocolo}] Status: {chamado.get_status_display()}",
        f"O status do seu chamado '{chamado.titulo}' foi atualizado para: "
        f"{chamado.get_status_display()}."
    )

    # Broadcast WebSocket
    _broadcast_status_ws(chamado)

    messages.success(request, f"Status atualizado para '{chamado.get_status_display()}'.")
    return redirect('chamados:detalhe', pk=pk)


@login_required
def download_anexo_view(request, pk):
    """Serve o arquivo de anexo com verificação de permissão."""
    anexo = get_object_or_404(AnexoChamado, pk=pk)
    chamado = anexo.mensagem.chamado
    user = request.user

    if not _is_informatica(user) and chamado.solicitante != user:
        raise Http404

    if not anexo.arquivo or not os.path.exists(anexo.arquivo.path):
        raise Http404

    content_type, _ = mimetypes.guess_type(anexo.nome)
    response = FileResponse(
        open(anexo.arquivo.path, 'rb'),
        content_type=content_type or 'application/octet-stream'
    )
    response['Content-Disposition'] = f'attachment; filename="{anexo.nome}"'
    return response
