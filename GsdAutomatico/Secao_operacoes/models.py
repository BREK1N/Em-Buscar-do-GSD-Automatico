from django.db import models
from Secao_pessoal.models import Efetivo

class Escala(models.Model):
    nome = models.CharField(max_length=100, verbose_name="Nome da Escala")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    militares = models.ManyToManyField(Efetivo, related_name='escalas_vinculadas', blank=True, verbose_name="Militares Vinculados")

    def __str__(self):
        return self.nome

class TurnoEscala(models.Model):
    escala = models.ForeignKey(Escala, on_delete=models.CASCADE, related_name='turnos')
    militar = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='turnos_escalados')
    data = models.DateField(verbose_name="Data do Serviço")
    observacao = models.TextField(blank=True, null=True, verbose_name="Observação")

    def __str__(self):
        return f"{self.militar.nome_guerra} - {self.escala.nome} ({self.data.strftime('%d/%m/%Y')})"
    
    class Meta:
        ordering = ['data']
        verbose_name = "Turno de Escala"
        verbose_name_plural = "Turnos de Escala"
