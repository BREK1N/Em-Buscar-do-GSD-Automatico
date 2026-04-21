from django.db import models
from django.contrib.auth import get_user_model
from Secao_pessoal.models import Efetivo

User = get_user_model()


# ─── Sistema legado de notificações (mantido para integrações existentes) ──────

class NotificacaoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted=False)


class Notificacao(models.Model):
    remetente = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='notificacoes_enviadas')
    destinatario = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='notificacoes_recebidas')
    titulo = models.CharField(max_length=200, verbose_name="Assunto")
    mensagem = models.TextField(verbose_name="Mensagem")
    lida = models.BooleanField(default=False)
    arquivada = models.BooleanField(default=False, verbose_name="Arquivada")
    anexo = models.FileField(upload_to='notificacoes_anexos/', null=True, blank=True, verbose_name="Anexo")
    deleted = models.BooleanField(default=False, verbose_name="Excluído (Lixeira)")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Exclusão")
    data_criacao = models.DateTimeField(auto_now_add=True)

    objects = NotificacaoManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'Secao_pessoal_notificacao'
        ordering = ['-data_criacao']
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self):
        return f"{self.titulo} - Para: {self.destinatario}"


# ─── Nova caixa de entrada ─────────────────────────────────────────────────────

class Mensagem(models.Model):
    TIPO_CHOICES = [
        ('mensagem', 'Mensagem'),
        ('chamado', 'Chamado'),
    ]
    STATUS_CHAMADO_CHOICES = [
        ('aberto', 'Aberto'),
        ('em_andamento', 'Em Andamento'),
        ('resolvido', 'Resolvido'),
    ]

    remetente = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='mensagens_enviadas', verbose_name="Remetente"
    )
    destinatarios = models.ManyToManyField(
        User, related_name='mensagens_recebidas',
        verbose_name="Destinatários"
    )
    assunto = models.CharField(max_length=255, verbose_name="Assunto")
    corpo = models.TextField(verbose_name="Mensagem")
    tipo = models.CharField(
        max_length=10, choices=TIPO_CHOICES,
        default='mensagem', verbose_name="Tipo"
    )
    status_chamado = models.CharField(
        max_length=15, choices=STATUS_CHAMADO_CHOICES,
        null=True, blank=True, verbose_name="Status do Chamado"
    )
    data_envio = models.DateTimeField(auto_now_add=True, verbose_name="Data de Envio")
    lida_por = models.ManyToManyField(
        User, through='LeituraMensagem',
        related_name='mensagens_lidas', blank=True
    )
    cc = models.ManyToManyField(
        User, related_name='mensagens_cc',
        blank=True, verbose_name="CC (com cópia)"
    )
    excluida_por = models.ManyToManyField(
        User, related_name='mensagens_excluidas',
        blank=True, verbose_name="Excluída por"
    )
    eh_rascunho = models.BooleanField(default=False, verbose_name="Rascunho")
    mensagem_original = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='respostas',
        verbose_name="Resposta a"
    )

    class Meta:
        ordering = ['-data_envio']
        verbose_name = "Mensagem"
        verbose_name_plural = "Mensagens"
        permissions = [('gerenciar_chamados', 'Pode gerenciar chamados')]

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.assunto}"

    def foi_lida_por(self, user):
        return self.lida_por.filter(pk=user.pk).exists()

    def foi_excluida_por(self, user):
        return self.excluida_por.filter(pk=user.pk).exists()

    def leituras_info(self):
        return self.leituraMensagem_set.select_related('usuario').all()


class LeituraMensagem(models.Model):
    mensagem = models.ForeignKey(Mensagem, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    data_leitura = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('mensagem', 'usuario')
        verbose_name = "Leitura"
        verbose_name_plural = "Leituras"

    def __str__(self):
        return f"{self.usuario} leu '{self.mensagem.assunto}'"


class Anexo(models.Model):
    mensagem = models.ForeignKey(
        Mensagem, on_delete=models.CASCADE,
        related_name='anexos', verbose_name="Mensagem"
    )
    arquivo = models.FileField(
        upload_to='inbox/anexos/%Y/%m/',
        verbose_name="Arquivo"
    )
    nome_original = models.CharField(max_length=255, verbose_name="Nome original")
    tamanho = models.IntegerField(verbose_name="Tamanho (bytes)")
    tipo_mime = models.CharField(max_length=100, verbose_name="Tipo MIME")

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"

    def __str__(self):
        return self.nome_original

    def tamanho_legivel(self):
        if self.tamanho < 1024:
            return f"{self.tamanho} B"
        elif self.tamanho < 1024 ** 2:
            return f"{self.tamanho / 1024:.1f} KB"
        return f"{self.tamanho / 1024 ** 2:.1f} MB"
