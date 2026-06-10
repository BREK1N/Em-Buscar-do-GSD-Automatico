from django.contrib import admin
from .models import TipoCurso, CursoEfetivo


@admin.register(TipoCurso)
class TipoCursoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo']
    list_filter = ['ativo']
    search_fields = ['nome']


@admin.register(CursoEfetivo)
class CursoEfetivoAdmin(admin.ModelAdmin):
    list_display = ['efetivo', 'tipo_curso', 'data_realizacao', 'data_validade', 'instituicao']
    list_filter = ['tipo_curso', 'data_realizacao']
    search_fields = ['efetivo__nome_completo', 'efetivo__nome_guerra', 'tipo_curso__nome']
    date_hierarchy = 'data_realizacao'
