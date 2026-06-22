from django.db import models
from django.utils import timezone

DIAS_RETENCAO_LIXEIRA_EFETIVO = 30

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
    deleted = models.BooleanField(default=False, db_index=True, verbose_name="Excluído")
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Data de Exclusão")

    # Campos de Prestação de Serviço
    unidade_prestacao_servico = models.CharField(max_length=100, blank=True, null=True, verbose_name="Unidade de Prestação de Serviço")
    data_inicio_prestacao = models.DateField(null=True, blank=True, verbose_name="Data de Início da Apresentação")
    data_vencimento_prestacao = models.DateField(null=True, blank=True, verbose_name="Data de Vencimento da Prestação")
    portaria_prestacao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Portaria da Prestação de Serviço")
    data_portaria_prestacao = models.DateField(null=True, blank=True, verbose_name="Data da Portaria")
    boletim_prestacao = models.CharField(max_length=100, blank=True, null=True, verbose_name="Boletim de Prestação de Serviço")
    data_boletim_prestacao = models.DateField(null=True, blank=True, verbose_name="Data do Boletim")

    # Campos de Desligamento
    data_desligamento = models.DateField(null=True, blank=True, verbose_name="Data do Desligamento")
    motivo_desligamento = models.TextField(blank=True, null=True, verbose_name="Motivo do Desligamento")
    documento_desligamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Documento de Publicação")
    funcao_desligamento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Função (conforme publicado)")

    # Informações Pessoais Estendidas
    identidade_civil = models.CharField(max_length=30, blank=True, null=True, verbose_name="Identidade Civil")
    identidade_aer = models.CharField(max_length=30, blank=True, null=True, verbose_name="Identidade Aeronáutica")
    cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name="CPF")
    data_nascimento = models.DateField(null=True, blank=True, verbose_name="Data de Nascimento")
    nome_mae = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nome da Mãe")
    nome_pai = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nome do Pai")
    conjuge = models.CharField(max_length=255, blank=True, null=True, verbose_name="Cônjuge")
    ano_praca = models.CharField(max_length=4, blank=True, null=True, verbose_name="Ano de Praça")
    contato_1 = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nº Contato 1")
    contato_2 = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nº Contato 2")
    contato_3 = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nº Contato 3")
    contato_4 = models.CharField(max_length=20, blank=True, null=True, verbose_name="Nº Contato 4")
    email_1 = models.EmailField(max_length=254, blank=True, null=True, verbose_name="E-mail 1")
    email_2 = models.EmailField(max_length=254, blank=True, null=True, verbose_name="E-mail 2")
    email_3 = models.EmailField(max_length=254, blank=True, null=True, verbose_name="E-mail 3")
    cep = models.CharField(max_length=9, blank=True, null=True, verbose_name="CEP")
    endereco = models.CharField(max_length=255, blank=True, null=True, verbose_name="Endereço")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")

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

    @property
    def dias_para_exclusao(self):
        if self.deleted and self.deleted_at:
            delta = timezone.now() - self.deleted_at
            return max(DIAS_RETENCAO_LIXEIRA_EFETIVO - delta.days, 0)
        return None

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

class LotacaoPessoal(models.Model):
    posto = models.CharField(max_length=50, blank=True, verbose_name="Posto/Grad")
    quad = models.CharField(max_length=50, blank=True, verbose_name="Quadro")
    especializacao = models.CharField(max_length=100, blank=True, verbose_name="Especialidade")
    om = models.CharField(max_length=100, blank=True, verbose_name="OM")
    vagas_previstas = models.PositiveIntegerField(default=0, verbose_name="TLP (Vagas Previstas)")

    class Meta:
        ordering = ['posto', 'quad', 'especializacao']
        verbose_name = "Lotação de Pessoal (TLP)"
        verbose_name_plural = "Lotações de Pessoal (TLP)"
        constraints = [
            models.UniqueConstraint(fields=['posto', 'quad', 'especializacao', 'om'], name='uniq_lotacao_combo')
        ]

    def __str__(self):
        return f"{self.posto}/{self.quad}/{self.especializacao} ({self.om}) - {self.vagas_previstas} vagas"

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


class MovimentacaoEfetivo(models.Model):
    militar = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='movimentacoes', verbose_name="Militar")
    data_movimentacao = models.DateField(verbose_name="Data da Movimentação")
    om_destino = models.CharField(max_length=100, blank=True, verbose_name="OM de Destino")
    sigad_movimentacao = models.CharField(max_length=100, blank=True, verbose_name="SIGAD")
    boletim_movimentacao = models.CharField(max_length=100, blank=True, verbose_name="Boletim (BCA/Bol. INT)")
    observacao = models.TextField(blank=True, null=True, verbose_name="Observação")
    data_registro = models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro")

    class Meta:
        ordering = ['-data_movimentacao']
        verbose_name = "Movimentação de Efetivo"
        verbose_name_plural = "Movimentações de Efetivo"

    def __str__(self):
        return f"Movimentação {self.militar.nome_guerra} -> {self.om_destino}"


class RegistroChamada(models.Model):
    data = models.DateField(auto_now_add=True, verbose_name="Data da Chamada")
    militar = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name="chamadas", verbose_name="Militar")
    presente = models.BooleanField(default=False, verbose_name="Presente")
    observacao = models.CharField(max_length=255, blank=True, null=True, verbose_name="Observação")
    
    class Meta:
        verbose_name = "Registro de Chamada"
        verbose_name_plural = "Registros de Chamada"
        ordering = ['-data', 'militar__nome_guerra']

    def __str__(self):
        return f"Chamada {self.data.strftime('%d/%m/%Y')} - {self.militar.nome_guerra}"