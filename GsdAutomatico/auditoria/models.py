from django.conf import settings
from django.db import models


class LogAuditoria(models.Model):
    """Registro humano-legível e pesquisável de uma ação de usuário em qualquer seção."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='logs_auditoria',
    )
    # Snapshots: sobrevivem mesmo que o usuário/militar seja depois renomeado ou excluído.
    username = models.CharField(max_length=150, verbose_name="Usuário")
    nome_guerra = models.CharField(max_length=100, blank=True, verbose_name="Nome de Guerra")
    permissao = models.CharField(max_length=100, blank=True, verbose_name="Permissão")

    secao = models.CharField(max_length=30, blank=True, verbose_name="Seção")
    acao = models.CharField(max_length=30, blank=True, verbose_name="Ação")
    objeto_tipo = models.CharField(max_length=60, blank=True, verbose_name="Tipo de Objeto")
    objeto_id = models.CharField(max_length=60, blank=True, verbose_name="ID/Número do Objeto")
    descricao = models.TextField(verbose_name="Descrição")

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['secao', 'criado_em']),
            models.Index(fields=['username']),
        ]

    @property
    def linha_formatada(self) -> str:
        nome = self.nome_guerra or self.username
        return f"Usuário: {self.username} Nome de guerra: {nome} (permissão: {self.permissao or '—'}) -> {self.descricao}"

    def __str__(self):
        return self.linha_formatada
