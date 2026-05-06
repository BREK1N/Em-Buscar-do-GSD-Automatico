from django.db import models
from Secao_pessoal.models import Efetivo
from datetime import date

class RegistroChamada(models.Model):
    STATUS_CHOICES = [
        ('P', 'Presente'),
        ('F', 'Falta'),
        ('M', 'Missão'),
        ('ESV', 'Entrando de Serviço'),
        ('SSV', 'Saindo de Serviço'),
        ('DPC', 'Dispensado pelo Chefe'),
    ]

    militar = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='registros_chamada', verbose_name='Militar')
    data = models.DateField(default=date.today, verbose_name='Data da Chamada')
    status = models.CharField(max_length=5, choices=STATUS_CHOICES, null=True, blank=True, verbose_name='Status')
    observacao = models.CharField(max_length=255, null=True, blank=True, verbose_name='Observação')

    class Meta:
        app_label = 'chamada'
        verbose_name = 'Registro de Chamada'
        verbose_name_plural = 'Registros de Chamada'
        ordering = ['-data', 'militar__nome_guerra']

    def __str__(self):
        return f"{self.militar.nome_guerra} - {self.data} - {self.get_status_display()}"