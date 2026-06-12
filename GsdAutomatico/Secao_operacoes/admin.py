from django.contrib import admin
from .models import SituacaoEspecialEfetivo


@admin.register(SituacaoEspecialEfetivo)
class SituacaoEspecialEfetivoAdmin(admin.ModelAdmin):
    list_display = ['efetivo', 'tipo', 'data_inicio', 'data_fim', 'registrado_por']
    list_filter = ['tipo']
    search_fields = ['efetivo__nome_guerra', 'efetivo__nome_completo']
    date_hierarchy = 'data_inicio'
