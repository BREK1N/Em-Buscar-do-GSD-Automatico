from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

TIPO_CHOICES = [
    ('mensagem',    'Mensagem'),
    ('autorizacao', 'Autorização'),
    ('sistema',     'Sistema'),
    ('patd',        'PATD'),
]


class Notificacao(models.Model):
    usuario     = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='notificacoes_unificadas')
    tipo        = models.CharField(max_length=20, choices=TIPO_CHOICES, default='sistema')
    titulo      = models.CharField(max_length=255)
    corpo       = models.TextField(blank=True, default='')
    url         = models.CharField(max_length=500, blank=True, default='')
    lida        = models.BooleanField(default=False, db_index=True)
    criado_em   = models.DateTimeField(auto_now_add=True, db_index=True)
    origem_id   = models.PositiveIntegerField(null=True, blank=True)
    origem_tipo = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['usuario', 'lida']),
        ]
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'

    def __str__(self):
        return f"[{self.tipo}] {self.titulo} → {self.usuario}"
