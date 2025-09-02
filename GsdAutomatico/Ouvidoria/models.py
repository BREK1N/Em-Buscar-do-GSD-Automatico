from django.db import models
from django.utils import timezone

class Configuracao(models.Model):
    comandante_gsd = models.ForeignKey(
        'Militar',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        limit_choices_to={'oficial': True},
        verbose_name="Comandante do GSD Padrão"
    )
    prazo_defesa_dias = models.IntegerField(
        default=5,
        verbose_name="Prazo para Defesa (dias úteis)"
    )
    prazo_defesa_minutos = models.IntegerField(
        default=0,
        verbose_name="Prazo para Defesa (minutos)"
    )

    def save(self, *args, **kwargs):
        # Garante que só existe uma instância deste modelo
        self.pk = 1
        super(Configuracao, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        # Método de conveniência para obter a instância de configuração
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Configurações Gerais"

    class Meta:
        verbose_name = "Configuração Geral"
        verbose_name_plural = "Configurações Gerais"


class Militar(models.Model):
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
        db_table = 'Efetivo_Militar'


class PATD(models.Model):
    
    STATUS_CHOICES = [
        ('definicao_oficial', 'Aguardando definição do Oficial'),
        ('ciencia_militar', 'Aguardando ciência do militar'),
        ('aguardando_justificativa', 'Aguardando Justificativa'),
        ('prazo_expirado', 'Prazo expirado'),
        ('preclusao', 'Preclusão - Sem Defesa'),
        ('em_apuracao', 'Em Apuração'),
        ('apuracao_preclusao', 'Em Apuração (Preclusão)'), 
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
    data_ciencia = models.DateTimeField(null=True, blank=True, verbose_name="Data da Ciência")
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='definicao_oficial',
        verbose_name="Status"
    )
    assinatura_oficial = models.TextField(blank=True, null=True, verbose_name="Assinatura do Oficial (Base64)")
    assinatura_militar_ciencia = models.TextField(blank=True, null=True, verbose_name="Assinatura de Ciência do Militar (Base64)")
    assinatura_testemunha1 = models.TextField(blank=True, null=True, verbose_name="Assinatura da 1ª Testemunha (Base64)")
    assinatura_testemunha2 = models.TextField(blank=True, null=True, verbose_name="Assinatura da 2ª Testemunha (Base64)")
    alegacao_defesa = models.TextField(blank=True, null=True, verbose_name="Alegação de Defesa")
    documento_texto = models.TextField(blank=True, null=True, verbose_name="Texto do Documento")
    itens_enquadrados = models.JSONField(null=True, blank=True, verbose_name="Itens Enquadrados na Análise")
    circunstancias = models.JSONField(null=True, blank=True, verbose_name="Atenuantes e Agravantes")
    punicao_sugerida = models.TextField(blank=True, null=True, verbose_name="Punição Sugerida pela IA")
    
    # NOVOS CAMPOS ADICIONADOS
    protocolo_comaer = models.CharField(max_length=255, blank=True, verbose_name="Protocolo COMAER")
    oficio_transgrecao = models.CharField(max_length=255, blank=True, verbose_name="Ofício Transgressão")
    data_oficio = models.DateField(null=True, blank=True, verbose_name="Data do Ofício")
    data_alegacao = models.DateTimeField(null=True, blank=True, verbose_name="Data da Alegação de Defesa")
    alegacao_defesa_resumo = models.TextField(blank=True, null=True, verbose_name="Resumo da Alegação de Defesa")
    comprovante = models.TextField(blank=True, null=True, verbose_name="Comprovante da Transgressão")
    dias_punicao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Dias de Punição")
    punicao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Punição")
    transgressao_afirmativa = models.TextField(blank=True, null=True, verbose_name="Transgressão Afirmativa")
    natureza_transgressao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Natureza da Transgressão")
    comportamento = models.CharField(max_length=100, blank=True, null=True, default="Permanece no \"Bom comportamento\"", verbose_name="Comportamento")


    def __str__(self):
        return f"PATD N° {self.numero_patd} - {self.militar.nome_guerra}"

    def save(self, *args, **kwargs):
        
        is_new = self._state.adding
        orig = None
        if not is_new:
            # Pega o estado original do objeto do banco de dados
            orig = PATD.objects.get(pk=self.pk)

        # --- LÓGICA DE ATUALIZAÇÃO DE STATUS ---
        # 1. Se um oficial for REMOVIDO (deixou de ter um para não ter nenhum)
        if not self.oficial_responsavel:
            self.status = 'definicao_oficial'
        # 2. Se um oficial for ADICIONADO pela primeira vez (ou se o status era 'aguardando')
        elif self.oficial_responsavel and (is_new or (orig and orig.status == 'definicao_oficial')):
            self.status = 'ciencia_militar'
        
        # --- LÓGICA DE ATUALIZAÇÃO DE ASSINATURA ---
        # Apenas executa se não for um objeto novo e se o oficial tiver mudado
        if not is_new and orig and orig.oficial_responsavel != self.oficial_responsavel:
            # Se um novo oficial foi atribuído e ele tem uma assinatura padrão
            if self.oficial_responsavel and self.oficial_responsavel.assinatura:
                self.assinatura_oficial = self.oficial_responsavel.assinatura
            # Se o oficial foi removido ou o novo oficial não tem assinatura
            else:
                self.assinatura_oficial = None

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "PATD"
        verbose_name_plural = "PATDs"