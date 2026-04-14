from django.db import models
from django.contrib.auth.models import Group
from Secao_pessoal.models import Efetivo


SECAO_CHOICES = [
    ('geral',       'Geral'),
    ('ouvidoria',   'Ouvidoria'),
    ('operacoes',   'Seção de Operações'),
    ('pessoal',     'Seção de Pessoal'),
    ('informatica', 'Informática'),
    ('outros',      'Outros'),
]


class GroupProfile(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='secao_profile')
    secao = models.CharField(max_length=30, choices=SECAO_CHOICES, default='geral', verbose_name='Seção')

    class Meta:
        verbose_name        = 'Perfil do Grupo'
        verbose_name_plural = 'Perfis dos Grupos'

    def __str__(self):
        return f"{self.group.name} [{self.get_secao_display()}]"


# Create your models here.

class GrupoMaterial(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome do Grupo")

    def __str__(self):
        return self.nome


class SubgrupoMaterial(models.Model):
    grupo = models.ForeignKey(GrupoMaterial, on_delete=models.CASCADE, related_name='subgrupos')
    nome = models.CharField(max_length=100)

    class Meta:
        unique_together = ('grupo', 'nome')

    def __str__(self):
        return f"{self.grupo.nome} - {self.nome}"

# --- NOVOS MODELOS PARA ARMÁRIOS E PRATELEIRAS ---
class Armario(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome/Número do Armário")
    localizacao = models.CharField(max_length=150, blank=True, null=True, verbose_name="Localização (Sala/Setor)")

    def __str__(self):
        return self.nome

class Prateleira(models.Model):
    armario = models.ForeignKey(Armario, on_delete=models.CASCADE, related_name='prateleiras')
    nome = models.CharField(max_length=50, verbose_name="Nome/Número da Prateleira")

    class Meta:
        unique_together = ('armario', 'nome')

    def __str__(self):
        return f"{self.armario.nome} - {self.nome}"
# ------------------------------------------------


class Material(models.Model):
    subgrupo = models.ForeignKey(SubgrupoMaterial, on_delete=models.PROTECT, related_name='materiais')
    nome = models.CharField(max_length=150)

    # --- NOVO CAMPO: SEÇÃO/SETOR ---
    secao = models.ForeignKey('Secao_pessoal.Setor', on_delete=models.SET_NULL, null=True, blank=True, related_name='materiais_informatica', verbose_name="Seção/Setor alocado")

    codigo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código Interno")

    # Serial é opcional (para permitir itens em quantidade como pendrives)
    serial = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Série")

    # Nova Relação com Prateleira (Opcional)
    prateleira = models.ForeignKey(Prateleira, on_delete=models.SET_NULL, null=True, blank=True, related_name='materiais', verbose_name="Localização na Prateleira")

    # Quantidades
    quantidade = models.IntegerField(default=1, verbose_name="Quantidade Total")
    quantidade_disponivel = models.IntegerField(default=1, verbose_name="Quantidade Disponível")

    funcionando = models.BooleanField(default=True, verbose_name="Em funcionamento?")
    motivo_defeito = models.TextField(blank=True, null=True, verbose_name="Motivo do Defeito")
    disponivel = models.BooleanField(default=True, verbose_name="Disponível para Cautela")
    atributos_extras = models.JSONField(default=dict, blank=True, null=True, verbose_name="Atributos Específicos")

    def __str__(self):
        sn_text = f" (S/N: {self.serial})" if self.serial else ""
        return f"{self.nome}{sn_text} - Qtd: {self.quantidade_disponivel}/{self.quantidade}"


class Cautela(models.Model):
    data_emissao = models.DateTimeField(auto_now_add=True)
    data_devolucao = models.DateTimeField(null=True, blank=True)

    sobreaviso = models.ForeignKey(Efetivo, on_delete=models.PROTECT, related_name='cautelas_liberadas')
    recebedor = models.ForeignKey(Efetivo, on_delete=models.PROTECT, related_name='cautelas_recebidas')

    assinatura_sobreaviso = models.TextField()
    assinatura_recebedor = models.TextField()

    ativa = models.BooleanField(default=True)
    nome_missao = models.CharField(max_length=200, blank=True, null=True, verbose_name="Missão/Formatura")
    telefone_contato = models.CharField(max_length=50, blank=True, null=True, verbose_name="Telefone de Contato")

    # Quem recebeu a devolução da Cautela inteira
    recebedor_devolucao = models.ForeignKey(Efetivo, on_delete=models.PROTECT, related_name='devolucoes_gerais', null=True, blank=True)
    assinatura_devolucao = models.TextField(null=True, blank=True)


class CautelaItem(models.Model):
    cautela = models.ForeignKey(Cautela, on_delete=models.CASCADE, related_name='itens')
    material = models.ForeignKey(Material, on_delete=models.PROTECT)

    quantidade = models.IntegerField(default=1)

    devolvido = models.BooleanField(default=False)
    data_devolucao = models.DateTimeField(null=True, blank=True)

    # Quem recebeu a devolução deste item individual
    recebedor_devolucao = models.ForeignKey(Efetivo, on_delete=models.PROTECT, related_name='devolucoes_individuais', null=True, blank=True)
    assinatura_devolucao = models.TextField(null=True, blank=True)
