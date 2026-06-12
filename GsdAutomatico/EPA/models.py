from django.db import models
from Secao_operacoes.models import Missao
from Secao_pessoal.models import Efetivo


class EscalaMissaoEPA(models.Model):
    """Escalação de militares do EPA para uma missão da S.Op."""
    missao = models.OneToOneField(
        Missao, on_delete=models.CASCADE,
        related_name='escala_epa',
        verbose_name="Missão"
    )
    militares = models.ManyToManyField(
        Efetivo, blank=True,
        related_name='escalas_epa',
        verbose_name="Militares Escalados"
    )
    identificacao_pelotao = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Identificação do Pelotão/Seção"
    )
    grupos_json = models.TextField(blank=True, default='', verbose_name="Grupos por Função (JSON)")
    observacoes = models.TextField(blank=True, verbose_name="Observações")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Escala EPA"
        verbose_name_plural = "Escalas EPA"
        ordering = ['-missao__data_missao']

    def __str__(self):
        return f"Escala EPA — {self.missao}"
