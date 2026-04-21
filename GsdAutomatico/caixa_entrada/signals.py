from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings


def _get_email(user):
    return user.email if user.email else None


@receiver(post_save, sender='caixa_entrada.Mensagem')
def notificar_destinatarios(sender, instance, created, **kwargs):
    if not created or instance.eh_rascunho:
        return
    # E-mail disparado apenas se houver configuração de e-mail no settings
    if not getattr(settings, 'EMAIL_HOST', None):
        return
    try:
        emails = [
            u.email for u in instance.destinatarios.all() if u.email
        ]
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


@receiver(post_save, sender='caixa_entrada.Mensagem')
def notificar_mudanca_status_chamado(sender, instance, created, **kwargs):
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
