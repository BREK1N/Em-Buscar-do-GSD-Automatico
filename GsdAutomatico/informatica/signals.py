from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_migrate
from django.dispatch import receiver
import logging

logger = logging.getLogger('django')


@receiver(post_migrate)
def create_informatica_groups(sender, **kwargs):
    if sender.name == 'informatica':
        from django.contrib.auth.models import Group
        Group.objects.get_or_create(name='informatica-admin')
        Group.objects.get_or_create(name='informatica-secao')


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    logger.info(f"✅ LOGIN SUCESSO: Utilizador '{user.username}' entrou no sistema. (IP: {ip})")

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        logger.info(f"🚪 LOGOUT: Utilizador '{user.username}' saiu do sistema.")

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    username = credentials.get('username', 'desconhecido')
    logger.warning(f"⚠️ LOGIN FALHOU: Tentativa falhada para utilizador '{username}'. (IP: {ip})")