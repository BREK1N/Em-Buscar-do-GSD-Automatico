from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group


@receiver(post_migrate)
def create_operacoes_groups(sender, **kwargs):
    if sender.name == 'Secao_operacoes':
        sop_group, created = Group.objects.get_or_create(name='SOP - Operações')
        if created:
            try:
                from informatica.models import GroupProfile
                GroupProfile.objects.get_or_create(
                    group=sop_group,
                    defaults={'secao': 'operacoes'}
                )
            except Exception:
                pass
        Group.objects.get_or_create(name='SOP- Escalas')


# ==========================================
# AUDITORIA (Fase 3)
# ==========================================
from auditoria.registry import registrar_modelo
from auditoria.utils import resolver_label
from .models import Missao, Escala

_OPERACOES_PERMISSAO_MAP = {
    'SOP - Operações': 'Sop- Missões',
    'SOP- Escalas': 'Sop- Escalas',
    'ESI-Missões': 'ESI- Missões',
}

registrar_modelo(
    Missao, secao='operacoes', objeto_tipo='Missão/OMIS', label='a omis',
    permissao_resolver=lambda user: resolver_label(user, _OPERACOES_PERMISSAO_MAP),
    campo_id=lambda m: m.numero,
    campos_monitorados=['nome_missao', 'data_missao', 'local', 'cmt_missao_id', 'motorista_id'],
)

registrar_modelo(
    Escala, secao='operacoes', objeto_tipo='Escala de Serviço', label='a escala',
    permissao_resolver=lambda user: resolver_label(user, _OPERACOES_PERMISSAO_MAP),
    campo_id=lambda e: e.nome,
    campos_monitorados=['tipo', 'duracao_horas', 'ativo'],
)
