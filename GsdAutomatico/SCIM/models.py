from django.db import models
from Secao_pessoal.models import Efetivo


class TipoCurso(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Tipo de Curso'
        verbose_name_plural = 'Tipos de Curso'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CursoEfetivo(models.Model):
    efetivo = models.ForeignKey(Efetivo, on_delete=models.CASCADE, related_name='cursos')
    tipo_curso = models.ForeignKey(TipoCurso, on_delete=models.PROTECT, verbose_name='Tipo de Curso')
    data_realizacao = models.DateField(verbose_name='Data de Realização')
    instituicao = models.CharField(max_length=200, blank=True, verbose_name='Instituição/Local')
    certificado = models.FileField(upload_to='scim/certificados/', null=True, blank=True, verbose_name='Certificado')
    observacoes = models.TextField(blank=True, verbose_name='Observações')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Curso do Efetivo'
        verbose_name_plural = 'Cursos do Efetivo'
        ordering = ['-data_realizacao']

    def __str__(self):
        return f'{self.efetivo} — {self.tipo_curso} ({self.data_realizacao})'
