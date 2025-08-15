from django.db import models
from django.utils import timezone

class Militar(models.Model):
    """
    Tabela para armazenar o cadastro de todos os militares.
    """
    posto = models.CharField(max_length=50, blank=True, verbose_name="Posto")
    quad = models.CharField(max_length=50, blank=True, verbose_name="QUAD")
    especializacao = models.CharField(max_length=100, blank=True, verbose_name="Especialização")
    saram = models.IntegerField(unique=True, null=True, blank=True, verbose_name="SARAM")
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo")
    nome_guerra = models.CharField(max_length=100, verbose_name="Nome de Guerra")
    turma = models.CharField(max_length=100, blank=True, verbose_name="Turma")
    situacao = models.CharField(max_length=50, blank=True, verbose_name="Situação")
    om = models.CharField(max_length=100, blank=True, verbose_name="OM")
    setor = models.CharField(max_length=100, blank=True, verbose_name="Setor")
    subsetor = models.CharField(max_length=100, blank=True, verbose_name="Subsetor")
    oficial = models.BooleanField(default=False, verbose_name="É Oficial?")
    assinatura = models.TextField(blank=True, null=True, verbose_name="Assinatura Padrão (Base64)")


    def __str__(self):
        return f"{self.posto} {self.nome_guerra}"

    class Meta:
        verbose_name = "Militar"
        verbose_name_plural = "Militares"


class PATD(models.Model):
    """
    Tabela para registar os Processos Administrativos Disciplinares (PATD).
    """
    
    STATUS_CHOICES = [
        ('definicao_oficial', 'Aguardando definição do Oficial'),
        ('ciencia_militar', 'Aguardando ciência do militar'),
        ('aguardando_justificativa', 'Aguardando Justificativa (5 dias)'),
        ('prazo_expirado', 'Prazo expirado'),
        ('em_apuracao', 'Aguardando Apuração'),
        ('aguardando_punicao', 'Aguardando Aplicação da Punição'),
        ('aguardando_assinatura', 'Aguardando Assinatura NPD'),
    ]

    militar = models.ForeignKey(Militar, on_delete=models.CASCADE, related_name='patds', verbose_name="Militar Acusado")
    transgressao = models.TextField(verbose_name="Transgressão")
    numero_patd = models.IntegerField(unique=True, verbose_name="N° PATD")
    oficial_responsavel = models.ForeignKey(
        Militar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patds_responsaveis',
        limit_choices_to={'oficial': True}, 
        verbose_name="Oficial Responsável"
    )
    # CAMPOS DE TESTEMUNHA ADICIONADOS
    testemunha1 = models.ForeignKey(
        Militar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patds_testemunha1',
        verbose_name="1ª Testemunha"
    )
    testemunha2 = models.ForeignKey(
        Militar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patds_testemunha2',
        verbose_name="2ª Testemunha"
    )
    data_ocorrencia = models.DateField(null=True, blank=True, verbose_name="Data da Ocorrência")
    data_inicio = models.DateTimeField(default=timezone.now, verbose_name="Data de Início")
    data_termino = models.DateTimeField(null=True, blank=True, verbose_name="Data de Término")
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='definicao_oficial',
        verbose_name="Status"
    )
    assinatura_oficial = models.TextField(blank=True, null=True, verbose_name="Assinatura do Oficial (Base64)")

    def __str__(self):
        return f"PATD N° {self.numero_patd} - {self.militar.nome_guerra}"

    def save(self, *args, **kwargs):
        if self.pk is not None: 
            orig = PATD.objects.get(pk=self.pk)
            if self.oficial_responsavel and orig.status == 'definicao_oficial':
                self.status = 'ciencia_militar'
            
            if orig.oficial_responsavel != self.oficial_responsavel:
                self.assinatura_oficial = None
        
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "PATD"
        verbose_name_plural = "PATDs"
