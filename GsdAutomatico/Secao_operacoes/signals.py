from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group

@receiver(post_migrate)
def createSecaoOperacoesGroup(sender, **Kwargs):
    if sender.name == 'Secao_operacoes':
       Group.objects.get_or_create(name='seção de operação')

