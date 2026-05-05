from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver


# ── Mensagem enviada → cria Notificacao para cada destinatário ───────────────

def _notificar_mensagem(instance, pk_set):
    """Chamado via m2m_changed quando destinatários são adicionados a uma Mensagem."""
    from notificacoes.utils import notificar
    from django.contrib.auth import get_user_model
    from django.urls import reverse
    User = get_user_model()
    try:
        if instance.eh_rascunho:
            return
        usuarios = list(User.objects.filter(pk__in=pk_set))
        if not usuarios:
            return
        try:
            label = instance.remetente.profile.militar.nome_guerra
        except Exception:
            label = instance.remetente.get_full_name() or instance.remetente.username
        try:
            url = reverse('caixa_entrada:detalhe', kwargs={'pk': instance.pk})
        except Exception:
            url = ''
        notificar(
            usuarios,
            titulo=f"{label}: {instance.assunto}",
            corpo=instance.corpo[:200],
            url=url,
            tipo='mensagem',
            origem_id=instance.pk,
            origem_tipo='caixa_entrada.Mensagem',
        )
    except Exception:
        pass


# ── SolicitacaoTrocaSetor criada → notifica chefes ───────────────────────────

@receiver(post_save, sender='Secao_pessoal.SolicitacaoTrocaSetor')
def notificar_solicitacao_troca(sender, instance, created, **kwargs):
    if not created:
        return
    from notificacoes.utils import notificar
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        nome_militar = str(instance.militar) if hasattr(instance, 'militar') else 'Militar'
        titulo = f"Autorização pendente: {nome_militar}"
        try:
            from django.urls import reverse
            url = reverse('caixa_entrada:inbox') + '?box=autorizacoes'
        except Exception:
            url = '/comunicacoes/?box=autorizacoes'

        for chefe_efetivo in filter(None, [instance.chefe_atual, instance.chefe_destino]):
            user = User.objects.filter(profile__militar=chefe_efetivo).first()
            if user:
                notificar(user, titulo, tipo='autorizacao', url=url,
                          origem_id=instance.pk, origem_tipo='Secao_pessoal.SolicitacaoTrocaSetor')
    except Exception:
        pass


# ── PATD prazo expirado → notifica grupo Ouvidoria ───────────────────────────

@receiver(post_save, sender='Ouvidoria.PATD')
def notificar_patd_expirado(sender, instance, **kwargs):
    if getattr(instance, 'status', None) != 'prazo_expirado':
        return
    # Evita duplicar se já existe notificacao não lida para este PATD
    from notificacoes.models import Notificacao
    ja_existe = Notificacao.objects.filter(
        lida=False, origem_id=instance.pk, origem_tipo='Ouvidoria.PATD'
    ).exists()
    if ja_existe:
        return
    from notificacoes.utils import notificar
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        users = User.objects.filter(groups__name='Ouvidoria', is_active=True)
        nome = str(getattr(instance, 'militar', '') or '')
        notificar(
            users,
            titulo=f"PATD Nº {instance.numero_patd} — prazo expirado ({nome})",
            url=f"/Ouvidoria/patd/{instance.pk}/",
            tipo='patd',
            origem_id=instance.pk,
            origem_tipo='Ouvidoria.PATD',
        )
    except Exception:
        pass
