from django.db import models

class Efetivo(models.Model):
    posto = models.CharField(max_length=50, blank=True, verbose_name="Posto")
    quad = models.CharField(max_length=50, blank=True, verbose_name="QUAD")
    especializacao = models.CharField(max_length=100, blank=True, verbose_name="Especialização")
    saram = models.IntegerField(unique=True, null=True, blank=True, verbose_name="SARAM")
    nome_completo = models.CharField(max_length=255, verbose_name="Nome Completo")
    nome_guerra = models.CharField(max_length=100,blank=True, verbose_name="Nome de Guerra")
    turma = models.CharField(max_length=100, blank=True, verbose_name="Turma")
    situacao = models.CharField(max_length=50, blank=True, verbose_name="Situação")
    om = models.CharField(max_length=100, blank=True, verbose_name="OM")
    setor = models.CharField(max_length=100, blank=True, verbose_name="Setor")
    subsetor = models.CharField(max_length=100, blank=True, verbose_name="Subsetor")
    oficial = models.BooleanField(default=False, verbose_name="É Oficial?")
    assinatura = models.TextField(blank=True, null=True, verbose_name="Assinatura Padrão (Base64)")
    senha_unica = models.CharField(max_length=128, blank=True, null=True, verbose_name="Senha Única")

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

        super(Efetivo, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.posto} {self.nome_guerra}"

    class Meta:
        db_table = 'Efetivo'