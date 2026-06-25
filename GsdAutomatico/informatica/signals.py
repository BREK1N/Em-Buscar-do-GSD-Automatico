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
    from auditoria.utils import registrar
    registrar(user, secao='login', permissao='—', acao='login', descricao=f'entrou no sistema (IP: {ip})')

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        logger.info(f"🚪 LOGOUT: Utilizador '{user.username}' saiu do sistema.")
        from auditoria.utils import registrar
        registrar(user, secao='login', permissao='—', acao='logout', descricao='saiu do sistema')

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    ip = request.META.get('REMOTE_ADDR')
    username = credentials.get('username', 'desconhecido')
    logger.warning(f"⚠️ LOGIN FALHOU: Tentativa falhada para utilizador '{username}'. (IP: {ip})")


# ==========================================
# AUDITORIA (Fase 3)
# ==========================================
from auditoria.registry import registrar_modelo
from auditoria.utils import resolver_label
from .models import Material, Cautela

_INFORMATICA_PERMISSAO_MAP = {
    'informatica-admin': 'Admin- Informática',
    'informatica-secao': 'Seção- Informática',
}

registrar_modelo(
    Material, secao='informatica', objeto_tipo='Material', label='o material',
    permissao_resolver=lambda user: resolver_label(user, _INFORMATICA_PERMISSAO_MAP),
    campo_id=lambda m: m.nome,
    campos_monitorados=['quantidade', 'quantidade_disponivel', 'funcionando', 'disponivel'],
)

registrar_modelo(
    Cautela, secao='informatica', objeto_tipo='Cautela', label='a cautela',
    permissao_resolver=lambda user: resolver_label(user, _INFORMATICA_PERMISSAO_MAP),
    campo_id=lambda c: c.pk,
    campos_monitorados=['ativa', 'nome_missao'],
)