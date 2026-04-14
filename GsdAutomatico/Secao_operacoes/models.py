from django.db import models
from Secao_pessoal.models import Efetivo


class Escala(models.Model):
    TIPO_CHOICES = [
        ('24h', '24 Horas'),
        ('turno', 'Turno (6h)'),
        ('permanencia', 'Permanência'),
        ('sbv', 'SBV — Sobre Aviso'),
    ]

    nome = models.CharField(max_length=100, verbose_name="Nome da Escala")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='24h',
        verbose_name="Tipo de Serviço"
    )
    duracao_horas = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Duração (horas)",
        help_text="Apenas para tipo Permanência"
    )
    militares = models.ManyToManyField(
        Efetivo,
        related_name='escalas_vinculadas',
        blank=True,
        verbose_name="Militares Vinculados"
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativa")

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Escala"
        verbose_name_plural = "Escalas"


class PostoEscala(models.Model):
    escala = models.ForeignKey(Escala, on_delete=models.CASCADE, related_name='postos', verbose_name="Escala")
    nome = models.CharField(max_length=100, verbose_name="Nome do Posto")
    horario = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Horário",
        help_text="Ex: 0h às 6h, 6h às 12h, Manhã, Tarde..."
    )

    def __str__(self):
        return f"{self.escala.nome} — {self.nome}"

    class Meta:
        ordering = ['nome']
        verbose_name = "Posto de Escala"
        verbose_name_plural = "Postos de Escala"


class TurnoEscala(models.Model):
    escala = models.ForeignKey(Escala, on_delete=models.CASCADE, related_name='turnos')
    militar = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='turnos_escalados')
    posto = models.ForeignKey(PostoEscala, on_delete=models.SET_NULL, null=True, blank=True, related_name='turnos', verbose_name="Posto")
    data = models.DateField(verbose_name="Data do Serviço")
    observacao = models.TextField(blank=True, null=True, verbose_name="Observação")

    def __str__(self):
        posto_str = f" [{self.posto.nome}]" if self.posto else ""
        return f"{self.militar.nome_guerra}{posto_str} - {self.escala.nome} ({self.data.strftime('%d/%m/%Y')})"

    class Meta:
        ordering = ['data']
        verbose_name = "Turno de Escala"
        verbose_name_plural = "Turnos de Escala"
