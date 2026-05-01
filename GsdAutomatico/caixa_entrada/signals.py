"""
Signals da Caixa de Entrada.

Responsabilidades:
  1. Enviar e-mail quando uma Mensagem é criada (opcional, depende de EMAIL_HOST)
  2. Marcar a Notificacao (legacy) como lida quando a Mensagem relacionada é excluída
  3. Marcar Notificacao como lida quando a Mensagem é permanentemente excluída (M2M)
"""
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings


def _get_email(user):
    return user.email if user.email else None


# ── 1. E-mail ao receber nova mensagem ───────────────────────────────────────

@receiver(post_save, sender='caixa_entrada.Mensagem')
def notificar_destinatarios(sender, instance, created, **kwargs):
    """Dispara e-mail para destinatários quando uma mensagem é criada."""
    if not created or instance.eh_rascunho:
        return
    if not getattr(settings, 'EMAIL_HOST', None):
        return
    try:
        emails = [u.email for u in instance.destinatarios.all() if u.email]
        if emails:
            nome_remetente = instance.remetente.get_full_name() or instance.remetente.username
            send_mail(
                subject=f"[{instance.get_tipo_display()}] {instance.assunto}",
                message=(
                    f"Você recebeu uma nova {instance.get_tipo_display().lower()} "
                    f"de {nome_remetente}.\n\n"
                    f"Assunto: {instance.assunto}\n\n"
                    f"Acesse o sistema para ler a mensagem completa."
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'sistema@gsd.mil.br'),
                recipient_list=emails,
                fail_silently=True,
            )
    except Exception:
        pass


# ── 2. Cascade delete: excluir Mensagem → marca Notificacao como lida ────────

@receiver(post_delete, sender='caixa_entrada.Mensagem')
def limpar_notificacao_ao_deletar(sender, instance, **kwargs):
    """
    Quando uma Mensagem é deletada fisicamente do banco, marca a Notificacao
    visual correspondente (legacy) como lida para não deixar alertas "fantasma".

    Critério de correspondência: assunto da mensagem ≈ título da notificação,
    ou usa o remetente como referência.
    """
    try:
        from .models import Notificacao
        # Marca como lida qualquer notificação cujo título contenha o assunto da mensagem
        Notificacao.objects.filter(
            titulo__icontains=instance.assunto,
            lida=False,
        ).update(lida=True)
    except Exception:
        pass


# ── 3. Cascade delete: exclusão permanente → marca Notificacao como lida ─────

def limpar_notificacao_ao_excluir_permanentemente(sender, instance, action, pk_set, **kwargs):
    """
    Quando um usuário exclui permanentemente uma mensagem (adiciona ao M2M
    permanentemente_excluida_por), marca as notificações relacionadas como lidas
    para esse usuário, evitando badges desatualizados.
    """
    if action != 'post_add' or not pk_set:
        return
    try:
        from .models import Notificacao
        from django.contrib.auth import get_user_model
        User = get_user_model()
        for user_pk in pk_set:
            try:
                user = User.objects.get(pk=user_pk)
                Notificacao.objects.filter(
                    titulo__icontains=instance.assunto,
                    lida=False,
                ).update(lida=True)
            except User.DoesNotExist:
                pass
    except Exception:
        pass


# ── 4. E-mail ao atualizar status de chamado (legacy) ────────────────────────

@receiver(post_save, sender='caixa_entrada.Mensagem')
def notificar_mudanca_status_chamado(sender, instance, created, **kwargs):
    """Dispara e-mail quando status de um chamado (legado) muda."""
    if created or instance.tipo != 'chamado' or not instance.status_chamado:
        return
    if not getattr(settings, 'EMAIL_HOST', None):
        return
    email = _get_email(instance.remetente)
    if not email:
        return
    STATUS_LABELS = {
        'aberto': 'Aberto',
        'em_andamento': 'Em Andamento',
        'resolvido': 'Resolvido',
    }
    try:
        send_mail(
            subject=f"Chamado atualizado: {instance.assunto}",
            message=(
                f"Seu chamado foi atualizado.\n\n"
                f"Assunto: {instance.assunto}\n"
                f"Novo status: {STATUS_LABELS.get(instance.status_chamado, instance.status_chamado)}\n\n"
                f"Acesse o sistema para mais detalhes."
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'sistema@gsd.mil.br'),
            recipient_list=[email],
            fail_silently=True,
        )
    except Exception:
        pass
