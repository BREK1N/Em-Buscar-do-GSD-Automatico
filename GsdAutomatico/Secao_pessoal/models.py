from django.db import models

class EfetivoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted=False)

class Efetivo(models.Model):
    posto = models.CharField(max_length=50, blank=True, verbose_name="Posto")
    quad = models.CharField(max_length=50, blank=True, verbose_name="QUAD")
    especializacao = models.CharField(max_length=100, blank=True, verbose_name="Especialização")
    saram = models.IntegerField(unique=True, null=True, blank=True, verbose_name="SARAM")
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo")
    nome_guerra = models.CharField(max_length=100,blank=True, verbose_name="Nome de Guerra")
    turma = models.CharField(max_length=100, blank=True, verbose_name="Turma")
    situacao = models.CharField(max_length=50, blank=True, verbose_name="Situação")
    observacao = models.TextField(blank=True, null=True, verbose_name="Observações / Motivo da Baixa")
    om = models.CharField(max_length=100, blank=True, verbose_name="OM")
    setor = models.CharField(max_length=100, blank=True, verbose_name="Setor")
    subsetor = models.CharField(max_length=100, blank=True, verbose_name="Subsetor")
    oficial = models.BooleanField(default=False, verbose_name="É Oficial?")
    assinatura = models.TextField(blank=True, null=True, verbose_name="Assinatura Padrão (Base64)")
    senha_unica = models.CharField(max_length=128, blank=True, null=True, verbose_name="Senha Única")
    inspsau_finalidade = models.CharField(max_length=5, blank=True, null=True, verbose_name="Finalidade INSPSAU")
    inspsau_validade = models.DateField(null=True, blank=True, verbose_name="Validade da INSPSAU")
    documento_inspsau = models.FileField(upload_to='inspsau_documentos/', null=True, blank=True, verbose_name="Documento da INSPSAU")
    inspsau_parecer = models.TextField(blank=True, null=True, verbose_name="Parecer da INSPSAU")
    deleted = models.BooleanField(default=False, verbose_name="Excluído")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Exclusão")

    objects = EfetivoManager()
    all_objects = models.Manager()

    def save(self, *args, **kwargs):
        postos_de_oficiais = [
            'ASP', 'ASPIRANTE',
            '2T', '2º TENENTE', '2º TEN',
            '1T', '1º TENENTE', '1º TEN',
            'CAP', 'CAPITÃO', 'CAPITAO','CP',
            'MAJ', 'MAJOR','MJ',
            'TC', 'TENENTE CORONEL', 'TEN CEL',
            'CEL', 'CORONEL','CL',
            'BRIG', 'BRIGADEIRO', 'BG'
        ]
        
        if self.posto and self.posto.upper() in postos_de_oficiais:
            self.oficial = True
        else:
            # Caso queira desmarcar automaticamente se não for oficial:
            self.oficial = False

        # --- INÍCIO DA PROTEÇÃO DE ASSINATURA ---
        if self.assinatura:
            # 1. Limpa quebras de linha ou espaços que o HTML ou JSON possam ter injetado
            self.assinatura = self.assinatura.strip().replace('\n', '').replace('\r', '').replace(' ', '+')
            
            # 2. Se a assinatura chegar apenas com o código puro (sem o prefixo), o Django adiciona!
            if not self.assinatura.startswith('data:image'):
                self.assinatura = f'data:image/jpeg;base64,{self.assinatura}'
        # --- FIM DA PROTEÇÃO DE ASSINATURA ---

        super(Efetivo, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.posto} {self.nome_guerra}"

    class Meta:
        db_table = 'Efetivo'

# Novas models para as opções
class Posto(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    class Meta:
        ordering = ['nome']
    def __str__(self):
        return self.nome

class Quad(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    class Meta:
        ordering = ['nome']
    def __str__(self):
        return self.nome

class Especializacao(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    class Meta:
        ordering = ['nome']
    def __str__(self):
        return self.nome

class OM(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    class Meta:
        ordering = ['nome']
    def __str__(self):
        return self.nome

class Setor(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    chefe = models.ForeignKey('Efetivo', on_delete=models.SET_NULL, null=True, blank=True, related_name='setores_chefiados', verbose_name="Chefe do Setor")
    
    class Meta:
        ordering = ['nome']
    def __str__(self):
        return self.nome

class Subsetor(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    class Meta:
        ordering = ['nome']
    def __str__(self):
        return self.nome

class SolicitacaoTrocaSetor(models.Model):
    militar = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='solicitacoes_troca', verbose_name="Militar")
    setor_atual = models.CharField(max_length=100, blank=True, verbose_name="Setor Atual")
    setor_destino = models.CharField(max_length=100, verbose_name="Setor Destino")
    chefe_atual = models.ForeignKey(Efetivo, on_delete=models.SET_NULL, null=True, blank=True, related_name='autorizacoes_saida', verbose_name="Chefe Atual")
    chefe_destino = models.ForeignKey(Efetivo, on_delete=models.SET_NULL, null=True, blank=True, related_name='autorizacoes_entrada', verbose_name="Chefe Destino")
    
    STATUS_CHOICES = [
        ('pendente_atual', 'Aguardando Chefe Atual'),
        ('pendente_destino', 'Aguardando Chefe Destino'),
        ('aprovado', 'Aprovado'),
        ('rejeitado', 'Rejeitado'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente_atual', verbose_name="Status")
    data_solicitacao = models.DateTimeField(auto_now_add=True, verbose_name="Data da Solicitação")

    class Meta:
        ordering = ['-data_solicitacao']

class HistoricoInspsau(models.Model):
    militar = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='historico_inspsau', verbose_name="Militar")
    data_registro = models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro")
    finalidade = models.CharField(max_length=10, blank=True, null=True, verbose_name="Finalidade")
    validade = models.DateField(null=True, blank=True, verbose_name="Validade")
    documento = models.FileField(upload_to='inspsau_historico/', null=True, blank=True, verbose_name="Documento")
    parecer = models.TextField(blank=True, null=True, verbose_name="Parecer")

    class Meta:
        ordering = ['-data_registro']
        verbose_name = "Histórico de INSPSAU"
        verbose_name_plural = "Históricos de INSPSAU"

    def __str__(self):
        return f"Histórico {self.finalidade} - {self.militar.nome_guerra}"