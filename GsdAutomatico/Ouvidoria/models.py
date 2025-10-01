from django.db import models
from django.utils import timezone
import os
from uuid import uuid4

def patd_anexo_path(instance, filename):
    patd_pk = instance.patd.pk
    upload_dir = f'patd_{patd_pk}/anexos/'
    # Gera um nome de ficheiro único para evitar sobreposições
    unique_filename = f"{uuid4().hex}_{filename}"
    return os.path.join(upload_dir, unique_filename)

def patd_signature_path(instance, filename):
    patd_pk = instance.pk if isinstance(instance, PATD) else instance.patd.pk
    upload_dir = f'patd_{patd_pk}/assinaturas/'
    unique_filename = f"{uuid4().hex}_{filename}"
    return os.path.join(upload_dir, unique_filename)

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
    senha_unica = models.CharField(max_length=128, blank=True, null=True, verbose_name="Senha Única")


    def __str__(self):
        return f"{self.posto} {self.nome_guerra}"

    class Meta:
        db_table = 'Efetivo_Militar'

class Anexo(models.Model):
    patd = models.ForeignKey('PATD', on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to=patd_anexo_path, verbose_name="Ficheiro")
    tipo = models.CharField(max_length=30, choices=[('defesa', 'Defesa'), ('reconsideracao', 'Reconsideração'), ('reconsideracao_oficial', 'Reconsideração Oficial')])
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anexo para PATD {self.patd.numero_patd} - {os.path.basename(self.arquivo.name)}"


class PATD(models.Model):
    
    STATUS_CHOICES = [
        # Fase Inicial
        ('definicao_oficial', 'Aguardando definição do Oficial'),
        ('aguardando_aprovacao_atribuicao', 'Aguardando aprovação de atribuição de oficial'),
        # Fase de Defesa
        ('ciencia_militar', 'Aguardando ciência do militar'),
        ('aguardando_justificativa', 'Aguardando Justificativa'),
        ('prazo_expirado', 'Prazo expirado'),
        # Fase de Apuração
        ('preclusao', 'Preclusão - Sem Defesa'),
        ('em_apuracao', 'Em Apuração'),
        ('apuracao_preclusao', 'Em Apuração (Preclusão)'), 
        ('aguardando_punicao', 'Aguardando Aplicação da Punição'),
        ('aguardando_punicao_alterar', 'Aguardando Punição (alterar)'),
        # Fase de Decisão
        ('analise_comandante', 'Em Análise pelo Comandante'),
        ('aguardando_assinatura_npd', 'Aguardando Assinatura NPD'),
        # Fase Final
        ('periodo_reconsideracao', 'Período de Reconsideração'),
        ('em_reconsideracao', 'Em Reconsideração'),
        ('aguardando_comandante_base', 'Aguardando Comandante da Base'),
        ('aguardando_preenchimento_npd_reconsideracao', 'Aguardando preenchimento NPD Reconsideração'),
        ('aguardando_publicacao', 'Aguardando publicação'),
        ('finalizado', 'Finalizado'),
    ]

    militar = models.ForeignKey(Militar, on_delete=models.CASCADE, related_name='patds', verbose_name="Militar Acusado")
    transgressao = models.TextField(verbose_name="Transgressão")
    ocorrencia_reescrita = models.TextField(blank=True, null=True, verbose_name="Ocorrência Reescrita (Formal)")
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
    data_publicacao_punicao = models.DateTimeField(null=True, blank=True, verbose_name="Data da Publicação da Punição")
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='definicao_oficial',
        verbose_name="Status"
    )
    status_anterior = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Status Anterior"
    )
    
    assinatura_oficial = models.FileField(upload_to=patd_signature_path, blank=True, null=True, verbose_name="Assinatura do Oficial")
    assinaturas_militar = models.JSONField(default=list, blank=True, null=True, verbose_name="Assinaturas do Militar Arrolado (Caminhos)")
    assinatura_testemunha1 = models.FileField(upload_to=patd_signature_path, blank=True, null=True, verbose_name="Assinatura da 1ª Testemunha")
    assinatura_testemunha2 = models.FileField(upload_to=patd_signature_path, blank=True, null=True, verbose_name="Assinatura da 2ª Testemunha")
    alegacao_defesa = models.TextField(blank=True, null=True, verbose_name="Alegação de Defesa")
    documento_texto = models.TextField(blank=True, null=True, verbose_name="Texto do Documento")
    itens_enquadrados = models.JSONField(null=True, blank=True, verbose_name="Itens Enquadrados na Análise")
    circunstancias = models.JSONField(null=True, blank=True, verbose_name="Atenuantes e Agravantes")
    punicao_sugerida = models.TextField(blank=True, null=True, verbose_name="Punição Sugerida pela IA")
    
    protocolo_comaer = models.CharField(max_length=255, blank=True, verbose_name="Protocolo COMAER")
    oficio_transgressao = models.CharField(max_length=255, blank=True, verbose_name="Ofício da Transgressão")
    data_oficio = models.DateField(null=True, blank=True, verbose_name="Data do Ofício")
    data_alegacao = models.DateTimeField(null=True, blank=True, verbose_name="Data da Alegação de Defesa")
    alegacao_defesa_resumo = models.TextField(blank=True, null=True, verbose_name="Resumo da Alegação de Defesa")
    comprovante = models.TextField(blank=True, null=True, verbose_name="Comprovante da Transgressão")
    dias_punicao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Dias de Punição")
    punicao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Punição")
    transgressao_afirmativa = models.TextField(blank=True, null=True, verbose_name="Transgressão Afirmativa")
    ocorrencia_reescrita = models.TextField(blank=True, null=True, verbose_name="Ocorrência Reescrita")
    natureza_transgressao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Natureza da Transgressão")
    comportamento = models.CharField(max_length=100, blank=True, null=True, default="Permanece no \"Bom comportamento\"", verbose_name="Comportamento")
    texto_reconsideracao = models.TextField(blank=True, null=True, verbose_name="Texto da Reconsideração")
    data_reconsideracao = models.DateTimeField(null=True, blank=True, verbose_name="Data da Reconsideração")
    texto_relatorio = models.TextField(blank=True, null=True, verbose_name="Texto do Relatório de Apuração")

    # NOVOS CAMPOS PARA ASSINATURAS ESPECÍFICAS
    assinatura_alegacao_defesa = models.FileField(upload_to=patd_signature_path, blank=True, null=True, verbose_name="Assinatura da Alegação de Defesa")
    assinatura_reconsideracao = models.FileField(upload_to=patd_signature_path, blank=True, null=True, verbose_name="Assinatura da Reconsideração")
    comentario_comandante = models.TextField(blank=True, null=True, verbose_name="Comentário do Comandante para Retorno")
    boletim_publicacao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Boletim de Publicação")
    justificado = models.BooleanField(default=False, verbose_name="Transgressão Justificada")
    anexo_reconsideracao_oficial = models.FileField(upload_to=patd_anexo_path, null=True, blank=True, verbose_name="Anexo da Reconsideração do Oficial")
    assinaturas_npd_reconsideracao = models.JSONField(default=list, blank=True, null=True, verbose_name="Assinaturas da NPD de Reconsideração (Base64)")


    def __str__(self):
        return f"PATD N° {self.numero_patd} - {self.militar.nome_guerra}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not is_new:
            orig = PATD.objects.get(pk=self.pk)
            # Se o oficial responsável mudou E um novo oficial foi definido
            if orig.oficial_responsavel != self.oficial_responsavel and self.oficial_responsavel:
                self.status = 'aguardando_aprovacao_atribuicao'
                # Não limpa mais a assinatura aqui para preservar a assinatura padrão que pode ser adicionada depois
        super(PATD, self).save(*args, **kwargs)


    class Meta:
        verbose_name = "PATD"
        verbose_name_plural = "PATDs"