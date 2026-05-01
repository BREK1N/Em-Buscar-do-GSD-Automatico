from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


STATUS_CHOICES = [
    ('aberto', 'Aberto'),
    ('em_atendimento', 'Em Atendimento'),
    ('aguardando_solicitante', 'Aguardando Solicitante'),
    ('resolvido', 'Resolvido'),
    ('fechado', 'Fechado'),
]

PRIORIDADE_CHOICES = [
    ('baixa', 'Baixa'),
    ('normal', 'Normal'),
    ('alta', 'Alta'),
    ('critica', 'Crítica'),
]


def _gerar_protocolo():
    now = timezone.now()
    prefixo = now.strftime('%Y%m')
    ultimo = (
        Chamado.objects
        .filter(protocolo__startswith=prefixo)
        .order_by('-protocolo')
        .values_list('protocolo', flat=True)
        .first()
    )
    if ultimo:
        seq = int(ultimo[-3:]) + 1
    else:
        seq = 1
    return f"{prefixo}{seq:03d}"


class Chamado(models.Model):
    protocolo    = models.CharField(max_length=9, unique=True, editable=False)
    titulo       = models.CharField(max_length=300)
    descricao    = models.TextField()
    solicitante  = models.ForeignKey(User, on_delete=models.PROTECT, related_name='chamados_abertos')
    atribuido_a  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='chamados_atribuidos')
    status       = models.CharField(max_length=30, choices=STATUS_CHOICES, default='aberto')
    prioridade   = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES, default='normal')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    fechado_em   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Chamado'
        verbose_name_plural = 'Chamados'

    def save(self, *args, **kwargs):
        if not self.protocolo:
            self.protocolo = _gerar_protocolo()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.protocolo}] {self.titulo}"

    @property
    def status_display_class(self):
        return {
            'aberto': 'status-aberto',
            'em_atendimento': 'status-atendimento',
            'aguardando_solicitante': 'status-aguardando',
            'resolvido': 'status-resolvido',
            'fechado': 'status-fechado',
        }.get(self.status, '')

    @property
    def prioridade_display_class(self):
        return {
            'baixa': 'prioridade-baixa',
            'normal': 'prioridade-normal',
            'alta': 'prioridade-alta',
            'critica': 'prioridade-critica',
        }.get(self.prioridade, '')


class MensagemChamado(models.Model):
    chamado    = models.ForeignKey(Chamado, on_delete=models.CASCADE, related_name='mensagens')
    autor      = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True)
    texto      = models.TextField()
    eh_sistema = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class AnexoChamado(models.Model):
    mensagem = models.ForeignKey(MensagemChamado, on_delete=models.CASCADE, related_name='anexos')
    arquivo  = models.FileField(upload_to='chamados/anexos/%Y/%m/')
    nome     = models.CharField(max_length=255)
    tamanho  = models.PositiveIntegerField()

    def __str__(self):
        return self.nome
