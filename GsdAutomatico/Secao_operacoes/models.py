from django.db import models
from django.contrib.auth import get_user_model
from Secao_pessoal.models import Efetivo

User = get_user_model()


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


# ── Configuração da Seção de Operações ──────────────────────────────────────

class ConfiguracaoOperacoes(models.Model):
    diretriz_padrao_1 = models.TextField(
        blank=True,
        default="Manter o Oficial de serviço do GSD GL / Sargento de Dia informado do início e do término da missão.",
        verbose_name="Diretriz padrão 1"
    )
    diretriz_padrao_2 = models.TextField(
        blank=True,
        default="O relatório da missão deverá ser confeccionado pelo Cmt da mesma e entregue, em até 24h, ao Sgt de dia ao GSD GL. Deverá conter além das informações inerentes a missão, o horário do término da mesma, as alterações de cumprimento do quadro de horários, transporte, alimentação, faltas, sugestões, ocorrências, bem como as providências adotadas.",
        verbose_name="Diretriz padrão 2"
    )
    observacoes_armamento_padrao = models.CharField(
        max_length=300, blank=True, default='',
        verbose_name="Armamento conforme RIMB (padrão)"
    )
    diretrizes_padrao_json = models.TextField(blank=True, default='', verbose_name="Diretrizes padrão (JSON)")

    class Meta:
        verbose_name = "Configuração de Operações"
        verbose_name_plural = "Configurações de Operações"

    def __str__(self):
        return "Configuração da Seção de Operações"

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ── Missão (OMIS) ────────────────────────────────────────────────────────────

class Missao(models.Model):
    numero = models.PositiveIntegerField(verbose_name="Número da OMIS")
    nome_missao = models.CharField(max_length=200, verbose_name="Nome/Tipo da Missão")
    local = models.CharField(max_length=200, verbose_name="Local")
    objetivo = models.TextField(verbose_name="Objetivo da Missão")
    endereco = models.CharField(max_length=300, blank=True, verbose_name="Endereço")
    acionador = models.CharField(max_length=200, blank=True, verbose_name="Acionador (Ofício Nº)")

    diretriz_1 = models.TextField(blank=True, verbose_name="Diretriz 1")
    diretriz_2 = models.TextField(blank=True, verbose_name="Diretriz 2")
    diretrizes_json = models.TextField(blank=True, default='', verbose_name="Diretrizes (JSON)")

    data_emissao = models.DateField(verbose_name="Data de Emissão")
    data_missao = models.DateField(verbose_name="Data da Missão")

    horario_chamada = models.TimeField(null=True, blank=True, verbose_name="Chamada")
    horario_armamento = models.TimeField(null=True, blank=True, verbose_name="Armamento")
    horario_alimentacao = models.TimeField(null=True, blank=True, verbose_name="Alimentação")
    horario_sala_sgt = models.TimeField(null=True, blank=True, verbose_name="Horário Sala Sgt de Dia")
    horario_saida = models.TimeField(null=True, blank=True, verbose_name="Saída do GSD GL")
    horario_pronto = models.TimeField(null=True, blank=True, verbose_name="Pronto no Objetivo")

    transporte = models.CharField(max_length=200, blank=True, verbose_name="Transporte")
    radio_nome = models.CharField(max_length=100, blank=True, verbose_name="Nome/Modelo do Rádio")
    radio_qtd = models.PositiveSmallIntegerField(default=0, verbose_name="Qtd. Rádios")
    radio_canal = models.CharField(max_length=50, blank=True, verbose_name="Canal Rádio")

    uniforme = models.CharField(max_length=100, blank=True, verbose_name="Uniforme")
    observacoes_armamento = models.TextField(blank=True, verbose_name="Observações sobre Armamento (RIMB)")

    # Efetivo
    efetivo_of = models.PositiveSmallIntegerField(default=0, verbose_name="OF")
    efetivo_so_sgt = models.PositiveSmallIntegerField(default=0, verbose_name="SO/SGT")
    efetivo_cb = models.PositiveSmallIntegerField(default=0, verbose_name="CB")
    efetivo_s1 = models.PositiveSmallIntegerField(default=0, verbose_name="S1")
    efetivo_s2 = models.PositiveSmallIntegerField(default=0, verbose_name="S2")
    efetivo_rec = models.PositiveSmallIntegerField(default=0, verbose_name="REC")

    cmt_a_cargo = models.CharField(max_length=200, blank=True, verbose_name="CMT a cargo de")
    mot_a_cargo = models.CharField(max_length=200, blank=True, verbose_name="MOT a cargo de")
    equipe_a_cargo = models.CharField(max_length=200, blank=True, verbose_name="Equipe a cargo de")

    cmt_missao = models.ForeignKey(
        Efetivo, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='missoes_como_cmt', verbose_name="Comandante da Missão"
    )
    equipe = models.ManyToManyField(
        Efetivo, blank=True,
        related_name='missoes_equipe',
        verbose_name="Equipe"
    )
    motorista = models.ForeignKey(
        Efetivo, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='missoes_como_mot', verbose_name="Motorista"
    )

    horarios_config = models.TextField(blank=True, default='', verbose_name="Configuração de horários (JSON)")

    criado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='missoes_criadas'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Missão (OMIS)"
        verbose_name_plural = "Missões (OMIS)"
        ordering = ['-data_missao', '-numero']

    def __str__(self):
        return f"OMIS Nº {self.numero} — {self.nome_missao}"


class ItemHorario(models.Model):
    missao = models.ForeignKey(Missao, on_delete=models.CASCADE, related_name='horarios_extras')
    label  = models.CharField(max_length=100, verbose_name="Descrição")
    horario = models.TimeField(null=True, blank=True, verbose_name="Horário")
    ordem  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['ordem']
        verbose_name = "Horário Extra"

    def __str__(self):
        return f"{self.label} – {self.horario}"


class ItemArmamento(models.Model):
    missao = models.ForeignKey(Missao, on_delete=models.CASCADE, related_name='armamentos')
    arma = models.CharField(max_length=100, verbose_name="Arma")
    quantidade = models.PositiveSmallIntegerField(default=0, verbose_name="Qtd")
    carregadores = models.PositiveSmallIntegerField(default=0, verbose_name="Carregadores")
    cartuchos = models.PositiveSmallIntegerField(default=0, verbose_name="Cartuchos")

    class Meta:
        verbose_name = "Item de Armamento"
        verbose_name_plural = "Itens de Armamento"

    def __str__(self):
        return f"{self.arma} x{self.quantidade}"


class ItemEquipamento(models.Model):
    missao = models.ForeignKey(Missao, on_delete=models.CASCADE, related_name='equipamentos')
    equipamento = models.CharField(max_length=100, verbose_name="Equipamento")
    quantidade = models.PositiveSmallIntegerField(default=0, verbose_name="Qtd")

    class Meta:
        verbose_name = "Item de Equipamento"
        verbose_name_plural = "Itens de Equipamento"

    def __str__(self):
        return f"{self.equipamento} x{self.quantidade}"


class EquipamentoCatalogo(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome do Equipamento")

    class Meta:
        verbose_name = "Equipamento (Catálogo)"
        verbose_name_plural = "Equipamentos (Catálogo)"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class RadioCatalogo(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome/Modelo do Rádio")
    canal_padrao = models.CharField(max_length=50, blank=True, verbose_name="Canal Padrão")

    class Meta:
        verbose_name = "Rádio (Catálogo)"
        verbose_name_plural = "Rádios (Catálogo)"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class UniformeCatalogo(models.Model):
    nome = models.CharField(max_length=200, unique=True, verbose_name="Uniforme")

    class Meta:
        verbose_name = "Uniforme (Catálogo)"
        verbose_name_plural = "Uniformes (Catálogo)"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ArmamentoCatalogo(models.Model):
    nome = models.CharField(max_length=150, unique=True, verbose_name="Nome da Arma")
    carregadores_por_unidade = models.PositiveSmallIntegerField(default=0, verbose_name="Carregadores por arma")
    cartuchos_por_unidade = models.PositiveSmallIntegerField(default=0, verbose_name="Cartuchos por arma")

    class Meta:
        verbose_name = "Armamento (Catálogo)"
        verbose_name_plural = "Armamentos (Catálogo)"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ACargaOpcao(models.Model):
    nome = models.CharField(max_length=200, unique=True, verbose_name="Opção 'A Cargo de'")

    class Meta:
        verbose_name = "Opção 'A Cargo de'"
        verbose_name_plural = "Opções 'A Cargo de'"
        ordering = ['nome']

    def __str__(self):
        return self.nome
