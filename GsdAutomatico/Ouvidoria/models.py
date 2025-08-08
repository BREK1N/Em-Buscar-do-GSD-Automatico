from django.db import models

class Militar(models.Model):
   
    #Tabela para armazenar o cadastro de todos os militares.
   
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo")
    nome_guerra = models.CharField(max_length=100, verbose_name="Nome de Guerra")
    saram = models.IntegerField(unique=True, verbose_name="SARAM")
    telefone = models.BigIntegerField(null=True, blank=True, verbose_name="Telefone")
    turma = models.CharField(max_length=100, blank=True, verbose_name="Turma")
    posto = models.CharField(max_length=50, blank=True, verbose_name="Posto")
    graduacao = models.CharField(max_length=50, blank=True, verbose_name="Graduação")
    secao_om = models.CharField(max_length=100, verbose_name="Seção/OM")
    oficial = models.BooleanField(default=False, verbose_name="É Oficial?")

    def __str__(self):
        # Retorna o posto ou graduação seguido do nome de guerra para fácil identificação
        return f"{self.posto or self.graduacao} {self.nome_guerra}"

    class Meta:
        verbose_name = "Militar"
        verbose_name_plural = "Militares"


class PATD(models.Model):
    # Tabela para registrar os Processos.
    
    militar = models.ForeignKey(Militar, on_delete=models.CASCADE, related_name='patds', verbose_name="Militar Acusado")
    transgressao = models.TextField(verbose_name="Transgressão")
    numero_patd = models.IntegerField(unique=True, verbose_name="N° PATD")
    oficial_responsavel = models.ForeignKey(
        Militar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patds_responsaveis',
        limit_choices_to={'oficial': True}, # Garante que apenas oficiais possam ser selecionados
        verbose_name="Oficial Responsável"
    )
    data_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Data de Início")
    data_termino = models.DateTimeField(null=True, blank=True, verbose_name="Data de Término")

    def __str__(self):
        return f"PATD N° {self.numero_patd} - {self.militar.nome_guerra}"

    class Meta:
        verbose_name = "PATD"
        verbose_name_plural = "PATDs"
