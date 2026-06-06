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
